# app/blog/routes.py

from flask import render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import OperationalError

from . import blog_bp
from app.extensions import db
from app.models import Post, Comment
from .forms import PostForm, BlogCommentForm


def is_admin(user) -> bool:
    """Prosty check: rola 'admin' lub flaga is_admin == True."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    role = getattr(user, "role", None)
    if role == "admin":
        return True
    if getattr(user, "is_admin", False):
        return True
    return False


# =====================================================
#   LISTA POSTÓW / BLOG
# =====================================================

@blog_bp.route("/")
def post_list():
    """
    Lista publicznych wpisów:
    - tylko status = 'zaakceptowany'
    - paginacja
    - prosty search po tytule / treści (q)
    """
    page = request.args.get("page", 1, type=int)
    q = (request.args.get("q") or "").strip()

    try:
        query = Post.query.filter_by(status="zaakceptowany")

        if q:
            like = f"%{q}%"
            query = query.filter(
                db.or_(
                    Post.title.ilike(like),
                    Post.content_html.ilike(like),
                )
            )

        query = query.order_by(Post.created_at.desc())
        posts = query.paginate(page=page, per_page=6, error_out=False)
    except OperationalError:
        posts = None

    # Sidebar – ostatnie wpisy
    try:
        recent_posts = (
            Post.query.filter_by(status="zaakceptowany")
            .order_by(Post.created_at.desc())
            .limit(5)
            .all()
        )
    except OperationalError:
        recent_posts = []

    # Na razie nie masz kategorii dla bloga – dajemy puste
    categories = []
    current_category_id = None

    return render_template(
        "blog/post_list.html",
        posts=posts,
        categories=categories,
        current_category_id=current_category_id,
        recent_posts=recent_posts,
        q=q,
    )


# =====================================================
#   SZCZEGÓŁY POSTA + KOMENTARZE
# =====================================================

@blog_bp.route("/post/<int:post_id>/", methods=["GET", "POST"])
def post_detail(post_id: int):
    """Szczegóły wpisu + komentarze + nawigacja poprzedni/następny."""
    try:
        post = Post.query.get_or_404(post_id)
    except OperationalError:
        return render_template("blog/post_detail.html", post=None), 404

    # Niezaakceptowany – widzi tylko autor lub admin
    if post.status != "zaakceptowany":
        if not current_user.is_authenticated:
            abort(404)
        if not (is_admin(current_user) or current_user.id == post.author_id):
            abort(404)

    # zaakceptowane komentarze
    try:
        comments = (
            Comment.query.filter_by(post_id=post.id, status="zaakceptowany")
            .order_by(Comment.created_at.desc())
            .all()
        )
    except OperationalError:
        comments = []

    form = BlogCommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("Musisz być zalogowany, żeby dodać komentarz.", "warning")
            return redirect(url_for("auth.login", next=request.url))

        try:
            comment = Comment(
                content=form.content.data,
                post_id=post.id,
                user_id=current_user.id,
            )
            db.session.add(comment)
            db.session.commit()
            flash("Komentarz dodany – pojawi się po akceptacji.", "success")
        except OperationalError:
            db.session.rollback()
            flash("Nie udało się dodać komentarza.", "danger")

        return redirect(url_for("blog.post_detail", post_id=post.id))

    # poprzedni / następny wpis (po ID)
    try:
        prev_post = (
            Post.query.filter(
                Post.status == "zaakceptowany",
                Post.id < post.id,
            )
            .order_by(Post.id.desc())
            .first()
        )
        next_post = (
            Post.query.filter(
                Post.status == "zaakceptowany",
                Post.id > post.id,
            )
            .order_by(Post.id.asc())
            .first()
        )
    except OperationalError:
        prev_post = None
        next_post = None

    return render_template(
        "blog/post_detail.html",
        post=post,
        comments=comments,
        form=form,
        prev_post=prev_post,
        next_post=next_post,
    )


# =====================================================
#   NOWY POST
# =====================================================

@blog_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_post():
    """
    Nowy wpis:
    - admin: od razu status 'zaakceptowany'
    - zwykły user: 'oczekuje' -> idzie do moderacji w panelu admina
    """
    form = PostForm()

    if form.validate_on_submit():
        is_admin_flag = is_admin(current_user)
        status = "zaakceptowany" if is_admin_flag else "oczekuje"

        # [ZMIANA] Rozszerzono blok try...except, aby złapać wszystkie błędy
        try:
            post = Post(
                title=form.title.data.strip(),
                content_html=form.content.data,
                author_id=current_user.id,
                status=status,
            )
            db.session.add(post)
            db.session.commit()
        except Exception as e: # [ZMIANA] Łapiemy ogólny błąd, a nie tylko OperationalError
            db.session.rollback()
            # [ZMIANA] Logujemy błąd do konsoli serwera (tam gdzie uruchamiasz 'flask run')
            current_app.logger.error(f"BŁĄD ZAPISU POSTA: {e}") 
            flash("Nie udało się zapisać wpisu. Sprawdź konsolę serwera.", "danger") # [ZMIANA] Lepszy komunikat
            return render_template("blog/new_post.html", form=form)

        if is_admin_flag:
            flash("Nowy wpis został opublikowany.", "success")
            return redirect(url_for("blog.post_detail", post_id=post.id))
        else:
            flash(
                "Twój wpis został zapisany i czeka na akceptację administratora.",
                "success",
            )
            return redirect(url_for("blog.post_list"))

    return render_template("blog/new_post.html", form=form)