"""Клиент против фейкового сервера: проверяем URL, параметры и обработку ответов без сети."""
import json
from urllib.parse import urlparse

import pytest
import requests

from funpay import FunPay, OrderStatus, RaiseTooEarlyError, UnauthorizedError, MessageNotSentError
from funpay.api.events import NewMessageEvent, NewOrderEvent, OrderStatusChangedEvent

from . import samples


def make_response(status=200, body="", headers=None, url="https://funpay.com/"):
    r = requests.Response()
    r.status_code = status
    if isinstance(body, (dict, list)):
        body = json.dumps(body)
        headers = {"content-type": "application/json", **(headers or {})}
    r._content = body.encode()
    r.headers.update(headers or {})
    r.url = url
    r.encoding = "utf-8"
    r.request = requests.Request("GET", url).prepare()
    return r


class FakeServer:
    """Подменяет ``requests.Session.request``. Маршруты: (метод, путь) -> функция(call) -> Response."""

    def __init__(self):
        self.routes = {}
        self.calls = []

    def route(self, method, path, handler):
        self.routes[(method, path)] = handler

    def __call__(self, method, url, data=None, params=None, **kw):
        path = urlparse(url).path.lstrip("/")
        call = {"method": method, "path": path, "data": data, "params": params or {}, **kw}
        self.calls.append(call)
        handler = self.routes.get((method, path))
        if handler is None:
            raise AssertionError(f"Нет маршрута {method} {path}")
        result = handler(call)
        if isinstance(result, requests.Response):
            return result
        return make_response(body=result, url=url)


@pytest.fixture
def server():
    return FakeServer()


@pytest.fixture
def client(server):
    c = FunPay("golden")
    c.http.session.request = server
    server.route("GET", "", lambda call: samples.MAIN_PAGE)
    return c


def runner_objects(call):
    return json.loads(call["data"]["objects"])


def test_login(client):
    me = client.login()
    assert me.id == 1000 and client.http.csrf_token == "csrf123"
    assert client.categories[0].subcategories[0].id == 81


def test_redirect_to_login_raises(client, server):
    server.route("GET", "", lambda call: make_response(302, headers={"Location": "https://funpay.com/account/login"}))
    with pytest.raises(UnauthorizedError):
        client.login()


def test_429_is_retried(client, server, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    answers = [make_response(429), make_response(body=samples.MAIN_PAGE)]
    server.route("GET", "", lambda call: answers.pop(0))
    assert client.login().username == "MySeller"


def test_get_chats_and_send(client, server):
    def runner(call):
        objs = runner_objects(call)
        request = call["data"]["request"]
        if request != "false":
            req = json.loads(request)
            assert req["action"] == "chat_message" and req["data"]["content"] == "⁡Привет"
            return {"objects": [{"type": "chat_node", "id": 555, "tag": "t", "data": {
                "node": {"id": 555, "name": "users-1000-54321", "silent": False},
                "messages": [{"id": 9003, "author": 1000, "html": samples.MESSAGE_HEADING.replace(
                    "users/54321/", "users/1000/").replace("MessageText", "⁡Привет")}]}}],
                "response": {"error": None}}
        assert objs[0]["type"] == "chat_bookmarks"
        assert call["data"]["csrf_token"] == "csrf123"
        return {"objects": [{"type": "chat_bookmarks", "tag": "x", "data": {"html": samples.CHAT_PREVIEWS}}]}

    server.route("POST", "runner/", runner)
    chats = client.get_chats()
    assert [c.username for c in chats] == ["Buyer1", "Buyer2"]
    msg = client.send_message(555, "Привет")
    assert msg.id == 9003 and msg.text == "Привет" and msg.by_bot


def test_send_error(client, server):
    server.route("POST", "runner/", lambda call: {"objects": [], "response": {"error": "Нельзя отправлять сообщения слишком часто."}})
    with pytest.raises(MessageNotSentError):
        client.send_message(555, "x")


def test_sales_pagination_and_limit(client, server):
    server.route("GET", "orders/trade", lambda call: samples.SALES_PAGE_1)

    def page2(call):
        assert call["data"]["continue"] == "AAAAAAA3" and call["data"]["state"] == "closed"
        return samples.SALES_PAGE_2

    server.route("POST", "orders/trade", page2)
    orders = list(client.get_sales(status=OrderStatus.CLOSED))
    assert [o.id for o in orders] == ["AAAAAAA1", "AAAAAAA2", "AAAAAAA3", "AAAAAAA4"]
    assert server.calls[-2]["params"] == {"state": "closed"}
    assert len(list(client.get_sales(limit=1))) == 1


def test_stats(client, server):
    server.route("GET", "orders/trade", lambda call: samples.SALES_PAGE_1)
    server.route("POST", "orders/trade", lambda call: samples.SALES_PAGE_2)
    s = client.get_stats()
    assert s.orders == 4 and s.unique_buyers == 3
    assert s.revenue == {"RUB": 1450.5} or s.revenue[list(s.revenue)[0]] == 1450.5
    assert s.by_status[OrderStatus.REFUNDED] == 1 and s.refund_rate == 0.25
    by_game = client.get_stats_by("game")
    assert by_game["CS2"].orders == 2 and by_game["Dota 2"].orders == 2
    assert client.get_top("lot")[0][0] == "Immortal"


def test_get_order(client, server):
    def api(call):
        body = json.loads(call["data"])
        assert body["order_uids"] == ["ABCDEFGH"]
        return {"status": "SUCCESS", "data": {"ABCDEFGH": {
            "order_uid": "ABCDEFGH", "status": "closed", "amount": "150.00", "currency": "RUB",
            "section": {"local_id": 81, "type_id": "lot"},
            "buyer": {"user_id": 5, "name": "Ann"}, "seller": {"user_id": 1000, "name": "MySeller"},
            "chat": {"node_name": "users-5-1000"},
            "review": {"text": "Супер", "rating": 5, "reply": "", "hidden": False},
            "type_data": {"amount": "2", "secrets": [{"value": "KEY-1"}],
                          "fields": {"player": {"value": "nick", "name": "Ник", "field_type_id": 1}}}}}}

    server.route("POST", "api/orders/get", api)
    order = client.get_order("ABCDEFGH")
    assert order.status is OrderStatus.CLOSED and order.price == 150 and order.amount == 2
    assert order.secrets == ["KEY-1"] and order.fields == {"player": "nick"}
    assert order.review.rating == 5 and order.buyer.username == "Ann"


def test_edit_and_delete_lot(client, server):
    server.route("GET", "lots/offerEdit", lambda call: samples.LOT_EDIT)
    saved = []
    server.route("POST", "lots/offerSave", lambda call: saved.append(call["data"]) or {"done": True})
    client.edit_lot(777, price=99, active=False)
    assert saved[0]["price"] == "99" and "active" not in saved[0] and saved[0]["offer_id"] == "777"
    assert saved[0]["csrf_token"] == "csrf123" and saved[0]["fields[desc][ru]"] == "Описание"
    client.delete_lot(777)
    assert saved[1]["deleted"] == "1" and saved[1]["offer_id"] == "777"
    with pytest.raises(TypeError):
        client.edit_lot(777, colour="red")


def test_raise_too_early(client, server):
    def handler(call):
        assert call["data"]["game_id"] == 41 and call["data"]["node_ids[]"] == [81]
        return {"error": 1, "msg": "Подождите 3 часа."}

    server.route("POST", "lots/raise", handler)
    with pytest.raises(RaiseTooEarlyError) as e:
        client.raise_lots(41)
    assert e.value.wait == 3 * 3600


def test_reviews_and_reply(client, server):
    pages = [samples.REVIEWS_PUBLIC, ""]
    server.route("POST", "users/reviews", lambda call: pages.pop(0))
    reviews = list(client.get_reviews(stars=5))
    assert len(reviews) == 2
    assert server.calls[1]["data"]["filter"] == "5" and server.calls[2]["data"]["continue"] == "=nextid"
    server.route("POST", "orders/review", lambda call: {"content": "<div/>"})
    client.reply_to_review("ABCDEFGH", "Спасибо")
    assert server.calls[-1]["data"]["rating"] == "" and server.calls[-1]["data"]["authorId"] == 1000


def test_listen_emits_new_order_and_message(client, server, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    sales = [samples.SALES_PAGE_1.replace('<input type="hidden" name="continue" value="AAAAAAA3">', "")]
    server.route("GET", "orders/trade", lambda call: sales[-1])
    bookmarks = [samples.CHAT_PREVIEWS]
    step = {"n": 0}

    def runner(call):
        objs = runner_objects(call)
        if objs[0]["type"] == "chat_node":
            return {"objects": [{"type": "chat_node", "id": 555, "tag": "t", "data": {
                "node": {"id": 555, "name": "users-1000-54321", "silent": False},
                "messages": [{"id": 9002, "author": 54321, "html": samples.MESSAGE_HEADING},
                             {"id": 9100, "author": 54321, "html": samples.MESSAGE_PLAIN}]}}]}
        step["n"] += 1
        return {"objects": [
            {"type": "orders_counters", "tag": f"o{step['n']}", "data": {"buyer": 0, "seller": 1}},
            {"type": "chat_bookmarks", "tag": f"c{step['n']}", "data": {"html": bookmarks[-1]}}]}

    server.route("POST", "runner/", runner)
    events = client.listen(delay=0)
    first = next(events)  # первый шаг только запоминает состояние, значит это уже второй шаг
    sales.append(sales[0].replace("text-primary", "text-success").replace('class="tc-item info"', 'class="tc-item "')
                 + samples.order_html("NEWORDER", "text-primary", "info", "500"))
    bookmarks.append(samples.CHAT_PREVIEWS.replace('data-node-msg="9002"', 'data-node-msg="9100"'))
    # первый next() уже выдал счётчики второго шага; собираем события третьего шага
    collected = []
    for e in events:
        collected.append(e)
        if isinstance(e, NewMessageEvent):
            break
    types = [type(e).__name__ for e in collected]
    assert "NewOrderEvent" in types and "OrderStatusChangedEvent" in types
    new_order = next(e for e in collected if isinstance(e, NewOrderEvent))
    assert new_order.order.id == "NEWORDER"
    changed = next(e for e in collected if isinstance(e, OrderStatusChangedEvent))
    assert changed.order.id == "AAAAAAA1" and changed.old_status is OrderStatus.PAID
    msg = collected[-1]
    assert msg.message.id == 9100 and not msg.by_me
    assert type(first).__name__ == "OrdersCountersChangedEvent"


def test_handlers_dispatch(client):
    from funpay.models import Message
    from funpay.enums import MessageType
    seen = []

    @client.on_message(contains="цена")
    def handler(e):
        seen.append(e.message.text)

    def ev(text, author):
        return NewMessageEvent(Message(1, 555, author, "x", text, None, MessageType.TEXT), None, by_me=author == 1000)

    client.dispatch(ev("Какая цена?", 5))
    client.dispatch(ev("Привет", 5))
    client.dispatch(ev("цена 100", 1000))
    assert seen == ["Какая цена?"]
