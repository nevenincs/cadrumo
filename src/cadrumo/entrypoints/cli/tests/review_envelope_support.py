"""Envelope contract for the canonical modelo work review record."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_profile_storage_root,
)
from cadrumo.application.modelo.work_review import ModeloWorkReview, build_modelo_work_review
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.calculations.row_source_identity import RowSourceIdentity
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    derive_verification_report_id,
)
from cadrumo.domain.modelos.verification_repository import upsert_verification_report
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id

_NOW = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
RAW_ROW_IDENTITY = "opaque-inventory-activity-review-canary"
ROW_FINGERPRINT = "d" * 64
_ROW_BINDING_ID = "review-inventory-row"


@dataclass(frozen=True, slots=True)
class SeededBlockedReview:
    review: ModeloWorkReview
    report: VerificationReport
    objects: SecureObjectRepository
    storage_root: Path
    profile_id: UUID
    label: str


@contextmanager
def persist_blocked_review(tmp_path: Path, *, operation: PinnedAuthorityOperation) -> Generator[SeededBlockedReview]:
    """Build the application record from genuine encrypted repositories."""
    with ExitStack() as stack:
        storage_root = stack.enter_context(isolated_profile_storage_root(tmp_path=tmp_path))
        label = "review-envelope"
        bucket_id = register_cli_profile(label=label, log_in=False)
        objects = secure_object_repository_for_active_bucket()
        work_repository = WorkUnitCatalogueRepository(objects=objects)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=objects)
        verification_repository = VerificationReportCatalogueRepository(objects=objects)
        modelo = ModeloCode("130")
        filing_year = 2026
        period = Period.from_year_and_code(filing_year, "1T")
        snapshot = published_snapshot(modelo, filing_year=filing_year, period=period.registry_token)
        affected_casilla = next(casilla for casilla in snapshot.revision.casillas if casilla.legal_refs)

        work_unit_id = derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=snapshot.revision.id,
        )
        calculation_revision_id = derive_calculation_revision_id(
            work_unit_id=work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            row_binding_values={_ROW_BINDING_ID: {"1": "100"}},
            row_source_identities={
                (_ROW_BINDING_ID, 1): RowSourceIdentity(
                    source_kind=BindingSourceKind.INVENTORY,
                    source_row_identity=RAW_ROW_IDENTITY,
                    fingerprint=ROW_FINGERPRINT,
                ),
            },
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
        )
        work_unit = WorkUnit(
            work_unit_id=work_unit_id,
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=snapshot.revision.id,
            name="130-2026-1T",
            current_calculation_revision_id=calculation_revision_id,
            created_at=_NOW,
            updated_at=_NOW,
        )
        calculation_revision = CalculationRevision(
            calculation_revision_id=calculation_revision_id,
            work_unit_id=work_unit_id,
            registry_snapshot_ref=snapshot.snapshot_ref,
            state=CalculationRevisionState.BORRADOR,
            created_at=_NOW,
            updated_at=_NOW,
            filing_instance_evidence=None,
            source_provenance=(),
            row_binding_values={_ROW_BINDING_ID: {"1": "100"}},
            row_source_identities={
                (_ROW_BINDING_ID, 1): RowSourceIdentity(
                    source_kind=BindingSourceKind.INVENTORY,
                    source_row_identity=RAW_ROW_IDENTITY,
                    fingerprint=ROW_FINGERPRINT,
                ),
            },
        )
        finding = ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            casilla_id=affected_casilla.id,
            message_locale_key="application.modelo.findings.blocking_rule",
            message_facts={"casilla_id": str(affected_casilla.id)},
            legal_refs=tuple(affected_casilla.legal_refs),
            source_refs=tuple(affected_casilla.source_refs),
        )
        verification_report_id = derive_verification_report_id(
            calculation_revision_id=calculation_revision_id,
            completeness_status=VerificationCompletenessStatus.BLOCKED,
            findings=(finding,),
            verified_by="review-envelope-test",
        )
        report = VerificationReport(
            verification_report_id=verification_report_id,
            calculation_revision_id=calculation_revision_id,
            registry_snapshot_ref=snapshot.snapshot_ref,
            completeness_status=VerificationCompletenessStatus.BLOCKED,
            findings=(finding,),
            run_at=_NOW,
            verified_by="review-envelope-test",
            granted_verificado_completo=False,
        )

        work_repository.save(upsert_work_unit(work_repository.load(), work_unit))
        calculation_repository.save(
            upsert_calculation_revision(calculation_repository.load(), calculation_revision),
        )
        verification_repository.save(upsert_verification_report(verification_repository.load(), report))

        review = build_modelo_work_review(
            bucket_id,
            modelo,
            filing_year,
            period,
            work_unit_repository=work_repository,
            calculation_repository=calculation_repository,
            verification_repository=verification_repository,
            operation=operation,
        )
        yield SeededBlockedReview(review, report, objects, storage_root, UUID(bucket_id), label)
