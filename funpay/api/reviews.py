"""Отзывы: список, ответ, отзыв от покупателя, удаление."""
from __future__ import annotations

from typing import Iterator

from .. import parsers
from ..exceptions import ReviewError
from ..models import Review
from .base import BaseClient


class ReviewsMixin(BaseClient):

    def get_reviews(self, user_id: int | None = None, stars: int | None = None, limit: int | None = None
                    ) -> Iterator[Review]:
        """Отзывы о продавце (без ``user_id`` — о себе), от новых к старым. ``stars`` — фильтр по оценке 1..5."""
        self._ensure()
        user_id = user_id or self.user_id
        cursor = ""
        count = 0
        while True:
            response = self.http.request("POST", "users/reviews", ajax=True, data={
                "user_id": user_id, "continue": cursor, "filter": str(stars) if stars else ""})
            page = parsers.parse_reviews(response.text)
            for r in page.reviews:
                yield r
                count += 1
                if limit is not None and count >= limit:
                    return
            if not page.next_cursor or not page.reviews or page.next_cursor == cursor:
                return
            cursor = page.next_cursor

    def get_order_review(self, order_id: str) -> Review | None:
        """Отзыв по заказу (или ``None``, если его нет)."""
        return self.get_order(order_id).review  # type: ignore[attr-defined]

    def _review(self, order_id: str, text: str, rating: int | str) -> str:
        self._ensure()
        response = self.http.request("POST", "orders/review", ajax=True, check=False, data={
            "authorId": self.user_id, "orderId": order_id, "text": text, "rating": rating})
        data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        if response.status_code != 200 or data.get("error"):
            raise ReviewError(response, data.get("msg"))
        return data.get("content", "")

    def reply_to_review(self, order_id: str, text: str) -> None:
        """Отвечает на отзыв к своей продаже (или меняет ответ)."""
        self._review(order_id, text, "")

    def leave_review(self, order_id: str, text: str, stars: int = 5) -> None:
        """Оставляет или меняет отзыв к своей покупке."""
        if not 1 <= stars <= 5:
            raise ValueError("stars от 1 до 5")
        self._review(order_id, text, stars)

    def delete_review(self, order_id: str) -> None:
        """Удаляет свой отзыв (как покупатель) или свой ответ на отзыв (как продавец)."""
        self._ensure()
        response = self.http.request("POST", "orders/reviewDelete", ajax=True, check=False, data={
            "authorId": self.user_id, "orderId": order_id})
        data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        if response.status_code != 200 or data.get("error"):
            raise ReviewError(response, data.get("msg"))

    delete_review_reply = delete_review
