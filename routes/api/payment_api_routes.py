import stripe
from flask import Blueprint, redirect, url_for, session, request, jsonify
import environment
from objects import Account

payments_api_blueprint = Blueprint('payment api', __name__)
stripe.api_key = environment.stripe_secret_key


@payments_api_blueprint.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    user_id = Account.id_from_session(request.cookies.get('session'))
    if user_id is None:
        return "Unauthorized", 401

    try:
        weeks = int(request.form.get('weeks', 0))
        print(weeks)
    except ValueError:
        return "Invalid input", 400

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'{weeks} Week(s) Supporter Status',
                        'description': 'Thank you for supporting gdcheerios.com',
                    },
                    'unit_amount': environment.weekly_cost,
                },
                'quantity': weeks,
            }],
            mode='payment',
            success_url=f"{environment.domain}/payment/success",
            cancel_url=f"{environment.domain}/supporter",
            client_reference_id=str(user_id),
            metadata={
                'weeks': weeks
            }
        )
    except Exception as e:
        return str(e), 500

    return redirect(checkout_session.url, code=303)


@payments_api_blueprint.get('/success')
def payment_success():
    return redirect(f"/account/{Account.id_from_session(request.cookies.get('session'))}")


@payments_api_blueprint.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=False)
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, environment.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError as e:
        print(f"Signature verification failed: {e}")
        return jsonify(success=False), 400
    except ValueError as e:
        print(f"Invalid payload: {e}")
        return jsonify(success=False), 400

    if event['type'] == 'checkout.session.completed':
        session_obj = event['data']['object']
        user_id = session_obj.get('client_reference_id')
        metadata = session_obj.get('metadata', {})
        weeks = int(metadata.get('weeks', 1))

        if user_id:
            from objects.Account import Account
            Account.make_supporter(int(user_id), weeks)

    return jsonify(success=True), 200
