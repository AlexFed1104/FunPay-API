"""Чаты: список, история, отправка сообщений и картинок."""
from __future__ import annotations

import io
import os
from typing import IO

from .. import parsers
from ..exceptions import ImageUploadError, MessageNotSentError
from ..models import BuyerViewing, Chat, ChatShort, Message
from ..utils import random_tag
from .base import BaseClient, _json


class ChatsMixin(BaseClient):

    def get_chats(self) -> list[ChatShort]:
        """Последние диалоги (до 50), как в списке чатов на сайте."""
        data = self.runner([{"type": "chat_bookmarks", "id": self.user_id, "tag": random_tag(), "data": False}])
        for obj in data.get("objects", []):
            if obj.get("type") == "chat_bookmarks" and obj.get("data"):
                return parsers.parse_chat_previews(obj["data"].get("html", ""))
        return []

    def get_chat_by_username(self, username: str) -> ChatShort | None:
        """Ищет чат по нику среди последних диалогов."""
        low = username.lower()
        return next((c for c in self.get_chats() if c.username.lower() == low), None)

    def get_chat(self, chat_id: int) -> Chat:
        """Страница чата: собеседник, «Покупатель смотрит» и последние сообщения."""
        self._ensure()
        soup, _ = self.http.get_html("chat/", params={"node": chat_id})
        return parsers.parse_chat_page(soup, chat_id)

    def get_messages(self, chat_id: int | str, before: int | None = None) -> list[Message]:
        """История чата, до 50 сообщений перед сообщением ``before`` (по умолчанию — последние).

        Чтобы листать дальше назад, передайте ``before=messages[0].id``.
        """
        self._ensure()
        params = {"node": chat_id, "last_message": before if before is not None else 999999999999}
        response = self.http.request("GET", "chat/history", params=params, ajax=True)
        chat = (_json(response) or {}).get("chat") or {}
        return parsers.parse_messages(chat.get("messages") or [], chat_id)

    def get_chats_messages(self, chat_ids: list[int | str]) -> dict[int | str, list[Message]]:
        """Последние сообщения сразу нескольких чатов (до 10 за запрос) через ``runner/``.

        Побочный эффект: чаты помечаются прочитанными.
        """
        result: dict[int | str, list[Message]] = {}
        for i in range(0, len(chat_ids), 10):
            batch = chat_ids[i:i + 10]
            data = self.runner([self._chat_node(c) for c in batch])
            result.update(self._messages_from_runner(data, batch))
        return result

    def _messages_from_runner(self, data: dict, chat_ids: list[int | str]) -> dict[int | str, list[Message]]:
        result: dict[int | str, list[Message]] = {}
        wanted = {str(c): c for c in chat_ids}
        for obj in data.get("objects", []):
            if obj.get("type") != "chat_node":
                continue
            node_data = obj.get("data") or {}
            node = node_data.get("node") or {}
            key = None
            for candidate in (obj.get("id"), node.get("id"), node.get("name")):
                if candidate is not None and str(candidate) in wanted:
                    key = wanted[str(candidate)]
                    break
            if key is None:
                continue
            result[key] = parsers.parse_messages(node_data.get("messages") or [], node.get("id", key))
        return result

    def mark_as_read(self, chat_id: int | str) -> None:
        """Отмечает чат прочитанным. Отдельного эндпоинта нет: чат читается, когда его запрашивают через ``runner/``."""
        self.runner([self._chat_node(chat_id)])

    def send_message(self, chat_id: int | str, text: str, mark_read: bool = True, as_bot: bool = True) -> Message | None:
        """Отправляет текст в чат.

        ``chat_id`` — числовой id чата или имя узла (``users-1-2``).
        ``as_bot`` добавляет невидимую метку, по которой :meth:`listen` отличает сообщения бота.
        ``mark_read=False`` оставляет чат непрочитанным, но тогда отправленное сообщение не возвращается.
        """
        content = f"{parsers.BOT_MARK}{text}" if as_bot else text
        return self._send(chat_id, {"content": content}, mark_read)

    def send_image(self, chat_id: int | str, image: str | bytes | IO[bytes] | int, mark_read: bool = True
                   ) -> Message | None:
        """Отправляет картинку: путь к файлу, байты, файловый объект или id уже загруженной картинки."""
        image_id = image if isinstance(image, int) else self.upload_image(image, "chat")
        return self._send(chat_id, {"content": "", "image_id": image_id}, mark_read)

    def _send(self, chat_id: int | str, extra: dict, mark_read: bool) -> Message | None:
        request = {"action": "chat_message", "data": {"node": chat_id, "last_message": -1, **extra}}
        objects = [self._chat_node(chat_id)] if mark_read else []
        data = self.runner(objects, request)
        resp = data.get("response")
        if not resp or resp.get("error"):
            raise MessageNotSentError(None, (resp or {}).get("error") or "пустой ответ", chat_id)
        messages = self._messages_from_runner(data, [chat_id]).get(chat_id) or []
        mine = [m for m in messages if m.author_id == self.user_id]
        return mine[-1] if mine else None

    def upload_image(self, image: str | bytes | IO[bytes], kind: str = "chat") -> int:
        """Загружает картинку для чата (``kind="chat"``) или лота (``kind="offer"``). Возвращает id файла."""
        self._ensure()
        if kind not in ("chat", "offer"):
            raise ValueError("kind должен быть chat или offer")
        if isinstance(image, str):
            name = os.path.basename(image)
            with open(image, "rb") as f:
                content = f.read()
        elif isinstance(image, bytes):
            name, content = "image.png", image
        else:
            name, content = getattr(image, "name", "image.png"), image.read()
        files = {"file": (os.path.basename(str(name)), io.BytesIO(content), "image/png")}
        response = self.http.request("POST", f"file/add{kind.title()}Image", data={"file_id": "0"}, files=files,
                                     ajax=True, check=False)
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code != 200 or not data.get("fileId"):
            raise ImageUploadError(response, data.get("msg"))
        return int(data["fileId"])

    def mute_chat(self, chat_id: int, mute: bool = True) -> None:
        """Выключает (или включает обратно) уведомления чата."""
        self._ensure()
        self.http.request("POST", "chat/mute", data={"node_id": chat_id, "mute": int(mute)}, ajax=True)

    def get_buyer_viewing(self, user_id: int) -> BuyerViewing:
        """Что сейчас открыто у покупателя (блок «Покупатель смотрит»)."""
        data = self.runner([{"type": "c-p-u", "id": str(user_id), "tag": "00000000", "data": False}])
        for obj in data.get("objects", []):
            if obj.get("type") == "c-p-u" and str(obj.get("id")) == str(user_id):
                return parsers.parse_buyer_viewing(obj)
        return BuyerViewing(user_id, None, None)
