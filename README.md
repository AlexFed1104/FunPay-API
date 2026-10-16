# funpay-api

Неофициальная Python-библиотека для [FunPay](https://funpay.com): чаты, лоты, заказы, профиль, отзывы, статистика и события в реальном времени.

Официального API у FunPay нет, поэтому библиотека работает как браузер: ходит на страницы сайта и его внутренние AJAX-эндпоинты и разбирает HTML. Если FunPay поменяет вёрстку, часть методов может сломаться.

## Установка

```bash
pip install ./funpay-api        # из папки проекта
```

Нужен Python 3.10+. Зависимости: `requests`, `beautifulsoup4`, `lxml`.

## Авторизация

Нужна кука `golden_key` из браузера, где вы вошли на funpay.com (DevTools → Application → Cookies → `golden_key`). Логина по паролю нет. Желательно передать `user_agent` того же браузера.

```python
from funpay import FunPay

client = FunPay("ваш golden_key", user_agent="Mozilla/5.0 ...")
me = client.login()
print(me.username, me.balance)
```

Сессия и CSRF-токен обновляются сами раз в 40 минут. Ключ никому не передавайте: он даёт полный доступ к аккаунту.

## Что умеет

### Чаты
| Метод | Что делает |
|---|---|
| `get_chats()` | последние диалоги |
| `get_chat_by_username(name)` | найти чат по нику |
| `get_chat(chat_id)` | страница чата и «Покупатель смотрит» |
| `get_messages(chat_id, before=None)` | история, листание назад |
| `get_chats_messages([ids])` | последние сообщения нескольких чатов разом |
| `send_message(chat_id, text)` | отправить текст |
| `send_image(chat_id, path_or_bytes)` | отправить картинку |
| `mark_as_read(chat_id)` | отметить прочитанным |
| `mute_chat(chat_id, mute=True)` | выключить уведомления |
| `get_buyer_viewing(user_id)` | что открыто у покупателя |

`chat_id` — числовой id чата или имя узла `users-<id1>-<id2>` (см. `funpay.utils.private_chat_name`).

### Лоты
| Метод | Что делает |
|---|---|
| `get_my_lots(subcategory_id=None)` | свои лоты (с подкатегорией — включая выключенные) |
| `get_lot(lot_id)` | все поля лота (`LotFields`) |
| `create_lot(subcategory_id, title, price, ...)` | создать лот |
| `edit_lot(lot_id, price=..., amount=..., ...)` | изменить поля |
| `activate_lot` / `deactivate_lot` / `delete_lot` | включить / выключить / удалить |
| `set_lots_hidden(True)` | скрыть все лоты разом |
| `raise_lots(category_id)` | поднять лоты игры |
| `get_category_lots(subcategory_id)` | чужие лоты в подкатегории |
| `get_categories()` | дерево игр и подкатегорий |
| `calc_price(subcategory_id, price)` | цена для покупателя с комиссией |
| `get_chips` / `save_chips` | игровая валюта |
| `upload_lot_image(path)` | картинка для лота |

### Заказы
| Метод | Что делает |
|---|---|
| `get_sales(status=, buyer=, game_id=, date_from=, date_to=, limit=)` | продажи, генератор с пагинацией |
| `get_purchases(...)` | покупки |
| `get_order(order_id)` / `get_orders([ids])` | подробности (до 10 за раз) |
| `refund(order_id)` | возврат |

### Профиль и деньги
`get_profile(user_id=None)`, `get_user_lots(user_id)`, `get_balance()`, `get_transactions(filter=, limit=)`, `get_wallets()`, `calc_withdraw(...)`, `withdraw(...)`, `set_currency(...)`, `is_banned()`.

### Отзывы
`get_reviews(user_id=None, stars=None)`, `get_order_review(order_id)`, `reply_to_review(order_id, text)`, `leave_review(order_id, text, stars)`, `delete_review(order_id)`.

### Статистика
У FunPay нет страницы статистики, поэтому она считается по продажам:

```python
s = client.get_stats(date_from=datetime(2026, 9, 1, tzinfo=MSK))
s.orders, s.revenue, s.average_check, s.refund_rate, s.unique_buyers

client.get_stats_by("day")      # также month, weekday, hour, game, category, lot, buyer
client.get_top("lot", n=5)      # топ по выручке
client.get_rating_stats()       # рейтинг и распределение по звёздам
client.export_sales("sales.csv")
```

Те же функции есть в `funpay.stats` для уже загруженного списка заказов, чтобы не ходить на сайт повторно.

### События
```python
@client.on_message(contains="цена")
def on_price(event):
    client.send_message(event.message.chat_id, "Цены в лотах")

@client.on_new_order()
def on_order(event):
    print("Новый заказ", event.order.id, event.order.total)

client.run()          # или: for event in client.listen(): ...
```

События: `NewMessageEvent`, `ChatsChangedEvent`, `NewOrderEvent`, `OrderStatusChangedEvent`, `OrdersCountersChangedEvent`. Свои сообщения обработчик `on_message` пропускает. Сообщения, отправленные библиотекой, помечаются невидимым символом, как в FunPayCardinal (`message.by_bot`).

Чтобы прочитать новые сообщения, библиотека запрашивает историю чата, и FunPay помечает такой чат прочитанным.

## Ошибки
Все исключения наследуются от `FunPayError`: `UnauthorizedError`, `RequestFailedError`, `RateLimitError`, `ParseError`, `MessageNotSentError`, `ImageUploadError`, `LotSaveError`, `RaiseTooEarlyError` (поле `wait` — секунды до следующего поднятия), `RefundError`, `ReviewError`, `WithdrawError`.

На 429 библиотека ждёт и повторяет запрос (до 2 минут), на 5xx — повторяет до 5 раз.

## Что не проверено вживую
Код написан по двум рабочим проектам (FunPayCardinal и FunPayBotEngine) и проверен тестами на образцах HTML, но против настоящего funpay.com не запускался. Меньше всего уверенности в:
- `set_currency` (поле `confirmed=true` — предположение);
- `calc_withdraw` и `withdraw` (ответ возвращается как есть);
- `get_chips` / `save_chips` (форма валюты разбирается целиком, без удобных полей);
- `get_balance` (поле «доступно к выводу» берётся, только если оно есть на странице).

## Тесты
```bash
pip install pytest
pytest
```

Образцы HTML в `tests/samples.py` частично взяты из [funpayparsers](https://github.com/funpayhub/funpayparsers) (MIT).

## Лицензия
MIT.
