"""Envelope contract for the canonical modelo work review record."""

from __future__ import annotations

import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from typer.testing import CliRunner

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.secure_object_namespaces import MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE
from ....adapters.persistence.storage.sql._orm import SecureObjectRow
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....application.modelo.work_review import ModeloWorkReview, build_modelo_work_review
from ....core.aggregation import BindingSourceKind
from ....core.json_contract import (
    EnvelopeStatus,
    SchemaEnvelope,
    derive_status,
)
from ....core.operator_action_enums import OperatorActionAxis
from ....core.period import Period
from ....domain.calculations._row_source_identity import RowSourceIdentity
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    derive_verification_report_id,
)
from ....domain.modelos.verification_repository import upsert_verification_report
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from .. import app
from .._command_schema import command_schema_types
from .._modelo_payloads import WorkReviewPayload, WorkReviewResult
from .._modelo_rendering import verification_report_notices
from .._modelo_work_review_cli import _review_lines

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_COMMAND = "modelo.work.review"
_NOW = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
_RAW_ROW_IDENTITY = "opaque-inventory-activity-review-canary"
_ROW_FINGERPRINT = "d" * 64
_ROW_BINDING_ID = "review-inventory-row"


def _orphan_row_source_identity(document: dict[str, Any]) -> None:
    revision = next(iter(document["payload"]["revisions"].values()))
    identity = revision["row_source_identities"][0]
    assert identity["source_row_identity"] == _RAW_ROW_IDENTITY
    assert identity["fingerprint"] == _ROW_FINGERPRINT
    identity["row_index"] = 2
    assert identity["source_row_identity"] == _RAW_ROW_IDENTITY
    assert identity["fingerprint"] == _ROW_FINGERPRINT


@contextmanager
def _persist_blocked_review(
    tmp_path: Path,
) -> Iterator[tuple[ModeloWorkReview, VerificationReport, SecureObjectRepository]]:
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
            row_binding_values={_ROW_BINDING_ID: {"1": "100"}},
            row_source_identities={
                (_ROW_BINDING_ID, 1): RowSourceIdentity(
                    source_kind=BindingSourceKind.INVENTORY,
                    source_row_identity=_RAW_ROW_IDENTITY,
                    fingerprint=_ROW_FINGERPRINT,
                ),
            },
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
            row_binding_values={_ROW_BINDING_ID: {"1": "100"}},
            row_source_identities={
                (_ROW_BINDING_ID, 1): RowSourceIdentity(
                    source_kind=BindingSourceKind.INVENTORY,
                    source_row_identity=_RAW_ROW_IDENTITY,
                    fingerprint=_ROW_FINGERPRINT,
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
        yield review, report, objects


def test_review_record_round_trips_through_registered_schema_envelope(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with _persist_blocked_review(tmp_path) as (review, report, objects):
        result = WorkReviewResult(review=WorkReviewPayload.from_review(review))
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
        assert result.review.casilla_count == len(review.casillas)
        assert result.review.row_source_fingerprint_count == len(review.row_source_fingerprints)
        assert round_tripped == envelope
        assert round_tripped.status is EnvelopeStatus.WARNING
        assert "casillas" not in document["result"]["review"]
        blocker = round_tripped.result.review.blockers[0]
        notice = round_tripped.notices[0]
        assert blocker.axis is OperatorActionAxis.SUPPLY_MANUAL_INPUT
        assert blocker.native_code == ModeloVerificationFindingKind.BLOCKING_RULE.value
        assert blocker.facts == {"casilla_id": review.findings[0].casilla_id}
        assert notice.context is not None
        assert notice.context["kind"] == blocker.native_code
        assert notice.context["casilla_id"] == blocker.facts["casilla_id"]
        assert document["result"]["review"]["row_source_fingerprint_count"] == 1
        rendered = f"{document!r} {envelope.model_dump_json()} {_review_lines(result)!r} {result!r}"
        assert _RAW_ROW_IDENTITY not in rendered
        assert _ROW_FINGERPRINT not in rendered
        secure_context_dump = result.model_dump(
            mode="json",
            context={"secure_calculation_revision": True, "secure_modelo_binding_value": True},
        )
        assert _RAW_ROW_IDENTITY not in repr(secure_context_dump)

        command = CliRunner().invoke(
            app,
            ["--format", "json", "app", "modelo", "work", "review", review.work_unit_id],
        )
        assert command.exit_code == 0, command.output
        command_surface = f"{command.stdout} {command.stderr} {command.exception!r}"
        assert _RAW_ROW_IDENTITY not in command_surface
        assert _ROW_FINGERPRINT not in command.stdout
        assert _RAW_ROW_IDENTITY not in caplog.text

        mutate_encrypted_secure_object_json(
            objects._engine,
            row_statement=select(SecureObjectRow).where(
                SecureObjectRow.namespace == MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.namespace,
                SecureObjectRow.object_key
                == MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.require_default_object_key(),
            ),
            mutate=_orphan_row_source_identity,
        )
        failed = CliRunner().invoke(
            app,
            ["--format", "json", "app", "modelo", "work", "review", review.work_unit_id],
        )
        assert failed.exit_code != 0
        formatted = "" if failed.exception is None else "".join(traceback.format_exception(failed.exception))
        failure_surface = f"{failed.stdout} {failed.stderr} {failed.exception!r} {formatted} {caplog.text}"
        assert _RAW_ROW_IDENTITY not in failure_surface
        assert _ROW_FINGERPRINT not in failure_surface


def test_review_payload_refuses_raw_identity_fields_without_echoing_value(tmp_path: Path) -> None:
    with _persist_blocked_review(tmp_path) as (review, _, _):
        payload = WorkReviewPayload.from_review(review).model_dump(mode="python")
        payload["row_source_identity"] = _RAW_ROW_IDENTITY

        with pytest.raises(ValidationError) as exc_info:
            WorkReviewPayload.model_validate(payload)

        rendered = f"{exc_info.value!r} {exc_info.value}"
        assert _RAW_ROW_IDENTITY not in rendered
