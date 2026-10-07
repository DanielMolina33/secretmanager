import unicodedata


MIN_MASTER_PASSWORD_CODE_POINTS = 12
MAX_MASTER_PASSWORD_CODE_POINTS = 64


class MasterPasswordPolicyError(ValueError):
    """A new master password failed a length rule."""

    def __init__(self, rule: str, limit: int):
        self.rule = rule
        self.limit = limit
        super().__init__(rule)


def normalize_master_password(password: str) -> str:
    """Normalize equivalent Unicode text consistently before deriving keys."""
    return unicodedata.normalize("NFC", password)


def master_password_length(password: str) -> int:
    """Count supplied Unicode code points without treating emoji specially."""
    return len(password)


def validate_new_master_password(password: str) -> str:
    """Validate a new master password and return its canonical NFC form."""
    length = master_password_length(password)
    if length < MIN_MASTER_PASSWORD_CODE_POINTS:
        raise MasterPasswordPolicyError("minimum", MIN_MASTER_PASSWORD_CODE_POINTS)
    if length > MAX_MASTER_PASSWORD_CODE_POINTS:
        raise MasterPasswordPolicyError("maximum", MAX_MASTER_PASSWORD_CODE_POINTS)
    return normalize_master_password(password)
