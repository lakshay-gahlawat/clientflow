"""
Shared application exceptions. Kept intentionally small for now —
expanded in Phase 13 (error handling) once real endpoints exist.
"""


class ClientFlowError(Exception):
    """Base exception for all application-raised errors."""


class NotFoundError(ClientFlowError):
    pass


class PermissionDeniedError(ClientFlowError):
    pass


class ValidationFailedError(ClientFlowError):
    pass
