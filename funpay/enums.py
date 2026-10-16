"""Перечисления."""
from __future__ import annotations

from enum import Enum


class Currency(str, Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def parse(cls, text: str | None) -> "Currency":
        if not text:
            return cls.UNKNOWN
        text = text.strip()
        return _CURRENCY_SIGNS.get(text, _CURRENCY_SIGNS.get(text.upper(), cls.UNKNOWN))

    @property
    def code(self) -> str:
        return {"RUB": "rub", "USD": "usd", "EUR": "eur"}.get(self.value, "")


_CURRENCY_SIGNS = {
    "₽": Currency.RUB, "RUB": Currency.RUB, "¤": Currency.RUB, "РУБ": Currency.RUB,
    "$": Currency.USD, "USD": Currency.USD,
    "€": Currency.EUR, "EUR": Currency.EUR,
}


class OrderStatus(str, Enum):
    UNPAID = "unpaid"
    PAID = "paid"
    CLOSED = "closed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class SubcategoryType(str, Enum):
    """Тип подкатегории: обычные лоты или игровая валюта."""
    LOTS = "lots"
    CHIPS = "chips"


class MessageType(str, Enum):
    """Тип сообщения в чате. Всё, кроме ``TEXT`` и ``IMAGE``, — системные сообщения FunPay."""
    TEXT = "text"
    IMAGE = "image"
    NEW_ORDER = "new_order"
    ORDER_CLOSED = "order_closed"
    ORDER_CLOSED_BY_ADMIN = "order_closed_by_admin"
    ORDER_REOPENED = "order_reopened"
    ORDER_REFUNDED = "order_refunded"
    ORDER_REFUNDED_BY_ADMIN = "order_refunded_by_admin"
    ORDER_PARTIALLY_REFUNDED = "order_partially_refunded"
    NEW_REVIEW = "new_review"
    REVIEW_CHANGED = "review_changed"
    REVIEW_DELETED = "review_deleted"
    NEW_REVIEW_REPLY = "new_review_reply"
    REVIEW_REPLY_CHANGED = "review_reply_changed"
    REVIEW_REPLY_DELETED = "review_reply_deleted"
    SYSTEM_OTHER = "system_other"


class TransactionStatus(str, Enum):
    COMPLETED = "complete"
    PENDING = "waiting"
    CANCELLED = "cancel"
    UNKNOWN = "unknown"


class TransactionFilter(str, Enum):
    """Фильтр для ``get_transactions``."""
    ALL = ""
    PAYMENTS = "payment"
    WITHDRAWALS = "withdraw"
    ORDERS = "order"
    OTHER = "other"


class EventType(str, Enum):
    CHATS_CHANGED = "chats_changed"
    NEW_MESSAGE = "new_message"
    ORDERS_COUNTERS_CHANGED = "orders_counters_changed"
    NEW_ORDER = "new_order"
    ORDER_STATUS_CHANGED = "order_status_changed"
