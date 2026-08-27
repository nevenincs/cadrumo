"""Real model-boundary proofs for ordered safe operation events."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict

import pytest
from pydantic import TypeAdapter, ValidationError

from ....core import OperationEffect, OperationEventKind, OperationTerminalCondition
from ....tests.aeat_literal_fixtures import REDACTION_SESSION_QUERY_URL_CANARY
from ..events import OperationLogSeverity
from ..models import OperationIdentity, OperationReconciliationOutcome, OperationTerminalReceipt
from ..persistence.events import (
    OperationDiagnosticEvent,
    OperationEvent,
    OperationLogRecord,
    OperationProgressEvent,
    OperationReconciliationEvent,
    OperationTerminalEvent,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 13, 18, 0, tzinfo=UTC)
_IDENTITY = OperationIdentity(operation_id="a" * 64, definition_id="profile.sync", subject_ref="profile:active")
_DIAGNOSTIC_REF = "sha256:0123456789ab"


class _EventBase(TypedDict):
    """Typed common constructor fields shared by every event variant."""

    identity: OperationIdentity
    revision: int
    sequence: int
    timestamp: datetime
    code: str


def _base(
    *,
    revision: int = 3,
    sequence: int = 7,
    timestamp: datetime = _NOW,
    code: str = "profile.sync.progress",
) -> _EventBase:
    return {
        "identity": _IDENTITY,
        "revision": revision,
        "sequence": sequence,
        "timestamp": timestamp,
        "code": code,
    }


def test_discriminated_event_union_round_trips_exact_variant() -> None:
    adapter = TypeAdapter(OperationEvent)
    event = adapter.validate_python(
        {**_base(), "kind": "progress", "completed": 2, "total": 5, "unit_code": "profile.field"}
    )

    assert isinstance(event, OperationProgressEvent)
    assert adapter.validate_json(adapter.dump_json(event)) == event


def test_progress_refuses_impossible_counts() -> None:
    with pytest.raises(ValidationError, match="cannot exceed total"):
        OperationProgressEvent(**_base(), completed=6, total=5)


def test_event_ordering_and_time_are_fail_closed() -> None:
    with pytest.raises(ValidationError):
        OperationDiagnosticEvent(**_base(sequence=0), diagnostic_ref=_DIAGNOSTIC_REF)
    with pytest.raises(ValidationError):
        OperationDiagnosticEvent(**_base(timestamp=datetime(2026, 8, 13, 18, 0)), diagnostic_ref=_DIAGNOSTIC_REF)


def test_log_record_has_no_message_or_untyped_fact_channel() -> None:
    with pytest.raises(ValidationError):
        OperationLogRecord(
            **_base(),
            severity=OperationLogSeverity.ERROR,
            diagnostic_ref=_DIAGNOSTIC_REF,
            message="secret-bearing free text",
        )


def test_unknown_or_mismatched_event_discriminator_is_refused() -> None:
    adapter = TypeAdapter(OperationEvent)
    with pytest.raises(ValidationError):
        adapter.validate_python({**_base(), "kind": "unknown", "completed": 1, "total": 1})
    with pytest.raises(ValidationError):
        adapter.validate_python({**_base(), "kind": OperationEventKind.EFFECT, "completed": 1, "total": 1})


def test_terminal_event_binds_exact_receipt_identity_revision_and_time() -> None:
    receipt = OperationTerminalReceipt(
        identity=_IDENTITY,
        revision=3,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=_NOW,
        result_ref="result:one",
    )
    event = OperationTerminalEvent(**_base(), receipt=receipt)
    assert event.kind is OperationEventKind.TERMINAL

    with pytest.raises(ValidationError, match="revision does not match"):
        OperationTerminalEvent(**_base(revision=4), receipt=receipt)


def test_reconciliation_event_round_trips_closed_outcome_and_opaque_lease_evidence() -> None:
    adapter = TypeAdapter(OperationEvent)
    event = OperationReconciliationEvent(
        **_base(code="operation.reconciliation"),
        outcome=OperationReconciliationOutcome.RECOVERED,
        lease_evidence_ref="a" * 64,
    )

    assert adapter.validate_json(adapter.dump_json(event)) == event
    with pytest.raises(ValidationError):
        OperationReconciliationEvent(
            **_base(code="operation.reconciliation"),
            outcome="frontend_decision",
            lease_evidence_ref="unsafe prose",
        )


def test_event_models_are_strict_frozen_and_codes_are_stable() -> None:
    event = OperationDiagnosticEvent(**_base(), diagnostic_ref=_DIAGNOSTIC_REF)
    with pytest.raises(ValidationError):
        event.sequence = 8
    with pytest.raises(ValidationError):
        OperationDiagnosticEvent(**_base(code="Localized prose!"), diagnostic_ref=_DIAGNOSTIC_REF)


@pytest.mark.parametrize(
    "unsafe_reference",
    (
        "12345678Z",
        "secret:correct-horse-battery-staple",
        "token:eyJhbGciOiJIUzI1NiJ9.payload.signature",
        "Bearer abcdefghijklmnopqrstuvwxyz",
        REDACTION_SESSION_QUERY_URL_CANARY,
        "C:/Users/operator/private.log",
        "The browser raised TimeoutError while authenticating",
        "diagnóstico privado del contribuyente",
    ),
)
def test_diagnostic_channels_refuse_raw_or_prose_references(unsafe_reference: str) -> None:
    with pytest.raises(ValidationError):
        OperationDiagnosticEvent(**_base(), diagnostic_ref=unsafe_reference)
    with pytest.raises(ValidationError):
        OperationLogRecord(**_base(), severity=OperationLogSeverity.ERROR, diagnostic_ref=unsafe_reference)


def test_diagnostic_channels_admit_opaque_correlation_fingerprints() -> None:
    diagnostic = OperationDiagnosticEvent(**_base(), diagnostic_ref=_DIAGNOSTIC_REF)
    log = OperationLogRecord(**_base(), severity=OperationLogSeverity.WARNING, diagnostic_ref="sha256:" + "a" * 64)

    assert diagnostic.diagnostic_ref == _DIAGNOSTIC_REF
    assert log.diagnostic_ref == "sha256:" + "a" * 64


@pytest.mark.parametrize("hex_length", (13, 63))
def test_diagnostic_channels_refuse_unrecognised_fingerprint_lengths(hex_length: int) -> None:
    with pytest.raises(ValidationError):
        OperationDiagnosticEvent(**_base(), diagnostic_ref="sha256:" + "a" * hex_length)
