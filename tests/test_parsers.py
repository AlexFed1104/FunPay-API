from datetime import datetime

from bs4 import BeautifulSoup

from funpay import parsers
from funpay.enums import Currency, MessageType, OrderStatus, SubcategoryType, TransactionStatus
from funpay.utils import MSK, parse_date, parse_money, parse_wait_seconds

from . import samples


def soup(html):
    return BeautifulSoup(html, "lxml")


def test_me_and_categories():
    s = soup(samples.MAIN_PAGE)
    me = parsers.parse_me(s)
    assert (me.id, me.username, me.active_sales, me.active_purchases) == (1000, "MySeller", 3, 1)
    assert me.balance.value == 1234 and me.balance.currency is Currency.RUB
    cats = parsers.parse_categories(s)
    assert cats[0].id == 41 and cats[0].name == "Dota 2"
    assert [(x.id, x.type) for x in cats[0].subcategories] == [(81, SubcategoryType.LOTS), (82, SubcategoryType.CHIPS)]


def test_chat_previews():
    chats = parsers.parse_chat_previews(samples.CHAT_PREVIEWS)
    assert [c.id for c in chats] == [555, 556]
    assert chats[0].unread and chats[0].last_message_id == 9002 and chats[0].username == "Buyer1"
    assert chats[0].avatar_url == "https://sfunpay.com/a.jpg"
    assert not chats[1].unread and chats[1].by_bot and chats[1].last_message_text == "Спасибо за покупку!"


def test_messages_carry_author_to_next_message():
    msgs = parsers.parse_messages([
        {"id": 12345, "author": 54321, "html": samples.MESSAGE_HEADING},
        {"id": 12346, "author": 54321, "html": samples.MESSAGE_PLAIN},
        {"id": 12348, "author": 54321, "html": samples.MESSAGE_IMAGE},
    ], chat_id=555)
    assert msgs[0].author_username == "Username" and msgs[0].text == "MessageText"
    assert msgs[0].date.month == 5 and msgs[0].date.day == 26
    assert msgs[1].author_username == "Username" and msgs[1].text == "Second" and msgs[1].date == msgs[0].date
    assert msgs[2].type is MessageType.IMAGE and msgs[2].image_url.endswith("img.jpg")


def test_system_message():
    msg = parsers.parse_message_html(samples.MESSAGE_REFUND, 12347, 555, author_id=0)
    assert msg.is_system and msg.type is MessageType.ORDER_REFUNDED
    assert msg.order_id == "AAAAAAAA" and msg.author_id == 0 and msg.badge == "оповещение"
    assert msg.text.startswith("Продавец SellerUsername вернул деньги")


def test_order_previews():
    orders, cursor = parsers.parse_order_previews(samples.SALES_PAGE_1)
    assert cursor == "AAAAAAA3"
    assert [o.id for o in orders] == ["AAAAAAA1", "AAAAAAA2"]
    assert orders[0].status is OrderStatus.PAID and orders[1].status is OrderStatus.CLOSED
    assert orders[1].total.value == 1250.5 and orders[1].total.currency is Currency.RUB
    assert orders[0].counterparty.id == 1 and orders[0].counterparty.username == "Ann"
    assert orders[0].category_text == "Dota 2, Предметы" and orders[1].title == "Immortal"
    refunded, _ = parsers.parse_order_previews(samples.SALES_PAGE_2)
    assert refunded[0].status is OrderStatus.REFUNDED
    assert refunded[0].date == datetime(2024, 1, 5, 12, 0, tzinfo=MSK)


def test_reviews():
    page = parsers.parse_reviews(samples.REVIEWS_PUBLIC)
    assert page.next_cursor == "=nextid"
    a, b = page.reviews
    assert (a.rating, a.text, a.reply, a.category_text) == (5, "ReviewText", "ReviewReply", "Game")
    assert a.order_total.value == 100 and a.author_id is None
    assert (b.rating, b.order_id, b.author_id, b.author_username) == (3, "ABCDEFGH", 54321, "SenderUername")
    assert b.category_text == "Dota 2, Предметы" and b.reply is None


def test_review_on_order_page():
    r = parsers.parse_reviews(samples.REVIEW_ORDER_PAGE).reviews[0]
    assert (r.rating, r.order_id, r.author_id, r.reply) == (1, "ABCDEFGH", 54321, "ReviewReply")
    assert r.order_total.value == 500 and r.order_total.currency is Currency.USD


def test_transactions():
    items, cursor = parsers.parse_transactions(samples.TRANSACTIONS)
    assert cursor == "101010"
    assert items[0].status is TransactionStatus.COMPLETED and items[0].amount.value == 1.23
    assert items[0].order_id == "ABCDEFGH"
    assert items[1].status is TransactionStatus.CANCELLED and items[1].amount.value == -1234.56


def test_lot_previews():
    lot = parsers.parse_lot_previews(samples.LOT_PREVIEW, subcategory_id=81)[0]
    assert lot.id == 12345 and lot.price == 3499.796334 and lot.currency is Currency.RUB
    assert lot.auto_delivery and lot.promoted and lot.amount == 1
    assert lot.seller.id == 54321 and lot.seller.username == "SellerUsername" and lot.seller.online
    assert lot.seller_rating == 5 and lot.seller_reviews == 105


def test_profile():
    p = parsers.parse_profile(soup(samples.PROFILE), 1234)
    assert (p.username, p.online, p.banned, p.avatar_url) == ("SomeSeller", True, False, "/img/a.jpg")
    assert p.registration_text == "15 August 2015, 18:01"
    assert p.rating.stars == 4.9 and p.rating.reviews_count == 1049 and p.rating.distribution[5] == 90
    assert len(p.lots) == 1 and p.lots[0].subcategory_id == 81 and p.lots[0].price == 3499.79


def test_lot_fields():
    lot = parsers.parse_lot_fields(soup(samples.LOT_EDIT), 777)
    assert lot.title == "Старое название" and lot.price == 100 and lot.amount == 5
    assert lot.active and not lot.auto_delivery and lot.secrets == ["key1", "key2"]
    assert lot.fields["fields[type]"] == "2" and "fields[hidden]" not in lot.fields
    assert lot.subcategory_id == 81 and lot.currency is Currency.RUB
    lot.active = False
    lot.price = 150.5
    assert "active" not in lot.fields and lot.fields["price"] == "150.5"


def test_utils():
    now = datetime(2026, 10, 16, 12, 0, tzinfo=MSK)
    assert parse_date("сегодня, 13:33", now) == datetime(2026, 10, 16, 13, 33, tzinfo=MSK)
    assert parse_date("вчера, 10:00", now) == datetime(2026, 10, 15, 10, 0, tzinfo=MSK)
    assert parse_date("26 мая, 11:21:41", now) == datetime(2026, 5, 26, 11, 21, 41, tzinfo=MSK)
    assert parse_date("28 декабря, 10:00", now).year == 2025
    assert parse_date("15 August 2015, 18:01", now) == datetime(2015, 8, 15, 18, 1, tzinfo=MSK)
    assert parse_date("20 января в 12:58, 3 месяца назад", now) == datetime(2026, 1, 20, 12, 58, tzinfo=MSK)
    assert parse_date("2 месяца назад", now) is None
    assert parse_money("1 234.56 ₽") == (1234.56, Currency.RUB)
    assert parse_money("− 5 $") == (-5.0, Currency.USD)
    assert parse_wait_seconds("Подождите 2 часа.") == 7200
