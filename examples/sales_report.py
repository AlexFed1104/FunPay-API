"""Отчёт по продажам за 30 дней и рейтинг.

Запуск: FUNPAY_KEY=ваш_golden_key python sales_report.py
"""
import os
from datetime import datetime, timedelta

from funpay import FunPay, stats
from funpay.utils import MSK

client = FunPay(os.environ["FUNPAY_KEY"])
client.login()

since = datetime.now(MSK) - timedelta(days=30)
orders = list(client.get_sales(date_from=since))

s = stats.summarize(orders)
print(f"Заказов: {s.orders}, покупателей: {s.unique_buyers}, возвратов: {s.refund_rate:.0%}")
for currency, value in s.revenue.items():
    print(f"Выручка: {value} {currency.value}, средний чек {s.average_check.get(currency)}")

print("\nПо дням:")
for day, d in stats.group_by(orders, "day").items():
    print(day, d.orders, {c.value: v for c, v in d.revenue.items()})

print("\nТоп лотов:")
for title, revenue, count in stats.top(orders, "lot", n=5):
    print(f"{title}: {revenue} ₽, {count} шт.")

rating = client.get_rating_stats()
if rating:
    print(f"\nРейтинг {rating.stars} по {rating.reviews_count} отзывам, распределение {rating.distribution}")

stats.export_csv(orders, "sales.csv")
