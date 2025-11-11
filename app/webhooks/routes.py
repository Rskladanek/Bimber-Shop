import stripe
from flask import request, current_app

from . import webhooks_bp
from app.extensions import db
from app.models import Order
from flask_mail import Message
from app.extensions import mail


@webhooks_bp.route("/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    endpoint_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")
    if not endpoint_secret:
        # If not configured, ignore
        return "", 200
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except stripe.error.SignatureVerificationError:
        current_app.logger.warning("Stripe webhook signature verification failed")
        return "", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id")
        if order_id:
            order = Order.query.get(int(order_id))
            if order:
                order.status = "opłacone"
                db.session.commit()
                user = order.user
                if user.email:
                    msg = Message(
                        subject=f"Potwierdzenie płatności za zamówienie #{order.id}",
                        sender="sklep@bimberek.local",
                        recipients=[user.email],
                    )
                    msg.body = (
                        f"Cześć {user.email},\n\n"
                        f"Twoje zamówienie nr {order.id} zostało opłacone.\n"
                        f"Dziękujemy za zakupy w Bimberek Białostocki.\n"
                    )
                    try:
                        mail.send(msg)
                    except Exception:
                        current_app.logger.exception("Nie udało się wysłać maila potwierdzającego.")
    return "", 200
