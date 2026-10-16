"""Парсеры HTML/JSON FunPay. Чистые функции без сети, их удобно тестировать на сохранённых страницах."""
from __future__ import annotations

import html as html_lib
import json
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from .enums import Currency, MessageType, OrderStatus, SubcategoryType, TransactionStatus
from .exceptions import ParseError
from .models import (
    Balance, BuyerViewing, Category, Chat, ChatShort, LotFields, LotShort, Me, Message, Money,
    Order, OrderShort, PriceCalc, Profile, Rating, Review, ReviewsPage, Subcategory, Transaction,
    UserShort, Wallet, ChipsFields,
)
from .utils import ORDER_ID_RE, detect_system_message, parse_date, parse_money, strip_invisible

BOT_MARK = "⁡"
"""Невидимый символ в начале сообщений, отправленных библиотекой (как в FunPayCardinal)."""

_URL_RE = re.compile(r"url\(['\"]?([^'\")]+)['\"]?\)")
_USER_ID_RE = re.compile(r"/users/(\d+)/?")


def soup_of(source: str | BeautifulSoup | Tag) -> BeautifulSoup | Tag:
    if isinstance(source, (BeautifulSoup, Tag)):
        return source
    return BeautifulSoup(source, "lxml")


def _text(tag: Tag | None, strip: bool = True) -> str | None:
    if tag is None:
        return None
    return tag.get_text(strip=strip) if strip else tag.get_text()


def _css_url(style: str | None) -> str | None:
    if not style:
        return None
    m = _URL_RE.search(style)
    return m.group(1) if m else None


def _user_id_from(href: str | None) -> int | None:
    if not href:
        return None
    m = _USER_ID_RE.search(href)
    return int(m.group(1)) if m else None


def _int(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def _hidden_input(soup: BeautifulSoup | Tag, name: str) -> str | None:
    tag = soup.find("input", {"type": "hidden", "name": name})
    return tag.get("value") if tag else None


# ---------- главная страница ----------

def parse_app_data(soup: BeautifulSoup) -> dict:
    body = soup.find("body")
    raw = body.get("data-app-data") if body else None
    if not raw:
        raise ParseError("На странице нет data-app-data")
    return json.loads(raw)


def parse_me(soup: BeautifulSoup) -> Me:
    """Данные аккаунта из шапки любой страницы."""
    app = parse_app_data(soup)
    username = soup.find("div", class_="user-link-name")
    if not username or not app.get("userId"):
        raise ParseError("Не найден ник в шапке: похоже, golden_key неверный")
    balance = None
    if badge := soup.find("span", class_="badge-balance"):
        value, currency = parse_money(badge.get_text(" ", strip=True))
        balance = Money(value, currency)
    sales = soup.find("span", class_="badge-trade")
    purchases = soup.find("span", class_="badge-orders")
    return Me(
        id=int(app["userId"]),
        username=username.get_text(strip=True),
        balance=balance,
        active_sales=_int(_text(sales)) or 0,
        active_purchases=_int(_text(purchases)) or 0,
        locale=app.get("locale") or "ru",
    )


def parse_categories(soup: BeautifulSoup) -> list[Category]:
    """Дерево игр и подкатегорий с главной страницы."""
    tables = soup.find_all("div", class_="promo-game-list")
    if not tables:
        return []
    table = tables[1] if len(tables) > 1 else tables[0]
    result: dict[int, Category] = {}
    for item in table.find_all("div", class_="promo-game-item"):
        title = item.find("div", class_="game-title")
        if not title or not title.get("data-id"):
            continue
        gid = int(title["data-id"])
        name = item.find("a").get_text(strip=True)
        result[gid] = Category(gid, name)
        if group := item.find("div", {"role": "group"}):
            for btn in group.find_all("button"):
                rid = int(btn["data-id"])
                result[rid] = Category(rid, f"{name} ({btn.get_text(strip=True)})")
        for ul in item.find_all("ul", class_="list-inline"):
            cat = result.get(int(ul.get("data-id", gid)), result[gid])
            for a in ul.find_all("a"):
                href = a.get("href", "")
                sid = _int(href.rstrip("/").rsplit("/", 1)[-1])
                if sid is None:
                    continue
                stype = SubcategoryType.CHIPS if "/chips/" in href else SubcategoryType.LOTS
                cat.subcategories.append(Subcategory(sid, a.get_text(strip=True), stype, cat.id))
    return list(result.values())


# ---------- чаты ----------

def parse_chat_previews(source: str | BeautifulSoup) -> list[ChatShort]:
    soup = soup_of(source)
    chats = []
    for a in soup.find_all("a", class_="contact-item"):
        msg = a.find("div", class_="contact-item-message")
        if msg is None:
            continue
        text = msg.get_text()
        by_bot = text.startswith(BOT_MARK)
        if by_bot:
            text = text[1:]
        photo = a.find("div", class_="avatar-photo")
        chats.append(ChatShort(
            id=int(a["data-id"]),
            username=_text(a.find("div", class_="media-user-name")) or "",
            last_message_text=strip_invisible(text),
            last_message_id=int(a.get("data-node-msg") or 0),
            last_read_message_id=int(a.get("data-user-msg") or 0),
            unread="unread" in (a.get("class") or []),
            by_bot=by_bot,
            time_text=_text(a.find("div", class_="contact-item-time")),
            avatar_url=_css_url(photo.get("style")) if photo else None,
            raw=str(a),
        ))
    return chats


def parse_message_html(html: str, message_id: int, chat_id: int | str, author_id: int | None = None,
                       ) -> Message:
    """Одно сообщение из ``chat/history`` или ``runner/``."""
    soup = BeautifulSoup(html.replace("<br>", "\n"), "lxml")
    author_username = None
    badge = None
    date = None
    if name_div := soup.find("div", class_="media-user-name"):
        link = name_div.find("a")
        if link:
            author_username = link.get_text(strip=True)
            author_id = author_id if author_id is not None else _user_id_from(link.get("href"))
        else:
            author_username = next(name_div.stripped_strings, None)
        if label := name_div.find("span", class_="chat-msg-author-label"):
            badge = label.get_text(strip=True)
        if date_div := name_div.find("div", class_="chat-msg-date"):
            date = parse_date(date_div.get("title") or date_div.get_text(strip=True))

    image_url = None
    text = None
    if img := soup.find("a", class_="chat-img-link"):
        image_url = img.get("href")
        mtype = MessageType.IMAGE
    else:
        alert = soup.find("div", role="alert")
        text_div = soup.find("div", class_="chat-msg-text")
        text = strip_invisible((text_div or alert).get_text()) if (text_div or alert) else ""
        if alert is not None or author_id == 0:
            author_id = 0
            mtype = detect_system_message(text)
        else:
            mtype = MessageType.TEXT
    by_bot = bool(text) and text.startswith(BOT_MARK)
    if by_bot:
        text = text[1:]
    order_id = None
    if mtype not in (MessageType.TEXT, MessageType.IMAGE) and text:
        if m := ORDER_ID_RE.search(text):
            order_id = m.group(1)
    return Message(id=message_id, chat_id=chat_id, author_id=author_id, author_username=author_username,
                   text=text, image_url=image_url, type=mtype, date=date, badge=badge, by_bot=by_bot,
                   order_id=order_id, raw=html)


def parse_messages(json_messages: list[dict], chat_id: int | str) -> list[Message]:
    """Список сообщений из JSON (``chat.messages`` или ``objects[].data.messages``).

    В подряд идущих сообщениях одного автора FunPay не повторяет шапку с ником,
    поэтому ник и дата протягиваются от предыдущего сообщения.
    """
    result: list[Message] = []
    names: dict[int, str] = {0: "FunPay"}
    for item in json_messages:
        msg = parse_message_html(item["html"], int(item["id"]), chat_id, item.get("author"))
        if msg.author_username and msg.author_id is not None:
            names[msg.author_id] = msg.author_username
        elif msg.author_id is not None:
            msg.author_username = names.get(msg.author_id)
        if msg.date is None and result and result[-1].author_id == msg.author_id:
            msg.date = result[-1].date
        result.append(msg)
    return result


def parse_chat_page(soup: BeautifulSoup, chat_id: int) -> Chat:
    header = soup.find("div", class_="chat-header")
    name_link = header.find("div", class_="media-user-name").find("a") if header else None
    if not name_link:
        raise ParseError(f"Чат {chat_id} не найден")
    looking_text = looking_link = None
    if panel := soup.find("div", class_="chat-panel"):
        if a := panel.find("a"):
            looking_text, looking_link = a.get_text(strip=True), a.get("href")
    messages: list[Message] = []
    for item in soup.find_all("div", class_="chat-msg-item"):
        mid = _int((item.get("id") or "").replace("message-", ""))
        if mid is not None:
            messages.append(parse_message_html(str(item), mid, chat_id))
    return Chat(id=chat_id, username=name_link.get_text(strip=True),
                interlocutor_id=_user_id_from(name_link.get("href")),
                looking_at_text=looking_text, looking_at_link=looking_link,
                messages=messages, raw=str(soup))


def parse_buyer_viewing(obj: dict) -> BuyerViewing:
    buyer_id = int(obj.get("id"))
    data = obj.get("data") or {}
    html = (data.get("html") or {}) if isinstance(data, dict) else {}
    desktop = html.get("desktop") if isinstance(html, dict) else None
    if not desktop:
        return BuyerViewing(buyer_id, None, None)
    a = BeautifulSoup(desktop, "lxml").find("a")
    return BuyerViewing(buyer_id, a.get("href") if a else None, a.get_text(strip=True) if a else None)


# ---------- лоты ----------

def parse_lot_previews(source: str | BeautifulSoup | Tag, subcategory_id: int | None = None,
                       mine: bool = False) -> list[LotShort]:
    """Лоты из таблицы ``a.tc-item`` (подкатегория, профиль, свои лоты на ``lots/{id}/trade``)."""
    soup = soup_of(source)
    result = []
    for a in soup.find_all("a", class_="tc-item"):
        classes = a.get("class") or []
        href = a.get("href", "")
        lot_id: int | str | None = a.get("data-offer")
        if lot_id is None and "id=" in href:
            lot_id = href.split("id=")[1].split("&")[0]
        if lot_id is None:
            continue
        lot_id = int(lot_id) if str(lot_id).isdigit() else lot_id
        price_div = a.find("div", class_="tc-price")
        price, currency = None, Currency.UNKNOWN
        if price_div is not None:
            if price_div.get("data-s"):
                price = float(price_div["data-s"])
                unit = price_div.find("span", class_="unit")
                currency = Currency.parse(unit.get_text(strip=True) if unit else None)
            else:
                price, currency = parse_money(price_div.get_text(" ", strip=True))
        amount_div = a.find("div", class_="tc-amount")
        seller = None
        stars = reviews = None
        if not mine and (body := a.find("div", class_="media-body")):
            name = body.find("div", class_="media-user-name")
            span = name.find(attrs={"data-href": True}) if name else None
            uid = _user_id_from(span.get("data-href")) if span else _int(a.get("data-user"))
            if uid is not None:
                seller = UserShort(uid, name.get_text(strip=True), online=a.get("data-online") == "1")
            if st := body.find("div", class_="rating-stars"):
                stars = len(st.find_all("i", class_="fas"))
            if cnt := body.find(class_="rating-mini-count") or body.find("div", class_="media-user-reviews"):
                reviews = _int(cnt.get_text())
        result.append(LotShort(
            id=lot_id,
            subcategory_id=subcategory_id,
            description=_text(a.find("div", class_="tc-desc-text")),
            price=price,
            currency=currency,
            amount=_int(_text(amount_div)),
            server=_text(a.find("div", class_="tc-server")),
            side=_text(a.find("div", class_="tc-side")),
            auto_delivery=a.get("data-auto") == "1" or a.find("i", class_="auto-dlv-icon") is not None,
            active="warning" not in classes,
            promoted="offer-promo" in classes,
            seller=seller,
            seller_rating=stars,
            seller_reviews=reviews,
            raw=str(a),
        ))
    return result


def parse_lot_fields(soup: BeautifulSoup, lot_id: int) -> LotFields:
    """Форма ``lots/offerEdit``: все input/textarea/select как словарь."""
    if (err := soup.find("p", class_="lead")) and not soup.find("form", class_="form-offer-editor"):
        raise ParseError(f"Лот {lot_id}: {err.get_text(strip=True)}")
    form = soup.find("form", class_="form-offer-editor")
    if form is None:
        raise ParseError(f"Форма лота {lot_id} не найдена")
    fields: dict[str, str] = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        if inp.get("type") == "checkbox":
            if inp.has_attr("checked"):
                fields[name] = "on"
            continue
        fields[name] = inp.get("value") or ""
    for ta in form.find_all("textarea"):
        if ta.get("name"):
            fields[ta["name"]] = ta.get_text()
    for sel in form.find_all("select"):
        if not sel.get("name"):
            continue
        group = sel.find_parent(class_="form-group")
        if group is not None and "hidden" in (group.get("class") or []):
            continue
        opt = sel.find("option", selected=True) or sel.find("option")
        if opt is not None:
            fields[sel["name"]] = opt.get("value", "")
    feedback = form.find("span", class_="form-control-feedback")
    currency = Currency.parse(feedback.get_text(strip=True) if feedback else None)
    return LotFields(lot_id=lot_id or int(fields.get("offer_id") or 0), fields=fields, currency=currency)


def parse_chips_fields(soup: BeautifulSoup, subcategory_id: int) -> ChipsFields:
    form = soup.find("form", class_="form-ajax-simple") or soup
    fields: dict[str, str] = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name or name == "query":
            continue
        if inp.get("type") == "checkbox":
            if inp.has_attr("checked"):
                fields[name] = "on"
            continue
        fields[name] = inp.get("value") or ""
    return ChipsFields(subcategory_id, fields)


def parse_calc(data: dict, price: float) -> PriceCalc:
    methods = {}
    for m in data.get("methods") or []:
        value, currency = parse_money(f"{m.get('price', '0')} {m.get('unit', '')}")
        methods[m.get("name", "")] = Money(value, currency)
    min_price = None
    if data.get("minPrice"):
        value, currency = parse_money(str(data["minPrice"]))
        min_price = Money(value, currency)
    return PriceCalc(price=price, methods=methods, min_price=min_price)


# ---------- заказы ----------

def _order_status(a: Tag) -> OrderStatus:
    classes = set(a.get("class") or [])
    status_div = a.find("div", class_="tc-status")
    classes |= set(status_div.get("class") or []) if status_div else set()
    if "warning" in classes or "text-warning" in classes:
        return OrderStatus.REFUNDED
    if "info" in classes or "text-primary" in classes:
        return OrderStatus.PAID
    return OrderStatus.CLOSED


def parse_order_previews(source: str | BeautifulSoup) -> tuple[list[OrderShort], str | None]:
    """Список продаж/покупок и курсор следующей страницы (``continue``)."""
    soup = soup_of(source)
    orders = []
    for a in soup.find_all("a", class_="tc-item"):
        order_div = a.find("div", class_="tc-order")
        if order_div is None:
            continue
        desc = a.find("div", class_="order-desc")
        title_div = desc.find("div") if desc else None
        user_span = a.find("div", class_="media-user-name")
        user_span = user_span.find(attrs={"data-href": True}) if user_span else None
        avatar = a.find("div", class_="avatar-photo")
        media = a.find("div", class_="media-user")
        price, currency = parse_money(_text(a.find("div", class_="tc-price")))
        date_text = _text(a.find("div", class_="tc-date-time")) or ""
        orders.append(OrderShort(
            id=order_div.get_text(strip=True).lstrip("#"),
            title=title_div.get_text(strip=True) if title_div else "",
            category_text=_text(a.find("div", class_="text-muted")) or "",
            status=_order_status(a),
            total=Money(price, currency),
            counterparty=UserShort(
                id=_user_id_from(user_span.get("data-href")) if user_span else 0,
                username=user_span.get_text(strip=True) if user_span else "",
                online="online" in (media.get("class") or []) if media else None,
                avatar_url=_css_url(avatar.get("style")) if avatar else None,
            ),
            date_text=date_text,
            date=parse_date(date_text),
            raw=str(a),
        ))
    return orders, _hidden_input(soup, "continue")


_ORDER_STATUS_JSON = {
    "unpaid": OrderStatus.UNPAID, "paid": OrderStatus.PAID, "closed": OrderStatus.CLOSED,
    "refunded": OrderStatus.REFUNDED, "partially_refunded": OrderStatus.PARTIALLY_REFUNDED,
}


def parse_order_json(data: dict) -> Order:
    """Заказ из ``api/orders/get``."""
    section = data.get("section") or {}
    buyer = data.get("buyer") or {}
    seller = data.get("seller") or {}
    type_data = data.get("type_data") or {}
    review = None
    if r := data.get("review"):
        if r.get("text") or r.get("rating") or r.get("reply"):
            review = Review(rating=r.get("rating"), text=r.get("text"), reply=r.get("reply"),
                            order_id=data.get("order_uid"), author_id=buyer.get("user_id"),
                            author_username=buyer.get("name"), hidden=bool(r.get("hidden")))
    amount = type_data.get("amount")
    return Order(
        id=data["order_uid"],
        status=_ORDER_STATUS_JSON.get(data.get("status", ""), OrderStatus.PAID),
        subcategory_id=section.get("local_id"),
        subcategory_type=(SubcategoryType.LOTS if section.get("type_id") == "lot" else SubcategoryType.CHIPS)
        if section else None,
        price=float(data.get("amount") or 0),
        currency=Currency.parse(data.get("currency")),
        amount=float(amount) if amount not in (None, "") else None,
        buyer=UserShort(int(buyer.get("user_id") or 0), buyer.get("name") or ""),
        seller=UserShort(int(seller.get("user_id") or 0), seller.get("name") or ""),
        chat_name=(data.get("chat") or {}).get("node_name"),
        fields={k: v.get("value") for k, v in (type_data.get("fields") or {}).items()},
        secrets=[s.get("value") for s in type_data.get("secrets") or []],
        review=review,
        raw=data,
    )


# ---------- отзывы, профиль ----------

def _parse_review_container(div: Tag) -> Review:
    rating = None
    if data_rating := div.get("data-rating"):
        rating = int(data_rating) if data_rating.isdigit() else None
    else:
        for i in range(1, 6):
            if div.find("div", class_=f"rating{i}"):
                rating = i
                break
    order_id = div.get("data-order")
    if order_a := div.find("div", class_="review-item-order"):
        if m := ORDER_ID_RE.search(order_a.get_text()):
            order_id = m.group(1)
    author_id = None
    author_username = None
    if row := div.find("div", attrs={"data-row": "review", "data-author": True}):
        author_id = int(row["data-author"])
    if name := div.find("div", class_="media-user-name"):
        author_username = name.get_text(strip=True)
        if a := name.find("a"):
            author_id = _user_id_from(a.get("href")) or author_id
    detail = _text(div.find("div", class_="review-item-detail"))
    category_text, total = None, None
    if detail:
        parts = detail.rsplit(", ", 1)
        if len(parts) == 2:
            category_text = parts[0]
            value, currency = parse_money(parts[1])
            total = Money(value, currency)
        else:
            category_text = detail
    reply = None
    if reply_div := div.find("div", class_="review-compiled-reply"):
        inner = reply_div.find("div", class_=False)
        reply = (inner or reply_div).get_text(strip=True) or None
    text_div = div.find("div", class_="review-item-text")
    return Review(
        rating=rating,
        text=text_div.get_text(strip=True) if text_div else None,
        reply=reply,
        order_id=order_id,
        author_id=author_id,
        author_username=author_username,
        date_text=_text(div.find("div", class_="review-item-date")),
        category_text=category_text,
        order_total=total,
        raw=str(div),
    )


def parse_reviews(source: str | BeautifulSoup) -> ReviewsPage:
    """Отзывы из ``users/reviews`` или с профиля, плюс курсор ``continue``."""
    soup = soup_of(source)
    reviews = [_parse_review_container(d) for d in soup.find_all("div", class_="review-container")]
    return ReviewsPage(reviews=reviews, next_cursor=_hidden_input(soup, "continue") or None)


def parse_rating(soup: BeautifulSoup | Tag) -> Rating | None:
    block = soup.find("div", class_="profile-header-col-rating") or soup.select_one("div.param-item.mb10")
    if block is None or not block.select_one("div.rating-value"):
        return None
    stars_text = _text(block.select_one("div.rating-value span.big"))
    try:
        stars = float(stars_text) if stars_text else None
    except ValueError:
        stars = None
    count_div = block.find("div", class_="rating-full-count") or block.find("div", class_="mb5")
    distribution = {}
    for i in range(1, 6):
        bar = block.select_one(f"div.rating-full-item{i} div.rating-progress > div")
        if bar is not None:
            m = re.search(r"([\d.]+)", bar.get("style", ""))
            distribution[i] = float(m.group(1)) if m else 0.0
    return Rating(stars=stars, reviews_count=_int(_text(count_div)) or 0, distribution=distribution)


def parse_profile(soup: BeautifulSoup, user_id: int) -> Profile:
    header = soup.find("div", class_="profile-header") or soup
    name = header.find("span", class_="mr4")
    if name is None:
        raise ParseError(f"Профиль {user_id} не найден")
    h1 = header.find("h1")
    status = header.find("span", class_="media-user-status")
    avatar = soup.find("div", class_="avatar-photo")
    banned = soup.find("span", class_="label-danger") is not None
    registration = None
    if isinstance(header, Tag) and (reg := header.find("div", class_="param-item")):
        strings = list(reg.stripped_strings)
        registration = strings[-2] if len(strings) >= 3 else (strings[-1] if strings else None)
    lots: list[LotShort] = []
    for offer in soup.find_all("div", class_="offer"):
        if not offer.find("a", class_="tc-item"):
            continue
        title = offer.find(class_="offer-list-title") or offer.find(class_="offer-list-title-container")
        link = title.find("a") if title else None
        href = link.get("href", "") if link else ""
        sid = _int(href.rstrip("/").rsplit("/", 1)[-1]) if href else None
        lots.extend(parse_lot_previews(offer, subcategory_id=sid, mine=True))
    online = bool(h1 and "online" in (h1.get("class") or [])) or bool(
        status and any(w in status.get_text().lower() for w in ("онлайн", "online")))
    return Profile(
        id=user_id,
        username=name.get_text(strip=True),
        online=online,
        banned=banned,
        avatar_url=_css_url(avatar.get("style")) if avatar else None,
        status_text=status.get_text(strip=True) if status else None,
        registration_text=registration,
        rating=parse_rating(soup),
        lots=lots,
        raw=str(soup),
    )


# ---------- финансы ----------

def parse_balance(soup: BeautifulSoup) -> Balance:
    """Баланс со страницы ``account/balance``."""
    total: dict[Currency, float] = {}
    for span in soup.find_all("span", class_="balances-value")[:3]:
        value, currency = parse_money(span.get_text(" ", strip=True))
        if currency is not Currency.UNKNOWN:
            total[currency] = value
    available: dict[Currency, float] = {}
    if sel := soup.find("select", {"name": "method"}):
        for cur in (Currency.RUB, Currency.USD, Currency.EUR):
            if (v := sel.get(f"data-balance-{cur.code}")) is not None:
                available[cur] = float(v)
            if (v := sel.get(f"data-balance-total-{cur.code}")) is not None:
                total.setdefault(cur, float(v))
    return Balance(total=total, available=available or dict(total))


def parse_transactions(source: str | BeautifulSoup) -> tuple[list[Transaction], str | None]:
    soup = soup_of(source)
    result = []
    for div in soup.find_all("div", class_="tc-item"):
        tid = div.get("data-transaction")
        if not tid:
            continue
        classes = " ".join(div.get("class") or [])
        status = TransactionStatus.UNKNOWN
        for s in (TransactionStatus.COMPLETED, TransactionStatus.PENDING, TransactionStatus.CANCELLED):
            if f"transaction-status-{s.value}" in classes:
                status = s
        desc = _text(div.find("span", class_="tc-title")) or ""
        value, currency = parse_money(_text(div.find("div", class_="tc-price")))
        date_text = _text(div.find(class_="tc-date-time")) or ""
        m = ORDER_ID_RE.search(desc)
        result.append(Transaction(
            id=int(tid), date_text=date_text, date=parse_date(date_text), description=desc,
            status=status, amount=Money(value, currency), order_id=m.group(1) if m else None, raw=str(div),
        ))
    return result, _hidden_input(soup, "continue") or None


def parse_wallets(soup: BeautifulSoup) -> list[Wallet]:
    form = soup.find("form", class_="details-editor")
    if form is None:
        return []
    result = []
    for group in form.find_all("div", class_="form-group"):
        n = group.get("data-n")
        if n is None:
            continue
        detail = group.find("input", {"name": f"details[{n}][detail_id]"})
        if not detail or not int(detail.get("value") or 0):
            continue
        masked = group.find("input", {"name": f"details[{n}][is_masked]"})
        data = group.find("input", {"name": f"details[{n}][data]"})
        sel = group.find("select", {"name": f"details[{n}][type_id]"})
        opt = sel.find("option", selected=True) if sel else None
        result.append(Wallet(
            index=int(n), detail_id=int(detail["value"]),
            type_id=opt.get("value", "") if opt else "", type_name=opt.get_text(strip=True) if opt else "",
            data=data.get("value", "") if data else "", masked=bool(int(masked.get("value") or 0)) if masked else False,
        ))
    return result


def unescape_json_attr(value: str) -> Any:
    return json.loads(html_lib.unescape(value))
