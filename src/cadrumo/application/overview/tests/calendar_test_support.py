"""Shared production-model fixtures for overview calendar tests."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Literal, override

from pydantic import AnyHttpUrl, TypeAdapter

from cadrumo.domain.contribuyente.entity_type import EntityType
from cadrumo.domain.deadlines.models import IrpfEstimationRegime, IrpfIncomeCategory, IVARegime

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.tests.published_authority import published_selected_revision_id
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from ....domain.deadlines.engine import DeadlineEngine
from ....domain.deadlines.models import TaxpayerProfile
from ....domain.iva_compensation.filed_derivation import M303CompensationBasis
from ....domain.justificante.schema import Justificante
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....tests.aeat_literal_fixtures import aeat_url, justificante_cotejo_url
from ...calculations.observations_repository import ObservationEnvelopePayload, ResultDispositionProjection
from ...calculations.ports import (
    FiledDeclaracionArtefactProtocol,
    FiledDeclaracionObservationProtocol,
    ObservedCasillaValueProtocol,
)
from ..calendar import build_overview_calendar
from ..calendar_models import (
    OverviewCalendar,
    OverviewCalendarEvent,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
)

SOURCE_URL = aeat_url("sede", "/")
WORK_UNIT_ID = "a" * 64
CALCULATION_REVISION_ID = "b" * 64
BUCKET_ID = "7390a6bb-5577-4e08-8518-16e6292f690f"
PERIOD_2025_1T = Period.from_year_and_code(2025, "1T")
FILED_JUSTIFICANTE_STORAGE_REF = "secure-object:financial:" + "d" * 64
OBSERVED_CASILLA: CasillaId = validated_casilla_id("01", surface="overview calendar observed casilla")


@dataclass(frozen=True)
class _CalendarFiledArtefact(FiledDeclaracionArtefactProtocol):
    """Application-test fake for the artefact fields the calendar reads."""

    _kind: Literal["register_row", "submitted_file", "declaration_pdf", "justificante_pdf"]
    _sha256: str | None = None
    _storage_ref: str | None = None

    @property
    @override
    def kind(self) -> str:
        return self._kind

    @property
    @override
    def sha256(self) -> str | None:
        return self._sha256

    @property
    @override
    def storage_ref(self) -> str | None:
        return self._storage_ref


@dataclass(frozen=True)
class _CalendarFiledObservation(FiledDeclaracionObservationProtocol):
    """Application-test fake implementing the overview filed-observation port."""

    _modelo: str
    _ejercicio: int
    _period: Period
    _expediente_id: str
    _status: str
    _presented_at: datetime
    _authenticated_identity: str
    _artefacts: tuple[_CalendarFiledArtefact, ...]
    _casillas: tuple[ObservedCasillaValueProtocol, ...] = ()

    @property
    @override
    def modelo(self) -> str:
        return self._modelo

    @property
    @override
    def ejercicio(self) -> int:
        return self._ejercicio

    @property
    @override
    def period(self) -> Period:
        return self._period

    @property
    @override
    def expediente_id(self) -> str:
        return self._expediente_id

    @property
    @override
    def status(self) -> str:
        return self._status

    @property
    @override
    def presented_at(self) -> datetime:
        return self._presented_at

    @property
    @override
    def authenticated_identity(self) -> str:
        return self._authenticated_identity

    @property
    @override
    def artefacts(self) -> tuple[FiledDeclaracionArtefactProtocol, ...]:
        return self._artefacts

    @property
    @override
    def casillas(self) -> tuple[ObservedCasillaValueProtocol, ...]:
        return self._casillas

    def model_copy(self, *, update: Mapping[str, str]) -> _CalendarFiledObservation:
        unknown = set(update) - {"status", "authenticated_identity"}
        if unknown:
            raise ValueError(f"unsupported calendar observation update: {sorted(unknown)}")
        return replace(
            self,
            _status=update.get("status", self._status),
            _authenticated_identity=update.get("authenticated_identity", self._authenticated_identity),
        )


@cache
def observed_revision_id() -> str:
    """Return the law-determined revision an observation is stamped with.

    Naming that revision is revision SELECTION, resolved from the filing scope
    by law. It is not a filing operation, so it is read through the non-filing
    inspection: a filing-grade snapshot would additionally demand operator
    review of a revision no calendar test ever files.

    Resolved on first use rather than at import. Loading the registry authority
    is expensive and can fail on material unrelated to any caller, and doing it
    while the module is still importing makes that failure a COLLECTION error
    for every module that imports this one -- including modules that never touch
    a revision id. As a module-level constant this reached four test modules
    that only wanted the shared taxpayer persona.
    """
    return str(
        published_selected_revision_id("303", filing_year=2025, period=PERIOD_2025_1T.registry_token),
    )


@cache
def calendar_engine() -> DeadlineEngine:
    return DeadlineEngine()


@cache
def april_2025_range() -> OverviewCalendarRange:
    return OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30))


def calendar_with_evidence(
    *,
    events: tuple[OverviewCalendarEvent, ...],
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...],
    calendar_range: OverviewCalendarRange | None = None,
) -> OverviewCalendar:
    with bundled_indexed_authority().operation() as operation:
        return build_overview_calendar(
            profile(),
            calendar_range or april_2025_range(),
            operation=operation,
            today=date(2025, 4, 10),
            events=events,
            filing_evidence=filing_evidence,
            engine=DeadlineEngine(authority=operation),
        )


def modelo_record(
    *,
    modelo: str = "303",
    filing_year: int = 2025,
    period: Period = PERIOD_2025_1T,
    aeat_accepted: bool = False,
    external_evidence: ExternalEvidence | None = None,
    filed_by: str = "operator",
) -> ModeloRecord:
    filed_at = datetime(2025, 4, 14, 12, 0, tzinfo=UTC)
    filing_record_id = derive_filing_record_id(
        work_unit_id=WORK_UNIT_ID,
        calculation_revision_id=CALCULATION_REVISION_ID,
        filed_by=filed_by,
    )
    return ModeloRecord(
        filing_record_id=filing_record_id,
        work_unit_id=WORK_UNIT_ID,
        calculation_revision_id=CALCULATION_REVISION_ID,
        bucket_id=BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=period,
        filed_at=filed_at,
        filed_by=filed_by,
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.CONFIRMADA if aeat_accepted else AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=external_evidence,
    )


def filed_declaration_observation(
    *,
    artefacts: tuple[_CalendarFiledArtefact, ...],
    expediente_id: str = "12345678901234567890",
) -> _CalendarFiledObservation:
    return _CalendarFiledObservation(
        _modelo="303",
        _ejercicio=2025,
        _period=PERIOD_2025_1T,
        _expediente_id=expediente_id,
        _status="ALTA",
        _presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
        _authenticated_identity="X1234567L",
        _artefacts=artefacts,
    )


def filed_declaration_artefact(
    *,
    kind: Literal["register_row", "submitted_file", "declaration_pdf", "justificante_pdf"] = "justificante_pdf",
    storage_ref: str | None = FILED_JUSTIFICANTE_STORAGE_REF,
    byte_count: int = 128,
) -> _CalendarFiledArtefact:
    del byte_count
    return _CalendarFiledArtefact(
        _kind=kind,
        _sha256="d" * 64,
        _storage_ref=storage_ref,
    )


def justificante_metadata(
    *,
    csv: str = "JUST3032025X1T7",
    modelo: str = "303",
    filing_year: int = 2025,
    period: Period = PERIOD_2025_1T,
    tax_id: str = "X1234567L",
) -> Justificante:
    pdf_bytes = f"{csv}-pdf".encode()
    source_pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    return Justificante(
        csv=csv,
        modelo=modelo,
        period=period,
        ejercicio=str(filing_year),
        presentation_id=None,
        presented_at=datetime(filing_year, 4, 15, 9, 30, tzinfo=UTC),
        tax_id=tax_id,
        total_a_ingresar=None,
        total_a_devolver=None,
        verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
        source_pdf_path=Path("calendar-test-source.pdf"),
        source_pdf_sha256=source_pdf_sha256,
        parsed_at=datetime(filing_year, 4, 16, 12, 0, tzinfo=UTC),
    )


def external_evidence(
    kind: ExternalEvidenceKind,
    reference_id: str,
    *,
    imported_at: datetime | None = None,
) -> ExternalEvidence:
    return ExternalEvidence(
        kind=kind,
        reference_id=reference_id,
        imported_at=imported_at or datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
    )


def observed_casilla_observations(value: Decimal):
    return registry_grounded_observations(
        modelo="303",
        filing_year=2025,
        period="1T",
        casilla_values={OBSERVED_CASILLA: value},
    )


def calculation_observation_payload(
    *,
    source_kind: str,
    source_metadata: dict[str, str] | None = None,
    value: Decimal = Decimal("123.45"),
) -> ObservationEnvelopePayload:
    observation = RegistryModeloObservation(
        modelo="303",
        filing_year=2025,
        period="1T",
        observations=observed_casilla_observations(value),
    )
    if source_metadata is None:
        return ObservationEnvelopePayload(
            observation=observation,
            captured_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
            source_kind=source_kind,
            stamped_revision_id=observed_revision_id(),
            result_disposition=ResultDispositionProjection(
                disposition=ResultDisposition.INGRESO,
                provenance_kind="app_filing",
                provenance_locator="overview-calendar-fixture",
            ),
            m303_compensation_basis=M303CompensationBasis.RESULTADO,
        )
    return ObservationEnvelopePayload(
        observation=observation,
        captured_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
        source_kind=source_kind,
        stamped_revision_id=observed_revision_id(),
        source_metadata=source_metadata,
        result_disposition=ResultDispositionProjection(
            disposition=ResultDisposition.INGRESO,
            provenance_kind="app_filing",
            provenance_locator="overview-calendar-fixture",
        ),
        m303_compensation_basis=M303CompensationBasis.RESULTADO,
    )


def profile() -> TaxpayerProfile:
    """A declared autónomo en estimación directa."""

    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.from_registry("natural_person"),
        irpf_income_categories=frozenset({IrpfIncomeCategory.from_registry("actividad_economica")}),
        irpf_estimation_regime=IrpfEstimationRegime.from_registry("directa_normal"),
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_professionals_with_retencion=False,
        professional_income_withholding_ge_70pct=False,
        art109_activity_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        notes="overview-calendar test profile",
    )
