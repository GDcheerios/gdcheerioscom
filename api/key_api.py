import environment
import time, base64, hmac, hashlib, os, json
from flask import request, jsonify, g
from functools import wraps


JWT_SECRET = environment.secret
JWT_TTL = 3600


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


def issue_access_token(user_id: int | str) -> str:
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
    payload = {"sub": str(user_id), "iat": now, "exp": now + JWT_TTL}
    return sign_jwt(payload)


# endregion


# region API
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

    auth = request.headers.get("Authorization", "")
    combined = auth.strip()
    if "." not in combined:
        print(f"[API] Missing key ID/secret")
        return None
    key_id, secret = combined.split(".", 1)

    row = environment.database.fetch_to_dict(
        "SELECT user_id, secret_hash, scopes, status, expires_at FROM api_keys WHERE key_id = %s",
        params=(key_id,)
    )
    
    if row is None:
        print(f"[API] Invalid key ID")
        return None

    if row["status"] != "active":
        print(f"[API] {row[key_id]} inactive")
        return None

    if row["expires_at"] and row["expires_at"] < environment.database.now():
        print(f"[API] {row[key_id]} expired")
        return None

    if not environment.bcrypt.check_password_hash(row["secret_hash"], secret):
        print(f"[API] {row[key_id]} invalid secret")
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
