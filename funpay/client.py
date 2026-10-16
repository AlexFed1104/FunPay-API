"""Главный класс :class:`FunPay`."""
from __future__ import annotations

from .api.chats import ChatsMixin
from .api.events import EventsMixin
from .api.lots import LotsMixin
from .api.orders import OrdersMixin
from .api.profile import ProfileMixin
from .api.reviews import ReviewsMixin
from .api.stats import StatsMixin


class FunPay(EventsMixin, StatsMixin, ReviewsMixin, ProfileMixin, OrdersMixin, LotsMixin, ChatsMixin):
    """Клиент FunPay.

    >>> client = FunPay("ваш golden_key")
    >>> client.login()
    >>> for chat in client.get_chats():
    ...     print(chat.username, chat.last_message_text)

    ``golden_key`` — кука из браузера, где вы залогинены на funpay.com.
    ``user_agent`` лучше указать того же браузера.
    Сессия и CSRF-токен обновляются автоматически раз в 40 минут.
    """
