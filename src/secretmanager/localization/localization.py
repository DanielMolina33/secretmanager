"""Qt Linguist lookup helpers for application-owned UI messages."""

from PySide6.QtCore import QCoreApplication


def master_password_policy_text(error) -> str:
    """Localize a password policy error using its domain rule code."""
    if error.rule == "minimum":
        return QCoreApplication.translate("SecretManager", "ui.password_policy.minimum")
    if error.rule == "maximum":
        return QCoreApplication.translate("SecretManager", "ui.password_policy.maximum").replace("%1", str(error.limit))
    raise ValueError(f"Unknown master-password policy rule: {error.rule}")
