"""Envelope contract for the canonical modelo work review record."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....application.modelo import ModeloWorkReview, build_modelo_work_review
from ....core import EstadoCasillaOficial, OperatorActionAxis, Period
from ....core.json_contract import (
    EnvelopeStatus,
    SchemaEnvelope,
    derive_status,
)
from ....domain.calculations.registry import bundled_authority
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    WorkUnit,
    derive_calculation_revision_id,
    derive_verification_report_id,
    derive_work_unit_id,
    upsert_calculation_revision,
    upsert_verification_report,
    upsert_work_unit,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._command_schema import command_schema_types
from .._modelo_payloads import WorkReviewResult
from .._modelo_rendering import verification_report_notices

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_COMMAND = "modelo.work.review"
_NOW = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)


@contextmanager
def _persist_blocked_review(tmp_path: Path) -> Iterator[tuple[ModeloWorkReview, VerificationReport]]:
    """Build the application record from genuine encrypted repositories."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        objects = runtime.repository
        work_repository = WorkUnitCatalogueRepository(objects=objects)
        calculation_repository = CalculationRevisionCatalogueRepository(objects=objects)
        verification_repository = VerificationReportCatalogueRepository(objects=objects)
        modelo = ModeloCode("130")
        filing_year = 2026
        period = Period.from_year_and_code(filing_year, "1T")
        authority = bundled_authority()
        snapshot = authority.snapshot(modelo, filing_year=filing_year, period=period.registry_token)
        affected_casilla = next(casilla for casilla in snapshot.revision.casillas if casilla.legal_refs)

        work_unit_id = derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=snapshot.revision.id,
        )
        calculation_revision_id = derive_calculation_revision_id(
            work_unit_id=work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
        )
        work_unit = WorkUnit(
            work_unit_id=work_unit_id,
            bucket_id=_BUCKET_ID,
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
            state=CalculationRevisionState.BORRADOR,
            created_at=_NOW,
            updated_at=_NOW,
            filing_instance_evidence=None,
            source_provenance=(),
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
            _BUCKET_ID,
            modelo,
            filing_year,
            period,
            authority=authority,
            work_unit_repository=work_repository,
            calculation_repository=calculation_repository,
            verification_repository=verification_repository,
        )
        yield review, report


def test_review_record_round_trips_through_registered_schema_envelope(tmp_path: Path) -> None:
    with _persist_blocked_review(tmp_path) as (review, report):
        result = WorkReviewResult(review=review)
        notices = verification_report_notices(report)
        envelope_cls = cast(Any, SchemaEnvelope)[WorkReviewResult]
        envelope = envelope_cls(
            command=_COMMAND,
            status=derive_status(notices),
            result=result,
            notices=notices,
        )

        document = envelope.model_dump(mode="json")
        round_tripped = envelope_cls.model_validate_json(envelope.model_dump_json())

        assert command_schema_types()[_COMMAND] is WorkReviewResult
        assert result.review is review
        assert round_tripped == envelope
        assert round_tripped.status is EnvelopeStatus.WARNING
        casilla_document = document["result"]["review"]["casillas"][0]
        assert casilla_document["estado_casilla_oficial"] in {member.value for member in EstadoCasillaOficial}
        assert "official_box_" + "status" not in casilla_document
        blocker = round_tripped.result.review.blockers[0]
        notice = round_tripped.notices[0]
        assert blocker.axis is OperatorActionAxis.SUPPLY_MANUAL_INPUT
        assert blocker.native_code == ModeloVerificationFindingKind.BLOCKING_RULE.value
        assert blocker.facts == {"casilla_id": review.findings[0].casilla_id}
        assert notice.context is not None
        assert notice.context["kind"] == blocker.native_code
        assert notice.context["casilla_id"] == blocker.facts["casilla_id"]
