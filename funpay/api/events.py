"""События в реальном времени через ``runner/``: новые сообщения и заказы, обработчики-декораторы."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterator, Union

from .. import parsers
from ..enums import EventType, OrderStatus
from ..exceptions import FunPayError, RateLimitError, RequestFailedError
from ..models import ChatShort, Message, OrderShort
from ..utils import MSK, random_tag
from .base import BaseClient

log = logging.getLogger("funpay.events")


@dataclass
class ChatsChangedEvent:
    chats: list[ChatShort]
    type: EventType = EventType.CHATS_CHANGED
    time: datetime = field(default_factory=lambda: datetime.now(MSK))


@dataclass
class NewMessageEvent:
    message: Message
    chat: ChatShort | None
    by_me: bool
    type: EventType = EventType.NEW_MESSAGE
    time: datetime = field(default_factory=lambda: datetime.now(MSK))


@dataclass
class OrdersCountersChangedEvent:
    purchases: int
    sales: int
    type: EventType = EventType.ORDERS_COUNTERS_CHANGED
    time: datetime = field(default_factory=lambda: datetime.now(MSK))


@dataclass
class NewOrderEvent:
    order: OrderShort
    type: EventType = EventType.NEW_ORDER
    time: datetime = field(default_factory=lambda: datetime.now(MSK))


@dataclass
class OrderStatusChangedEvent:
    order: OrderShort
    old_status: OrderStatus
    type: EventType = EventType.ORDER_STATUS_CHANGED
    time: datetime = field(default_factory=lambda: datetime.now(MSK))


Event = Union[ChatsChangedEvent, NewMessageEvent, OrdersCountersChangedEvent, NewOrderEvent,
              OrderStatusChangedEvent]
Handler = Callable[..., None]


class EventsMixin(BaseClient):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._handlers: list[tuple[EventType, Handler, Callable[[Event], bool] | None]] = []

    # ---------- генератор событий ----------

    def listen(self, delay: float = 6.0, orders: bool = True, chats: bool = True) -> Iterator[Event]:
        """Бесконечный генератор событий. Опрашивает FunPay каждые ``delay`` секунд.

        На первом шаге запоминает текущее состояние и ничего не выдаёт, дальше — только новое.
        Сначала выдаются события заказов, потом чатов, чтобы автовыдача увидела заказ раньше сообщения.
        Учтите: чтобы получить новые сообщения, библиотека запрашивает историю чата, и FunPay
        помечает такой чат прочитанным.
        """
        bookmarks_tag, orders_tag = random_tag(), random_tag()
        last_ids: dict[int, int] = {}
        saved_orders: dict[str, OrderStatus] = {}
        first = True
        while True:
            started = time.monotonic()
            try:
                objects = []
                if chats:
                    objects.append({"type": "chat_bookmarks", "id": self.user_id, "tag": bookmarks_tag, "data": False})
                if orders:
                    objects.append({"type": "orders_counters", "id": self.user_id, "tag": orders_tag, "data": False})
                data = self.runner(objects)
                order_events: list[Event] = []
                chat_events: list[Event] = []
                for obj in data.get("objects", []):
                    if not obj.get("data"):
                        continue
                    if obj.get("type") == "orders_counters":
                        orders_tag = obj.get("tag", orders_tag)
                        counters = obj["data"]
                        if not first:
                            order_events.append(OrdersCountersChangedEvent(
                                int(counters.get("buyer", 0) or 0), int(counters.get("seller", 0) or 0)))
                        order_events.extend(self._diff_orders(saved_orders, emit=not first))
                    elif obj.get("type") == "chat_bookmarks":
                        bookmarks_tag = obj.get("tag", bookmarks_tag)
                        previews = parsers.parse_chat_previews(obj["data"].get("html", ""))
                        chat_events.extend(self._diff_chats(previews, last_ids, emit=not first))
                first = False
                yield from order_events
                yield from chat_events
            except RateLimitError:
                log.warning("429 при опросе, пропускаю шаг")
            except (RequestFailedError, FunPayError, ValueError) as e:
                log.warning("Ошибка опроса: %s", e)
            time.sleep(max(0.0, delay - (time.monotonic() - started)))

    def _diff_orders(self, saved: dict[str, OrderStatus], emit: bool) -> list[Event]:
        events: list[Event] = []
        current = list(self.get_sales(limit=100))  # type: ignore[attr-defined]
        for order in reversed(current):
            old = saved.get(order.id)
            if emit and old is None:
                events.append(NewOrderEvent(order))
            elif emit and old is not order.status:
                events.append(OrderStatusChangedEvent(order, old))
            saved[order.id] = order.status
        return events

    def _diff_chats(self, previews: list[ChatShort], last_ids: dict[int, int], emit: bool) -> list[Event]:
        if not emit:
            for c in previews:
                last_ids[c.id] = c.last_message_id
            return []
        changed = [c for c in previews if c.last_message_id > last_ids.get(c.id, 0)]
        events: list[Event] = [ChatsChangedEvent(previews)] if changed else []
        if not changed:
            return events
        by_id = {c.id: c for c in changed}
        histories = self.get_chats_messages(list(by_id))  # type: ignore[attr-defined]
        me = self.user_id
        for chat_id, chat in by_id.items():
            known = last_ids.get(chat_id, 0)
            for msg in histories.get(chat_id, []):
                if msg.id > known:
                    events.append(NewMessageEvent(msg, chat, by_me=msg.author_id == me))
            last_ids[chat_id] = chat.last_message_id
        return events

    # ---------- обработчики ----------

    def on(self, event_type: EventType, filter: Callable[[Event], bool] | None = None) -> Callable[[Handler], Handler]:
        def deco(func: Handler) -> Handler:
            self._handlers.append((event_type, func, filter))
            return func
        return deco

    def on_message(self, ignore_own: bool = True, chat_id: int | None = None, contains: str | None = None
                   ) -> Callable[[Handler], Handler]:
        """Обработчик новых сообщений. Функция получает :class:`NewMessageEvent`.

        ``ignore_own`` пропускает свои сообщения (чтобы бот не отвечал сам себе).
        """
        def check(e: Event) -> bool:
            assert isinstance(e, NewMessageEvent)
            if ignore_own and (e.by_me or e.message.by_bot):
                return False
            if chat_id is not None and e.message.chat_id != chat_id:
                return False
            if contains and contains.lower() not in (e.message.text or "").lower():
                return False
            return True
        return self.on(EventType.NEW_MESSAGE, check)

    def on_new_order(self) -> Callable[[Handler], Handler]:
        return self.on(EventType.NEW_ORDER)

    def on_order_status(self) -> Callable[[Handler], Handler]:
        return self.on(EventType.ORDER_STATUS_CHANGED)

    def dispatch(self, event: Event) -> None:
        for type_, func, flt in self._handlers:
            if type_ is not event.type or (flt and not flt(event)):
                continue
            try:
                func(event)
            except Exception:
                log.exception("Ошибка в обработчике %s", getattr(func, "__name__", func))

    def run(self, delay: float = 6.0) -> None:
        """Запускает опрос и вызывает обработчики. Блокирует поток; остановка — Ctrl+C."""
        need_orders = any(t in (EventType.NEW_ORDER, EventType.ORDER_STATUS_CHANGED,
                                EventType.ORDERS_COUNTERS_CHANGED) for t, _, _ in self._handlers)
        need_chats = any(t in (EventType.NEW_MESSAGE, EventType.CHATS_CHANGED) for t, _, _ in self._handlers)
        if not (need_orders or need_chats):
            raise FunPayError("Нет ни одного обработчика")
        for event in self.listen(delay=delay, orders=need_orders, chats=need_chats):
            self.dispatch(event)
