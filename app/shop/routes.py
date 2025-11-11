# app/shop/routes.py

from decimal import Decimal

import stripe
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app,
)
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models import (
    Product,
    Category,
    Comment,
    Slider,
    SliderItem,
    Order,
    OrderItem,
)
from .forms import CommentForm, CheckoutForm


# Uwaga: blueprint jest importowany w app/shop/__init__.py
# jako: from .routes import shop_bp
shop_bp = Blueprint("shop", __name__, template_folder="templates")


# ============================================================
#  DASHBOARD SKLEPU (widok kafelków, kategorie + produkty)
# ============================================================

@shop_bp.route("/sklep")
def shop_dashboard():
    # kategorie
    try:
        categories = Category.query.order_by(Category.name).all()
    except OperationalError:
        categories = []

    # wszystkie produkty
    try:
        products = Product.query.order_by(Product.id.desc()).all()
    except OperationalError:
        products = []

    # ikonki dla wybranych kategorii (reszta ma kółko)
    category_icons = {
        "Zaprawki, esencje, aromaty": "bi-magic",
        "Gorzelnictwo": "bi-droplet-half",
        "Piwowarstwo": "bi-cup-straw",
        "Winiarstwo": "bi-cup-straw",
        "Akcesoria": "bi-tools",
        "Opakowania szklane": "bi-bottle",
        "Opakowania ozdobne": "bi-gift",
        "Dezynfekcja, klarowanie, enzymy": "bi-beaker",
        "Etykiety": "bi-tag",
        "Wędliniarstwo": "bi-pepper-hot",
        "Piekarnictwo": "bi-egg-fried",
        "Serowarstwo": "bi-basket3",
        "Destylatory i alembiki": "bi-gear-wide-connected",
        "Przyprawy": "bi-cup-straw",
        "Kuchnia": "bi-house-door",
        "Cukrówki": "bi-cup-straw",
        "Zbożowe": "bi-bag-fill",
        "Kukurydza": "bi-bag",
        "Pszenica": "bi-basket",
        "Żyto": "bi-basket2",
    }

    return render_template(
        "shop/dashboard.html",
        categories=categories,
        products=products,
        category_icons=category_icons,
    )


# ============================================================
#  STRONA GŁÓWNA SKLEPU
# ============================================================

@shop_bp.route("/")
def index():
    # ---------- SLIDER ----------
    slider = None
    slider_items = []
    try:
        slider = Slider.query.filter_by(is_active=True).first()
        if slider:
            slider_items = (
                SliderItem.query.filter_by(slider_id=slider.id)
                .order_by(SliderItem.order_index)
                .all()
            )
    except OperationalError:
        slider = None
        slider_items = []

    # ---------- KATEGORIE ----------
    try:
        categories = Category.query.order_by(Category.name).all()
    except OperationalError:
        categories = []

    # ---------- PRODUKTY: nowości / "bestsellery" ----------
    try:
        newest_products = Product.query.order_by(Product.id.desc()).limit(8).all()
        featured_products = Product.query.order_by(Product.id.asc()).limit(8).all()
    except OperationalError:
        newest_products = []
        featured_products = []

    return render_template(
        "shop/index.html",
        slider=slider,
        slider_items=slider_items,
        categories=categories,
        newest_products=newest_products,
        featured_products=featured_products,
    )


# ============================================================
#  KATEGORIA
# ============================================================

@shop_bp.route("/category/<int:category_id>/")
def category_view(category_id):
    # jak nie ma tabeli kategorii / produktów, wyświetlamy pustą kategorię
    try:
        category = Category.query.get_or_404(category_id)
    except OperationalError:
        category = None

    if category is None:
        products = []
        categories = []
    else:
        try:
            products = (
                Product.query.filter_by(category_id=category.id)
                .order_by(Product.name)
                .all()
            )
        except OperationalError:
            products = []

        try:
            categories = Category.query.order_by(Category.name).all()
        except OperationalError:
            categories = []

    return render_template(
        "shop/category.html",
        category=category,
        products=products,
        categories=categories,
    )


# ============================================================
#  SZCZEGÓŁ PRODUKTU + KOMENTARZE
# ============================================================

@shop_bp.route("/product/<int:product_id>", methods=["GET", "POST"])
def product_detail(product_id):
    try:
        product = Product.query.get_or_404(product_id)
    except OperationalError:
        # jak nie ma tabeli products – zwracamy 404
        return render_template("shop/product_detail.html", product=None), 404

    form = CommentForm()

    # Dodawanie komentarza
    if current_user.is_authenticated and form.validate_on_submit():
        comment = Comment(
            content=form.content.data,
            user_id=current_user.id,
            product_id=product.id,
        )
        db.session.add(comment)
        db.session.commit()
        flash("Komentarz dodany i oczekuje na akceptację moderatora.", "info")
        return redirect(url_for("shop.product_detail", product_id=product.id))

    # Widoczne komentarze:
    # - zaakceptowane każdego
    # - ORAZ wszystkie komentarze zalogowanego usera (w tym oczekujące)
    try:
        if current_user.is_authenticated:
            comments = (
                Comment.query.filter(
                    Comment.product_id == product.id,
                    or_(
                        Comment.status == "zaakceptowany",
                        Comment.user_id == current_user.id,
                    ),
                )
                .order_by(Comment.created_at.desc())
                .all()
            )
        else:
            comments = (
                Comment.query.filter_by(
                    product_id=product.id, status="zaakceptowany"
                )
                .order_by(Comment.created_at.desc())
                .all()
            )
    except OperationalError:
        comments = []

    # Podobne produkty (ta sama kategoria)
    try:
        similar_products = (
            Product.query.filter(
                Product.category_id == product.category_id,
                Product.id != product.id,
            )
            .limit(4)
            .all()
        )
    except OperationalError:
        similar_products = []

    return render_template(
        "shop/product_detail.html",
        product=product,
        form=form,
        comments=comments,
        similar_products=similar_products,
    )


# ============================================================
#  KOSZYK
# ============================================================

@shop_bp.route("/cart")
def cart_view():
    cart = session.get("cart", {})
    if not cart:
        return render_template("shop/cart.html", cart_items=[], total=Decimal("0.00"))

    product_ids = [int(pid) for pid in cart.keys()]
    try:
        products = Product.query.filter(Product.id.in_(product_ids)).all()
    except OperationalError:
        products = []

    cart_items = []
    total = Decimal("0.00")

    for prod in products:
        qty = int(cart.get(str(prod.id), 0))
        item_total = Decimal(str(prod.price)) * qty
        total += item_total
        cart_items.append((prod, qty, item_total))

    return render_template("shop/cart.html", cart_items=cart_items, total=total)


@shop_bp.route("/add_to_cart/<int:product_id>", methods=["GET", "POST"])
def add_to_cart(product_id):
    """
    Dodaje produkt do koszyka.

    - jeśli wywołane metodą POST z formularza (np. strona produktu),
      próbuje wziąć ilość z pola `quantity`
    - jeśli GET (np. przycisk z listy produktów), dodaje 1 sztukę
    """
    try:
        product = Product.query.get_or_404(product_id)
    except OperationalError:
        flash("Produkt niedostępny.", "warning")
        return redirect(request.referrer or url_for("shop.index"))

    cart = session.get("cart", {})
    key = str(product_id)

    if request.method == "POST":
        try:
            quantity = int(request.form.get("quantity", 1))
        except (TypeError, ValueError):
            quantity = 1
        if quantity < 1:
            quantity = 1
    else:
        quantity = 1

    cart[key] = cart.get(key, 0) + quantity
    session["cart"] = cart

    flash(f'Dodano "{product.name}" do koszyka (łącznie: {cart[key]}).', "success")
    return redirect(request.referrer or url_for("shop.product_detail", product_id=product.id))


@shop_bp.route("/remove_from_cart/<int:product_id>")
def remove_from_cart(product_id):
    cart = session.get("cart", {})
    key = str(product_id)
    if key in cart:
        cart.pop(key)
        session["cart"] = cart
        flash("Produkt został usunięty z koszyka.", "info")
    return redirect(url_for("shop.cart_view"))


# ============================================================
#  CHECKOUT / PŁATNOŚĆ
# ============================================================

@shop_bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart = session.get("cart", {})
    if not cart:
        flash("Koszyk jest pusty.", "warning")
        return redirect(url_for("shop.index"))

    form = CheckoutForm()
    if form.validate_on_submit():
        try:
            order = Order(
                user_id=current_user.id,
                status="oczekuje",
                shipping_address=form.address.data,
            )
            db.session.add(order)
            db.session.flush()

            total_amount = Decimal("0.00")
            for pid_str, qty in cart.items():
                product = Product.query.get(int(pid_str))
                if not product:
                    continue
                item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=qty,
                    price_at_order=product.price,
                )
                db.session.add(item)
                total_amount += Decimal(str(product.price)) * qty

            db.session.commit()
        except OperationalError:
            db.session.rollback()
            flash("Błąd bazy danych przy tworzeniu zamówienia.", "danger")
            return redirect(url_for("shop.cart_view"))

        session["cart"] = {}
        flash(
            f"Zamówienie {order.id} zostało utworzone. Przejdź do płatności.",
            "success",
        )
        return redirect(url_for("shop.payment", order_id=order.id))

    return render_template("shop/checkout.html", form=form)


@shop_bp.route("/payment/<int:order_id>")
@login_required
def payment(order_id):
    try:
        order = Order.query.get_or_404(order_id)
    except OperationalError:
        flash("Zamówienie nie istnieje.", "danger")
        return redirect(url_for("shop.index"))

    if order.user_id != current_user.id:
        flash("To nie jest Twoje zamówienie.", "danger")
        return redirect(url_for("shop.index"))

    line_items = []
    for item in order.items:
        line_items.append(
            {
                "price_data": {
                    "currency": "pln",
                    "product_data": {"name": item.product.name},
                    "unit_amount": int(Decimal(str(item.price_at_order)) * 100),
                },
                "quantity": item.quantity,
            }
        )

    try:
        stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            customer_email=current_user.email,
            success_url=url_for(
                "shop.payment_success", order_id=order.id, _external=True
            )
            + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=url_for(
                "shop.payment_cancel", order_id=order.id, _external=True
            ),
            metadata={"order_id": order.id},
        )
    except Exception as e:  # noqa: BLE001
        current_app.logger.error(f"Stripe error: {e}")
        flash("Błąd łączenia z bramką płatności.", "danger")
        return redirect(url_for("shop.cart_view"))

    return redirect(checkout_session.url, code=303)


@shop_bp.route("/payment/success/<int:order_id>")
@login_required
def payment_success(order_id):
    try:
        order = Order.query.get_or_404(order_id)
    except OperationalError:
        flash("Zamówienie nie istnieje.", "danger")
        return redirect(url_for("shop.index"))

    if order.user_id != current_user.id:
        flash("To nie jest Twoje zamówienie.", "danger")
        return redirect(url_for("shop.index"))

    return render
