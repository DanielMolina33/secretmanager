import secrets


KEY_SIZE = 32


def generate_dek() -> bytes:
    return secrets.token_bytes(KEY_SIZE)