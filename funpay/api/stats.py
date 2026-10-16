"""Статистика поверх продаж и отзывов."""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from .. import stats as st
from ..enums import Currency
from ..models import OrderShort, Rating
from .base import BaseClient


class StatsMixin(BaseClient):

    def _sales_list(self, date_from: datetime | None, date_to: datetime | None) -> list[OrderShort]:
        return list(self.get_sales(date_from=date_from, date_to=date_to))  # type: ignore[attr-defined]

    def get_stats(self, date_from: datetime | None = None, date_to: datetime | None = None) -> st.SalesStats:
        """Сводка продаж за период: число заказов, выручка, средний чек, доля возвратов."""
        return st.summarize(self._sales_list(date_from, date_to))

    def get_stats_by(self, field: str | Callable[[OrderShort], str], date_from: datetime | None = None,
                     date_to: datetime | None = None) -> dict[str, st.SalesStats]:
        """Разбивка продаж: ``day``, ``month``, ``weekday``, ``hour``, ``game``, ``category``, ``lot``, ``buyer``."""
        return st.group_by(self._sales_list(date_from, date_to), field)

    def get_top(self, field: str, n: int = 10, currency: Currency = Currency.RUB, date_from: datetime | None = None,
                date_to: datetime | None = None) -> list[tuple[str, float, int]]:
        """Топ лотов/игр/покупателей по выручке."""
        return st.top(self._sales_list(date_from, date_to), field, n, currency)

    def get_rating_stats(self, user_id: int | None = None, from_reviews: bool = False) -> Rating | None:
        """Рейтинг продавца.

        По умолчанию берётся с профиля (то, что показывает FunPay). ``from_reviews=True``
        пересчитывает по всем отзывам — дольше, но работает и для старых профилей.
        """
        if from_reviews:
            return st.rating_stats(self.get_reviews(user_id))  # type: ignore[attr-defined]
        return self.get_profile(user_id).rating  # type: ignore[attr-defined]

    def export_sales(self, path: str, date_from: datetime | None = None, date_to: datetime | None = None) -> int:
        """Выгружает продажи в CSV. Возвращает число строк."""
        return st.export_csv(self.get_sales(date_from=date_from, date_to=date_to), path)  # type: ignore[attr-defined]
