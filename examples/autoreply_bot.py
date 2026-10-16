"""Простой бот: отвечает на «цена» и благодарит за покупку.

Запуск: FUNPAY_KEY=ваш_golden_key python autoreply_bot.py
"""
import logging
import os

from funpay import FunPay, NewMessageEvent, NewOrderEvent
from funpay.utils import private_chat_name

logging.basicConfig(level=logging.INFO)

client = FunPay(os.environ["FUNPAY_KEY"])
me = client.login()
print(f"Вошёл как {me.username}, баланс {me.balance}")


@client.on_message(contains="цена")
def price(event: NewMessageEvent) -> None:
    client.send_message(event.message.chat_id, "Цены указаны в лотах, пишите, если есть вопросы.")


@client.on_new_order()
def thanks(event: NewOrderEvent) -> None:
    order = event.order
    chat = private_chat_name(client.user_id, order.counterparty.id)
    client.send_message(chat, f"Спасибо за заказ #{order.id}! Скоро выдам товар.")


client.run()
