"""Errors raised by the IRPF activity-asset domain."""

from ....core.errors.hierarchy import CadrumoError


class ActividadAssetError(CadrumoError):
    """Base error for IRPF activity-asset contracts."""


class ActividadAssetValidationError(ActividadAssetError):
    """Raised when a lifecycle fact violates its typed contract."""


class ActividadAssetUnsupportedError(ActividadAssetError):
    """Raised when a requested asset shape has no enrolled authority."""


class ActividadAssetIncompleteError(ActividadAssetError):
    """Raised when a filing-grade schedule lacks required history."""


class ActividadAssetClaimConflictError(ActividadAssetError):
    """Raised when a replay or covered interval conflicts with claim history."""


__all__ = [
    "ActividadAssetClaimConflictError",
    "ActividadAssetError",
    "ActividadAssetIncompleteError",
    "ActividadAssetUnsupportedError",
    "ActividadAssetValidationError",
]
