"""Профиль и финансы: профиль, баланс, история операций, кошельки, вывод."""
from __future__ import annotations

from typing import Iterator

from .. import parsers
from ..enums import Currency, TransactionFilter
from ..exceptions import FunPayError, WithdrawError
from ..models import Balance, LotShort, Profile, Transaction, Wallet
from .base import BaseClient


class ProfileMixin(BaseClient):

    def get_profile(self, user_id: int | None = None) -> Profile:
        """Профиль пользователя (без ``user_id`` — свой): ник, онлайн, рейтинг, лоты."""
        self._ensure()
        user_id = user_id or self.user_id
        soup, _ = self.http.get_html(f"users/{user_id}/")
        return parsers.parse_profile(soup, user_id)

    def get_user_lots(self, user_id: int) -> list[LotShort]:
        return self.get_profile(user_id).lots

    def get_balance(self) -> Balance:
        """Баланс по валютам со страницы ``account/balance``."""
        self._ensure()
        soup, _ = self.http.get_html("account/balance")
        return parsers.parse_balance(soup)

    def get_transactions(self, filter: TransactionFilter = TransactionFilter.ALL, limit: int | None = None
                         ) -> Iterator[Transaction]:
        """История операций по балансу, от новых к старым (``users/transactions``)."""
        self._ensure()
        cursor = ""
        count = 0
        while True:
            response = self.http.request("POST", "users/transactions", ajax=True, data={
                "user_id": self.user_id, "filter": filter.value, "continue": cursor})
            items, next_cursor = parsers.parse_transactions(response.text)
            for t in items:
                yield t
                count += 1
                if limit is not None and count >= limit:
                    return
            if not next_cursor or not items or next_cursor == cursor:
                return
            cursor = next_cursor

    def get_wallets(self) -> list[Wallet]:
        """Сохранённые реквизиты для вывода."""
        self._ensure()
        soup, _ = self.http.get_html("account/wallets")
        return parsers.parse_wallets(soup)

    def calc_withdraw(self, currency: Currency, wallet_type: str, address: str, amount: float) -> dict:
        """Сколько придёт на кошелёк после комиссии (``withdraw/calc``). Ответ FunPay как есть."""
        self._ensure()
        return self.http.post_json("withdraw/calc", {
            "preview": "1", "currency_id": currency.code, "ext_currency_id": wallet_type,
            "wallet": address, "amount_int": str(amount)})

    def withdraw(self, currency: Currency, wallet_type: str, address: str, amount: float) -> float:
        """Выводит деньги. ``wallet_type`` — код FunPay: ``card_rub``, ``fps``, ``usdt_trc``, ``binance`` и т.п.

        Возвращает сумму, которая придёт на кошелёк.
        """
        self._ensure()
        data = self.http.post_json("withdraw/withdraw", {
            "currency_id": currency.code, "ext_currency_id": wallet_type, "wallet": address,
            "amount_int": str(amount)})
        if data.get("error"):
            raise WithdrawError(None, data.get("msg"))
        return float(data.get("amount_ext") or 0)

    def set_currency(self, currency: Currency) -> None:
        """Меняет валюту аккаунта."""
        if currency is Currency.UNKNOWN:
            raise FunPayError("Неизвестная валюта")
        self._ensure()
        self.http.post_json("account/switchCurrency", {"cy": currency.code, "confirmed": "true"})
