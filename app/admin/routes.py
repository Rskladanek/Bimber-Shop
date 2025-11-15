# app/admin/routes.py
from __future__ import annotations  # <-- POPRAWKA: Ta linia musi być PIERWSZA

import os
import uuid
from decimal import Decimal
from werkzeug.utils import secure_filename
from werkzeug.routing import BuildError

from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
)
from flask_login import login_required, current_user

from . import admin_bp
# POPRAWKA: Scaliłem zduplikowane importy.
# Teraz importujemy wszystko, czego potrzebujemy, w jednym miejscu.
from .forms import ProductForm, SliderForm, AddSliderItemForm
from app.extensions import db
from app.models import (
    Product,
    Category,
    Comment,
    Post,
    Slider,
    Report,
    SliderItem,  # Dodany SliderItem
)


# =============================
#  Helpers / security
# =============================

def admin_required() -> bool:
    """Prosta bramka – dopuszcza tylko adminów."""
    if not current_user.is_authenticated:
        return False
    if getattr(current_user, "is_admin", False):
        return True
    if getattr(current_user, "role", None) == "admin":
        return True
    return False


def _product_upload_path() -> str:
    return os.path.join(current_app.root_path, "static", "images", "products")


def _save_image(file_storage):
    """Zapisuje obraz i zwraca nazwę pliku lub None."""
    if not file_storage:
        return None
    filename = secure_filename(file_storage.filename or "")
    if not filename:
        return None
    base, ext = os.path.splitext(filename)
    unique_name = f"{uuid.uuid4().hex}{ext.lower()}"
    dst_dir = _product_upload_path()
    os.makedirs(dst_dir, exist_ok=True)
    file_storage.save(os.path.join(dst_dir, unique_name))
    return unique_name


def _category_choices():
    """Lista opcji dla SelectField (0 oznacza brak kategorii)."""
    cats = Category.query.order_by(Category.name).all()
    return [(0, "--- brak kategorii ---")] + [(c.id, c.name) for c in cats]


# --- OPIS: różne nazwy pola w modelu ---
_DESC_FIELDS = ("description", "description_html", "desc", "body", "content")


def _get_description(product: Product) -> str:
    for field in _DESC_FIELDS:
        if hasattr(product, field):
            val = getattr(product, field)
            if val:
                return str(val)
    return ""


def _set_description(product: Product, text: str) -> bool:
    for field in _DESC_FIELDS:
        if hasattr(product, field):
            setattr(product, field, text or "")
            return True
    return False


# --- ILOŚĆ: różne nazwy pola w modelu ---
_STOCK_FIELDS = (
    "stock", "quantity", "qty", "inventory", "amount",
    "in_stock", "units", "on_hand", "available",
)


def _get_stock(product: Product) -> int:
    for field in _STOCK_FIELDS:
        if hasattr(product, field):
            try:
                val = getattr(product, field)
                if val is None:
                    return 0
                return int(val)
            except Exception:
                return 0
    return 0


def _set_stock(product: Product, value: int) -> bool:
    for field in _STOCK_FIELDS:
        if hasattr(product, field):
            setattr(product, field, int(value))
            return True
    return False


def _endpoint_exists(name: str) -> bool:
    """Sprawdza, czy endpoint istnieje – żeby nie wysadzać dashboardu url_for-em."""
    try:
        url_for(name)
        return True
    except BuildError:
        return False


# =============================
#  Dashboard
# =============================

@admin_bp.route("/")
@login_required
def dashboard():
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))

    # --- PODSTAWOWE METRYKI ---
    products_count = db.session.query(Product).count()
    categories_count = db.session.query(Category).count()
    comments_count = db.session.query(Comment).count()

    # komentarze oczekujące
    try:
        comments_pending = Comment.query.filter(Comment.status != "zaakceptowany").count()
    except Exception:
        try:
            comments_pending = Comment.query.filter_by(status="oczekuje").count()
        except Exception:
            comments_pending = 0

    # blog – ilość wpisów / oczekujące
    posts_total = 0
    posts_pending = 0
    try:
        posts_total = Post.query.count()
        posts_pending = Post.query.filter(Post.status != "zaakceptowany").count()
    except Exception:
        pass

    # slidery – ilość + aktywny
    try:
        sliders_count = Slider.query.count()
        active_slider = Slider.query.filter_by(is_active=True).first()
    except Exception:
        sliders_count = 0
        active_slider = None

    # raporty / zgłoszenia
    try:
        reports_open = Report.query.filter_by(status="open").count()
    except Exception:
        reports_open = 0

    reports_endpoint_exists = _endpoint_exists("admin.reports")
    themes_endpoint_exists = _endpoint_exists("admin.themes")

    # ostatnie produkty (po ID – auto-inkrement)
    latest_products = (
        Product.query
        .order_by(Product.id.desc())
        .limit(10)
        .all()
    )

    # najnowsze komentarze
    try:
        latest_comments = (
            Comment.query
            .order_by(Comment.created_at.desc())
            .limit(10)
            .all()
        )
    except Exception:
        latest_comments = []

    # produkty z niskim stanem magazynowym (<= 3 szt.)
    low_stock_products = []
    low_stock_count = 0
    try:
        low_stock_query = Product.query.filter(Product.stock <= 3)
        low_stock_count = low_stock_query.count()
        low_stock_products = (
            low_stock_query
            .order_by(Product.stock.asc(), Product.id.asc())
            .limit(20)
            .all()
        )
    except Exception:
        low_stock_products = []
        low_stock_count = 0

    return render_template(
        "admin/dashboard.html",
        products_count=products_count,
        categories_count=categories_count,
        comments_count=comments_count,
        comments_pending=comments_pending,
        posts_total=posts_total,
        posts_pending=posts_pending,
        sliders_count=sliders_count,
        active_slider=active_slider,
        reports_open=reports_open,
        reports_endpoint_exists=reports_endpoint_exists,
        themes_endpoint_exists=themes_endpoint_exists,
        latest_products=latest_products,
        latest_comments=latest_comments,
        low_stock_products=low_stock_products,
        low_stock_count=low_stock_count,
    )


# =============================
#  Moderacja komentarzy
# =============================

@admin_bp.route("/comments/moderation")
@login_required
def moderate_comments():
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))

    comments = (
        Comment.query.filter_by(status="oczekuje")
        .order_by(Comment.created_at.desc())
        .all()
    )

    return render_template("admin/moderation.html", comments=comments)


# [ZMIANA] Dodano methods=["POST"]
@admin_bp.route("/comments/<int:comment_id>/approve", methods=["POST"])
@login_required
def approve_comment(comment_id: int):
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))

    comment = Comment.query.get_or_404(comment_id)
    comment.status = "zaakceptowany"
    db.session.commit()
    flash("Komentarz został zaakceptowany.", "success")
    return redirect(request.referrer or url_for("admin.moderate_comments"))


# [ZMIANA] Dodano methods=["POST"]
@admin_bp.route("/comments/<int:comment_id>/reject", methods=["POST"])
@login_required
def reject_comment(comment_id: int):
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))

    comment = Comment.query.get_or_404(comment_id)
    comment.status = "odrzucony"
    db.session.commit()
    flash("Komentarz został odrzucony.", "info")
    return redirect(request.referrer or url_for("admin.moderate_comments"))


# =============================
#  Moderacja wpisów na blogu
# =============================

@admin_bp.route("/blog/moderation")
@login_required
def moderate_posts():
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))

    posts = (
        Post.query.filter(Post.status != "zaakceptowany")
        .order_by(Post.created_at.desc())
        .all()
    )

    return render_template("admin/blog_posts.html", posts=posts)


# [ZMIANA] Dodano methods=["POST"]
@admin_bp.route("/blog/<int:post_id>/approve", methods=["POST"])
@login_required
def approve_post(post_id: int):
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))

    post = Post.query.get_or_404(post_id)
    post.status = "zaakceptowany"
    db.session.commit()
    flash("Wpis został opublikowany.", "success")
    return redirect(request.referrer or url_for("admin.moderate_posts"))


# [ZMIANA] Dodano methods=["POST"]
@admin_bp.route("/blog/<int:post_id>/reject", methods=["POST"])
@login_required
def reject_post(post_id: int):
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))

    post = Post.query.get_or_404(post_id)
    post.status = "odrzucony"
    db.session.commit()
    flash("Wpis został oznaczony jako odrzucony.", "info")
    return redirect(request.referrer or url_for("admin.moderate_posts"))


# =============================
#  Slidery
# =============================

@admin_bp.route("/sliders", methods=["GET", "POST"])
@login_required
def sliders():
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))

    form = SliderForm()
    if form.validate_on_submit():
        # jeżeli zaznaczony jako aktywny – wyłącz wszystkie inne
        if form.is_active.data:
            Slider.query.update({Slider.is_active: False})

        slider = Slider(
            name=form.name.data.strip(),
            is_active=bool(form.is_active.data),
        )
        db.session.add(slider)
        db.session.commit()
        flash("Slider został utworzony.", "success")
        return redirect(url_for("admin.sliders"))

    sliders = Slider.query.order_by(Slider.id.asc()).all()
    return render_template("admin/sliders.html", form=form, sliders=sliders)


@admin_bp.route("/sliders/set-active/<int:slider_id>")
@login_required
def set_active_slider(slider_id: int):
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))

    slider = Slider.query.get_or_404(slider_id)

    # wyłącz wszystkie slidery
    Slider.query.update({Slider.is_active: False})
    slider.is_active = True
    db.session.commit()

    flash(f"Aktywny slider ustawiony na \"{slider.name}\".", "success")
    return redirect(url_for("admin.sliders"))


# =============================
#  Slidery - ZARZĄDZANIE (NOWY KOD)
# =============================

@admin_bp.route("/sliders/<int:slider_id>", methods=["GET", "POST"])
@login_required
def slider_detail(slider_id: int):
    """
    Widok zarządzania pojedynczym sliderem (dodawanie/przeglądanie itemów).
    Renderuje szablon slider_detail.html.
    """
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))

    slider = Slider.query.get_or_404(slider_id)
    form = AddSliderItemForm() # Formularz z forms.py

    if form.validate_on_submit():
        # Sprawdź, czy ten produkt nie jest już w sliderze
        exists = SliderItem.query.filter_by(
            slider_id=slider.id,
            product_id=form.product_id.data
        ).first()

        if exists:
            flash("Ten produkt jest już w tym sliderze.", "warning")
        else:
            new_item = SliderItem(
                slider_id=slider.id,
                product_id=form.product_id.data,
                order_index=form.order_index.data or 0
            )
            db.session.add(new_item)
            db.session.commit()
            flash("Produkt został dodany do slidera.", "success")
        
        return redirect(url_for("admin.slider_detail", slider_id=slider.id))

    # Pobieramy itemy (są już posortowane dzięki 'order_by' w modelu)
    items_in_slider = slider.items

    return render_template(
        "admin/slider_detail.html",
        slider=slider,
        items_in_slider=items_in_slider,
        form=form
    )


@admin_bp.route("/sliders/item/<int:item_id>/delete", methods=["POST"])
@login_required
def remove_slider_item(item_id: int):
    """
    Usuwa pojedynczy element (SliderItem) ze slidera.
    Wywoływane przez formularz w slider_detail.html.
    """
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))

    item = SliderItem.query.get_or_404(item_id)
    slider_id = item.slider_id # Zapamiętujemy ID, żeby wiedzieć gdzie wrócić

    db.session.delete(item)
    db.session.commit()
    
    flash("Produkt został usunięty ze slidera.", "success")
    # Wracamy na stronę zarządzania sliderem
    return redirect(url_for("admin.slider_detail", slider_id=slider_id))


# =============================
#  Produkty CRUD
# =============================

@admin_bp.route("/products")
@login_required
def list_products():
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))
    products = Product.query.order_by(Product.id.desc()).all()
    return render_template("admin/products.html", products=products)


@admin_bp.route("/products/new", methods=["GET", "POST"])
@login_required
def new_product():
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))

    form = ProductForm()
    form.category.choices = _category_choices()

    if form.validate_on_submit():
        product = Product(
            name=form.name.data,
            price=Decimal(str(form.price.data or 0)),
        )
        _set_description(product, form.description.data or "")
        _set_stock(product, form.stock.data or 0)

        if form.category.data:
            if form.category.data != 0:
                product.category_id = form.category.data

        image = request.files.get("image")
        if image and image.filename:
            filename = _save_image(image)
            product.image_filename = filename

        db.session.add(product)
        db.session.commit()
        flash("Produkt został dodany.", "success")
        return redirect(url_for("admin.list_products"))

    return render_template("admin/add_product.html", form=form, edit_mode=False, product=None)


@admin_bp.route("/products/<int:product_id>")
@login_required
def product_detail(product_id: int):
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))
    product = Product.query.get_or_404(product_id)
    comments = (
        Comment.query.filter_by(product_id=product.id)
        .order_by(Comment.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template("admin/product_detail.html", product=product, comments=comments)


# [ZMIANA] Poprawka literówki z 'admin_Sbp' na 'admin_bp'
@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id: int):
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))

    product = Product.query.get_or_404(product_id)

    # Wstępne wartości do formularza
    initial_desc = _get_description(product)
    initial_stock = _get_stock(product)

    form = ProductForm(
        name=product.name,
        price=product.price,
        description=initial_desc,
        stock=initial_stock,
    )
    form.category.choices = _category_choices()
    form.category.data = product.category_id or 0

    if form.validate_on_submit():
        product.name = form.name.data
        product.price = Decimal(str(form.price.data or 0))
        _set_description(product, form.description.data or "")
        _set_stock(product, form.stock.data or 0)

        if form.category.data:
            if form.category.data != 0:
                product.category_id = form.category.data
            else:
                product.category_id = None

        image = request.files.get("image")
        if image and image.filename:
            filename = _save_image(image)
            product.image_filename = filename

        db.session.commit()
        flash("Produkt został zaktualizowany.", "success")
        return redirect(url_for("admin.product_detail", product_id=product.id))

    return render_template("admin/add_product.html", form=form, edit_mode=True, product=product)


@admin_bp.route("/products/<int:product_id>/delete", methods=["POST"])
@login_required
def delete_product(product_id: int):
    if not admin_required():
        flash("Brak uprawnień do panelu administratora.", "danger")
        return redirect(url_for("shop.index"))
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash("Produkt został usunięty.", "success")
    return redirect(url_for("admin.list_products"))