# app/blog/routes.py

from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import OperationalError

from . import blog_bp
from app.extensions import db
from app.models import Post
from .forms import PostForm


def is_admin(user) -> bool:
    """Prosty check: rola 'admin' lub flaga is_admin == True."""
    if not user.is_authenticated:
        return False
    role = getattr(user, "role", None)
    if role == "admin":
        return True
    if getattr(user, "is_admin", False):
        return True
    return False


@blog_bp.route("/")
def post_list():
    try:
        posts = Post.query.order_by(Post.created_at.desc()).all()
    except OperationalError:
        posts = []

    return render_template("blog/post_list.html", posts=posts)


@blog_bp.route("/post/<int:post_id>")
def post_detail(post_id):
    try:
        post = Post.query.get_or_404(post_id)
    except OperationalError:
        return render_template("blog/post_detail.html", post=None), 404

    return render_template("blog/post_detail.html", post=post)


@blog_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_post():
    # TYLKO ADMIN
    if not is_admin(current_user):
        abort(403)

    form = PostForm()
    if form.validate_on_submit():
        # Zakładam, że w PostForm masz pola: title, content
        # i w modelu: title, content_html, author_id
        post = Post(
            title=form.title.data,
            content_html=form.content.data,
            author_id=current_user.id,
        )
        db.session.add(post)
        db.session.commit()
        flash("Nowy wpis na blogu został dodany.", "success")
        return redirect(url_for("blog.post_detail", post_id=post.id))

    return render_template("blog/new_post.html", form=form)
