"""Общая часть клиента: авторизация, обновление сессии, запросы к ``runner/``."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from .. import parsers
from ..exceptions import ParseError, UnauthorizedError
from ..models import Category, Me, Subcategory
from ..transport import Transport
from ..enums import SubcategoryType

log = logging.getLogger("funpay")

SESSION_TTL = 40 * 60
"""Через сколько секунд переобновлять сессию и CSRF (FunPayCardinal советует 40–60 минут)."""


class BaseClient:
    def __init__(self, golden_key: str, user_agent: str | None = None, locale: str = "ru",
                 proxy: str | None = None, timeout: float = 15.0):
        self.http = Transport(golden_key, user_agent=user_agent, locale=locale, proxy=proxy, timeout=timeout)
        self.me: Me | None = None
        self.categories: list[Category] = []
        self._logged_in_at = 0.0

    # ---------- сессия ----------

    def login(self) -> Me:
        """Загружает главную страницу: id, ник, баланс, CSRF, список категорий."""
        soup, _ = self.http.get_html("")
        try:
            self.me = parsers.parse_me(soup)
        except ParseError as e:
            raise UnauthorizedError(None, str(e)) from e
        if not self.categories:
            self.categories = parsers.parse_categories(soup)
        self._logged_in_at = time.monotonic()
        return self.me

    refresh = login

    @property
    def user_id(self) -> int:
        self._ensure()
        return self.me.id  # type: ignore[union-attr]

    def _ensure(self) -> None:
        """Логинится при первом вызове и обновляет сессию раз в 40 минут."""
        if self.me is None or time.monotonic() - self._logged_in_at > SESSION_TTL:
            self.login()

    def set_locale(self, locale: str) -> None:
        """Язык страниц: ``ru``, ``en`` или ``uk``. Парсеры понимают все три."""
        if locale not in ("ru", "en", "uk"):
            raise ValueError("locale должен быть ru, en или uk")
        self.http.locale = locale

    def is_banned(self) -> bool:
        """``True``, если аккаунт заблокирован (``account/blocked`` отвечает 200)."""
        return self.http.request("GET", "account/blocked", check=False).status_code == 200

    def logout(self) -> None:
        self._ensure()
        self.http.request("GET", "account/logout", check=False)
        self.me = None

    # ---------- категории ----------

    def get_categories(self) -> list[Category]:
        """Дерево игр и подкатегорий (берётся с главной при входе)."""
        self._ensure()
        return self.categories

    def get_subcategory(self, subcategory_id: int, type_: SubcategoryType = SubcategoryType.LOTS
                        ) -> Subcategory | None:
        for cat in self.get_categories():
            for sub in cat.subcategories:
                if sub.id == subcategory_id and sub.type is type_:
                    return sub
        return None

    # ---------- runner ----------

    def runner(self, objects: list[dict] | None = None, request: dict | None = None) -> dict:
        """Сырой запрос к ``runner/``: подписки ``objects`` и действие ``request``."""
        self._ensure()
        payload = {
            "objects": json.dumps(objects or []),
            "request": json.dumps(request) if request else "false",
        }
        response = self.http.request("POST", "runner/", data=payload, ajax=True,
                                     headers={"content-type": "application/x-www-form-urlencoded; charset=UTF-8"})
        return _json(response)

    def _chat_node(self, chat_id: int | str, last_message: int = -1, tag: str = "00000000") -> dict:
        return {"type": "chat_node", "id": chat_id, "tag": tag,
                "data": {"node": chat_id, "last_message": last_message, "content": ""}}


def _json(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError as e:
        raise ParseError(f"Ответ {response.url} не JSON") from e

