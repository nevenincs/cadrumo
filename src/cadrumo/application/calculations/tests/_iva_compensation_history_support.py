"""Shared builders for IVA compensation history tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from functools import cache

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.iva_compensation_provenance import IvaCompensationStateProvenance
from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.iva_compensation.carry_forward import IvaCompensationPeriodState

#: A checksum-valid synthetic NIF. ``IvaCompensationPeriodState.taxpayer_nif``
#: is a ``SubjectTaxId``, so a placeholder label is refused at the boundary
#: and the fixture must carry a real identifier shape.
_TAXPAYER_REF = "12345678Z"


@dataclass(frozen=True)
class _WalletObservation:
    """Inward fake for the wallet surface consumed by reconciliation policy."""

    taxpayer_nif: str
    target_year: int
    target_period: Period
    total_pending: Decimal
    source_url: str
    captured_at: datetime
    generation_year: int


@cache
def m303_registry_snapshot_ref(filing_year: int, period: str) -> RegistrySnapshotRef:
    """Return the law-selected canonical coordinate used by a test fixture."""
    return published_snapshot(
        Modelo("303").value,
        filing_year=filing_year,
        period=period,
    ).snapshot_ref


_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA: CasillaId = validated_casilla_id(
    "iva.anual.compensacion-generada-ejercicio-no-97"
)


def _state(
    *,
    filing_year: int,
    period: str,
    generated: Decimal = Decimal("0.00"),
    applied: Decimal = Decimal("0.00"),
    available: Decimal | None = None,
) -> IvaCompensationPeriodState:
    return IvaCompensationPeriodState(
        provenance=IvaCompensationStateProvenance.APP_FILING,
        taxpayer_nif=_TAXPAYER_REF,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        registry_snapshot_ref=m303_registry_snapshot_ref(filing_year, period),
        presented_at=datetime(filing_year + 1, 1, 20, 12, 0, tzinfo=UTC),
        prior_pending_amount=None,
        applied_amount=applied,
        pending_for_later_amount=None,
        period_result_amount=None,
        final_result_amount=None,
        generated_amount=generated,
        available_end_amount=generated if available is None else available,
        source_observation_key=f"303:{filing_year}:{period}:EXP",
    )


def _wallet(amount: Decimal, *, generation_year: int = 2022) -> _WalletObservation:
    return _WalletObservation(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        total_pending=amount,
        source_url="https://example.test/iva-compensation-wallet",
        captured_at=datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
        generation_year=generation_year,
    )
