"""Document-link resolution under the minimal-scope posture (follow-up contract).

The integration deliberately requests only the non-sensitive ``drive.file``
scope. This gate locks the resolver's contract offline, with no network:

- ``parse_drive_file_id`` recovers a Drive file id from the three recorded link
  shapes (``/file/d/<id>``, ``?id=<id>``, bare id) and returns ``None`` otherwise;
- the Drive download path preserves Google ``files.get_media`` byte payloads;
- Gmail links, arbitrary external URLs, and ``drive.file``-unreachable Drive files
  are refused with a typed scope error naming the sensitive scope the operator
  would need to grant — never silently swallowed.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from .....core import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .....domain.attachments import AttachmentSource
from ...storage import (
    OutboundStorageNetworkError,
    OutboundStoragePermissionError,
    OutboundStorageValidationError,
)
from .._document_link_resolver import _download_drive_file_from_service, parse_drive_file_id, resolve_document_link
from .drive_media_server import drive_media_endpoint

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_FILE_ID = "1AbcDEfgHIjkLMnoPQRstuVWxyz12345"


def _assert_closed_outcome(
    error: BaseException,
    *,
    condition_id: str,
    facts: dict[str, str | int | bool],
    outcome: NoRecoveryOutcome,
) -> None:
    """Assert the adapter emitted one fact-only, non-actionable terminal verdict."""
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == condition_id
    assert len(verdict.evidence) == 1
    evidence = verdict.evidence[0]
    assert evidence.condition_id == condition_id
    assert evidence.evidence_id == f"{condition_id}.observation"
    assert evidence.provenance is ActionEvidenceProvenance.RUNTIME_OBSERVATION
    assert evidence.values == facts
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.missing_argument_names == ()
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is outcome


def test_parse_drive_file_id_accepts_recorded_shapes_and_rejects_non_ids() -> None:
    cases: tuple[tuple[str, str, str | None], ...] = (
        ("drive file URL", f"https://drive.google.com/file/d/{_FILE_ID}/view", _FILE_ID),
        ("drive open URL", f"https://drive.google.com/open?id={_FILE_ID}", _FILE_ID),
        ("docs spreadsheet URL", f"https://docs.google.com/spreadsheets/d/{_FILE_ID}/edit#gid=0", _FILE_ID),
        ("bare id", _FILE_ID, _FILE_ID),
        ("padded bare id", "  " + _FILE_ID + "  ", _FILE_ID),
        ("hyphenated non-id token", "not-a-drive-reference", None),
        ("short token", "short", None),
        ("empty reference", "", None),
    )

    for label, reference, expected in cases:
        assert parse_drive_file_id(reference) == expected, label


def test_unresolvable_remote_sources_name_required_sensitive_scope() -> None:
    cases: tuple[tuple[AttachmentSource, str, str], ...] = (
        (AttachmentSource.GMAIL, "anything", "https://www.googleapis.com/auth/gmail.readonly"),
        (
            AttachmentSource.URL,
            "https://example.com/justificante.pdf",
            "https://www.googleapis.com/auth/drive.readonly",
        ),
    )

    for source, reference, required_scope in cases:
        with pytest.raises(OutboundStoragePermissionError) as excinfo:
            resolve_document_link(source=source, reference=reference, credentials=None)
        assert excinfo.value.context is not None, source.value
        assert excinfo.value.context["required_scope"] == required_scope
        _assert_closed_outcome(
            excinfo.value,
            condition_id="google.document_link.source_scope_sufficient",
            facts={"source": source.value, "required_scope": required_scope, "scope_sufficient": False},
            outcome=NoRecoveryOutcome.SAFETY,
        )


def test_non_resolvable_inputs_are_validation_errors() -> None:
    cases: tuple[tuple[AttachmentSource, str, str, dict[str, str | int | bool]], ...] = (
        (
            AttachmentSource.LOCAL_FILE,
            "local-store/x.pdf",
            "google.document_link.remote_source_supported",
            {"source": AttachmentSource.LOCAL_FILE.value, "remote_source_supported": False},
        ),
        (
            AttachmentSource.GOOGLE_DRIVE,
            "no-id-here",
            "google.document_link.drive_reference_identified",
            {"source": AttachmentSource.GOOGLE_DRIVE.value, "reference_identified": False},
        ),
    )

    for source, reference, condition_id, facts in cases:
        with pytest.raises(OutboundStorageValidationError) as excinfo:
            resolve_document_link(source=source, reference=reference, credentials=None)
        _assert_closed_outcome(
            excinfo.value,
            condition_id=condition_id,
            facts=facts,
            outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )


def test_missing_google_api_client_is_a_closed_safety_outcome() -> None:
    """A fresh interpreter proves the optional-client import refusal without a patch seam."""
    script = """
import importlib.abc
import json
import sys

from cadrumo.adapters.outbound.google._document_link_resolver import _drive_service
from cadrumo.adapters.outbound.storage import OutboundStorageNetworkError


class _MissingGoogleApiFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == \"googleapiclient\" or fullname.startswith(\"googleapiclient.\"):
            raise ModuleNotFoundError(fullname)
        return None


finder = _MissingGoogleApiFinder()
sys.meta_path.insert(0, finder)
try:
    _drive_service(None)
except OutboundStorageNetworkError as error:
    verdict = error.terminal_precondition_verdict
else:
    raise AssertionError(\"the unavailable client did not refuse\")
finally:
    sys.meta_path.remove(finder)

assert verdict is not None
assert len(verdict.evidence) == 1
evidence = verdict.evidence[0]
print(json.dumps({
    \"condition_id\": verdict.failed_condition_id,
    \"evidence_condition_id\": evidence.condition_id,
    \"evidence_id\": evidence.evidence_id,
    \"provenance\": evidence.provenance.value,
    \"values\": dict(evidence.values),
    \"action\": verdict.action,
    \"conditionality\": verdict.conditionality.value,
    \"outcome\": verdict.no_recovery_outcome.value,
}))
"""
    completed = subprocess.run(
        (sys.executable, "-c", script),
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "condition_id": "google.document_link.api_client_available",
        "evidence_condition_id": "google.document_link.api_client_available",
        "evidence_id": "google.document_link.api_client_available.observation",
        "provenance": "runtime_observation",
        "values": {"client_available": False, "dependency": "google_api_python_client"},
        "action": None,
        "conditionality": "not_applicable",
        "outcome": "safety",
    }


def test_drive_download_preserves_google_media_bytes() -> None:
    payload = b"%PDF-1.4 justificante bytes"

    with drive_media_endpoint(payload=payload) as endpoint:
        out = _download_drive_file_from_service(_FILE_ID, endpoint.service)

    assert out == payload
    assert endpoint.requested_paths == [f"/drive/v3/files/{_FILE_ID}?alt=media"]


@pytest.mark.parametrize("status", (403, 404))
def test_drive_file_scope_refusals_are_closed_safety_outcomes(status: int) -> None:
    with (
        drive_media_endpoint(payload=b"{}", status=status) as endpoint,
        pytest.raises(OutboundStoragePermissionError) as excinfo,
    ):
        _download_drive_file_from_service(_FILE_ID, endpoint.service)

    assert excinfo.value.context is not None
    assert excinfo.value.context["required_scope"] == "https://www.googleapis.com/auth/drive.readonly"
    _assert_closed_outcome(
        excinfo.value,
        condition_id="google.document_link.file_scope_sufficient",
        facts={
            "file_id": _FILE_ID,
            "required_scope": "https://www.googleapis.com/auth/drive.readonly",
            "status": str(status),
            "scope_sufficient": False,
        },
        outcome=NoRecoveryOutcome.SAFETY,
    )


def test_drive_media_transport_refusal_is_a_closed_safety_outcome() -> None:
    with (
        drive_media_endpoint(payload=b"{}", status=500) as endpoint,
        pytest.raises(OutboundStorageNetworkError) as excinfo,
    ):
        _download_drive_file_from_service(_FILE_ID, endpoint.service)

    _assert_closed_outcome(
        excinfo.value,
        condition_id="google.document_link.media_transport_available",
        facts={"file_id": _FILE_ID, "status": "500", "transport_available": False},
        outcome=NoRecoveryOutcome.SAFETY,
    )


class _NonBytesMediaRequest:
    """Drive request seam returning one invalid successful payload."""

    def execute(self) -> object:
        return {"not": "bytes"}


class _NonBytesMediaFiles:
    """Drive files resource supplying the invalid media request."""

    def get_media(self, *, fileId: str) -> _NonBytesMediaRequest:  # noqa: N803 - Drive API kwarg name
        assert fileId == _FILE_ID
        return _NonBytesMediaRequest()


class _NonBytesMediaService:
    """Minimal Drive service exercising successful-payload validation."""

    def files(self) -> _NonBytesMediaFiles:
        return _NonBytesMediaFiles()


def test_non_bytes_successful_media_payload_is_a_validation_outcome() -> None:
    with pytest.raises(OutboundStorageValidationError) as excinfo:
        _download_drive_file_from_service(_FILE_ID, _NonBytesMediaService())

    _assert_closed_outcome(
        excinfo.value,
        condition_id="google.document_link.media_payload_bytes",
        facts={"file_id": _FILE_ID, "payload_bytes": False, "payload_type": "dict"},
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )
