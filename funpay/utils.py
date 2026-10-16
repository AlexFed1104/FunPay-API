"""Вспомогательные функции: даты, деньги, теги, распознавание системных сообщений."""
from __future__ import annotations

import random
import re
import string
import unicodedata
from datetime import datetime, timedelta, timezone

from .enums import Currency, MessageType

MSK = timezone(timedelta(hours=3))

MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6,
    "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_TODAY = ("сегодня", "сьогодні", "today")
_YESTERDAY = ("вчера", "вчора", "yesterday")

_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})\s+(?P<month>[^\W\d_]+)(?:\s+(?P<year>\d{4}))?(?:,|\s+в|\s+at)?\s*(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}))?"
)
_TIME_RE = re.compile(r"(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}))?")
_NUMERIC_DATE_RE = re.compile(r"^(?P<d>\d{2})\.(?P<mo>\d{2})\.(?P<y>\d{2,4})$")


def random_tag() -> str:
    """Случайный тег для объектов ``runner/``."""
    return "".join(random.choice(string.digits + string.ascii_lowercase) for _ in range(10))


def parse_date(text: str | None, now: datetime | None = None) -> datetime | None:
    """Разбирает дату в формате FunPay («сегодня, 12:30», «5 мая, 10:00», «20 января 2024, 23:11»).

    Возвращает время по Москве или ``None``, если формат не распознан.
    """
    if not text:
        return None
    text = text.strip()
    now = now or datetime.now(MSK)
    low = text.lower()
    if any(w in low for w in _TODAY + _YESTERDAY):
        t = _TIME_RE.search(low)
        if not t:
            return None
        day = now - timedelta(days=1) if any(w in low for w in _YESTERDAY) else now
        return datetime(day.year, day.month, day.day, int(t["h"]), int(t["m"]), int(t["s"] or 0), tzinfo=MSK)
    if m := _NUMERIC_DATE_RE.match(low):
        year = int(m["y"])
        year = year + 2000 if year < 100 else year
        return datetime(year, int(m["mo"]), int(m["d"]), tzinfo=MSK)
    m = _DATE_RE.search(low)
    if not m or m["month"] not in MONTHS:
        t = _TIME_RE.fullmatch(low)
        if t:
            return datetime(now.year, now.month, now.day, int(t["h"]), int(t["m"]), int(t["s"] or 0), tzinfo=MSK)
        return None
    month = MONTHS[m["month"]]
    year = int(m["year"]) if m["year"] else now.year
    result = datetime(year, month, int(m["day"]), int(m["h"]), int(m["m"]), int(m["s"] or 0), tzinfo=MSK)
    if not m["year"] and result > now + timedelta(days=1):
        result = result.replace(year=year - 1)
    return result


_MONEY_RE = re.compile(r"([+\-−]?)\s*([\d\s ]+(?:[.,]\d+)?)")


def parse_money(text: str | None) -> tuple[float, Currency]:
    """«1 234.56 ₽» → (1234.56, Currency.RUB). Знак «−» сохраняется."""
    if not text:
        return 0.0, Currency.UNKNOWN
    text = text.strip()
    m = _MONEY_RE.search(text)
    if not m:
        return 0.0, Currency.parse(text)
    number = re.sub(r"[\s ]", "", m.group(2)).replace(",", ".")
    value = float(number) if number else 0.0
    if m.group(1) in ("-", "−"):
        value = -value
    rest = text[m.end():].strip()
    return value, Currency.parse(rest.split()[0] if rest else "")


def strip_invisible(text: str) -> str:
    """Убирает невидимые символы и пробелы в конце строки."""
    end = len(text)
    while end > 0 and (text[end - 1].isspace() or unicodedata.category(text[end - 1]) == "Cf"):
        end -= 1
    return text[:end]


def private_chat_name(user_a: int, user_b: int) -> str:
    """Имя узла личного чата: ``users-<меньший id>-<больший id>``."""
    a, b = sorted((int(user_a), int(user_b)))
    return f"users-{a}-{b}"


_U = r"[\w\-]{2,25}"
_O = r"#[A-Z0-9]{8}"
ORDER_ID_RE = re.compile(r"#([A-Z0-9]{8})")

_SYSTEM_MESSAGES: list[tuple[MessageType, re.Pattern[str]]] = [
    (MessageType.NEW_ORDER, re.compile(
        rf"(Покупатель|The buyer|Покупець) {_U} (оплатил заказ|has paid for order|сплатив замовлення) {_O}")),
    (MessageType.ORDER_CLOSED_BY_ADMIN, re.compile(
        rf"(Администратор|The administrator|Адміністратор) {_U} (подтвердил успешное выполнение заказа|has confirmed that order|підтвердив успішне виконання замовлення) {_O}")),
    (MessageType.ORDER_CLOSED, re.compile(
        rf"(Покупатель|The buyer|Покупець) {_U} (подтвердил успешное выполнение заказа|has confirmed that order|підтвердив успішне виконання замовлення) {_O}")),
    (MessageType.ORDER_REOPENED, re.compile(
        rf"(Заказ|Order|Замовлення) {_O} (открыт повторно|has been reopened|відкрито повторно)")),
    (MessageType.ORDER_REFUNDED_BY_ADMIN, re.compile(
        rf"(Администратор|The administrator|Адміністратор) {_U} (вернул деньги покупателю|has refunded the buyer|повернув гроші покупцеві)")),
    (MessageType.ORDER_REFUNDED, re.compile(
        rf"(Продавец|The seller|Продавець) {_U} (вернул деньги покупателю|has refunded the buyer|повернув гроші покупцеві)")),
    (MessageType.ORDER_PARTIALLY_REFUNDED, re.compile(
        rf"(Часть средств по заказу|A part of the funds pertaining to the order|Частину коштів за замовленням) {_O}")),
    (MessageType.NEW_REVIEW, re.compile(
        rf"(Покупатель|The buyer|Покупець) {_U} (написал отзыв к заказу|has given feedback to the order|написав відгук до замовлення) {_O}")),
    (MessageType.REVIEW_CHANGED, re.compile(
        rf"(Покупатель|The buyer|Покупець) {_U} (изменил отзыв к заказу|has edited their feedback to the order|змінив відгук до замовлення) {_O}")),
    (MessageType.REVIEW_DELETED, re.compile(
        rf"(Покупатель|The buyer|Покупець) {_U} (удалил отзыв к заказу|has deleted their feedback to the order|видалив відгук до замовлення) {_O}")),
    (MessageType.NEW_REVIEW_REPLY, re.compile(
        rf"(Продавец|The seller|Продавець) {_U} (ответил на отзыв к заказу|has replied to their feedback to the order|відповів на відгук до замовлення) {_O}")),
    (MessageType.REVIEW_REPLY_CHANGED, re.compile(
        rf"(Продавец|The seller|Продавець) {_U} (изменил ответ на отзыв к заказу|has edited a reply to their feedback to the order|змінив відповідь на відгук до замовлення) {_O}")),
    (MessageType.REVIEW_REPLY_DELETED, re.compile(
        rf"(Продавец|The seller|Продавець) {_U} (удалил ответ на отзыв к заказу|has deleted a reply to their feedback to the order|видалив відповідь на відгук до замовлення) {_O}")),
]


def detect_system_message(text: str) -> MessageType:
    """Тип системного сообщения FunPay по его тексту."""
    for type_, pattern in _SYSTEM_MESSAGES:
        if pattern.search(text):
            return type_
    return MessageType.SYSTEM_OTHER


def parse_wait_seconds(text: str | None) -> int | None:
    """«Подождите 2 часа.» → 7200. Нужно для ошибки поднятия лотов."""
    if not text:
        return None
    digits = "".join(c for c in text if c.isdigit())
    n = int(digits) if digits else 1
    low = text.lower()
    if "секунд" in low or "second" in low:
        return n
    if "минут" in low or "хвилин" in low or "minute" in low:
        return n * 60
    if "час" in low or "годин" in low or "hour" in low:
        return n * 3600
    return None
