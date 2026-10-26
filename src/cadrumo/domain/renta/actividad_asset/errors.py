"""Errors raised by the IRPF activity-asset domain."""

from collections.abc import Mapping
from dataclasses import dataclass

from ....core.errors.hierarchy import CadrumoError, TerminalPreconditionErrorMixin


class ActividadAssetError(CadrumoError):
    """Base error for IRPF activity-asset contracts."""


class ActividadAssetValidationError(ActividadAssetError):
    """Raised when a lifecycle fact violates its typed contract."""


class ActividadAssetUnsupportedError(ActividadAssetError):
    """Raised when a requested asset shape has no enrolled authority."""


class ActividadAssetAcceleratedDa18DepreciationError(ActividadAssetUnsupportedError):
    """Raised when LIS DA 18 grants the tax period accelerated rather than free depreciation.

    For new electric vehicles and charging points, LIS DA 18 has granted a
    coefficient of twice the maximum linear coefficient in some tax periods
    and free depreciation in others.  Only the free regime is an amortization
    method; the accelerated one stays outside the method set, so a claim that
    falls under it is refused with this identity instead of the generic
    unenrolled-method refusal, and nothing is charged.
    """


@dataclass(frozen=True, slots=True)
class VehicleAffectationRecovery:
    """The asset revision an operator must correct with a vehicle declaration."""

    asset_id: str
    revision_id: str
    class_key: str


class ActividadAssetIncompleteError(TerminalPreconditionErrorMixin[object], ActividadAssetError):
    """Raised when a filing-grade schedule lacks required history or facts.

    A missing vehicle affectation declaration also names the revision to
    correct, so the application boundary can attach its recovery action.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        precondition_verdict: object | None = None,
        vehicle_affectation_recovery: VehicleAffectationRecovery | None = None,
    ) -> None:
        """Retain the optional correctable revision beside the error facts."""
        super().__init__(
            message,
            context=context,
            translated_message=translated_message,
            precondition_verdict=precondition_verdict,
        )
        self.vehicle_affectation_recovery = vehicle_affectation_recovery


class ActividadAssetClaimConflictError(ActividadAssetError):
    """Raised when a replay or covered interval conflicts with claim history."""


__all__ = [
    "ActividadAssetAcceleratedDa18DepreciationError",
    "ActividadAssetClaimConflictError",
    "ActividadAssetError",
    "ActividadAssetIncompleteError",
    "ActividadAssetUnsupportedError",
    "ActividadAssetValidationError",
    "VehicleAffectationRecovery",
]
