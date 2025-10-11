import environment
import time, base64, hmac, hashlib, os, json
from flask import request, jsonify, g
from functools import wraps


def _rand_b64url(n_bytes: int) -> str:
    return base64.urlsafe_b64encode(os.urandom(n_bytes)).decode().rstrip("=")


def generate_key_pair():
    key_id = _rand_b64url(12)
    secret = _rand_b64url(32)
    return key_id, secret, f"{key_id}.{secret}"


def hash_secret(secret: str) -> str:
    return environment.bcrypt.generate_password_hash(secret).decode()


JWT_SECRET = environment.secret
JWT_TTL = 3600


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def sign_jwt(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    h = b64url(json.dumps(header, separators=(",", ":")).encode())
    p = b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(JWT_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    s = b64url(sig)
    return f"{h}.{p}.{s}"


def issue_access_token(user_id: int | str) -> str:
    now = int(time.time())
    payload = {"sub": str(user_id), "iat": now, "exp": now + JWT_TTL}
    return sign_jwt(payload)


def verify_api_key_header():
    auth = request.headers.get("Authorization", "")
    prefix = "ApiKey "
    if not auth.startswith(prefix):
        return None
    combined = auth[len(prefix):].strip()
    if "." not in combined:
        return None
    key_id, secret = combined.split(".", 1)
    # Lookup key by key_id in your DB (fetch secret_hash, user_id, scopes, status, expires_at)
    row = environment.database.fetch_to_dict(
        "SELECT user_id, secret_hash, scopes, status, expires_at FROM api_keys WHERE key_id = %s",
        params=(key_id,)
    )
    if not row or row["status"] != "active":
        return None
    # Check expiry
    if row["expires_at"] and row["expires_at"] < environment.database.now():  # replace with proper now()
        return None
    # Verify secret against hash
    if not environment.bcrypt.check_password_hash(row["secret_hash"], secret):
        return None
    # Attach identity and scopes for downstream use
    g.current_user_id = str(row["user_id"])
    g.current_scopes = row["scopes"]
    return g.current_user_id


def require_scopes(required: list[str]):
    def decorator(fn):
        @wraps(fn)  # preserve endpoint name and metadata
        def wrapper(*args, **kwargs):
            uid = verify_api_key_header()
            if not uid:
                return jsonify({"error": "unauthorized"}), 401
            have = set(g.get("current_scopes", []))
            if not set(required).issubset(have):
                return jsonify({"error": "forbidden", "missing_scopes": list(set(required) - have)}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
