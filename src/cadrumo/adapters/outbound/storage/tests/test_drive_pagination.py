from __future__ import annotations

import pytest

from .....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .. import OutboundStorageNetworkError, next_drive_page_token

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize(
    ("value", "condition_id", "facts"),
    (
        (42, "storage.drive.pagination.token_string", {"operation": "files.list", "token_type": "int"}),
        ("page-1", "storage.drive.pagination.token_unique", {"operation": "files.list", "token_repeated": True}),
    ),
)
def test_pagination_transport_failures_are_typed_safety_outcomes(
    value: object,
    condition_id: str,
    facts: dict[str, object],
) -> None:
    seen = {"page-1"} if value == "page-1" else set()
    with pytest.raises(OutboundStorageNetworkError) as raised:
        next_drive_page_token(value, seen_tokens=seen, action="files.list")

    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == condition_id
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.SAFETY
    assert len(verdict.evidence) == 1
    evidence = verdict.evidence[0]
    assert evidence.evidence_id == f"{condition_id}.observation"
    assert evidence.provenance is ActionEvidenceProvenance.RUNTIME_OBSERVATION
    assert dict(evidence.values) == facts
