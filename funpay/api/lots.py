"""Лоты: просмотр, создание, изменение, удаление, поднятие, игровая валюта."""
from __future__ import annotations

from typing import IO, Any

from .. import parsers
from ..enums import SubcategoryType
from ..exceptions import FunPayError, LotSaveError, RaiseTooEarlyError
from ..models import ChipsFields, LotFields, LotShort, PriceCalc
from ..utils import parse_wait_seconds
from .base import BaseClient

FORM_HEADERS = {"content-type": "application/x-www-form-urlencoded; charset=UTF-8"}

_EDITABLE = {
    "title": "title", "title_en": "title_en", "description": "description",
    "description_en": "description_en", "payment_message": "payment_message", "price": "price",
    "amount": "amount", "active": "active", "auto_delivery": "auto_delivery", "secrets": "secrets",
    "images": "images",
}


class LotsMixin(BaseClient):

    # ---------- чтение ----------

    def get_my_lots(self, subcategory_id: int | None = None) -> list[LotShort]:
        """Свои лоты.

        С ``subcategory_id`` — все лоты подкатегории, включая выключенные (``lots/{id}/trade``).
        Без него — активные лоты из своего профиля по всем категориям.
        """
        self._ensure()
        if subcategory_id is None:
            return self.get_profile().lots  # type: ignore[attr-defined]
        soup, _ = self.http.get_html(f"lots/{subcategory_id}/trade")
        return parsers.parse_lot_previews(soup, subcategory_id=subcategory_id, mine=True)

    def get_category_lots(self, subcategory_id: int, type_: SubcategoryType = SubcategoryType.LOTS
                          ) -> list[LotShort]:
        """Все лоты подкатегории на рынке (для мониторинга цен конкурентов)."""
        self._ensure()
        soup, _ = self.http.get_html(f"{type_.value}/{subcategory_id}/")
        return parsers.parse_lot_previews(soup, subcategory_id=subcategory_id)

    def get_lot(self, lot_id: int) -> LotFields:
        """Все поля своего лота из формы редактирования."""
        self._ensure()
        soup, _ = self.http.get_html("lots/offerEdit", params={"offer": lot_id})
        return parsers.parse_lot_fields(soup, lot_id)

    # ---------- изменение ----------

    def save_lot(self, lot: LotFields) -> None:
        """Сохраняет форму лота как есть (``lots/offerSave``)."""
        self._ensure()
        fields = dict(lot.fields)
        fields["csrf_token"] = self.http.csrf_token or ""
        fields.setdefault("offer_id", str(lot.lot_id or 0))
        data = self.http.post_json("lots/offerSave", fields, headers=FORM_HEADERS)
        if data.get("error") or data.get("errors"):
            errors = dict(data["errors"]) if isinstance(data.get("errors"), list) else data.get("errors") or {}
            raise LotSaveError(None, data.get("msg") or str(data.get("error") or ""), lot.lot_id, errors)

    def create_lot(self, subcategory_id: int, title: str, price: float, description: str = "",
                   amount: int | None = None, active: bool = True, fields: dict[str, str] | None = None,
                   **changes: Any) -> None:
        """Создаёт лот в подкатегории.

        Обязательные поля подкатегории (сервер, тип товара и т.п.) передавайте в ``fields``
        под именами из формы, например ``{"fields[server]": "123"}``. Посмотреть их можно
        через ``client.get_new_lot_form(subcategory_id).fields``.
        """
        lot = self.get_new_lot_form(subcategory_id)
        lot.title = title
        lot.price = price
        lot.description = description
        lot.amount = amount
        lot.active = active
        if fields:
            lot.fields.update(fields)
        self._apply(lot, changes)
        self.save_lot(lot)

    def get_new_lot_form(self, subcategory_id: int) -> LotFields:
        """Пустая форма нового лота в подкатегории."""
        self._ensure()
        soup, _ = self.http.get_html("lots/offerEdit", params={"node": subcategory_id})
        lot = parsers.parse_lot_fields(soup, 0)
        lot.fields["offer_id"] = "0"
        return lot

    def edit_lot(self, lot_id: int, fields: dict[str, str] | None = None, **changes: Any) -> LotFields:
        """Меняет поля лота и сохраняет его.

        Пример: ``client.edit_lot(123, price=99, amount=10, description="...")``.
        Доступно: title, title_en, description, description_en, payment_message, price,
        amount, active, auto_delivery, secrets, images. Остальное — через ``fields``.
        """
        lot = self.get_lot(lot_id)
        if fields:
            lot.fields.update(fields)
        self._apply(lot, changes)
        self.save_lot(lot)
        return lot

    @staticmethod
    def _apply(lot: LotFields, changes: dict[str, Any]) -> None:
        for key, value in changes.items():
            if key not in _EDITABLE:
                raise TypeError(f"Неизвестное поле лота: {key}")
            setattr(lot, _EDITABLE[key], value)

    def activate_lot(self, lot_id: int) -> None:
        self.edit_lot(lot_id, active=True)

    def deactivate_lot(self, lot_id: int) -> None:
        self.edit_lot(lot_id, active=False)

    def delete_lot(self, lot_id: int) -> None:
        """Удаляет лот (``lots/offerSave`` с ``deleted=1``)."""
        self._ensure()
        lot = LotFields(lot_id, {"offer_id": str(lot_id), "deleted": "1"})
        self.save_lot(lot)

    def set_lots_hidden(self, hidden: bool) -> None:
        """Скрывает или показывает сразу все свои лоты (``trade/tradeLockSettings``)."""
        self._ensure()
        self.http.request("POST", "trade/tradeLockSettings", data={"userId": self.user_id, "mode": int(hidden)},
                          ajax=True)

    def raise_lots(self, category_id: int, subcategory_ids: list[int] | None = None) -> int | None:
        """Поднимает лоты игры. Возвращает примерное время ожидания до следующего поднятия (сек), если FunPay его прислал.

        Если поднимать рано, выбрасывает :class:`RaiseTooEarlyError` с полем ``wait``.
        """
        self._ensure()
        if subcategory_ids is None:
            cat = next((c for c in self.categories if c.id == category_id), None)
            if cat is None:
                raise FunPayError(f"Категория {category_id} не найдена")
            subcategory_ids = [s.id for s in cat.subcategories if s.type is SubcategoryType.LOTS]
        if not subcategory_ids:
            raise FunPayError(f"В категории {category_id} нет подкатегорий с лотами")
        payload = {"game_id": category_id, "node_id": subcategory_ids[0], "node_ids[]": subcategory_ids}
        data = self.http.post_json("lots/raise", payload, headers=FORM_HEADERS)
        if data.get("error") or data.get("url"):
            msg = data.get("msg") or data.get("url")
            raise RaiseTooEarlyError(None, msg, data.get("wait") or parse_wait_seconds(data.get("msg")))
        return data.get("wait")

    def calc_price(self, subcategory_id: int, price: float, type_: SubcategoryType = SubcategoryType.LOTS
                   ) -> PriceCalc:
        """Цена для покупателя с комиссией по способам оплаты.

        Для валюты (``CHIPS``) передайте id игры (категории) в ``subcategory_id``.
        """
        self._ensure()
        key = "nodeId" if type_ is SubcategoryType.LOTS else "game"
        data = self.http.post_json(f"{type_.value}/calc", {key: subcategory_id, "price": price},
                                   headers=FORM_HEADERS)
        if data.get("error"):
            raise FunPayError(f"Калькулятор: {data.get('error')}")
        return parsers.parse_calc(data, price)

    def upload_lot_image(self, image: str | bytes | IO[bytes]) -> int:
        """Загружает картинку для лота, возвращает её id для ``images``."""
        return self.upload_image(image, "offer")  # type: ignore[attr-defined]

    # ---------- игровая валюта ----------

    def get_chips(self, subcategory_id: int) -> ChipsFields:
        """Форма своих предложений игровой валюты (``chips/{id}/trade``)."""
        self._ensure()
        soup, _ = self.http.get_html(f"chips/{subcategory_id}/trade")
        return parsers.parse_chips_fields(soup, subcategory_id)

    def save_chips(self, chips: ChipsFields) -> None:
        """Сохраняет форму валюты. Поля меняйте в ``chips.fields`` по именам из формы."""
        self._ensure()
        fields = dict(chips.fields)
        fields["csrf_token"] = self.http.csrf_token or ""
        data = self.http.post_json("chips/saveOffers", fields, headers=FORM_HEADERS)
        if data.get("error") or data.get("errors"):
            raise LotSaveError(None, data.get("msg") or str(data.get("error") or ""), chips.subcategory_id,
                               dict(data.get("errors") or []))
