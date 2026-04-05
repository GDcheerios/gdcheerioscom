import datetime as dt
import environment
import time, base64, hmac, hashlib, os, json
from flask import request, jsonify, g
from functools import wraps
from utils.logger import setup_logger

logger = setup_logger("api.key")


JWT_SECRET = environment.secret
JWT_TTL = 3600
API_KEY_ACCESS_TOKEN_TTL = 3600
API_KEY_REFRESH_TOKEN_TTL = 60 * 60 * 24 * 30
API_KEY_ACCESS_TOKEN_TYPE = "api_key_access"
EXPIRED_KEY_CLEANUP_INTERVAL_SECONDS = 300
_last_expired_key_cleanup_at = 0.0


# region Helpers
def _rand_b64url(n_bytes: int) -> str:
    """
    Generate a random base64 URL-safe string.

    This function generates a random string by creating a sequence of random bytes,
    encoding it into a base64 URL-safe format, and stripping padding characters.

    Parameters:
    n_bytes: int
        The number of random bytes to generate.

    Returns:
    str
        A base64 URL-safe encoded string derived from the specified number of random
        bytes.
    """
    return base64.urlsafe_b64encode(os.urandom(n_bytes)).decode().rstrip("=")


def generate_key_pair():
    """
    Generates a new key pair consisting of a key ID and a secret, as well as their
    concatenated value.

    This function creates a random key ID and secret using base64 URL encoding with
    specified lengths. It then combines them into a single string in the format of
    "key_id.secret".

    Returns:
        tuple[str, str, str]: A tuple containing the key ID, secret, and their
        concatenated value as a string.
    """
    key_id = _rand_b64url(12)
    secret = _rand_b64url(32)
    return key_id, secret, f"{key_id}.{secret}"


def hash_secret(secret: str) -> str:
    """
    Hashes a secret string using bcrypt.

    This function takes a plain text secret and securely hashes it using
    the bcrypt hashing algorithm. The resulting hash is suitable for
    secure storage and can later be used to verify the original secret
    without exposing it.

    Args:
        secret: A plain text string that needs to be hashed.

    Returns:
        The hashed representation of the provided secret as a string.
    """

    return environment.bcrypt.generate_password_hash(secret).decode()


def b64url(data: bytes) -> str:
    """
    Encodes binary data into a URL-safe Base64-encoded string.

    This function converts the provided binary data into a Base64-encoded
    string suitable for inclusion in URLs. Any padding ('=') characters
    normally added by Base64 encoding are stripped to further optimize
    the output for URL usage.

    Parameters:
    data (bytes): The binary data to be encoded.

    Returns:
    str: The URL-safe Base64-encoded string representation of the input data.
    """

    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def sign_jwt(payload: dict) -> str:
    """
    Signs a payload and generates a JWT token.

    This function creates a JSON Web Token (JWT) using the HMAC SHA-256 algorithm.
    It takes a payload dictionary, encodes it along with a predefined header, and computes
    a signature using a secret key. The resulting JWT is returned as a string, formatted
    as `header.payload.signature`.

    Args:
        payload (dict): The payload data to be included in the JWT. The payload typically
                        contains claims, which are statements about an entity (e.g., user
                        details, permissions) and any metadata relevant to the token.

    Returns:
        str: The generated JWT as a string, formatted as `header.payload.signature`.
    """

    header = {"alg": "HS256", "typ": "JWT"}
    h = b64url(json.dumps(header, separators=(",", ":")).encode())
    p = b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(JWT_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    s = b64url(sig)
    return f"{h}.{p}.{s}"


def issue_access_token(user_id: int | str, claims: dict | None = None, ttl: int = JWT_TTL) -> str:
    """
    Generates and signs a JSON Web Token (JWT) for a specified user.

    This function creates a JWT using the provided user identifier as the subject
    and sets the issued-at time (`iat`) and expiration time (`exp`) for the token
    based on the current time and a predefined token time-to-live (`JWT_TTL`). The
    generated token is then signed and returned as a string.

    Arguments:
        user_id (int | str): The unique identifier of the user for whom the token
        is being issued. This can be either an integer or a string.

    Returns:
        str: A signed JWT string that represents the issued token.
    """

    now = int(time.time())
    payload = {"sub": str(user_id), "iat": now, "exp": now + ttl}
    if claims:
        payload.update(claims)
    return sign_jwt(payload)


def issue_api_key_access_token(user_id: int | str, key_id: str, scopes: list[str] | None = None) -> str:
    return issue_access_token(
        user_id=user_id,
        claims={
            "typ": API_KEY_ACCESS_TOKEN_TYPE,
            "kid": key_id,
            "scp": scopes or [],
        },
        ttl=API_KEY_ACCESS_TOKEN_TTL,
    )


def cleanup_expired_api_keys(force: bool = False) -> int:
    """
    Deletes expired API keys from storage.

    The cleanup runs at most once per interval unless `force=True`.
    """
    global _last_expired_key_cleanup_at

    now_ts = time.time()
    if not force and (now_ts - _last_expired_key_cleanup_at) < EXPIRED_KEY_CLEANUP_INTERVAL_SECONDS:
        return 0

    _last_expired_key_cleanup_at = now_ts

    try:
        deleted_count = environment.database.fetch_one(
            """
            WITH deleted AS (
                DELETE
                FROM api_keys
                WHERE expires_at IS NOT NULL
                  AND expires_at < now()
                RETURNING 1
            )
            SELECT COUNT(*)
            FROM deleted
            """
        )[0]
    except Exception:
        logger.exception("[API] Failed to cleanup expired API keys")
        return 0

    if deleted_count:
        logger.info("[API] Deleted %s expired API key(s)", deleted_count)

    return int(deleted_count)


# endregion


# region API
def _extract_api_key_from_request() -> str | None:
    header_key = request.headers.get("X-API-Key")
    if header_key:
        return header_key.strip()

    auth = request.headers.get("Authorization", "").strip()
    if not auth:
        return None

    # Preferred format: Authorization: ApiKey <key_id.secret>
    if auth.startswith("ApiKey "):
        return auth[len("ApiKey "):].strip()

    # Backward-compatible format: Authorization: <key_id.secret>
    if " " not in auth:
        return auth

    return None


def _extract_bearer_from_request() -> str | None:
    auth = request.headers.get("Authorization", "").strip()
    if not auth.startswith("Bearer "):
        return None
    return auth[len("Bearer "):].strip()


def _json_to_dict(raw_value) -> dict:
    if raw_value is None:
        return {}
    if isinstance(raw_value, dict):
        return raw_value
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def _parse_expiry(value) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value.astimezone(dt.timezone.utc)
    if isinstance(value, str):
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.astimezone(dt.timezone.utc)
        except ValueError:
            return None
    return None


def _is_api_key_row_active(row: dict, key_id: str) -> bool:
    if row["status"] != "active":
        logger.warning("[API] key_id=%s inactive", key_id)
        return False

    if row["expires_at"] and row["expires_at"] < environment.database.now():
        logger.warning("[API] key_id=%s expired", key_id)
        return False

    return True


def _touch_api_key_usage(key_id: str):
    try:
        environment.database.execute(
            """
            UPDATE api_keys
            SET last_used_at = now(),
                last_used_ip = %s
            WHERE key_id = %s
            """,
            params=(request.remote_addr, key_id),
        )
    except Exception:
        logger.exception("[API] Failed to update usage metadata for key_id=%s", key_id)


def verify_api_key_value(combined: str, update_usage: bool = True) -> dict | None:
    cleanup_expired_api_keys()

    if "." not in combined:
        logger.warning("[API] Missing key ID/secret")
        return None
    key_id, secret = combined.split(".", 1)

    row = environment.database.fetch_to_dict(
        "SELECT key_id, user_id, secret_hash, scopes, status, expires_at, metadata FROM api_keys WHERE key_id = %s",
        params=(key_id,),
    )

    if row is None:
        logger.warning("[API] Invalid key ID")
        return None

    if not _is_api_key_row_active(row, key_id):
        return None

    if not environment.bcrypt.check_password_hash(row["secret_hash"], secret):
        logger.warning("[API] key_id=%s invalid secret", key_id)
        return None

    scopes = row.get("scopes") or []
    if isinstance(scopes, str):
        try:
            scopes = json.loads(scopes)
        except json.JSONDecodeError:
            scopes = []

    metadata = _json_to_dict(row.get("metadata"))
    row["scopes"] = scopes if isinstance(scopes, list) else []
    row["metadata"] = metadata

    if update_usage:
        _touch_api_key_usage(key_id)

    return row


def _verify_bearer_api_key_access_token(token: str) -> dict | None:
    try:
        h, p, s = token.split(".")
    except ValueError:
        return None

    signing_input = f"{h}.{p}".encode()

    def b64pad(x: str) -> str:
        return x + "=" * (-len(x) % 4)

    try:
        sig = base64.urlsafe_b64decode(b64pad(s))
        payload_raw = base64.urlsafe_b64decode(b64pad(p))
        payload = json.loads(payload_raw.decode())
    except Exception:
        return None

    expect = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expect):
        return None

    now = int(time.time())
    if payload.get("exp") is None or int(payload["exp"]) < now:
        return None

    if payload.get("typ") != API_KEY_ACCESS_TOKEN_TYPE:
        return None

    sub = payload.get("sub")
    if not sub:
        return None

    scopes = payload.get("scp") or []
    if not isinstance(scopes, list):
        scopes = []

    return {
        "user_id": str(sub),
        "scopes": scopes,
        "key_id": payload.get("kid"),
    }


def issue_api_key_tokens_from_combined_key(combined_api_key: str) -> dict | None:
    row = verify_api_key_value(combined_api_key, update_usage=True)
    if not row:
        return None

    refresh_token, refresh_expires_at = rotate_refresh_token_for_key(
        key_id=row["key_id"],
        metadata=row.get("metadata"),
    )

    return {
        "access_token": issue_api_key_access_token(
            user_id=row["user_id"],
            key_id=row["key_id"],
            scopes=row["scopes"],
        ),
        "access_expires_in": API_KEY_ACCESS_TOKEN_TTL,
        "refresh_token": refresh_token,
        "refresh_expires_in": int((refresh_expires_at - dt.datetime.now(dt.timezone.utc)).total_seconds()),
        "key_id": row["key_id"],
        "scopes": row["scopes"],
    }


def rotate_refresh_token_for_key(key_id: str, metadata: dict | None = None) -> tuple[str, dt.datetime]:
    secret = _rand_b64url(48)
    refresh_token = f"rtk.{key_id}.{secret}"
    refresh_expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=API_KEY_REFRESH_TOKEN_TTL)

    merged = _json_to_dict(metadata)
    merged["refresh_token_hash"] = hash_secret(secret)
    merged["refresh_token_expires_at"] = refresh_expires_at.isoformat()
    merged["refresh_token_rotated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()

    environment.database.execute(
        """
        UPDATE api_keys
        SET metadata = %s::jsonb
        WHERE key_id = %s
        """,
        params=(json.dumps(merged), key_id),
    )
    return refresh_token, refresh_expires_at


def refresh_api_key_tokens(refresh_token: str) -> dict | None:
    parts = refresh_token.split(".")
    if len(parts) != 3 or parts[0] != "rtk":
        return None

    _, key_id, secret = parts
    row = environment.database.fetch_to_dict(
        "SELECT key_id, user_id, scopes, status, expires_at, metadata FROM api_keys WHERE key_id = %s",
        params=(key_id,),
    )

    if row is None:
        return None
    if not _is_api_key_row_active(row, key_id):
        return None

    metadata = _json_to_dict(row.get("metadata"))
    token_hash = metadata.get("refresh_token_hash")
    token_expiry = _parse_expiry(metadata.get("refresh_token_expires_at"))

    if not token_hash or token_expiry is None:
        return None
    if token_expiry < dt.datetime.now(dt.timezone.utc):
        return None
    if not environment.bcrypt.check_password_hash(token_hash, secret):
        return None

    scopes = row.get("scopes") or []
    if isinstance(scopes, str):
        try:
            scopes = json.loads(scopes)
        except json.JSONDecodeError:
            scopes = []
    if not isinstance(scopes, list):
        scopes = []

    new_refresh_token, refresh_expires_at = rotate_refresh_token_for_key(key_id, metadata)
    _touch_api_key_usage(key_id)

    return {
        "access_token": issue_api_key_access_token(row["user_id"], key_id, scopes),
        "access_expires_in": API_KEY_ACCESS_TOKEN_TTL,
        "refresh_token": new_refresh_token,
        "refresh_expires_in": int((refresh_expires_at - dt.datetime.now(dt.timezone.utc)).total_seconds()),
        "key_id": key_id,
        "scopes": scopes,
    }


def verify_api_key_header():
    """
    Validates the API key provided in the request header.

    This function checks the presence and validity of an API key in the
    "Authorization" header of the incoming request. It ensures that the key
    matches an active entry in the database, has not expired, and the provided
    secret matches the stored hash. If the validations succeed, the function attaches
    the current user's ID and scopes to the global context for further use.

    Returns:
        str: The user ID associated with the valid API key, if validation is successful.
        None: If the validation fails.

    Raises:
        None
    """
    bearer = _extract_bearer_from_request()
    if bearer:
        token_claims = _verify_bearer_api_key_access_token(bearer)
        if token_claims:
            g.current_user_id = token_claims["user_id"]
            g.current_scopes = token_claims["scopes"]
            return g.current_user_id

    combined = _extract_api_key_from_request()
    if not combined:
        return None

    row = verify_api_key_value(combined, update_usage=True)
    if not row:
        return None

    g.current_user_id = str(row["user_id"])
    g.current_scopes = row["scopes"]
    return g.current_user_id


def require_scopes(required: list[str]):
    """
    Decorator function to enforce required scopes for access to a route or endpoint.

    This decorator ensures that the API request can only proceed if the user has
    the necessary scopes. It compares the required scopes with the current scopes
    associated with the user, which are typically retrieved from a global context.

    Attributes:
        required (list[str]): A list of scopes that are required to access the
            endpoint.

    Parameters:
        required (list[str]): Specifies the required scopes that the user must
            possess to gain access to the decorated function.

    Returns:
        Callable: A decorated function that enforces scope validation before its
        execution.

    Raises:
        401 Unauthorized: If the API key is missing or invalid, thereby failing
            to retrieve the user's ID.
        403 Forbidden: If the required scopes are not a subset of the current
            user's scopes.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            uid = verify_api_key_header()
            if not uid:
                return jsonify({"error": "unauthorized"}), 401
            have = set(g.get("current_scopes", []))
            if "admin" in have:
                return fn(*args, **kwargs)
            if not set(required).issubset(have):
                return jsonify({"error": "forbidden", "missing_scopes": list(set(required) - have)}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator
# endregion
