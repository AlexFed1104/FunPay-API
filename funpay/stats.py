"""Статистика продаж. У FunPay нет страницы статистики, поэтому всё считается по списку заказов и отзывам.

Функции чистые: их можно вызывать на любом списке заказов, например сохранённом заранее.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable

from .enums import Currency, OrderStatus
from .models import OrderShort, Rating, Review


@dataclass
class SalesStats:
    """Сводка по заказам.

    ``revenue`` — сумма закрытых заказов, ``pending`` — оплаченных, но ещё не закрытых,
    ``refunded`` — сумма возвратов. Всё по валютам.
    """
    orders: int = 0
    by_status: dict[OrderStatus, int] = field(default_factory=dict)
    revenue: dict[Currency, float] = field(default_factory=dict)
    pending: dict[Currency, float] = field(default_factory=dict)
    refunded: dict[Currency, float] = field(default_factory=dict)
    average_check: dict[Currency, float] = field(default_factory=dict)
    refund_rate: float = 0.0
    unique_buyers: int = 0
    first_date: datetime | None = None
    last_date: datetime | None = None


def summarize(orders: Iterable[OrderShort]) -> SalesStats:
    stats = SalesStats()
    status_counter: Counter[OrderStatus] = Counter()
    revenue: dict[Currency, float] = defaultdict(float)
    pending: dict[Currency, float] = defaultdict(float)
    refunded: dict[Currency, float] = defaultdict(float)
    closed_count: Counter[Currency] = Counter()
    buyers = set()
    for o in orders:
        stats.orders += 1
        status_counter[o.status] += 1
        buyers.add(o.counterparty.id or o.counterparty.username)
        cur, value = o.total.currency, o.total.value
        if o.status is OrderStatus.CLOSED:
            revenue[cur] += value
            closed_count[cur] += 1
        elif o.status is OrderStatus.PAID:
            pending[cur] += value
        elif o.status in (OrderStatus.REFUNDED, OrderStatus.PARTIALLY_REFUNDED):
            refunded[cur] += value
        if o.date:
            stats.first_date = min(stats.first_date or o.date, o.date)
            stats.last_date = max(stats.last_date or o.date, o.date)
    stats.by_status = dict(status_counter)
    stats.revenue = {c: round(v, 2) for c, v in revenue.items()}
    stats.pending = {c: round(v, 2) for c, v in pending.items()}
    stats.refunded = {c: round(v, 2) for c, v in refunded.items()}
    stats.average_check = {c: round(revenue[c] / n, 2) for c, n in closed_count.items() if n}
    refunds = status_counter[OrderStatus.REFUNDED] + status_counter[OrderStatus.PARTIALLY_REFUNDED]
    stats.refund_rate = round(refunds / stats.orders, 4) if stats.orders else 0.0
    stats.unique_buyers = len(buyers)
    return stats


GROUPERS: dict[str, Callable[[OrderShort], str]] = {
    "day": lambda o: o.date.strftime("%Y-%m-%d") if o.date else "?",
    "month": lambda o: o.date.strftime("%Y-%m") if o.date else "?",
    "weekday": lambda o: o.date.strftime("%A") if o.date else "?",
    "hour": lambda o: f"{o.date.hour:02d}" if o.date else "?",
    "game": lambda o: o.category_text.split(", ")[0] if o.category_text else "?",
    "category": lambda o: o.category_text or "?",
    "lot": lambda o: o.title or "?",
    "buyer": lambda o: o.counterparty.username or "?",
    "status": lambda o: o.status.value,
}


def group_by(orders: Iterable[OrderShort], field_name: str | Callable[[OrderShort], str]) -> dict[str, SalesStats]:
    """Разбивка статистики: ``day``, ``month``, ``weekday``, ``hour``, ``game``, ``category``, ``lot``,
    ``buyer``, ``status`` или своя функция ``order -> ключ``."""
    key = GROUPERS[field_name] if isinstance(field_name, str) else field_name
    buckets: dict[str, list[OrderShort]] = defaultdict(list)
    for o in orders:
        buckets[key(o)].append(o)
    return {k: summarize(v) for k, v in sorted(buckets.items())}


def top(orders: Iterable[OrderShort], field_name: str, n: int = 10, currency: Currency = Currency.RUB
        ) -> list[tuple[str, float, int]]:
    """Топ ключей по выручке в валюте: ``[(ключ, выручка, число заказов), ...]``."""
    groups = group_by(orders, field_name)
    rows = [(k, s.revenue.get(currency, 0.0), s.orders) for k, s in groups.items()]
    return sorted(rows, key=lambda r: (r[1], r[2]), reverse=True)[:n]


def rating_stats(reviews: Iterable[Review]) -> Rating:
    """Средняя оценка и распределение по звёздам (в %) по списку отзывов."""
    counter: Counter[int] = Counter(r.rating for r in reviews if r.rating)
    total = sum(counter.values())
    avg = round(sum(k * v for k, v in counter.items()) / total, 2) if total else None
    dist = {i: round(counter[i] * 100 / total, 1) if total else 0.0 for i in range(1, 6)}
    return Rating(stars=avg, reviews_count=total, distribution=dist)


def export_csv(orders: Iterable[OrderShort], path: str) -> int:
    """Сохраняет заказы в CSV (UTF-8 с BOM, открывается в Excel). Возвращает число строк."""
    n = 0
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "date", "status", "title", "category", "buyer_id", "buyer", "amount", "currency"])
        for o in orders:
            w.writerow([o.id, o.date.isoformat() if o.date else o.date_text, o.status.value, o.title,
                        o.category_text, o.counterparty.id, o.counterparty.username, o.total.value,
                        o.total.currency.value])
            n += 1
    return n
