"""Исключения библиотеки."""
from __future__ import annotations

from typing import Any

import requests


class FunPayError(Exception):
    """Базовое исключение библиотеки."""


class RequestFailedError(FunPayError):
    """FunPay вернул неожиданный ответ."""

    def __init__(self, response: requests.Response | None, message: str | None = None):
        self.response = response
        self.status_code = response.status_code if response is not None else None
        self.message = message
        text = message or f"Запрос не удался (код {self.status_code})"
        if response is not None:
            text += f": {response.request.method} {response.url}"
        super().__init__(text)


class UnauthorizedError(RequestFailedError):
    """golden_key неверный или сессия истекла."""

    def __init__(self, response: requests.Response | None = None, message: str | None = None):
        super().__init__(response, message or "Не авторизован: проверьте golden_key")


class RateLimitError(RequestFailedError):
    """FunPay слишком долго отвечает 429."""


class ParseError(FunPayError):
    """Не удалось разобрать страницу. Скорее всего, FunPay поменял вёрстку."""


class NotInitializedError(FunPayError):
    """Метод требует авторизации: сначала вызовите ``client.login()``."""

    def __init__(self) -> None:
        super().__init__("Клиент не авторизован: вызовите client.login()")


class ActionError(RequestFailedError):
    """FunPay отклонил действие и вернул текст ошибки."""


class MessageNotSentError(ActionError):
    def __init__(self, response: requests.Response | None, message: str | None, chat_id: int | str):
        self.chat_id = chat_id
        super().__init__(response, f"Сообщение в чат {chat_id} не отправлено: {message}")


class ImageUploadError(ActionError):
    pass


class LotSaveError(ActionError):
    def __init__(self, response: requests.Response | None, message: str | None, lot_id: int,
                 errors: dict[str, Any] | None = None):
        self.lot_id = lot_id
        self.errors = errors or {}
        super().__init__(response, f"Лот {lot_id} не сохранён: {message or self.errors}")


class RaiseTooEarlyError(ActionError):
    """Лоты поднимать ещё рано. ``wait`` — примерное число секунд до следующей попытки."""

    def __init__(self, response: requests.Response | None, message: str | None, wait: int | None):
        self.wait = wait
        super().__init__(response, message)


class RefundError(ActionError):
    pass


class ReviewError(ActionError):
    pass


class WithdrawError(ActionError):
    pass
