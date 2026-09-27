"""One authored sealed revision the calculation-report tests build reports from.

The snapshot, the casilla definitions and their legal and source references come
from the published authority, so row identity, section order and grounding are
the registry's rather than a fixture's. The revision is authored here because the
subject is the projection, not the engine: the facts a persisted revision carries
-- realised observations, absent-by-design markers, resolver source traces -- are
each set explicitly so the report's treatment of them is observable.

:func:`fixture_report_digest` exists so determinism can be measured across
PROCESSES and not only across calls: it opens its own authority operation and
returns the report's digest, which a second interpreter can produce
independently. Every input it feeds the builder is a constant of this module, so
a disagreement between two processes is a determinism defect in the builder
rather than a difference in what was asked of it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import SecretBytes

from ....core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ....core.casilla_id import CasillaId
from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.filing.software_identity import AeatSoftwareIdentityGrade
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    CalculationSourceRef,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.verification_report import VerificationCompletenessStatus
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..calculation_report import ModeloCalculationReport, build_modelo_calculation_report
from ..calculation_report_provenance_key import CalculationReportProvenanceKey
from ..work_review import build_modelo_work_review_casillas

BUCKET_ID = "22222222-2222-4222-8222-222222222222"
MODELO = ModeloCode("130")
FILING_YEAR = 2026
PERIOD_CODE = "1T"
EXPORTED_AT = datetime(2026, 4, 12, 8, 0, tzinfo=UTC)
GENERATION = "b" * 64
VERIFICATION_REPORT_ID = "c" * 64
FILING_RECORD_ID = "d" * 64
TAXPAYER_TAX_ID = "00000001R"
TAXPAYER_NAME = "Perez Ruiz Ana"
MEASURED_CASILLA: CasillaId = "01"
ZERO_CASILLA: CasillaId = "02"
NOT_APPLICABLE_CASILLA: CasillaId = "05"
SOURCE_REF = "collectible_invoice:0e6f5b1a"
SOURCE_FINGERPRINT = "e" * 64

#: A synthetic checksum-shaped NIF standing in for a perceptor's identifier. The
#: retenciones resolver builds a source reference as ``perceptor:{nif}``, so a
#: revision can persist a THIRD PARTY's tax identity in its provenance; the value
#: here is a fixture, never a real identity.
PERCEPTOR_NIF = "12345678Z"
PERCEPTOR_SOURCE_REF = f"perceptor:{PERCEPTOR_NIF}"

#: A reference carrying a bare identifier and no family token at all. The shipped
#: resolvers all prefix a family, so this is the shape the report must refuse to
#: print rather than one it expects to meet.
UNFAMILIED_SOURCE_REF = PERCEPTOR_NIF

#: Fixed key material so two processes derive identical provenance digests. A real
#: key is derived from the profile's signing key and never written down.
FIXTURE_PROVENANCE_KEY = CalculationReportProvenanceKey(
    bucket_id=BUCKET_ID,
    key=SecretBytes(bytes(range(32))),
)


def fixture_snapshot(operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    """Resolve the published snapshot the fixture revision is calculated against."""
    period = Period.from_year_and_code(FILING_YEAR, PERIOD_CODE)
    selected = operation.revision_for_context(
        str(MODELO),
        filing_year=FILING_YEAR,
        period=period.registry_token,
    )
    return operation.snapshot(
        str(MODELO),
        filing_year=FILING_YEAR,
        period=period.registry_token,
        revision_id=selected.id,
        grade=selected.effective_authority_grade,
    )


def fixture_work_unit(snapshot: RegistrySnapshot) -> WorkUnit:
    """Build the work unit the fixture revision belongs to."""
    period = Period.from_year_and_code(FILING_YEAR, PERIOD_CODE)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=BUCKET_ID,
            modelo=MODELO,
            filing_year=FILING_YEAR,
            period=period,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=BUCKET_ID,
        modelo=MODELO,
        filing_year=FILING_YEAR,
        period=period,
        revision_id=snapshot.revision.id,
        name="report-builder",
        created_at=EXPORTED_AT,
        updated_at=EXPORTED_AT,
    )


def source_trace(source_ref: str, *, fingerprint: str | None = SOURCE_FINGERPRINT) -> CalculationSourceRef:
    """Build one persisted resolver trace naming the measured casilla."""
    return CalculationSourceRef(
        resolver_id="ledger_renta_income_aggregation",
        resolved_binding_source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        contributor_source_kind=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION.value,
        contributor_binding_source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        lineage_role=CalculationSourceLineageRole.PRIMARY,
        source_ref=source_ref,
        parent_source_ref=None,
        fingerprint=fingerprint,
        source_casilla_ids=(MEASURED_CASILLA,),
    )


def _observation(
    snapshot: RegistrySnapshot,
    casilla_id: CasillaId,
    value: Decimal,
    *,
    absent: bool,
) -> CasillaObservation:
    """Build one observation whose grounding is the registry's own for that casilla."""
    definition = next(casilla for casilla in snapshot.revision.casillas if casilla.id == casilla_id)
    return CasillaObservation(
        casilla_id=casilla_id,
        value=value,
        legal_refs=definition.legal_refs,
        source_refs=definition.source_refs,
        absent_by_design=absent,
    )


def fixture_revision(
    snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    *,
    source_provenance: tuple[CalculationSourceRef, ...] | None = None,
) -> CalculationRevision:
    """Author one sealed revision realising a value, a zero and an absence by design."""
    casilla_values = {
        MEASURED_CASILLA: Decimal("10000.00"),
        ZERO_CASILLA: Decimal("0.00"),
        NOT_APPLICABLE_CASILLA: Decimal("0"),
    }
    observations = (
        _observation(snapshot, MEASURED_CASILLA, casilla_values[MEASURED_CASILLA], absent=False),
        _observation(snapshot, ZERO_CASILLA, casilla_values[ZERO_CASILLA], absent=False),
        _observation(snapshot, NOT_APPLICABLE_CASILLA, casilla_values[NOT_APPLICABLE_CASILLA], absent=True),
    )
    provenance = (source_trace(SOURCE_REF),) if source_provenance is None else source_provenance
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values=casilla_values,
            source_provenance=provenance,
            filing_instance_evidence=None,
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=str(MODELO),
            revision_id=snapshot.revision.id,
            modelo_year=FILING_YEAR,
            period=PERIOD_CODE,
        ),
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        casilla_values=casilla_values,
        observations=observations,
        source_provenance=provenance,
        filing_instance_evidence=None,
        created_at=EXPORTED_AT,
        updated_at=EXPORTED_AT,
        verified_at=EXPORTED_AT,
        verified_by="operator",
    )


def build_fixture_report(
    operation: PinnedAuthorityOperation,
    *,
    source_provenance: tuple[CalculationSourceRef, ...] | None = None,
    report_language: OutputLanguage = OutputLanguage.ES,
    exported_at: datetime = EXPORTED_AT,
    provenance_key: CalculationReportProvenanceKey = FIXTURE_PROVENANCE_KEY,
) -> tuple[ModeloCalculationReport, RegistrySnapshot]:
    """Build the fixture revision's calculation report and return it with its snapshot."""
    snapshot = fixture_snapshot(operation)
    work_unit = fixture_work_unit(snapshot)
    revision = fixture_revision(snapshot, work_unit, source_provenance=source_provenance)
    report = build_modelo_calculation_report(
        revision=revision,
        work_unit=work_unit,
        review_casillas=build_modelo_work_review_casillas(
            snapshot=snapshot,
            revision=revision,
            operation=operation,
        ),
        taxpayer_tax_id=TAXPAYER_TAX_ID,
        taxpayer_name=TAXPAYER_NAME,
        verification_report_id=VERIFICATION_REPORT_ID,
        verification_outcome=VerificationCompletenessStatus.COMPLETE,
        filing_record_id=FILING_RECORD_ID,
        authority_logical_generation=GENERATION,
        software_identity_grade=AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK,
        provenance_key=provenance_key,
        report_language=report_language,
        exported_at=exported_at,
    )
    return report, snapshot


def fixture_report_digest() -> str:
    """Return the fixture report's digest, opening this process's own authority.

    Called both in-process and from a second interpreter, which is what turns
    byte determinism from a claim about one run into a measurement across runs.
    """
    with bundled_indexed_authority().operation() as operation:
        report, _snapshot = build_fixture_report(operation)
        return report.report_sha256


__all__ = [
    "BUCKET_ID",
    "EXPORTED_AT",
    "FILING_RECORD_ID",
    "FILING_YEAR",
    "FIXTURE_PROVENANCE_KEY",
    "GENERATION",
    "MEASURED_CASILLA",
    "MODELO",
    "NOT_APPLICABLE_CASILLA",
    "PERCEPTOR_NIF",
    "PERCEPTOR_SOURCE_REF",
    "PERIOD_CODE",
    "SOURCE_FINGERPRINT",
    "SOURCE_REF",
    "TAXPAYER_NAME",
    "TAXPAYER_TAX_ID",
    "UNFAMILIED_SOURCE_REF",
    "VERIFICATION_REPORT_ID",
    "ZERO_CASILLA",
    "build_fixture_report",
    "fixture_report_digest",
    "fixture_revision",
    "fixture_snapshot",
    "fixture_work_unit",
    "source_trace",
]
