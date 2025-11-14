# app/shop/routes.py
from __future__ import annotations

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
from sqlalchemy.exc import OperationalError
from sqlalchemy import or_

from . import shop_bp
from .forms import CommentForm, CheckoutForm
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

# =========================
# Helpers – CART
# =========================


def _ensure_cart_item_dict(pid: int, value) -> dict:
    """
    Gwarantuje format:
      {"product_id": int, "name": str, "price": float, "quantity": int}
    - jeżeli był stary format (liczba), migruje
    - jeżeli był słownik ale bez kluczy, uzupełnia
    """
    if isinstance(value, int):
        qty = int(value)
        p = Product.query.get(pid)
        return {
            "product_id": pid,
            "name": (p.name if p else ""),
            "price": float(p.price or 0) if p else 0.0,
            "quantity": max(0, qty),
        }

    if isinstance(value, dict):
        # uzupełnij brakujące pola
        out = dict(value)
        out.setdefault("product_id", pid)
        out.setdefault("name", "")
        out.setdefault("price", 0.0)
        out.setdefault("quantity", 0)
        # sanity
        try:
            out["quantity"] = int(out["quantity"])
        except Exception:
            out["quantity"] = 0
        try:
            out["price"] = float(out["price"])
        except Exception:
            out["price"] = 0.0

        # dociągnij nazwę i cenę z bazy jeśli puste
        try:
            p = Product.query.get(pid)
        except OperationalError:
            p = None

        if p:
            if not out["name"]:
                out["name"] = p.name or ""
            if out["price"] <= 0:
                try:
                    out["price"] = float(p.price or 0)
                except Exception:
                    out["price"] = 0.0
        return out

    # nieznany format -> zresetuj bezpiecznie
    p = Product.query.get(pid)
    return {
        "product_id": pid,
        "name": (p.name if p else ""),
        "price": float(p.price or 0) if p else 0.0,
        "quantity": 0,
    }


def _get_cart() -> dict[str, dict]:
    """
    Zwraca koszyk w nowym formacie:
      { "product_id": {"product_id":..., "name":..., "price":..., "quantity":...}, ... }
    """
    raw = session.get("cart", {})
    if not isinstance(raw, dict):
        raw = {}

    migrated: dict[str, dict] = {}
    for pid_str, val in raw.items():
        try:
            pid = int(pid_str)
        except (TypeError, ValueError):
            continue
        migrated[str(pid)] = _ensure_cart_item_dict(pid, val)

    # zapisz z powrotem już znormalizowany koszyk
    session["cart"] = migrated
    session.modified = True
    return migrated


def _save_cart(cart: dict[str, dict]) -> None:
    """Zapisuje koszyk w sesji."""
    session["cart"] = cart
    session.modified = True


def _cart_totals(cart: dict[str, dict]) -> tuple[Decimal, int]:
    """Liczy łączną kwotę i ilość sztuk w koszyku."""
    total = Decimal("0.00")
    count = 0
    for item in cart.values():
        try:
            price = Decimal(str(item.get("price", 0)))
            qty = int(item.get("quantity", 0))
        except Exception:
            continue
        if qty <= 0:
            continue
        total += price * qty
        count += qty
    return total, count


# =========================
# Główna strona sklepu
# =========================


@shop_bp.route("/")
def index():
    """Strona główna sklepu.

    - Na górze: slider z aktywnego Slidera (jeśli istnieje).
    - Prawa kolumna: kategorie + wyszukiwarka.
    - Poniżej: siatka produktów z paginacją i szybkim „Do koszyka”.
    """
    # --- Slider: aktywny slider + jego elementy (relacja .items załatwia kolejność) ---
    try:
        active_slider = Slider.query.filter_by(is_active=True).first()
    except OperationalError:
        # Brak migracji / tabela nie istnieje – strona ma dalej działać
        active_slider = None

    # --- Kategorie do prawej kolumny ---
    try:
        categories = Category.query.order_by(Category.name).all()
    except OperationalError:
        categories = []

    # --- Filtry: kategoria + wyszukiwarka ---
    page = request.args.get("page", 1, type=int)
    q = request.args.get("q", "", type=str).strip()
    current_category_id = request.args.get("cat", type=int)

    # --- Produkty: bazowe zapytanie + filtry ---
    products_pagination = None
    try:
        query = Product.query

        if current_category_id:
            query = query.filter(Product.category_id == current_category_id)

        if q:
            like = f"%{q}%"
            # wyszukiwanie po nazwie i opisie HTML (bezpieczne ilike)
            query = query.filter(
                or_(
                    Product.name.ilike(like),
                    Product.description_html.ilike(like),
                )
            )

        products_pagination = query.order_by(Product.id.desc()).paginate(
            page=page,
            per_page=12,
            error_out=False,
        )
    except OperationalError:
        # jeśli tabela products nie istnieje albo są problemy z migracją
        products_pagination = None

    return render_template(
        "shop/index.html",
        active_slider=active_slider,
        categories=categories,
        products=products_pagination,
        current_category_id=current_category_id,
        q=q,
    )


# =========================
# Kategorie (stary widok – nadal działa)
# =========================


@shop_bp.route("/category/<int:category_id>/")
def category_view(category_id: int):
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
                .order_by(Product.id.desc())
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


# =========================
# Szczegóły produktu + komentarze
# =========================


@shop_bp.route("/product/<int:product_id>/", methods=["GET", "POST"])
def product_detail(product_id: int):
    try:
        product = Product.query.get_or_404(product_id)
    except OperationalError:
        flash("Produkt nie istnieje lub baza jest niedostępna.", "danger")
        return redirect(url_for("shop.index"))

    form = CommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("Zaloguj się, aby dodać komentarz.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        try:
            comment = Comment(
                content=form.content.data,
                product_id=product.id,
                user_id=current_user.id,
            )
            db.session.add(comment)
            db.session.commit()
            flash("Dziękujemy za opinię – pojawi się po moderacji.", "success")
        except OperationalError:
            db.session.rollback()
            flash("Nie udało się dodać komentarza.", "danger")
        return redirect(url_for("shop.product_detail", product_id=product.id))

    # komentarze zaakceptowane
    try:
        comments = (
            Comment.query.filter_by(product_id=product.id, status="zaakceptowany")
            .order_by(Comment.created_at.desc())
            .all()
        )
    except OperationalError:
        comments = []

    return render_template(
        "shop/product_detail.html",
        product=product,
        comments=comments,
        form=form,
    )



# =========================
# Koszyk
# =========================


@shop_bp.route("/cart/")
def cart_view():
    cart = _get_cart()
    total, count = _cart_totals(cart)
    return render_template(
        "shop/cart.html",
        cart=cart,
        total=total,
        count=count,
    )


@shop_bp.route("/cart/add/<int:product_id>/", methods=["POST"])
def add_to_cart(product_id: int):
    cart = _get_cart()

    # normalizacja product_id jako string (klucz słownika)
    key = str(product_id)
    item = cart.get(key, None)
    item = _ensure_cart_item_dict(product_id, item or 0)

    # ilość z formularza (domyślnie 1)
    try:
        qty_delta = int(request.form.get("quantity", 1))
    except (TypeError, ValueError):
        qty_delta = 1

    item["quantity"] = max(0, item.get("quantity", 0) + qty_delta)
    cart[key] = item
    _save_cart(cart)

    flash("Produkt został dodany do koszyka.", "success")
    return redirect(request.referrer or url_for("shop.cart_view"))


@shop_bp.route("/cart/update/<int:product_id>/", methods=["POST"])
def update_cart_item(product_id: int):
    cart = _get_cart()
    key = str(product_id)
    if key not in cart:
        return redirect(url_for("shop.cart_view"))

    try:
        new_qty = int(request.form.get("quantity", 1))
    except (TypeError, ValueError):
        new_qty = 1

    if new_qty <= 0:
        cart.pop(key, None)
    else:
        cart[key]["quantity"] = new_qty

    _save_cart(cart)
    return redirect(url_for("shop.cart_view"))


@shop_bp.route("/cart/remove/<int:product_id>/", methods=["POST"])
def remove_from_cart(product_id: int):
    cart = _get_cart()
    key = str(product_id)
    cart.pop(key, None)
    _save_cart(cart)
    flash("Produkt został usunięty z koszyka.", "info")
    return redirect(url_for("shop.cart_view"))


@shop_bp.route("/cart/clear/", methods=["POST"])
def clear_cart():
    _save_cart({})
    flash("Koszyk został wyczyszczony.", "info")
    return redirect(url_for("shop.cart_view"))


# =========================
# Checkout / zamówienie
# =========================


@shop_bp.route("/checkout/", methods=["GET", "POST"])
@login_required
def checkout():
    cart = _get_cart()
    total, count = _cart_totals(cart)
    if count == 0:
        flash("Twój koszyk jest pusty.", "warning")
        return redirect(url_for("shop.cart_view"))

    form = CheckoutForm()
    if form.validate_on_submit():
        try:
            order = Order(
                user_id=current_user.id,
                total_amount=total,
                status="new",
                shipping_address=form.shipping_address.data,
                notes=form.notes.data,
            )
            db.session.add(order)
            db.session.flush()  # mamy id

            for item in cart.values():
                if item.get("quantity", 0) <= 0:
                    continue
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=item["product_id"],
                    product_name=item["name"],
                    unit_price=item["price"],
                    quantity=item["quantity"],
                )
                db.session.add(order_item)

            db.session.commit()
            _save_cart({})  # czyścimy koszyk
            flash("Zamówienie zostało utworzone. Przejdź do płatności.", "success")
            return redirect(url_for("shop.payment_start", order_id=order.id))
        except OperationalError:
            db.session.rollback()
            flash("Nie udało się utworzyć zamówienia.", "danger")

    return render_template(
        "shop/checkout.html",
        cart=cart,
        total=total,
        count=count,
        form=form,
    )


# =========================
# Stripe – płatności
# =========================


@shop_bp.route("/payment/<int:order_id>/start")
@login_required
def payment_start(order_id: int):
    try:
        order = Order.query.get_or_404(order_id)
    except OperationalError:
        flash("Zamówienie nie istnieje.", "danger")
        return redirect(url_for("shop.index"))

    if order.user_id != current_user.id:
        flash("To nie jest Twoje zamówienie.", "danger")
        return redirect(url_for("shop.index"))

    if order.status not in ("new", "payment_failed"):
        flash("To zamówienie nie jest gotowe do płatności.", "warning")
        return redirect(url_for("shop.index"))

    stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")

    line_items = []
    try:
        for item in order.items:
            line_items.append(
                {
                    "price_data": {
                        "currency": "pln",
                        "product_data": {"name": item.product_name},
                        "unit_amount": int(Decimal(str(item.unit_price)) * 100),
                    },
                    "quantity": item.quantity,
                }
            )
    except Exception:
        flash("Problem z generowaniem pozycji do płatności.", "danger")
        return redirect(url_for("shop.checkout"))

    try:
        session_stripe = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=url_for(
                "shop.payment_success", order_id=order.id, _external=True
            ),
            cancel_url=url_for(
                "shop.payment_cancel", order_id=order.id, _external=True
            ),
        )
    except Exception:
        flash("Nie udało się utworzyć sesji płatności.", "danger")
        return redirect(url_for("shop.checkout"))

    return redirect(session_stripe.url, code=303)


@shop_bp.route("/payment/<int:order_id>/success")
@login_required
def payment_success(order_id: int):
    try:
        order = Order.query.get_or_404(order_id)
    except OperationalError:
        flash("Zamówienie nie istnieje.", "danger")
        return redirect(url_for("shop.index"))

    if order.user_id != current_user.id:
        flash("To nie jest Twoje zamówienie.", "danger")
        return redirect(url_for("shop.index"))

    order.status = "paid"
    try:
        db.session.commit()
    except OperationalError:
        db.session.rollback()
        flash("Nie udało się zaktualizować statusu zamówienia.", "danger")
        return redirect(url_for("shop.index"))

    flash("Płatność zakończona sukcesem. Dziękujemy!", "success")
    return redirect(url_for("shop.index"))


@shop_bp.route("/payment/<int:order_id>/cancel")
@login_required
def payment_cancel(order_id: int):
    try:
        order = Order.query.get_or_404(order_id)
    except OperationalError:
        flash("Zamówienie nie istnieje.", "danger")
        return redirect(url_for("shop.index"))

    if order.user_id != current_user.id:
        flash("To nie jest Twoje zamówienie.", "danger")
        return redirect(url_for("shop.index"))

    flash("Płatność została anulowana.", "warning")
    return redirect(url_for("shop.cart_view"))
