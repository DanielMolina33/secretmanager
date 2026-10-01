class SecretError(Exception):
    """Base exception for secret-related errors."""


class InvalidSecretNameError(SecretError):
    """Raised when a secret name is invalid."""


class DuplicateSecretError(SecretError):
    """Raised when a secret name already exists."""


class EmptySecretValueError(SecretError):
    """Raised when a secret value is empty."""