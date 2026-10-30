"""In-memory history and register authority for activity-asset application tests."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date, datetime
from functools import cache

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetEdition
from cadrumo.application.actividad_asset.disposal_calculation import pinned_disposal_bounds
from cadrumo.application.actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from cadrumo.application.actividad_asset.operations import ActivityAssetRegisterAuthority
from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.actividad_asset_bindings import (
    ActivityAssetDisposalBounds,
    resolve_activity_asset_class_labels,
    resolve_activity_asset_schedule_authority,
)
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.ledger_renta_gastos_estimacion_directa_bindings import (
    activity_asset_amortization_casillas,
)
from cadrumo.domain.calculations.registry.ledger_renta_gastos_pago_fraccionado_bindings import (
    renta_gastos_pago_fraccionado_target_casilla,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import LegalReference
from cadrumo.domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue
from cadrumo.domain.contribuyente.tax_residence import ResidenceTerritory
from cadrumo.domain.renta.actividad_asset.claims import AmortizationClaim
from cadrumo.domain.renta.actividad_asset.election import DirectEstimationRegime
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetClaimConflictError
from cadrumo.domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from cadrumo.domain.renta.actividad_asset.schedule import ScheduleAuthority


class MemoryRepository:
    """Apply the real history rules to a document held in memory."""

    def __init__(self) -> None:
        """Start from the empty document."""
        self.history = ActivityAssetHistory()

    def load(self) -> ActivityAssetHistory:
        """Return the held document."""
        return self.history

    def append_revision(self, revision: ActivityAssetRevision) -> ActivityAssetHistory:
        """Append one revision."""
        self.history = self.history.append_revision(revision)
        return self.history

    def apply(self, mutation: Callable[[ActivityAssetHistory], ActivityAssetHistory]) -> ActivityAssetHistory:
        """Apply one change to the held document."""
        self.history = mutation(self.history)
        return self.history

    def record_claim(
        self,
        claim: AmortizationClaim,
        *,
        expected_history: ActivityAssetHistory | None = None,
        recorded_at: datetime | None = None,
    ) -> ActivityAssetHistoryClaimResult:
        """Record one claim, refusing a document that moved under its forecast."""
        if expected_history is not None and not self.history.same_tax_facts(expected_history):
            raise ActividadAssetClaimConflictError(
                translated_message="ledger.actividad_asset.errors.history_changed_after_forecast",
            )
        result = self.history.record_claim(claim, recorded_at=recorded_at)
        self.history = result.history
        return result


@cache
def _published_modelo_100() -> ModeloRevision:
    with bundled_indexed_authority().operation() as operation:
        return operation.revision_for_context("100", filing_year=2025, period="0A")


def _published_m130_box(period: Period) -> CasillaId:
    with bundled_indexed_authority().operation() as operation:
        return renta_gastos_pago_fraccionado_target_casilla(
            operation.revision_for_context("130", filing_year=period.filing_year, period=period.registry_token),
            modelo="130",
        )


@cache
def _published_support() -> SupportedFilingYearsCatalogue:
    with bundled_indexed_authority().operation() as operation:
        return operation.supported_filing_years()


def _published_authority(revision: ActivityAssetRevision, tax_year: int) -> ScheduleAuthority:
    with bundled_indexed_authority().operation() as operation:
        return resolve_activity_asset_schedule_authority(
            operation.revision_for_context("100", filing_year=tax_year, period="0A"),
            tax_year=tax_year,
            asset_revision=revision,
            authority_generation="register-support",
            workforce=(),
            legal_reference=operation.legal_reference,
        )


def _published_class_labels(regime: DirectEstimationRegime, tax_year: int) -> Mapping[str, str]:
    with bundled_indexed_authority().operation() as operation:
        return resolve_activity_asset_class_labels(operation, regime=regime, tax_year=tax_year)


def _published_legal_reference(reference_id: str) -> LegalReference:
    with bundled_indexed_authority().operation() as operation:
        return operation.legal_reference(reference_id)


def _published_disposal_bounds(revision: ActivityAssetRevision, tax_year: int) -> ActivityAssetDisposalBounds:
    with bundled_indexed_authority().operation() as operation:
        return pinned_disposal_bounds(operation)(revision, tax_year)


def memory_register_authority(
    *,
    today: date = date(2025, 12, 31),
    consumers: Mapping[str, tuple[str, ...]] | None = None,
    territory: ResidenceTerritory = ResidenceTerritory.COMMON,
    last_admitted_year: int | None = None,
) -> ActivityAssetRegisterAuthority:
    """Answer the register's profile and edition questions with fixed facts."""

    def claim_consumers(claim_ids: Iterable[str]) -> Mapping[str, tuple[str, ...]]:
        if consumers is None:
            return {claim_id: () for claim_id in claim_ids}
        return {claim_id: consumers.get(claim_id, ()) for claim_id in claim_ids}

    return ActivityAssetRegisterAuthority(
        edition=lambda tax_year: (
            ActivityAssetEdition(
                revision_id=_published_modelo_100().id,
                authored_filing_year=2025,
                projected=tax_year != 2025,
            ),
            _published_modelo_100(),
        ),
        admits_filing_year=_published_support().admits_filing_year,
        m130_amortization_casilla=_published_m130_box,
        m100_amortization_casillas=lambda _year: activity_asset_amortization_casillas(_published_modelo_100()),
        last_admitted_year=lambda: last_admitted_year or max(today.year, _published_support().horizon),
        agrarian_activities=lambda _on: frozenset(),
        residence_territory=lambda _on: territory,
        claim_consumers=claim_consumers,
        today=lambda: today,
        schedule_authority=_published_authority,
        disposal_bounds=_published_disposal_bounds,
        class_labels=_published_class_labels,
        legal_reference=_published_legal_reference,
    )


def describing(revision: ActivityAssetRevision | None = None) -> ActivityAssetDescriptorFacts:
    """State the minimum descriptor a creation requires."""
    return ActivityAssetDescriptorFacts(name="Element" if revision is None else revision.asset_id)
