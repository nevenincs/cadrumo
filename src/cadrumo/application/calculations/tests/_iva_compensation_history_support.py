"""Shared builders for IVA compensation history tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from functools import cache

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.casilla_value_kind import CasillaValueKind
from ....core.iva_compensation_provenance import IvaCompensationStateProvenance
from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
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


@dataclass(frozen=True)
class _ObservedCasilla:
    """Inward fake for one numeric filed-declaration observation."""

    casilla_id: CasillaId
    value: str
    value_kind: CasillaValueKind
    source_artefact_kind: str
    source_locator: str
    confidence: float

    def decimal_value(self) -> Decimal:
        return Decimal(self.value)


@dataclass(frozen=True)
class _FiledArtefact:
    """Inward fake for the artefact metadata read by annual-summary policy."""

    kind: str
    sha256: str | None
    storage_ref: str | None = None


@dataclass(frozen=True)
class _FiledObservation:
    """Inward fake implementing the filed-observation calculation port."""

    modelo: str
    ejercicio: int
    period: Period
    expediente_id: str
    status: str
    presented_at: datetime
    authenticated_identity: str
    artefacts: tuple[_FiledArtefact, ...]
    casillas: tuple[_ObservedCasilla, ...]


@cache
def m303_registry_snapshot_ref(filing_year: int, period: str) -> RegistrySnapshotRef:
    """Return the law-selected canonical coordinate used by a test fixture."""
    return (
        bundled_authority()
        .snapshot(
            Modelo("303").value,
            filing_year=filing_year,
            period=period,
        )
        .snapshot_ref
    )


_M390_COMPENSACION_ULTIMO_PERIODO_CASILLA: CasillaId = validated_casilla_id("iva.anual.compensacion-ultimo-periodo-97")
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


def _filed_390_observation(
    *,
    last_period_compensation: Decimal,
    generated_not_in_last_period: Decimal,
) -> _FiledObservation:
    return _FiledObservation(
        modelo="390",
        ejercicio=2025,
        period=Period.from_year_and_code(2025, "0A"),
        expediente_id="200039000000001Z",
        status="filed",
        presented_at=datetime(2026, 1, 30, 12, 0, tzinfo=UTC),
        authenticated_identity=_TAXPAYER_REF,
        artefacts=(
            _FiledArtefact(
                kind="submitted_file",
                sha256="b" * 64,
            ),
        ),
        casillas=(
            _ObservedCasilla(
                casilla_id=_M390_COMPENSACION_ULTIMO_PERIODO_CASILLA,
                value=str(last_period_compensation),
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:390:97",
                confidence=1.0,
            ),
            _ObservedCasilla(
                casilla_id=_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA,
                value=str(generated_not_in_last_period),
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:390:662",
                confidence=1.0,
            ),
        ),
    )
