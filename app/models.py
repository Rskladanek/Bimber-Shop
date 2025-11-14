# app/models.py
from flask_login import UserMixin
from .extensions import db


# -----------------------------
# Użytkownicy / motywy
# -----------------------------
class Theme(db.Model):
    __tablename__ = "themes"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    color1 = db.Column(db.String(7), nullable=False)  # hex, np. #ff0000
    color2 = db.Column(db.String(7), nullable=False)
    color3 = db.Column(db.String(7), nullable=False)

    users = db.relationship("User", back_populates="theme", lazy=True)

    def __repr__(self):
        return f"<Theme {self.name}>"


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default="user")  # user, moderator, admin
    google_id = db.Column(db.String(100), nullable=True)
    facebook_id = db.Column(db.String(100), nullable=True)
    theme_id = db.Column(db.Integer, db.ForeignKey("themes.id"), nullable=True)
    rank = db.Column(db.String(50), nullable=True)

    theme = db.relationship("Theme", back_populates="users")
    orders = db.relationship("Order", back_populates="user", lazy=True)

    def __repr__(self):
        return f"<User {self.email}>"


# -----------------------------
# Katalog / kategorie / produkty
# -----------------------------
class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)

    children = db.relationship(
        "Category",
        backref=db.backref("parent", remote_side=[id]),
        lazy=True,
    )
    products = db.relationship("Product", back_populates="category", lazy=True)

    def __repr__(self):
        return f"<Category {self.name}>"


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description_html = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    image_filename = db.Column(db.String(200), nullable=True)

    # stock już istnieje w bazie – NIE zmieniamy deklaracji:
    stock = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    category = db.relationship("Category", back_populates="products")
    comments = db.relationship("Comment", back_populates="product", lazy=True)
    slider_items = db.relationship("SliderItem", back_populates="product", lazy=True)

    def __repr__(self):
        return f"<Product {self.name}>"


# -----------------------------
# Media (zdjęcia do galerii/sliderów)
# -----------------------------
class Media(db.Model):
    __tablename__ = "media"
    id = db.Column(db.Integer, primary_key=True)

    # metadane pliku
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=True)

    # opis / SEO
    title = db.Column(db.String(200), nullable=True)
    alt_text = db.Column(db.String(200), nullable=True)
    description_html = db.Column(db.Text, nullable=True)

    # wymiary po autoskalowaniu
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # powiązania
    slider_items = db.relationship("SliderItem", back_populates="media", lazy=True)

    def __repr__(self):
        return f"<Media {self.id} {self.stored_filename}>"

    @property
    def url_path(self) -> str:
        # zakładamy zapis do static/images/media/<stored_filename>
        return f"images/media/{self.stored_filename}"


# -----------------------------
# Slidery / elementy slidera
# -----------------------------
class Slider(db.Model):
    __tablename__ = "sliders"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=False)

    items = db.relationship(
        "SliderItem",
        back_populates="slider",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="SliderItem.order_index.asc()",
    )

    def __repr__(self):
        return f"<Slider {self.name} active={self.is_active}>"


class SliderItem(db.Model):
    __tablename__ = "slider_items"
    id = db.Column(db.Integer, primary_key=True)

    slider_id = db.Column(db.Integer, db.ForeignKey("sliders.id"), nullable=False)

    # ALBO produkt, ALBO media (zdjęcie niezależne)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)

    # kolejność w sliderze
    order_index = db.Column(db.Integer, nullable=False, default=0)

    # opcjonalny podpis pod kaflem
    caption = db.Column(db.String(255), nullable=True)

    slider = db.relationship("Slider", back_populates="items")
    product = db.relationship("Product", back_populates="slider_items")
    media = db.relationship("Media", back_populates="slider_items")

    __table_args__ = (
        db.UniqueConstraint("slider_id", "order_index", name="uq_slider_order"),
    )

    def __repr__(self):
        kind = "media" if self.media_id else "product"
        ref = self.media_id or self.product_id
        return f"<SliderItem slider={self.slider_id} {kind}={ref} idx={self.order_index}>"


# -----------------------------
# Blog / komentarze / raporty
# -----------------------------
class Post(db.Model):
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content_html = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.String(20),
        default="oczekuje",
        nullable=False,
    )  # oczekuje, zaakceptowany, odrzucony
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    author = db.relationship("User")
    comments = db.relationship("Comment", back_populates="post", lazy=True)

    def __repr__(self):
        return f"<Post {self.title[:20]}>"


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.String(20),
        default="oczekuje",
    )  # oczekuje, zaakceptowany, odrzucony
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=True)

    user = db.relationship("User")
    product = db.relationship("Product", back_populates="comments")
    post = db.relationship("Post", back_populates="comments")
    votes = db.relationship("CommentVote", back_populates="comment", lazy=True)

    def __repr__(self):
        return f"<Comment {self.id} by={self.user_id}>"


class CommentVote(db.Model):
    __tablename__ = "comment_votes"
    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey("comments.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    value = db.Column(db.Integer, nullable=False)  # +1 / -1

    comment = db.relationship("Comment", back_populates="votes")
    user = db.relationship("User")

    def __repr__(self):
        return f"<CommentVote comment={self.comment_id} user={self.user_id} value={self.value}>"


# -----------------------------
# Zamówienia
# -----------------------------
class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), default="oczekuje")  # oczekuje, opłacone, wysłane
    shipping_address = db.Column(db.String(250), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", lazy=True)

    def __repr__(self):
        return f"<Order {self.id} user={self.user_id} status={self.status}>"


class OrderItem(db.Model):
    __tablename__ = "order_items"
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), primary_key=True)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_order = db.Column(db.Numeric(10, 2), nullable=False)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")

    def __repr__(self):
        return f"<OrderItem order={self.order_id} product={self.product_id}>"


# -----------------------------
# Zgłoszenia / moderacja
# -----------------------------
class Report(db.Model):
    __tablename__ = "reports"
    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey("comments.id"), nullable=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reason = db.Column(db.String(300), nullable=True)
    status = db.Column(db.String(20), default="open")
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    comment = db.relationship("Comment")
    post = db.relationship("Post")
    reporter = db.relationship("User")
    messages = db.relationship("ModeratorMessage", back_populates="report", lazy=True)

    def __repr__(self):
        return f"<Report {self.id} status={self.status}>"


class ModeratorMessage(db.Model):
    __tablename__ = "moderator_messages"
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("reports.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

    report = db.relationship("Report", back_populates="messages")
    sender = db.relationship("User")

    def __repr__(self):
        return f"<ModMsg report={self.report_id} sender={self.sender_id}>"
