"""HTTP-транспорт: куки, CSRF, ретраи, 429 и редиректы на логин."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import RateLimitError, RequestFailedError, UnauthorizedError

log = logging.getLogger("funpay")

BASE_URL = "https://funpay.com/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)
AJAX_HEADERS = {
    "accept": "*/*",
    "x-requested-with": "XMLHttpRequest",
}


class Transport:
    """Низкоуровневые запросы к funpay.com от имени браузера.

    Хранит ``golden_key``, ``PHPSESSID`` и CSRF-токен, повторяет запросы на 5xx,
    ждёт на 429 и превращает редирект на страницу входа в :class:`UnauthorizedError`.
    """

    def __init__(self, golden_key: str, user_agent: str | None = None, locale: str = "ru",
                 proxy: str | None = None, timeout: float = 15.0, max_429_wait: float = 120.0):
        self.golden_key = golden_key
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.locale = locale
        self.timeout = timeout
        self.max_429_wait = max_429_wait
        self.csrf_token: str | None = None
        self.session = requests.Session()
        retry = Retry(total=5, backoff_factor=0.5, status_forcelist=(500, 502, 503, 504),
                      allowed_methods=None, raise_on_status=False)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.cookies.set("golden_key", golden_key, domain="funpay.com")
        self.session.cookies.set("cookie_prefs", "1", domain="funpay.com")
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    def url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return BASE_URL + path.lstrip("/")

    def request(self, method: str, path: str, *, data: Any = None, params: dict | None = None,
                files: dict | None = None, json_body: Any = None, ajax: bool = False,
                headers: dict | None = None, check: bool = True) -> requests.Response:
        """Отправляет запрос. ``ajax=True`` добавляет заголовки XHR и CSRF-токен в POST."""
        url = self.url(path)
        hdrs = {"user-agent": self.user_agent}
        if ajax:
            hdrs.update(AJAX_HEADERS)
        if headers:
            hdrs.update(headers)
        params = dict(params or {})
        if method.upper() == "GET" and self.locale and self.locale != "ru" and "api/" not in url:
            params.setdefault("setlocale", self.locale)
        if method.upper() == "POST" and isinstance(data, dict) and self.csrf_token and "csrf_token" not in data:
            data = {**data, "csrf_token": self.csrf_token}

        started = time.monotonic()
        attempt = 0
        redirects = 0
        while True:
            attempt += 1
            response = self.session.request(method, url, data=data, params=params, files=files,
                                            json=json_body, headers=hdrs, timeout=self.timeout,
                                            allow_redirects=False)
            if response.status_code == 429:
                wait = min(2 ** attempt, 30)
                if time.monotonic() - started + wait > self.max_429_wait:
                    raise RateLimitError(response, "FunPay ограничил частоту запросов (429)")
                log.warning("429 от FunPay на %s, жду %s с", url, wait)
                time.sleep(wait)
                continue
            if 300 <= response.status_code < 400 and "Location" in response.headers:
                location = response.headers["Location"]
                if "account/login" in location:
                    raise UnauthorizedError(response)
                redirects += 1
                if redirects > 5:
                    raise RequestFailedError(response, "Слишком много редиректов")
                url = self.url(location)
                method, data, files, json_body, params = "GET", None, None, None, {}
                continue
            break

        if response.status_code in (401, 403):
            raise UnauthorizedError(response)
        if check and response.status_code != 200:
            raise RequestFailedError(response)
        return response

    def get_html(self, path: str, params: dict | None = None) -> tuple[BeautifulSoup, str]:
        """GET страницы. Попутно обновляет CSRF-токен и проверяет, что мы залогинены."""
        response = self.request("GET", path, params=params)
        html = response.text
        soup = BeautifulSoup(html, "lxml")
        self.update_csrf(soup)
        return soup, html

    def post_json(self, path: str, data: Any = None, **kwargs: Any) -> dict:
        """AJAX POST, ответ — JSON."""
        response = self.request("POST", path, data=data, ajax=True, **kwargs)
        try:
            return response.json()
        except ValueError as e:
            raise RequestFailedError(response, "Ответ не JSON") from e

    def update_csrf(self, soup: BeautifulSoup) -> dict | None:
        body = soup.find("body")
        raw = body.get("data-app-data") if body else None
        if not raw:
            return None
        try:
            app_data = json.loads(raw)
        except ValueError:
            return None
        self.csrf_token = app_data.get("csrf-token") or self.csrf_token
        return app_data
