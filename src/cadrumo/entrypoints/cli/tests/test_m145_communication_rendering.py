"""Rendering-boundary tests for Modelo 145 communication CLI output.

See Also:
    :mod:`~entrypoints.cli._modelo_m145_rendering`
        Rendering boundary under test for text lines and JSON payloads.
    :mod:`~entrypoints.cli._modelo_payloads_m145`
        Typed payload schemas returned by the renderer.
    :func:`~entrypoints.cli._common.emit_envelope`
        Central CLI envelope path used by the emitters.
    :class:`~application.modelo.M145CommunicationRecord`
        Backend record projected into mutation output.
    :class:`~application.modelo.M145CommunicationExportResult`
        Backend export DTO rendered into text and JSON output.
"""

from __future__ import annotations

from ....application.modelo.m145_communication_period import M145CommunicationPeriod

from datetime import UTC, datetime

import pytest

from ....application.modelo._m145_communication_records import (
    M145CommunicationExportResult,
    M145CommunicationRecord,
    M145CommunicationRecordState,
    M145CommunicationValidationIssue,
    M145CommunicationValidationIssueKind,
    M145CommunicationValidationResult,
)
from .._modelo_m145_rendering import (
    m145_export_result_lines,
    m145_export_result_payload,
    m145_record_result_lines,
    m145_record_result_payload,
    m145_validation_result_lines,
    m145_validation_result_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "44444444-4444-4444-8444-444444444444"
_COMMUNICATION_RECORD_ID = "a" * 64
_CREATED_AT = datetime(2026, 7, 5, 10, 30, tzinfo=UTC)


def _record() -> M145CommunicationRecord:
    return M145CommunicationRecord(
        communication_record_id=_COMMUNICATION_RECORD_ID,
        bucket_id=_BUCKET_ID,
        communication_year=2026,
        period_token=M145CommunicationPeriod.COMMUNICATION,
        revision_id="m145-2026",
        state=M145CommunicationRecordState.CREATED,
        field_values={"perceptor.nif": "12345678Z"},
        legal_refs=("boe-a-2011-208",),
        source_refs=("aeat-dr145-v20",),
        created_at=_CREATED_AT,
        note="operator note",
    )


def test_m145_record_rendering_projects_payload_and_lines() -> None:
    record = _record()

    payload = m145_record_result_payload(operation="modelo.m145.create", record=record)
    lines = m145_record_result_lines(operation="modelo.m145.create", record=record)

    assert payload.operation == "modelo.m145.create"
    assert payload.record.communication_record_id == _COMMUNICATION_RECORD_ID
    assert payload.record.state == "created"
    assert lines == [
        "operation\tmodelo.m145.create",
        f"communication_record_id\t{_COMMUNICATION_RECORD_ID}",
        f"bucket_id\t{_BUCKET_ID}",
        "modelo\t145",
        "communication_year\t2026",
        "period\tcomunicacion",
        "revision_id\tm145-2026",
        "state\tcreated",
        f"created_at\t{_CREATED_AT.isoformat()}",
        "note\toperator note",
    ]


def test_m145_validation_rendering_keeps_issue_rows_visible() -> None:
    issue = M145CommunicationValidationIssue(
        kind=M145CommunicationValidationIssueKind.MISSING_REQUIRED,
        casilla_id="perceptor.nombre",
        data_type="text",
        message="required field missing",
        legal_refs=("boe-a-2011-208",),
        source_refs=("aeat-mod145-form",),
    )
    result = M145CommunicationValidationResult(
        communication_record_id=_COMMUNICATION_RECORD_ID,
        bucket_id=_BUCKET_ID,
        communication_year=2026,
        period_token=M145CommunicationPeriod.COMMUNICATION,
        revision_id="m145-2026",
        valid=False,
        issue_count=1,
        issues=(issue,),
        legal_refs=("boe-a-2011-208",),
        source_refs=("aeat-mod145-form",),
    )

    payload = m145_validation_result_payload(result)
    lines = m145_validation_result_lines(result)

    assert payload.valid is False
    assert payload.issue_count == 1
    assert payload.issues[0].kind == "missing_required"
    assert lines == [
        "operation\tmodelo.m145.validate",
        f"communication_record_id\t{_COMMUNICATION_RECORD_ID}",
        "valid\tFalse",
        "issue_count\t1",
        "issue\tmissing_required\tperceptor.nombre\trequired field missing",
    ]


def test_m145_export_rendering_decodes_payload_once_for_text_and_json() -> None:
    result = M145CommunicationExportResult(
        communication_record_id=_COMMUNICATION_RECORD_ID,
        bucket_id=_BUCKET_ID,
        communication_year=2026,
        period_token=M145CommunicationPeriod.COMMUNICATION,
        revision_id="m145-2026",
        export_layout_id="modelo-145-dr-v20-fixed-width",
        encoding="utf-8",
        record_count=1,
        byte_length=9,
        payload_sha256="b6e7ebe9065f93e52bed04ddc0d3032b5126dc3d122ca7a5f9b31a6a1acf294d",
        payload=b"<T145010>",
        legal_refs=("boe-a-2011-208",),
        source_refs=("aeat-dr145-v20",),
    )

    payload = m145_export_result_payload(result)
    lines = m145_export_result_lines(result, payload=payload)

    assert payload.payload_text == "<T145010>"
    assert lines == [
        "operation\tmodelo.m145.export",
        f"communication_record_id\t{_COMMUNICATION_RECORD_ID}",
        "export_layout_id\tmodelo-145-dr-v20-fixed-width",
        "encoding\tutf-8",
        "record_count\t1",
        "byte_length\t9",
        f"payload_sha256\t{'b6e7ebe9065f93e52bed04ddc0d3032b5126dc3d122ca7a5f9b31a6a1acf294d'}",
        "payload_text\t<T145010>",
    ]
