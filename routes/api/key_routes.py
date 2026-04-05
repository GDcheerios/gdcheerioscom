from flask import Blueprint, request, jsonify

import environment
from api.key_api import *
import base64, json, hmac, hashlib, time, logging  # debug helpers

from objects import Account

key_blueprint = Blueprint('key', __name__)
ALLOWED_SCOPES = {
    "account:read",
    "account:write",
    "leaderboard:read",
    "leaderboard:write",
    "admin",
}


# helpy helper
def _extract_api_key_from_headers() -> str | None:
    header_key = request.headers.get("X-API-Key")
    if header_key:
        return header_key.strip()

    auth = request.headers.get("Authorization", "").strip()
    if auth.startswith("ApiKey "):
        return auth[len("ApiKey "):].strip()

    if auth and " " not in auth:
        return auth

    return None


# helpy helper
def _get_current_user_id_from_bearer():
    """
    Extracts and verifies a Bearer JWT from the Authorization header.
    Returns user_id (str) if valid, otherwise None.
    """
    try:
        has_auth = bool(request.headers.get("Authorization"))
        logging.debug(f"[keys] Authorization header present: {has_auth}")
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            logging.warning("[keys] Missing/invalid Authorization prefix")
            return None

        token = auth[len("Bearer "):].strip()
        parts = token.split(".")
        if len(parts) != 3:
            logging.warning("[keys] JWT does not have 3 parts")
            return None

        h, p, s = parts
        signing_input = f"{h}.{p}".encode()

        def b64pad(x):
            return x + "=" * (-len(x) % 4)

        try:
            sig = base64.urlsafe_b64decode(b64pad(s))
        except Exception:
            logging.warning("[keys] Failed to base64-decode signature")
            return None

        try:
            payload_bytes = base64.urlsafe_b64decode(b64pad(p))
            payload = json.loads(payload_bytes.decode())
        except Exception:
            logging.warning("[keys] Failed to decode/parse payload")
            return None

        expect = hmac.new(environment.secret.encode(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expect):
            logging.warning("[keys] Signature mismatch")
            return None

        now = int(time.time())
        exp = payload.get("exp")
        sub = payload.get("sub")

        # Only log boolean/status, not payload content
        logging.debug(f"[keys] JWT payload checked (sub present: {bool(sub)}, exp ok: {bool(exp and exp >= now)})")

        if exp is None or exp < now:
            logging.warning("[keys] Token expired or missing exp")
            return None
        if not sub:
            logging.warning("[keys] Token missing sub")
            return None

        return str(sub)
    except Exception:
        logging.error("[keys] Unexpected error verifying token")
        return None


@key_blueprint.post("/keys")
def create_key():
    """
    Creates a new API key for the authenticated user.
    Body (JSON): { "name": "My PC", "scopes": ["leaderboard:write"], "expires_at": "2025-12-31T23:59:59Z" }
    Returns: { "key": "<key_id>.<secret>", "key_id": "<key_id>", "name": "...", "scopes": [...], "expires_at": "..."}
    """
    user_id = _get_current_user_id_from_bearer()
    if not user_id:
        logging.warning("[keys] Unauthorized: could not resolve user from Authorization header")
        return jsonify({"error": "unauthorized"}), 401

    user_account = Account(user_id)

    payload = request.get_json(silent=True) or {}
    logging.debug("[keys] Request JSON received (fields: %s)", list(payload.keys()))
    name = payload.get("name") or "Unnamed key"
    scopes = payload.get("scopes") or []
    expires_at = payload.get("expires_at")

    if not isinstance(scopes, list):
        logging.warning("[keys] scopes is not a list")
        return jsonify({"error": "scopes_must_be_list"}), 400

    invalid_scopes = [scope for scope in scopes if scope not in ALLOWED_SCOPES]
    if invalid_scopes:
        logging.warning("[keys] invalid scopes requested")
        return jsonify({"error": "invalid_scopes", "invalid_scopes": invalid_scopes}), 400

    if 'admin' in scopes and not user_account.is_admin:
        logging.warning("[keys] Unauthorized: user is not an admin")
        return jsonify({"error": "unauthorized"}), 401

    key_id, secret, combined = generate_key_pair()
    secret_hash = hash_secret(secret)

    try:
        db = environment.database
        logging.debug("[keys] Inserting key (user_id present: %s, key_id length: %s, expires_at set: %s)",
                      bool(user_id), len(key_id), bool(expires_at))
        db.execute("""
                   INSERT INTO api_keys (user_id, key_id, secret_hash, name, scopes, created_by_ip, expires_at, status,
                                         created_at)
                   VALUES (%s, %s, %s, %s, %s::jsonb, %s,
                           CASE WHEN %s IS NULL THEN NULL ELSE %s::timestamptz END,
                           'active', now())
                   """, (
                       user_id,
                       key_id,
                       secret_hash,
                       name,
                       json.dumps(scopes),
                       request.remote_addr,
                       expires_at,
                       expires_at
                   ))
    except Exception as e:
        logging.error("[keys] DB insert failed")
        return jsonify({"error": "db_error"}), 500

    logging.info("[keys] Created key (key_id length: %s) for user", len(key_id))
    return jsonify({
        "key": combined,
        "key_id": key_id,
        "name": name,
        "scopes": scopes,
        "expires_at": expires_at,
        "tokens": issue_api_key_tokens_from_combined_key(combined),
    }), 201


@key_blueprint.post("/keys/token")
def issue_api_key_tokens():
    """
    Exchanges an API key for an API access token + refresh token pair.
    Accepted headers:
      - X-API-Key: <key_id.secret>
      - Authorization: ApiKey <key_id.secret>
    """
    combined = _extract_api_key_from_headers()
    if not combined:
        return jsonify({"error": "missing_api_key"}), 401

    tokens = issue_api_key_tokens_from_combined_key(combined)
    if not tokens:
        return jsonify({"error": "unauthorized"}), 401

    return jsonify({
        "token_type": "Bearer",
        **tokens
    }), 200


@key_blueprint.post("/keys/refresh")
def refresh_api_key_token():
    """
    Rotates refresh token and issues a new access token for API-key clients.
    Body (JSON): { "refresh_token": "rtk.<key_id>.<secret>" }
    """
    payload = request.get_json(silent=True) or {}
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        return jsonify({"error": "missing_refresh_token"}), 400

    tokens = refresh_api_key_tokens(refresh_token)
    if not tokens:
        return jsonify({"error": "invalid_refresh_token"}), 401

    return jsonify({
        "token_type": "Bearer",
        **tokens
    }), 200
