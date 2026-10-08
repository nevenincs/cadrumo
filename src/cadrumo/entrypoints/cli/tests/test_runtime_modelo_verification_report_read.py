"""Registered verification-report reads retain exact-profile rendering."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.modelo.verification_report_public_facts import ModeloVerificationReportProjection
from ....application.modelo.verification_report_read_contracts import (
    MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID,
    MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID,
    ModeloVerificationReportListRequest,
    ModeloVerificationReportViewRequest,
)
from ....application.modelo.verification_report_read_projection import (
    ModeloVerificationReportListProjection,
    ModeloVerificationReportViewProjection,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    derive_verification_report_id,
)
from .. import runtime_modelo_verification_report_read as bridge
from .._modelo_payloads import VerificationReportListResult, VerificationReportShowResult
from .._modelo_rendering import verification_report_lines, verification_report_payload
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 5, 27, 10, 0, tzinfo=UTC)
_CALCULATION_REVISION_ID = "b" * 64


def _report() -> VerificationReport:
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id="0100",
        message_locale_key="application.modelo.findings.cross_casilla_invariant_violated",
        message_facts={"predicate_id": "test-predicate"},
        legal_refs=("ley-58-2003:art-119", "ley-37-1992:art-88"),
        source_refs=("aeat-modelo-303-instructions",),
    )
    findings = (finding,)
    return VerificationReport(
        verification_report_id=derive_verification_report_id(
            calculation_revision_id=_CALCULATION_REVISION_ID,
            completeness_status=VerificationCompletenessStatus.BLOCKED,
            findings=findings,
            verified_by="test-actor",
        ),
        calculation_revision_id=_CALCULATION_REVISION_ID,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="303",
            revision_id="2026-y-siguientes",
            modelo_year=2026,
            period="1T",
        ),
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=findings,
        resolved_casilla_ids=("0101",),
        missing_required_casilla_ids=("00501",),
        run_at=_NOW,
        verified_by="test-actor",
        granted_verificado_completo=False,
    )


def _context() -> typer.Context:
    return cast(typer.Context, cast(object, None))


def _bind_list(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[ModeloVerificationReportListProjection],
    submitted: list[ModeloVerificationReportListRequest],
) -> None:
    client = SimpleNamespace(profile_id=_PROFILE)
    monkeypatch.setattr(bridge, "bound_profile_client", lambda *_args, **_kwargs: client)

    def submit(actual_client: object, request: ModeloVerificationReportListRequest, **kwargs: object):
        assert actual_client is client
        submitted.append(request)
        assert kwargs["definition_id"] == MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is ModeloVerificationReportListProjection
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def _bind_view(
    monkeypatch: pytest.MonkeyPatch,
    completion: RegisteredOperationCompletion[ModeloVerificationReportViewProjection],
    submitted: list[ModeloVerificationReportViewRequest],
) -> None:
    client = SimpleNamespace(profile_id=_PROFILE)
    monkeypatch.setattr(bridge, "bound_profile_client", lambda *_args, **_kwargs: client)

    def submit(actual_client: object, request: ModeloVerificationReportViewRequest, **kwargs: object):
        assert actual_client is client
        submitted.append(request)
        assert kwargs["definition_id"] == MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is ModeloVerificationReportViewProjection
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


def test_list_submits_bound_profile_and_filter_then_uses_existing_payload_and_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _report()
    row = ModeloVerificationReportProjection.from_report(report)
    projection = ModeloVerificationReportListProjection(
        profile_id=_PROFILE,
        calculation_revision_id_filter=_CALCULATION_REVISION_ID,
        report_count=1,
        reports=(row,),
    )
    submitted: list[ModeloVerificationReportListRequest] = []
    _bind_list(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
        ),
        submitted,
    )

    result, lines = bridge.read_modelo_verification_report_list(
        _context(), calculation_revision_id=_CALCULATION_REVISION_ID
    )

    expected_payload = verification_report_payload(report)
    assert result == VerificationReportListResult(
        calculation_revision_id_filter=_CALCULATION_REVISION_ID,
        report_count=1,
        reports=[expected_payload],
    )
    assert lines == [
        "operation\tmodelo.verification_report.list",
        f"calculation_revision_id_filter\t{_CALCULATION_REVISION_ID}",
        "report_count\t1",
        "verification_report_id\tcalculation_revision_id\tcompleteness_status\tgranted\trun_at\tverified_by",
        "\t".join(
            (
                report.verification_report_id,
                report.calculation_revision_id,
                "blocked",
                "false",
                report.run_at.isoformat(),
                report.verified_by,
            )
        ),
    ]
    assert submitted == [
        ModeloVerificationReportListRequest(
            profile_id=_PROFILE,
            calculation_revision_id=_CALCULATION_REVISION_ID,
        )
    ]
    assert result.reports[0].findings[0].legal_refs == tuple(report.findings[0].legal_refs)
    assert result.reports[0].findings[0].source_refs == list(report.findings[0].source_refs)
    assert result.reports[0].missing_required_casilla_ids == list(report.missing_required_casilla_ids)


def test_view_submits_bound_profile_and_report_then_uses_existing_payload_and_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _report()
    row = ModeloVerificationReportProjection.from_report(report)
    projection = ModeloVerificationReportViewProjection(
        profile_id=_PROFILE,
        verification_report_id=report.verification_report_id,
        report=row,
    )
    submitted: list[ModeloVerificationReportViewRequest] = []
    _bind_view(
        monkeypatch,
        RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        ),
        submitted,
    )

    result, lines = bridge.read_modelo_verification_report_view(
        _context(), verification_report_id=report.verification_report_id
    )

    expected_payload = verification_report_payload(report)
    assert result == VerificationReportShowResult.model_validate(expected_payload.model_dump(mode="python"))
    assert lines == ["operation\tmodelo.verification_report.show", *verification_report_lines(report)]
    assert submitted == [
        ModeloVerificationReportViewRequest(
            profile_id=_PROFILE,
            verification_report_id=report.verification_report_id,
        )
    ]
    assert result.findings[0].legal_refs == tuple(report.findings[0].legal_refs)
    assert result.findings[0].source_refs == list(report.findings[0].source_refs)


def test_list_refuses_result_for_another_profile_as_invalid_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    row = ModeloVerificationReportProjection.from_report(_report())
    invalid = ModeloVerificationReportListProjection.model_construct(
        result_version=1,
        profile_id=_OTHER_PROFILE,
        calculation_revision_id_filter=None,
        report_count=1,
        reports=(row,),
    )
    submitted: list[ModeloVerificationReportListRequest] = []
    _bind_list(
        monkeypatch,
        RegisteredOperationCompletion(operation_id=_OPERATION_ID, projection=invalid, effect=OperationEffect.NONE),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.read_modelo_verification_report_list(_context(), calculation_revision_id=None)

    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"
    assert submitted[0].profile_id == _PROFILE


def test_view_refuses_receipt_for_different_report_id_as_invalid_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _report()
    row = ModeloVerificationReportProjection.from_report(report)
    invalid = ModeloVerificationReportViewProjection.model_construct(
        result_version=1,
        profile_id=_PROFILE,
        verification_report_id="c" * 64,
        report=row,
    )
    submitted: list[ModeloVerificationReportViewRequest] = []
    _bind_view(
        monkeypatch,
        RegisteredOperationCompletion(operation_id=_OPERATION_ID, projection=invalid, effect=OperationEffect.NONE),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.read_modelo_verification_report_view(_context(), verification_report_id=report.verification_report_id)

    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"
    assert submitted == [
        ModeloVerificationReportViewRequest(
            profile_id=_PROFILE,
            verification_report_id=report.verification_report_id,
        )
    ]


def test_list_refuses_malformed_report_row_as_invalid_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    valid = ModeloVerificationReportProjection.from_report(_report())
    bad_snapshot = valid.registry_snapshot_ref.model_construct(
        modelo="303",
        revision_id="2026-y-siguientes",
        modelo_year=2026,
        period="not-a-period",
    )
    malformed_row = valid.model_copy(update={"registry_snapshot_ref": bad_snapshot})
    invalid = ModeloVerificationReportListProjection.model_construct(
        result_version=1,
        profile_id=_PROFILE,
        calculation_revision_id_filter=None,
        report_count=1,
        reports=(malformed_row,),
    )
    submitted: list[ModeloVerificationReportListRequest] = []
    _bind_list(
        monkeypatch,
        RegisteredOperationCompletion(operation_id=_OPERATION_ID, projection=invalid, effect=OperationEffect.NONE),
        submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.read_modelo_verification_report_list(_context(), calculation_revision_id=None)

    assert refused.value.context is not None
    assert refused.value.context["reason"] == "runtime_invalid_frame"
    assert len(submitted) == 1
