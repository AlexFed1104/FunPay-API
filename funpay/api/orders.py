"""Заказы: продажи, покупки, подробности, возврат."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Iterator

from .. import parsers
from ..enums import OrderStatus
from ..exceptions import RefundError, RequestFailedError
from ..models import Order, OrderShort
from .base import BaseClient, _json

_STATE = {OrderStatus.PAID: "paid", OrderStatus.CLOSED: "closed", OrderStatus.REFUNDED: "refunded"}


class OrdersMixin(BaseClient):

    def get_sales(self, status: OrderStatus | None = None, buyer: str | None = None, game_id: int | None = None,
                  order_id: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
                  limit: int | None = None) -> Iterator[OrderShort]:
        """Продажи, от новых к старым. Генератор: страницы подгружаются по мере перебора.

        ``status``, ``buyer``, ``game_id``, ``order_id`` фильтрует сам FunPay,
        ``date_from``/``date_to`` — библиотека (перебор останавливается на заказе старше ``date_from``).
        """
        filters = {"id": order_id, "buyer": buyer, "state": _STATE.get(status) if status else None, "game": game_id}
        return self._iter_orders("orders/trade", filters, date_from, date_to, limit)

    def get_purchases(self, status: OrderStatus | None = None, seller: str | None = None,
                      game_id: int | None = None, order_id: str | None = None, date_from: datetime | None = None,
                      date_to: datetime | None = None, limit: int | None = None) -> Iterator[OrderShort]:
        """Покупки, от новых к старым (``orders/``). Параметры как у :meth:`get_sales`."""
        filters = {"id": order_id, "buyer": seller, "state": _STATE.get(status) if status else None,
                   "game_id": game_id}
        return self._iter_orders("orders/", filters, date_from, date_to, limit)

    def _iter_orders(self, path: str, filters: dict, date_from: datetime | None, date_to: datetime | None,
                     limit: int | None) -> Iterator[OrderShort]:
        self._ensure()
        params = {k: v for k, v in filters.items() if v is not None}
        cursor: str | None = None
        count = 0
        while True:
            if cursor is None:
                soup, _ = self.http.get_html(path, params=params)
            else:
                response = self.http.request("POST", path, params=params, data={**params, "continue": cursor},
                                             ajax=True)
                soup = parsers.soup_of(response.text)
            orders, next_cursor = parsers.parse_order_previews(soup)
            for order in orders:
                if date_to and order.date and order.date > date_to:
                    continue
                if date_from and order.date and order.date < date_from:
                    return
                yield order
                count += 1
                if limit is not None and count >= limit:
                    return
            if not next_cursor or not orders or next_cursor == cursor:
                return
            cursor = next_cursor

    def get_orders(self, order_ids: list[str]) -> dict[str, Order]:
        """Подробности до 10 заказов за раз (JSON-эндпоинт ``api/orders/get``)."""
        if not 1 <= len(order_ids) <= 10:
            raise ValueError("Нужно от 1 до 10 id заказов")
        self._ensure()
        body = json.dumps({"order_uids": list(order_ids), "include": ["details", "users", "review"]})
        response = self.http.request("POST", "api/orders/get", data=body, headers={
            "content-type": "application/json", "accept-language": self.http.locale})
        data = _json(response)
        if data.get("status") != "SUCCESS" or "data" not in data:
            raise RequestFailedError(response, f"api/orders/get: {data.get('status')}")
        return {oid: parsers.parse_order_json(o) for oid, o in data["data"].items()}

    def get_order(self, order_id: str) -> Order:
        """Подробности заказа: покупатель, сумма, поля, товары автовыдачи, отзыв."""
        return self.get_orders([order_id])[order_id]

    def refund(self, order_id: str) -> None:
        """Возвращает деньги покупателю."""
        self._ensure()
        data = self.http.post_json("orders/refund", {"id": order_id})
        if data.get("error"):
            raise RefundError(None, data.get("msg"))
