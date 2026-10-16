"""Неофициальная библиотека для FunPay: чаты, лоты, заказы, профиль, отзывы, статистика, события."""
from .client import FunPay
from .enums import Currency, EventType, MessageType, OrderStatus, SubcategoryType, TransactionFilter, TransactionStatus
from .exceptions import (
    FunPayError, ImageUploadError, LotSaveError, MessageNotSentError, NotInitializedError, ParseError,
    RaiseTooEarlyError, RateLimitError, RefundError, RequestFailedError, ReviewError, UnauthorizedError,
    WithdrawError,
)
from .api.events import (
    ChatsChangedEvent, NewMessageEvent, NewOrderEvent, OrderStatusChangedEvent, OrdersCountersChangedEvent,
)
from . import models, stats

__version__ = "0.1.0"

__all__ = [
    "FunPay", "Currency", "EventType", "MessageType", "OrderStatus", "SubcategoryType", "TransactionFilter",
    "TransactionStatus", "FunPayError", "ImageUploadError", "LotSaveError", "MessageNotSentError",
    "NotInitializedError", "ParseError", "RaiseTooEarlyError", "RateLimitError", "RefundError",
    "RequestFailedError", "ReviewError", "UnauthorizedError", "WithdrawError", "ChatsChangedEvent",
    "NewMessageEvent", "NewOrderEvent", "OrderStatusChangedEvent", "OrdersCountersChangedEvent", "models", "stats",
]
