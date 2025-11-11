import os
import uuid

from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    jsonify,
    current_app,
)
from flask_login import login_required, current_user

from . import admin_bp
from .forms import ThemeForm, SliderForm
from app.extensions import db
from app.models import (
    Comment,
    Report,
    ModeratorMessage,
    Theme,
    Slider,
    SliderItem,
    Product,
    Category,
    Post,
)
from app.shop.forms import ProductForm


def admin_required() -> bool:
    """Sprawdza, czy użytkownik ma rolę admin/moderator."""
    if not current_user.is_authenticated or getattr(current_user, "role", "user") not in [
        "admin",
        "moderator",
    ]:
        flash("Brak uprawnień.", "danger")
        return False
    return True


@admin_bp.route("/")
@login_required
def dashboard():
    if not admin_required():
        return redirect(url_for("shop.index"))

    pending_comments = Comment.query.filter_by(status="oczekuje").count()
    open_reports = Report.query.filter_by(status="open").count()
    products_count = Product.query.count()
    posts_count = Post.query.count()
    last_products = Product.query.order_by(Product.id.desc()).limit(5).all()
    last_posts = Post.query.order_by(Post.created_at.desc()).limit(5).all()

    return render_template(
        "admin/dashboard.html",
        pending_comments=pending_comments,
        open_reports=open_reports,
        products_count=products_count,
        posts_count=posts_count,
        last_products=last_products,
        last_posts=last_posts,
    )


# ===================== KOMENTARZE / MODERACJA =====================

@admin_bp.route("/moderation")
@login_required
def moderation_queue():
    if not admin_required():
        return redirect(url_for("shop.index"))
    comments = (
        Comment.query.filter_by(status="oczekuje")
        .order_by(Comment.created_at.desc())
        .all()
    )
    return render_template("admin/moderation.html", comments=comments)


@admin_bp.route("/comment/<int:comment_id>/approve")
@login_required
def approve_comment(comment_id):
    if not admin_required():
        return redirect(url_for("shop.index"))
    comment = Comment.query.get_or_404(comment_id)
    comment.status = "zaakceptowany"
    db.session.commit()
    flash("Komentarz zaakceptowany.", "success")
    return redirect(url_for("admin.moderation_queue"))


@admin_bp.route("/comment/<int:comment_id>/reject")
@login_required
def reject_comment(comment_id):
    if not admin_required():
        return redirect(url_for("shop.index"))
    comment = Comment.query.get_or_404(comment_id)
    comment.status = "odrzucony"
    db.session.commit()
    flash("Komentarz odrzucony.", "info")
    return redirect(url_for("admin.moderation_queue"))


# ===================== ZGŁOSZENIA =====================

@admin_bp.route("/reports")
@login_required
def reports_list():
    if not admin_required():
        return redirect(url_for("shop.index"))
    reports = Report.query.filter_by(status="open").all()
    return render_template("admin/reports.html", reports=reports)


@admin_bp.route("/report/<int:report_id>", methods=["GET", "POST"])
@login_required
def report_detail(report_id):
    if not admin_required():
        return redirect(url_for("shop.index"))
    report = Report.query.get_or_404(report_id)

    messages = (
        ModeratorMessage.query.filter_by(report_id=report.id)
        .order_by(ModeratorMessage.timestamp.asc())
        .all()
    )

    if request.method == "POST":
        content = (request.form.get("message") or "").strip()
        if content:
            msg = ModeratorMessage(
                report_id=report.id,
                sender_id=current_user.id,
                content=content,
            )
            db.session.add(msg)
            db.session.commit()
            flash("Wiadomość dodana.", "success")
            return redirect(url_for("admin.report_detail", report_id=report.id))
        else:
            flash("Treść wiadomości nie może być pusta.", "warning")

    return render_template(
        "admin/report_detail.html",
        report=report,
        messages=messages,
    )


@admin_bp.route("/report/<int:report_id>/close")
@login_required
def close_report(report_id):
    if not admin_required():
        return redirect(url_for("shop.index"))
    report = Report.query.get_or_404(report_id)
    report.status = "closed"
    db.session.commit()
    flash("Zgłoszenie zamknięte.", "info")
    return redirect(url_for("admin.reports_list"))


# ===================== MOTYWY =====================

@admin_bp.route("/themes", methods=["GET", "POST"])
@login_required
def themes():
    if not admin_required():
        return redirect(url_for("shop.index"))

    form = ThemeForm()
    themes = Theme.query.order_by(Theme.name).all()

    if form.validate_on_submit():
        theme = Theme(
            name=form.name.data,
            color1=form.color1.data,
            color2=form.color2.data,
            color3=form.color3.data,
        )
        db.session.add(theme)
        db.session.commit()
        flash("Motyw dodany.", "success")
        return redirect(url_for("admin.themes"))

    return render_template("admin/themes.html", form=form, themes=themes)


@admin_bp.route("/themes/<int:theme_id>/delete")
@login_required
def delete_theme(theme_id):
    if not admin_required():
        return redirect(url_for("shop.index"))
    theme = Theme.query.get_or_404(theme_id)
    db.session.delete(theme)
    db.session.commit()
    flash("Motyw usunięty.", "info")
    return redirect(url_for("admin.themes"))


# ===================== PRODUKTY =====================

@admin_bp.route("/products")
@login_required
def list_products():
    if not admin_required():
        return redirect(url_for("shop.index"))
    products = Product.query.order_by(Product.id.desc()).all()
    return render_template("admin/products.html", products=products)


@admin_bp.route("/products/new", methods=["GET", "POST"])
@login_required
def add_product():
    if not admin_required():
        return redirect(url_for("shop.index"))

    form = ProductForm()

    categories = Category.query.order_by(Category.name).all()
    form.category.choices = [(0, "--- brak kategorii ---")] + [
        (c.id, c.name) for c in categories
    ]

    if form.validate_on_submit():
        category_id = form.category.data or None
        if category_id == 0:
            category_id = None

        product = Product(
            name=form.name.data,
            price=form.price.data,
            description_html=form.description.data or "",
            category_id=category_id,
        )

        if form.image.data:
            upload_folder = os.path.join(
                current_app.root_path, "static", "images", "products"
            )
            os.makedirs(upload_folder, exist_ok=True)

            orig_filename = form.image.data.filename
            ext = os.path.splitext(orig_filename)[1].lower() or ".jpg"
            filename = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(upload_folder, filename)
            form.image.data.save(filepath)
            product.image_filename = filename

        db.session.add(product)
        db.session.commit()
        flash("Produkt dodany.", "success")
        return redirect(url_for("admin.list_products"))

    return render_template("admin/add_product.html", form=form)


@admin_bp.route("/products/<int:product_id>")
@login_required
def view_product(product_id):
    if not admin_required():
        return redirect(url_for("shop.index"))

    product = Product.query.get_or_404(product_id)
    comments_accepted = Comment.query.filter_by(
        product_id=product.id, status="zaakceptowany"
    ).count()
    comments_pending = Comment.query.filter_by(
        product_id=product.id, status="oczekuje"
    ).count()
    comments_rejected = Comment.query.filter_by(
        product_id=product.id, status="odrzucony"
    ).count()

    return render_template(
        "admin/product_detail.html",
        product=product,
        comments_accepted=comments_accepted,
        comments_pending=comments_pending,
        comments_rejected=comments_rejected,
    )


@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    if not admin_required():
        return redirect(url_for("shop.index"))

    product = Product.query.get_or_404(product_id)
    form = ProductForm(obj=product)

    categories = Category.query.order_by(Category.name).all()
    form.category.choices = [(0, "--- brak kategorii ---")] + [
        (c.id, c.name) for c in categories
    ]
    form.category.data = product.category_id or 0

    if form.validate_on_submit():
        category_id = form.category.data or None
        if category_id == 0:
            category_id = None

        product.name = form.name.data
        product.price = form.price.data
        product.description_html = form.description.data or ""
        product.category_id = category_id

        if form.image.data:
            upload_folder = os.path.join(
                current_app.root_path, "static", "images", "products"
            )
            os.makedirs(upload_folder, exist_ok=True)

            orig_filename = form.image.data.filename
            ext = os.path.splitext(orig_filename)[1].lower() or ".jpg"
            filename = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(upload_folder, filename)
            form.image.data.save(filepath)
            product.image_filename = filename

        db.session.commit()
        flash("Produkt zaktualizowany.", "success")
        return redirect(url_for("admin.view_product", product_id=product.id))

    return render_template("admin/add_product.html", form=form, edit_mode=True)


@admin_bp.route("/products/<int:product_id>/delete")
@login_required
def delete_product(product_id):
    if not admin_required():
        return redirect(url_for("shop.index"))

    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash("Produkt usunięty.", "info")
    return redirect(url_for("admin.list_products"))


# ===================== SLIDERY =====================

@admin_bp.route("/sliders", methods=["GET", "POST"])
@login_required
def sliders():
    if not admin_required():
        return redirect(url_for("shop.index"))

    form = SliderForm()

    if form.validate_on_submit():
        slider = Slider(
            name=form.name.data,
            is_active=form.is_active.data,
        )
        if slider.is_active:
            Slider.query.update({Slider.is_active: False})
        db.session.add(slider)
        db.session.commit()
        flash("Slider dodany.", "success")
        return redirect(url_for("admin.sliders"))

    sliders = Slider.query.order_by(Slider.id.asc()).all()
    return render_template("admin/sliders.html", sliders=sliders, form=form)


@admin_bp.route("/sliders/<int:slider_id>/set_active")
@login_required
def set_active_slider(slider_id):
    if not admin_required():
        return redirect(url_for("shop.index"))
    slider = Slider.query.get_or_404(slider_id)

    Slider.query.update({Slider.is_active: False})
    slider.is_active = True
    db.session.commit()
    flash(f"Slider '{slider.name}' ustawiony jako aktywny.", "success")
    return redirect(url_for("admin.sliders"))


@admin_bp.route("/sliders/<int:slider_id>/order", methods=["POST"])
@login_required
def save_slider_order(slider_id):
    if not admin_required():
        return jsonify({"error": "Brak uprawnień"}), 403

    slider = Slider.query.get_or_404(slider_id)
    data = request.get_json()
    if not data:
        return jsonify({"error": "Brak danych"}), 400

    try:
        for item_data in data:
            item_id = int(item_data.get("item_id"))
            order_index = int(item_data.get("order"))
            item = SliderItem.query.get(item_id)
            if item and item.slider_id == slider.id:
                item.order_index = order_index

        db.session.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
