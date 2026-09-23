"""Encrypted adapter for the IVA compensation-history application port.

Core types:
:class:`~cadrumo.core.classification.policies.SensitivityClass`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar, override

from pydantic import BaseModel

from ....application.calculations.errors import IvaCompensationModeloError
from ....application.calculations.iva_compensation_history import (
    iva_compensation_period_key,
    require_iva_compensation_period_coordinates_current,
)
from ....application.calculations.iva_compensation_history_ports import (
    IvaCompensationHistoryPersistenceError,
    IvaCompensationHistoryRepositoryProtocol,
)
from ....application.calculations.observations_repository import CalculationObservationStorageProtocol
from ....core.classification.policies import SensitivityClass
from ....core.period import Period
from ....core.secure_object_write import SecureObjectWrite
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.iva_compensation.carry_forward import IvaCompensationPeriodState, iva_compensation_period_sort_key
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.secure_object_namespaces import IVA_COMPENSATION_HISTORY_NAMESPACE


def _call_storage[T](operation: str, callback: Callable[[], T]) -> T:
    """Translate adapter failures into the application-owned error contract."""
    try:
        return callback()
    except (IvaCompensationHistoryPersistenceError, IvaCompensationModeloError):
        raise
    except Exception as exc:
        raise IvaCompensationHistoryPersistenceError(
            translated_message="application.calculations.iva_compensation.errors.persistence",
            context={"operation": operation, "cause_type": type(exc).__name__},
        ) from exc


class IvaCompensationHistoryRepository(
    SecureBoundRepository[IvaCompensationPeriodState],
    IvaCompensationHistoryRepositoryProtocol,
):
    """Bind IVA compensation period states to encrypted profile storage."""

    namespace: ClassVar[str] = IVA_COMPENSATION_HISTORY_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = IVA_COMPENSATION_HISTORY_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = IVA_COMPENSATION_HISTORY_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = IvaCompensationPeriodState

    @override
    def extract_identifier(self, payload: IvaCompensationPeriodState) -> str:
        return iva_compensation_period_key(payload.period)

    @property
    @override
    def secure_object_repository(self) -> CalculationObservationStorageProtocol:
        """Expose the storage capability required for atomic co-commit."""
        return self._objects

    @override
    def load_period(self, period: Period) -> IvaCompensationPeriodState | None:
        """Load one period and re-confirm its registry coordinate."""
        return _call_storage("load", lambda: self._load_period(period))

    def _load_period(self, period: Period) -> IvaCompensationPeriodState | None:
        # A stored period validates its taxpayer identity against registry
        # vocabulary, so the decode itself needs the authority, not only the
        # coordinate check after it.
        with bundled_indexed_authority().operation() as operation:
            state = self.load(iva_compensation_period_key(period))
            if state is not None:
                require_iva_compensation_period_coordinates_current(state, operation=operation)
        return state

    @override
    def save_period(self, state: IvaCompensationPeriodState) -> None:
        """Persist one validated period state."""
        _call_storage("save", lambda: self.save(state))

    @override
    def list_periods(self) -> tuple[IvaCompensationPeriodState, ...]:
        """Load and sort all persisted period states."""

        def _list() -> tuple[IvaCompensationPeriodState, ...]:
            with bundled_indexed_authority().operation() as operation:
                states = tuple(
                    sorted(
                        self.iter_records(),
                        key=lambda item: (item.filing_year, iva_compensation_period_sort_key(item.period)),
                    ),
                )
                for state in states:
                    require_iva_compensation_period_coordinates_current(state, operation=operation)
            return states

        return _call_storage("list", _list)

    @override
    def to_secure_object_write(
        self,
        payload: IvaCompensationPeriodState,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Prepare one encrypted history write without committing it."""

        def _prepare() -> SecureObjectWrite:
            return super(IvaCompensationHistoryRepository, self).to_secure_object_write(
                payload,
                expected_revision_id=expected_revision_id,
            )

        return _call_storage("prepare", _prepare)


__all__ = ["IvaCompensationHistoryRepository"]
