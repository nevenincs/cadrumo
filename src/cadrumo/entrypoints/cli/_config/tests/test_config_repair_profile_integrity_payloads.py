"""Strict JSON payload checks for the config-repair profile/integrity envelopes.

``RepairProfileResult``, ``RepairIntegrityObjectsResult``, and
``WorkflowFingerprintPayload`` used to accept an arbitrary ``extra="allow"``
shape or permissive optional scalars. They now project the canonical
:class:`~cadrumo.application.workflow.ActiveProfileHealth`,
:class:`~cadrumo.application.diagnostics.SecureObjectIntegrityReport`, and
:class:`~cadrumo.application.workflow.WorkflowStateResetFingerprint` bounds
directly, so a malformed nested row is refused rather than forwarded.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ..._config_payloads import (
    RepairIntegrityObjectsResult,
    RepairProfileResult,
    WorkflowFingerprintPayload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _pointer_repair_payload(*, status: object = "none", source: object = "none") -> dict[str, object]:
    from .....application.profile_preconditions import inspect_active_profile_precondition
    from ..._common import resolve_cli_precondition_action

    verdict = inspect_active_profile_precondition(
        active_profile_present=False,
        registered_profile_count=0,
    )
    assert verdict is not None
    return {
        "dry_run": True,
        "cleared_pointer": False,
        "before": {
            "active_profile": None,
            "source": source,
            "status": status,
            "registered_bucket": False,
            "profile_record_present": False,
            "profile_record_error": "",
            "profile_present_keys": 0,
            "profile_total_keys": 2,
            "missing_required": ["identity.tax_id"],
            "repairable_by_clearing_pointer": False,
            "precondition_action": resolve_cli_precondition_action(verdict),
        },
        "after": None,
    }


def _profile_record_status_payload() -> dict[str, object]:
    return {
        "profile_id": "11111111-1111-4111-8111-111111111111",
        "bucket_id": "22222222-2222-4222-8222-222222222222",
        "display_name": "x",
        "registered_bucket": True,
        "profile_record_present": False,
        "status": "profile_record_unreadable",
        "error": "StorageDecryptionError",
    }


def test_repair_profile_result_projects_pointer_repair_branch() -> None:
    """The pointer-repair branch's nested health rows round-trip typed."""
    result = RepairProfileResult.model_validate(_pointer_repair_payload())

    assert result.before is not None
    assert result.before.status == "none"
    assert result.before.source == "none"
    assert result.before.missing_required == ["identity.tax_id"]
    assert result.after is None
    assert result.dry_run is True


def test_repair_profile_result_projects_profile_record_status_branch() -> None:
    """The inspection branch's ad-hoc status row round-trips typed."""
    result = RepairProfileResult.model_validate(_profile_record_status_payload())

    assert result.status == "profile_record_unreadable"
    assert result.error == "StorageDecryptionError"
    assert result.display_name == "x"
    assert result.before is None


@pytest.mark.parametrize("bad_status", ("bogus", "", 1))
def test_repair_profile_result_refuses_malformed_health_status(bad_status: object) -> None:
    """A nested health row with an unknown ``status`` value is refused."""
    payload = _pointer_repair_payload(status=bad_status)

    with pytest.raises(ValidationError):
        RepairProfileResult.model_validate(payload)


def test_repair_profile_result_refuses_malformed_health_source() -> None:
    """A nested health row with an unknown ``source`` value is refused."""
    payload = _pointer_repair_payload(source="bogus")

    with pytest.raises(ValidationError):
        RepairProfileResult.model_validate(payload)


def _integrity_objects_payload() -> dict[str, object]:
    return {
        "namespaces": [{"namespace": "workflow", "readable": 3, "unreadable": 0}],
        "readable_total": 3,
        "unreadable_total": 0,
        "check": {"status": "ok", "summary": "0 unreadable secure-object rows"},
    }


def test_repair_integrity_objects_result_projects_nested_report() -> None:
    """The typed report round-trips its namespace rows and verdict."""
    result = RepairIntegrityObjectsResult.model_validate(_integrity_objects_payload())

    assert result.namespaces[0].namespace == "workflow"
    assert result.check.status == "ok"


@pytest.mark.parametrize(
    "mutation",
    (
        {"unreadable_total": -1},
        {"readable_total": -1},
    ),
)
def test_repair_integrity_objects_result_refuses_negative_counts(mutation: dict[str, object]) -> None:
    """A negative aggregate count is refused."""
    payload = {**_integrity_objects_payload(), **mutation}

    with pytest.raises(ValidationError):
        RepairIntegrityObjectsResult.model_validate(payload)


def test_repair_integrity_objects_result_refuses_unknown_check_status() -> None:
    """The check verdict is a closed ``ok``/``fail`` vocabulary."""
    payload = _integrity_objects_payload()
    payload["check"] = {"status": "warn", "summary": "x"}

    with pytest.raises(ValidationError):
        RepairIntegrityObjectsResult.model_validate(payload)


def test_repair_integrity_objects_result_refuses_blank_namespace() -> None:
    """A namespace row must carry a non-empty name, mirroring the canonical row."""
    payload = _integrity_objects_payload()
    payload["namespaces"] = [{"namespace": "", "readable": 0, "unreadable": 0}]

    with pytest.raises(ValidationError):
        RepairIntegrityObjectsResult.model_validate(payload)


def test_workflow_fingerprint_payload_round_trips_valid_row() -> None:
    """A valid fingerprint round-trips with its aware timestamp intact."""
    written_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    payload = WorkflowFingerprintPayload(
        schema_version=1,
        written_at=written_at,
        byte_length=128,
        reason_class="readable",
        recovered_bucket_id="bucket-1",
    )

    assert payload.written_at == written_at
    assert payload.byte_length == 128


@pytest.mark.parametrize(
    "kwargs",
    (
        {"schema_version": 0, "reason_class": "readable"},
        {"byte_length": -1, "reason_class": "readable"},
        {"reason_class": ""},
    ),
)
def test_workflow_fingerprint_payload_refuses_out_of_bounds_fields(kwargs: dict[str, object]) -> None:
    """A non-positive schema version, negative byte length, or blank reason is refused."""
    with pytest.raises(ValidationError):
        WorkflowFingerprintPayload.model_validate(kwargs)
