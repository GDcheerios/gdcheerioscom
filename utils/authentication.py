def get_token(auth):
    token = auth.get("Authorization")
    if "Bearer" in token:
        return token[7:]

    return token

