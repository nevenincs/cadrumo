"""Application-owned capability for IVA compensation history persistence."""

from __future__ import annotations

from typing import Protocol

from ...core.period import Period
from ...core.secure_object_write import SecureObjectWrite
from ...domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from .errors import IvaCompensationModeloError
from .observations_repository import CalculationObservationStorageProtocol


class IvaCompensationHistoryPersistenceError(IvaCompensationModeloError):
    """Translated persistence failure at the IVA-history boundary."""


class IvaCompensationHistoryRepositoryProtocol(Protocol):
    """Required bucket-bound capability for IVA compensation period states."""

    def load_period(self, period: Period) -> IvaCompensationPeriodState | None:
        """Load one period state, or return ``None`` when absent."""
        ...

    def save_period(self, state: IvaCompensationPeriodState) -> None:
        """Persist one period state."""
        ...

    def list_periods(self) -> tuple[IvaCompensationPeriodState, ...]:
        """Return all period states in chronological order."""
        ...

    def to_secure_object_write(
        self,
        state: IvaCompensationPeriodState,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Prepare one history write for an atomic outer co-commit."""
        ...

    @property
    def secure_object_repository(self) -> CalculationObservationStorageProtocol:
        """Return the storage capability used for co-commit."""
        ...


__all__ = [
    "IvaCompensationHistoryPersistenceError",
    "IvaCompensationHistoryRepositoryProtocol",
]
