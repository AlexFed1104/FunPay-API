"""Образцы HTML FunPay для тестов.

Большая часть взята из тестов funpayparsers (https://github.com/funpayhub/funpayparsers, MIT),
главная страница собрана по селекторам FunPayCardinal.
"""

MAIN_PAGE = """<html><body data-app-data='{"locale":"ru","csrf-token":"csrf123","userId":1000}'>
<header>
  <div class="user-link-name">MySeller</div>
  <span class="badge badge-balance">1 234 ₽</span>
  <span class="badge badge-trade">3</span>
  <span class="badge badge-orders">1</span>
  <a class="menu-item-logout" href="https://funpay.com/account/logout?token=x">Выйти</a>
</header>
<div class="promo-game-list">
  <div class="promo-game-item">
    <div class="game-title" data-id="41"><a href="https://funpay.com/lots/81/">Dota 2</a></div>
    <ul class="list-inline" data-id="41">
      <li><a href="https://funpay.com/lots/81/">Предметы</a></li>
      <li><a href="https://funpay.com/chips/82/">Золото</a></li>
    </ul>
  </div>
</div>
</body></html>"""

CHAT_PREVIEWS = """
<a href="https://funpay.com/chat/?node=555" class="contact-item unread" data-id="555" data-node-msg="9002" data-user-msg="9000">
  <div class="contact-item-photo"><div class="avatar-photo" style="background-image: url(https://sfunpay.com/a.jpg);"></div></div>
  <div class="media-user-name">Buyer1</div>
  <div class="contact-item-message">Привет, есть в наличии?</div>
  <div class="contact-item-time">12:30</div>
</a>
<a href="https://funpay.com/chat/?node=556" class="contact-item" data-id="556" data-node-msg="8000" data-user-msg="8000">
  <div class="contact-item-photo"><div class="avatar-photo" style="background-image: url(/img/layout/avatar.png);"></div></div>
  <div class="media-user-name">Buyer2</div>
  <div class="contact-item-message">⁡Спасибо за покупку!</div>
  <div class="contact-item-time">вчера</div>
</a>
"""

MESSAGE_HEADING = """<div class="chat-msg-item chat-msg-with-head" id="message-12345">
    <div class="chat-message">
        <div class="media-user-name">
            <a href="https://funpay.com/users/54321/" class="chat-msg-author-link">Username</a>
            <div class="chat-msg-date" title="26 мая, 11:21:41">11:21:41</div>
        </div>
        <div class="chat-msg-body">
            <div class="chat-msg-text">MessageText</div>
        </div>
    </div>
</div>"""

MESSAGE_PLAIN = """<div class="chat-msg-item" id="message-12346">
    <div class="chat-message">
        <div class="chat-msg-body">
            <div class="chat-msg-text">Second</div>
        </div>
    </div>
</div>"""

MESSAGE_REFUND = """<div class="chat-msg-item chat-msg-with-head" id="message-12347">
    <div class="chat-message">
        <div class="media-user-name">
            FunPay <span class="chat-msg-author-label label label-primary">оповещение</span>
            <div class="chat-msg-date" title="4 мая, 10:41:16">04.05.2025</div>
        </div>
        <div class="chat-msg-body">
            <div class="alert alert-with-icon alert-info" role="alert">
                <i class="fas fa-info-circle alert-icon"></i>
                <div class="chat-msg-text">Продавец <a href="https://funpay.com/users/10/">SellerUsername</a> вернул деньги покупателю <a href="https://funpay.com/users/54321/">BuyerUsername</a> по <a href="https://funpay.com/orders/AAAAAAAA/">заказу #AAAAAAAA</a>.</div>
            </div>
        </div>
    </div>
</div>"""

MESSAGE_IMAGE = """<div class="chat-msg-item chat-msg-with-head" id="message-12348">
    <div class="chat-message">
        <div class="media-user-name">
            <a href="https://funpay.com/users/54321/" class="chat-msg-author-link">Username</a>
            <div class="chat-msg-date" title="26 мая, 11:25:00">11:25:00</div>
        </div>
        <div class="chat-msg-body">
            <a class="chat-img-link" href="https://sfunpay.com/s/chat/img.jpg"><img src="https://sfunpay.com/s/chat/img_t.jpg" alt="img.jpg"></a>
        </div>
    </div>
</div>"""


def order_html(order_id: str, status_cls: str, row_cls: str, price: str, date: str = "сегодня, 13:33",
               buyer_id: int = 123456, buyer: str = "BuyerName", category: str = "Dota 2, Предметы",
               title: str = "Arcana") -> str:
    return f"""
<a href="https://funpay.com/orders/{order_id}/" class="tc-item {row_cls}">
    <div class="tc-date">
        <div class="tc-date-time">{date}</div>
        <div class="tc-date-left">22 часа назад</div>
    </div>
    <div class="tc-order">#{order_id}</div>
    <div class="order-desc">
        <div>{title}</div>
        <div class="text-muted">{category}</div>
    </div>
    <div class="tc-user">
        <div class="media media-user offline">
            <div class="media-left">
                <div class="avatar-photo pseudo-a" tabindex="0" data-href="https://funpay.com/users/{buyer_id}/" style="background-image: url(path/to/avatar);"></div>
            </div>
            <div class="media-body">
                <div class="media-user-name">
                    <span class="pseudo-a" tabindex="0" data-href="https://funpay.com/users/{buyer_id}/">{buyer}</span>
                </div>
                <div class="media-user-status">был 1 час назад</div>
            </div>
        </div>
    </div>
    <div class="tc-status {status_cls}">Статус</div>
    <div class="tc-price text-nowrap tc-buyer-sum">{price} <span class="unit">₽</span></div>
</a>"""


SALES_PAGE_1 = ("""<html><body data-app-data='{"locale":"ru","csrf-token":"csrf123","userId":1000}'>
<div class="user-link-name">MySeller</div><h1 class="page-header page-header-no-hr">Мои продажи</h1>"""
                + order_html("AAAAAAA1", "text-primary", "info", "100", "сегодня, 13:33", buyer="Ann", buyer_id=1)
                + order_html("AAAAAAA2", "text-success", "", "1 250.50", "вчера, 10:00", buyer="Bob", buyer_id=2,
                             title="Immortal")
                + """<input type="hidden" name="continue" value="AAAAAAA3"></body></html>""")

SALES_PAGE_2 = (order_html("AAAAAAA3", "text-warning", "warning", "300", "5 января 2024, 12:00", buyer="Ann",
                           buyer_id=1, category="CS2, Скины", title="Knife")
                + order_html("AAAAAAA4", "text-success", "", "200", "4 января 2024, 12:00", buyer="Cid", buyer_id=3,
                             category="CS2, Скины", title="Knife"))

REVIEWS_PUBLIC = """
<div class="review-container">
  <div class="review-item">
    <div class="review-item-row">
      <div class="review-compiled-review">
        <div class="review-item-user">
          <div class="review-item-photo"><img src="/img/layout/avatar.png" alt=""></div>
          <div class="review-item-rating pull-right hidden-xs"><div class="rating"><div class="rating5"></div></div></div>
          <div class="review-item-date">2 месяца назад</div>
          <div class="review-item-detail">Game, 100 ₽</div>
        </div>
        <div class="review-item-text"> ReviewText </div>
      </div>
    </div>
    <div class="review-item-row">
      <div class="h5 mb5">Ответ продавца</div>
      <div class="review-item-answer review-compiled-reply"><div>ReviewReply</div></div>
    </div>
  </div>
</div>
<div class="review-container">
  <div class="review-item">
    <div class="review-item-row">
      <div class="review-compiled-review">
        <div class="review-item-user">
          <div class="review-item-photo"><a href="https://funpay.com/users/54321/"><img src="/img/layout/avatar.png" alt=""></a></div>
          <div class="review-item-rating pull-right hidden-xs"><div class="rating"><div class="rating3"></div></div></div>
          <div class="media-user-name"><a href="https://funpay.com/users/54321/">SenderUername</a></div>
          <div class="review-item-order"><a href="https://funpay.com/orders/ABCDEFGH/">Заказ #ABCDEFGH</a></div>
          <div class="review-item-date">20 января в 12:58, 3 месяца назад</div>
          <div class="review-item-detail">Dota 2, Предметы, 50 ₽</div>
        </div>
        <div class="review-item-text"> Норм </div>
      </div>
    </div>
  </div>
</div>
<input type="hidden" name="user_id" value="12345">
<input type="hidden" name="continue" value="=nextid">
<input type="hidden" name="filter" value="">
"""

REVIEW_ORDER_PAGE = """
<div class="review-container" data-order="ABCDEFGH" data-rating="1" data-rating-max="5">
  <div class="review-item">
    <div class="review-item-row" data-row="review" data-author="54321">
      <div class="review-compiled-review">
        <div class="review-item-user">
          <div class="review-item-photo"><a href="https://funpay.com/users/54321/"><img src="/img/layout/avatar.png" alt=""></a></div>
          <div class="review-item-date">2 месяца назад</div>
          <div class="review-item-detail">Game, 500 $</div>
        </div>
        <div class="review-item-text"> ReviewText </div>
      </div>
    </div>
    <div class="review-item-row" data-row="reply" data-author="12345">
      <div class="h5 mb5">Ответ продавца</div>
      <div class="review-item-answer review-compiled-reply">
        <div>ReviewReply</div>
        <div class="review-controls"><button class="btn btn-primary btn-sm action" data-action="edit">Редактировать</button></div>
      </div>
    </div>
  </div>
</div>
"""

TRANSACTIONS = """
<div class="tc-item transaction-status-complete" data-transaction="12345">
  <div class="tc-date"><span class="tc-date-time">20 января 2024, 23:11 </span><span class="tc-date-left">год назад</span></div>
  <div class="tc-desc"><span class="tc-title">Заказ #ABCDEFGH</span></div>
  <div class="tc-status transaction-status">Завершено</div>
  <div class="tc-price">+ 1.23 <span class="unit">₽</span></div>
</div>
<div class="tc-item transaction-status-cancel" data-transaction="12344">
  <div class="tc-date"><span class="tc-date-time">20 января 2024, 23:11 </span></div>
  <div class="tc-desc"><span class="tc-title">Вывод денег #54321</span></div>
  <div class="tc-status transaction-status">Отменено</div>
  <div class="tc-price">− 1234.56 <span class="unit">₽</span></div>
</div>
<form method="post" class="dyn-table-form" action="https://funpay.com/users/transactions">
    <input type="hidden" name="user_id" value="12345">
    <input type="hidden" name="continue" value="101010">
    <input type="hidden" name="filter" value="">
</form>
"""

LOT_PREVIEW = """<a href="https://funpay.com/lots/offer?id=12345" class="tc-item offer-promo offer-promoted"
    data-online="1" data-auto="1" data-user="54321">
  <div class="tc-desc"><div class="tc-desc-text">Lot Description</div></div>
  <div class="tc-user">
    <div class="media media-user online style-circle">
      <div class="media-body">
        <div class="media-user-name"><span class="pseudo-a" tabindex="0" data-href="https://funpay.com/users/54321/">SellerUsername</span></div>
        <div class="media-user-reviews">
          <div class="rating-stars rating-5"><i class="fas"></i><i class="fas"></i><i class="fas"></i><i class="fas"></i><i class="fas"></i></div>
          <span class="rating-mini-count">105</span>
        </div>
      </div>
    </div>
  </div>
  <div class="tc-amount hidden-xxs">1</div>
  <div class="tc-price" data-s="3499.796334"><div>3500 <span class="unit">₽</span></div></div>
</a>"""

PROFILE = """
<html>
<head><link rel="canonical" href="https://funpay.com/users/1234/"/></head>
<body data-app-data='{"locale": "ru", "csrf-token": "tok", "userId": 1000}'>
<div class="user-link-name">MySeller</div>
<div class="profile-header">
  <h1 class="mb40 online"><span class="mr4">SomeSeller</span></h1>
  <div class="avatar-photo" style="background-image: url(/img/a.jpg);"></div>
  <span class="media-user-status">Online</span>
  <div class="param-item">
    <div>Registered</div>
    <div>15 August 2015, 18:01</div>
    <div>10 years ago</div>
  </div>
</div>
<div class="param-item mb10">
  <div class="rating-value"><span class="big">4.9</span></div>
  <div class="mb5">1049 reviews</div>
  <div class="rating-full-item1"><div class="rating-progress"><div style="width: 1%"></div></div></div>
  <div class="rating-full-item2"><div class="rating-progress"><div style="width: 2%"></div></div></div>
  <div class="rating-full-item3"><div class="rating-progress"><div style="width: 3%"></div></div></div>
  <div class="rating-full-item4"><div class="rating-progress"><div style="width: 4%"></div></div></div>
  <div class="rating-full-item5"><div class="rating-progress"><div style="width: 90%"></div></div></div>
</div>
<div class="mb20">
  <div class="offer">
    <div class="offer-list-title"><a href="https://funpay.com/lots/81/"></a></div>
    <a href="https://funpay.com/lots/offer?id=12345" class="tc-item" data-online="1" data-auto="1" data-user="1234">
      <div class="tc-desc"><div class="tc-desc-text">Lot Description</div></div>
      <div class="tc-amount hidden-xxs">1</div>
      <div class="tc-price" data-s="3499.79"><div>3500 <span class="unit">₽</span></div></div>
    </a>
  </div>
</div>
</body>
</html>
"""

LOT_EDIT = """<html><body data-app-data='{"locale":"ru","csrf-token":"csrf123","userId":1000}'>
<form class="form-offer-editor" data-offer="{&quot;amount&quot;:5}">
  <input type="hidden" name="csrf_token" value="csrf123">
  <input type="hidden" name="offer_id" value="777">
  <input type="hidden" name="node_id" value="81">
  <input type="text" name="fields[summary][ru]" value="Старое название">
  <input type="text" name="fields[summary][en]" value="Old title">
  <textarea name="fields[desc][ru]">Описание</textarea>
  <textarea name="secrets">key1
key2</textarea>
  <input type="text" name="price" value="100">
  <input type="text" name="amount" value="5">
  <input type="checkbox" name="active" checked>
  <input type="checkbox" name="auto_delivery">
  <div class="form-group"><select name="fields[type]"><option value="1">A</option><option value="2" selected>B</option></select></div>
  <div class="form-group hidden"><select name="fields[hidden]"><option value="9" selected>H</option></select></div>
  <span class="form-control-feedback">₽</span>
</form>
</body></html>"""
