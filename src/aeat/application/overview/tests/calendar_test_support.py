"""Shared production-model fixtures for overview calendar tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, TypeAdapter

from ....adapters.outbound.aeat.sede._schema import FiledDeclaracionArtefact, FiledDeclaracionObservation
from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import CasillaId, RegistryModeloObservation, validated_casilla_id
from ....domain.deadlines import (
    DeadlineEngine,
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    TaxpayerProfile,
)
from ....domain.justificante import Justificante
from ....domain.modelos import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloCode,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ....tests.aeat_literal_fixtures import aeat_url, justificante_cotejo_url
from ....tests.registry_observations import registry_grounded_observations
from ...calculations import CalculationObservationRepository
from .. import (
    OverviewCalendar,
    OverviewCalendarEvent,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
    build_overview_calendar,
)

SOURCE_URL = aeat_url("sede", "/")
WORK_UNIT_ID = "a" * 64
CALCULATION_REVISION_ID = "b" * 64
BUCKET_ID = "7390a6bb-5577-4e08-8518-16e6292f690f"
PERIOD_2025_1T = Period.from_year_and_code(2025, "1T")
FILED_JUSTIFICANTE_STORAGE_REF = "secure-object:financial:" + "d" * 64
OBSERVED_CASILLA: CasillaId = validated_casilla_id("01", surface="overview calendar observed casilla")
OBSERVED_REVISION_ID = str(
    resources().modelos.authority.snapshot("303", filing_year=2025, period=PERIOD_2025_1T.registry_token).revision.id,
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
    return build_overview_calendar(
        profile(),
        calendar_range or april_2025_range(),
        today=date(2025, 4, 10),
        events=events,
        filing_evidence=filing_evidence,
        engine=calendar_engine(),
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
        filed_at=filed_at,
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
        aeat_accepted=aeat_accepted,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=external_evidence,
    )


def filed_declaration_observation(
    *,
    artefacts: tuple[FiledDeclaracionArtefact, ...],
    expediente_id: str = "12345678901234567890",
) -> FiledDeclaracionObservation:
    return FiledDeclaracionObservation(
        modelo="303",
        ejercicio=2025,
        period=PERIOD_2025_1T,
        expediente_id=expediente_id,
        status="ALTA",
        presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
        authenticated_identity="X1234567L",
        artefacts=artefacts,
    )


def filed_declaration_artefact(
    *,
    kind: Literal["register_row", "submitted_file", "declaration_pdf", "justificante_pdf"] = "justificante_pdf",
    storage_ref: str | None = FILED_JUSTIFICANTE_STORAGE_REF,
    byte_count: int = 128,
) -> FiledDeclaracionArtefact:
    return FiledDeclaracionArtefact(
        kind=kind,
        source_url=AnyHttpUrl(SOURCE_URL),
        content_type="application/pdf",
        byte_count=byte_count,
        sha256="d" * 64,
        captured_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
        storage_ref=storage_ref,
    )


def justificante_metadata(
    *,
    csv: str = "JUST-303-2025-1T",
    modelo: str = "303",
    filing_year: int = 2025,
    period: Period = PERIOD_2025_1T,
    tax_id: str = "X1234567L",
) -> Justificante:
    pdf_bytes = f"{csv}-pdf".encode()
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
        source_pdf_path=Path("var") / "justificantes" / f"{csv}.pdf",
        source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
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
) -> object:
    observation = RegistryModeloObservation(
        modelo="303",
        filing_year=2025,
        period="1T",
        observations=observed_casilla_observations(value),
    )
    if source_metadata is None:
        return CalculationObservationRepository.payload_type(
            observation=observation,
            captured_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
            source_kind=source_kind,
            stamped_revision_id=OBSERVED_REVISION_ID,
        )
    return CalculationObservationRepository.payload_type(
        observation=observation,
        captured_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
        source_kind=source_kind,
        stamped_revision_id=OBSERVED_REVISION_ID,
        source_metadata=source_metadata,
    )


def profile() -> TaxpayerProfile:
    """A declared autónomo en estimación directa."""

    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_professionals_with_retencion=False,
        professional_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        notes="overview-calendar test profile",
    )
