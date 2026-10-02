"""Focused presenter tests for ledger evidence batch notices and actions.

The complete CLI batch journey is exercised through the authenticated profile
worker in ``test_runtime_ledger_evidence_ingestion_native``. These tests isolate
the CLI-owned presentation of canonical pause, refusal, review, and unreadable
source results.
"""

from __future__ import annotations

import pytest

from ....application.ledger.batch_ingest import (
    BatchItemResult,
    BatchRunResult,
    InferencePause,
    UnresolvedBatchSource,
    batch_item_identity,
)
from ....application.ledger.preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict
from ....application.operator_actions.models import ConditionEvidence, PreconditionVerdict
from ....application.provisioning_contracts import ProvisioningPreconditionCondition
from ....core.json_contract import ResolvedActionReference, ResolvedNoticeAction, ResolvedPreconditionAction
from ....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ....domain.iva.classification import InvoiceKind
from .._ledger_evidence_batch_cli import _batch_payload, _batch_text_lines, _run_notices

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ADDRESS = "a" * 64
_RUNTIME_REACHABLE = ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value


def _paused_row(name: str) -> BatchItemResult:
    return BatchItemResult(
        content_address=_ADDRESS,
        identity=batch_item_identity(content_address=_ADDRESS, direction=InvoiceKind.RECEIVED),
        direction=InvoiceKind.RECEIVED,
        source_name=name,
        status="paused",
    )


def _pending_review_row(name: str) -> BatchItemResult:
    return BatchItemResult(
        content_address=_ADDRESS,
        identity=batch_item_identity(content_address=_ADDRESS, direction=InvoiceKind.RECEIVED),
        direction=InvoiceKind.RECEIVED,
        source_name=name,
        status="pending_review",
    )


def _refused_row(name: str) -> BatchItemResult:
    address = "b" * 64
    return BatchItemResult(
        content_address=address,
        identity=batch_item_identity(content_address=address, direction=InvoiceKind.RECEIVED),
        direction=InvoiceKind.RECEIVED,
        source_name=name,
        status="refused",
        refusal_code="not_readable",
        refusal_verdict=ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_TEXT_LAYER_AVAILABLE,
            facts={"layer_available": False},
        ),
    )


_PAUSE = InferencePause(
    facts={"runtime_reachable": False, "runtime_url": "http://127.0.0.1:11434"},
    precondition_verdict=PreconditionVerdict(
        failed_condition_id=_RUNTIME_REACHABLE,
        evidence=(
            ConditionEvidence(
                condition_id=_RUNTIME_REACHABLE,
                evidence_id=f"{_RUNTIME_REACHABLE}.observation",
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                values={"runtime_reachable": False, "runtime_url": "http://127.0.0.1:11434"},
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    ),
)


def test_a_deferred_run_reports_distinctly_from_a_failed_one() -> None:
    """Deferral and refusal remain distinct signals with grounded recovery facts."""
    deferred = BatchRunResult(items=(_paused_row("scan.pdf"),), inference_pause=_PAUSE)
    assert deferred.any_deferred is True
    assert deferred.any_failed is False

    codes = {notice.code for notice in _run_notices(deferred)}
    assert codes == {"ledger.evidence.batch.work_deferred"}
    deferred_notice = _run_notices(deferred)[0]
    assert isinstance(deferred_notice.action, ResolvedPreconditionAction)
    assert deferred_notice.action.failed_condition_id == _RUNTIME_REACHABLE
    assert deferred_notice.context == {"paused": "1"}

    pause_payload = _batch_payload(deferred, bucket_id="bucket", direction=InvoiceKind.RECEIVED)
    assert pause_payload.inference_pause is not None
    assert pause_payload.inference_pause.facts == _PAUSE.facts
    assert pause_payload.inference_pause.precondition_action.failed_condition_id == _RUNTIME_REACHABLE

    lines = _batch_text_lines(deferred, bucket_id="bucket", direction=InvoiceKind.RECEIVED)
    assert "paused.facts.runtime_reachable\tfalse" in lines
    assert any(line.startswith("paused.precondition_action.failed_condition_id\t") for line in lines)

    failed = BatchRunResult(items=(_refused_row("broken.pdf"),))
    assert {notice.code for notice in _run_notices(failed)} == {"ledger.evidence.batch.items_refused"}

    both = BatchRunResult(
        items=(_paused_row("scan.pdf"), _refused_row("broken.pdf")),
        inference_pause=_PAUSE,
    )
    assert {notice.code for notice in _run_notices(both)} == {
        "ledger.evidence.batch.items_refused",
        "ledger.evidence.batch.work_deferred",
    }


def test_pending_review_resolves_the_review_queue_action() -> None:
    notices = _run_notices(BatchRunResult(items=(_pending_review_row("review.pdf"),)))

    (notice,) = notices
    assert notice.code == "ledger.evidence.batch.pending_review"
    notice_action = notice.action
    assert isinstance(notice_action, ResolvedNoticeAction)
    action_reference = notice_action.action
    assert isinstance(action_reference, ResolvedActionReference)
    assert action_reference.action_id == "operator.ledger.evidence.review.list"
    assert action_reference.target_command_key == "ledger.evidence.review.list"
    assert notice_action.argument_bindings == ()


def test_an_unreadable_source_counts_as_a_failure_without_becoming_an_item() -> None:
    """An unreadable source has no content identity but still has a visible refusal."""
    run = BatchRunResult(
        unresolved=(
            UnresolvedBatchSource(
                source_name="gone.pdf",
                refusal_code="unreadable_source",
                refusal_verdict=ledger_no_recovery_verdict(
                    LedgerPreconditionCondition.EVIDENCE_FILE_READABLE,
                    facts={"source_name": "gone.pdf", "file_readable": False},
                ),
            ),
        ),
    )
    assert run.any_failed is True
    notices = _run_notices(run)
    assert [notice.code for notice in notices] == ["ledger.evidence.batch.items_refused"]
    refusal_context = notices[0].context
    assert refusal_context == {"refused": "0", "unresolved": "1"}
