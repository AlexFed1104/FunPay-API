"""Модели данных. У каждой модели есть поле ``raw`` с исходным HTML/JSON для отладки."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .enums import Currency, MessageType, OrderStatus, SubcategoryType, TransactionStatus


@dataclass
class Money:
    value: float
    currency: Currency = Currency.UNKNOWN

    def __str__(self) -> str:
        return f"{self.value:g} {self.currency.value}"


# ---------- аккаунт и категории ----------

@dataclass
class Me:
    """Данные авторизованного аккаунта с главной страницы."""
    id: int
    username: str
    balance: Money | None
    active_sales: int
    active_purchases: int
    locale: str


@dataclass
class Subcategory:
    id: int
    name: str
    type: SubcategoryType
    category_id: int


@dataclass
class Category:
    """Игра или раздел FunPay."""
    id: int
    name: str
    subcategories: list[Subcategory] = field(default_factory=list)


@dataclass
class Balance:
    """Баланс по валютам: ``total`` — всего, ``available`` — доступно к выводу."""
    total: dict[Currency, float]
    available: dict[Currency, float]


@dataclass
class Wallet:
    """Сохранённый кошелёк для вывода."""
    index: int
    detail_id: int
    type_id: str
    type_name: str
    data: str
    masked: bool


# ---------- пользователи и профиль ----------

@dataclass
class UserShort:
    id: int
    username: str
    online: bool | None = None
    avatar_url: str | None = None


@dataclass
class Rating:
    """Рейтинг продавца. ``distribution`` — доля отзывов (в %) по звёздам 1..5."""
    stars: float | None
    reviews_count: int
    distribution: dict[int, float] = field(default_factory=dict)


@dataclass
class Profile:
    id: int
    username: str
    online: bool
    banned: bool
    avatar_url: str | None
    status_text: str | None
    registration_text: str | None
    rating: Rating | None
    lots: list["LotShort"]
    raw: str = field(default="", repr=False)


# ---------- чаты ----------

@dataclass
class ChatShort:
    """Диалог из списка чатов."""
    id: int
    username: str
    last_message_text: str
    last_message_id: int
    last_read_message_id: int
    unread: bool
    by_bot: bool = False
    time_text: str | None = None
    avatar_url: str | None = None
    raw: str = field(default="", repr=False)


@dataclass
class Message:
    id: int
    chat_id: int | str
    author_id: int | None
    author_username: str | None
    text: str | None
    image_url: str | None
    type: MessageType
    date: datetime | None = None
    badge: str | None = None
    by_bot: bool = False
    order_id: str | None = None
    raw: str = field(default="", repr=False)

    @property
    def is_system(self) -> bool:
        return self.type not in (MessageType.TEXT, MessageType.IMAGE)


@dataclass
class Chat:
    """Страница чата: собеседник и привязанный заказ/лот из боковой панели."""
    id: int
    username: str
    interlocutor_id: int | None
    looking_at_text: str | None
    looking_at_link: str | None
    messages: list[Message] = field(default_factory=list)
    raw: str = field(default="", repr=False)


@dataclass
class BuyerViewing:
    """Блок «Покупатель смотрит»."""
    buyer_id: int
    lot_link: str | None
    lot_text: str | None


# ---------- лоты ----------

@dataclass
class LotShort:
    """Лот из списка (чужой или свой)."""
    id: int | str
    subcategory_id: int | None
    description: str | None
    price: float | None
    currency: Currency
    amount: int | None
    server: str | None = None
    side: str | None = None
    auto_delivery: bool = False
    active: bool = True
    promoted: bool = False
    seller: UserShort | None = None
    seller_rating: int | None = None
    seller_reviews: int | None = None
    raw: str = field(default="", repr=False)


@dataclass
class LotFields:
    """Все поля формы редактирования лота (``lots/offerEdit``).

    Удобные свойства меняют ``fields`` напрямую; любые другие поля формы
    можно поменять через ``fields["fields[...]"]``.
    """
    lot_id: int
    fields: dict[str, str]
    currency: Currency = Currency.UNKNOWN

    def _get(self, key: str) -> str:
        return self.fields.get(key, "")

    @property
    def subcategory_id(self) -> int:
        return int(self._get("node_id") or 0)

    @property
    def title(self) -> str:
        return self._get("fields[summary][ru]")

    @title.setter
    def title(self, value: str) -> None:
        self.fields["fields[summary][ru]"] = value

    @property
    def title_en(self) -> str:
        return self._get("fields[summary][en]")

    @title_en.setter
    def title_en(self, value: str) -> None:
        self.fields["fields[summary][en]"] = value

    @property
    def description(self) -> str:
        return self._get("fields[desc][ru]")

    @description.setter
    def description(self, value: str) -> None:
        self.fields["fields[desc][ru]"] = value

    @property
    def description_en(self) -> str:
        return self._get("fields[desc][en]")

    @description_en.setter
    def description_en(self, value: str) -> None:
        self.fields["fields[desc][en]"] = value

    @property
    def payment_message(self) -> str:
        return self._get("fields[payment_msg][ru]")

    @payment_message.setter
    def payment_message(self, value: str) -> None:
        self.fields["fields[payment_msg][ru]"] = value

    @property
    def price(self) -> float | None:
        v = self._get("price")
        return float(v) if v else None

    @price.setter
    def price(self, value: float | None) -> None:
        self.fields["price"] = "" if value is None else f"{value:g}"

    @property
    def amount(self) -> int | None:
        v = self._get("amount")
        return int(v) if v.isdigit() else None

    @amount.setter
    def amount(self, value: int | None) -> None:
        self.fields["amount"] = "" if value is None else str(value)

    @property
    def active(self) -> bool:
        return self.fields.get("active") == "on"

    @active.setter
    def active(self, value: bool) -> None:
        if value:
            self.fields["active"] = "on"
        else:
            self.fields.pop("active", None)

    @property
    def auto_delivery(self) -> bool:
        return self.fields.get("auto_delivery") == "on"

    @auto_delivery.setter
    def auto_delivery(self, value: bool) -> None:
        if value:
            self.fields["auto_delivery"] = "on"
        else:
            self.fields.pop("auto_delivery", None)

    @property
    def secrets(self) -> list[str]:
        """Товары для автовыдачи, по одному на строку."""
        return [s for s in self._get("secrets").split("\n") if s.strip()]

    @secrets.setter
    def secrets(self, value: list[str]) -> None:
        self.fields["secrets"] = "\n".join(value)

    @property
    def images(self) -> list[int]:
        return [int(i) for i in self._get("fields[images]").split(",") if i.strip()]

    @images.setter
    def images(self, value: list[int]) -> None:
        self.fields["fields[images]"] = ",".join(str(i) for i in value)


@dataclass
class ChipsFields:
    """Форма игровой валюты (``chips/{id}/trade``)."""
    subcategory_id: int
    fields: dict[str, str]


@dataclass
class PriceCalc:
    """Результат калькулятора комиссии: цена для покупателя по способам оплаты."""
    price: float
    methods: dict[str, Money]
    min_price: Money | None


# ---------- заказы ----------

@dataclass
class OrderShort:
    """Заказ из списка продаж или покупок."""
    id: str
    title: str
    category_text: str
    status: OrderStatus
    total: Money
    counterparty: UserShort
    date_text: str
    date: datetime | None
    raw: str = field(default="", repr=False)


@dataclass
class Review:
    rating: int | None
    text: str | None
    reply: str | None
    order_id: str | None = None
    author_id: int | None = None
    author_username: str | None = None
    date_text: str | None = None
    category_text: str | None = None
    order_total: Money | None = None
    hidden: bool = False
    raw: str = field(default="", repr=False)


@dataclass
class Order:
    """Подробности заказа из ``api/orders/get``."""
    id: str
    status: OrderStatus
    subcategory_id: int | None
    subcategory_type: SubcategoryType | None
    price: float
    currency: Currency
    amount: float | None
    buyer: UserShort
    seller: UserShort
    chat_name: str | None
    fields: dict[str, str]
    secrets: list[str]
    review: Review | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


# ---------- отзывы и финансы ----------

@dataclass
class ReviewsPage:
    reviews: list[Review]
    next_cursor: str | None


@dataclass
class Transaction:
    id: int
    date_text: str
    date: datetime | None
    description: str
    status: TransactionStatus
    amount: Money
    order_id: str | None = None
    raw: str = field(default="", repr=False)
