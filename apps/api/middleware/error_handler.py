"""
Error handling middleware and exception classes.
"""

from typing import Any


class RevTownException(Exception):
    """Base exception for RevTown API errors."""

    def __init__(
        self,
        message: str,
        code: str = "REVTOWN_ERROR",
        status_code: int = 400,
        bead_id: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.bead_id = bead_id
        self.details = details or {}
        super().__init__(message)


class NotFoundError(RevTownException):
    """Resource not found."""

    def __init__(self, message: str, bead_id: str | None = None):
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=404,
            bead_id=bead_id,
        )


class ValidationError(RevTownException):
    """Validation error."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class AuthenticationError(RevTownException):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401,
        )


class AuthorizationError(RevTownException):
    """Authorization failed."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=403,
        )


class ConflictError(RevTownException):
    """Resource conflict (e.g., version conflict)."""

    def __init__(self, message: str, bead_id: str | None = None):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=409,
            bead_id=bead_id,
        )


class RateLimitError(RevTownException):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
        )


class QuotaExceededError(RevTownException):
    """Usage quota exceeded."""

    def __init__(self, message: str = "Usage quota exceeded"):
        super().__init__(
            message=message,
            code="QUOTA_EXCEEDED",
            status_code=402,
        )


class NeurometricError(RevTownException):
    """Error from Neurometric gateway."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            code="NEUROMETRIC_ERROR",
            status_code=502,
            details=details,
        )


class RefineryError(RevTownException):
    """Content failed Refinery checks."""

    def __init__(self, message: str, bead_id: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            code="REFINERY_FAILED",
            status_code=422,
            bead_id=bead_id,
            details=details,
        )


class WitnessError(RevTownException):
    """Witness detected consistency issues."""

    def __init__(self, message: str, bead_id: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            code="WITNESS_FAILED",
            status_code=422,
            bead_id=bead_id,
            details=details,
        )


class PolecatError(RevTownException):
    """Polecat execution error."""

    def __init__(self, message: str, polecat_id: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            code="POLECAT_ERROR",
            status_code=500,
            details={"polecat_id": polecat_id, **(details or {})},
        )
