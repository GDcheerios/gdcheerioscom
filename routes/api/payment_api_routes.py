import stripe
from flask import Blueprint, redirect, url_for, session
import environment

payments_bp = Blueprint('payments', __name__)
stripe.api_key = environment.STRIPE_SECRET_KEY


@payments_bp.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    # Assuming you store the user ID in the session
    user_id = session.get('user_id')
    if not user_id:
        return "Unauthorized", 401

    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[{
                'price': 'price_H5ggYPr3u9q047',  # Create this in Stripe Dashboard
                'quantity': 1,
            }],
            mode='payment',  # or 'subscription'
            success_url=f"{environment.domain}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{environment.domain}/cancel",
            client_reference_id=str(user_id),  # Very important to identify the user later
        )
    except Exception as e:
        return str(e)

    return redirect(checkout_session.url, code=303)
