"""Which purchase-invoice evidence operations the live registry opens to an MCP client."""

from __future__ import annotations

import pytest

from ...application.operations.mcp_admission import McpExclusionReason, mcp_admission_decision
from ...application.operations.registry import OperationFrontendProjection
from .test_operation_catalogue import _registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MCP = OperationFrontendProjection.MCP
_PERSON_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})

_READS_OPEN_TO_EVERY_FRONTEND = (
    "ledger.evidence.attachment_queue",
    "ledger.evidence.attachment_view",
    "ledger.evidence.consent.list",
    "ledger.evidence.review.list",
    "ledger.evidence.reader-readiness",
)
_EVIDENCE_WRITES = (
    "ledger.evidence.add",
    "ledger.evidence.batch",
    "ledger.evidence.update",
    "ledger.evidence.remove",
    "ledger.evidence.extract",
    "ledger.evidence.confirm",
)
_PERSON_PROJECTION_AND_ITS_AGENT_FACING_SIBLING = (
    # The list and the view return the path the operator typed.
    ("ledger.evidence.list", "ledger.evidence.query"),
    ("ledger.evidence.view", "ledger.evidence.query"),
    # The review view returns text taken verbatim from the document.
    ("ledger.evidence.review.view", "ledger.evidence.review.summary"),
)


@pytest.mark.parametrize("definition_id", _READS_OPEN_TO_EVERY_FRONTEND)
def test_each_evidence_metadata_read_lists_mcp_in_the_live_registry(definition_id: str) -> None:
    registry = _registry()

    assert registry.lookup(definition_id).permitted_frontends == frozenset(OperationFrontendProjection)
    assert registry.lookup_public_contract(definition_id).permitted_frontends == frozenset(OperationFrontendProjection)


@pytest.mark.parametrize("definition_id", _EVIDENCE_WRITES)
def test_no_evidence_write_lists_mcp(definition_id: str) -> None:
    registry = _registry()

    assert _MCP not in registry.lookup(definition_id).permitted_frontends
    assert _MCP not in registry.lookup_public_contract(definition_id).permitted_frontends


@pytest.mark.parametrize(("person_id", "sibling_id"), _PERSON_PROJECTION_AND_ITS_AGENT_FACING_SIBLING)
def test_a_person_projection_stays_off_mcp_and_its_sibling_is_open_to_mcp_alone(
    person_id: str, sibling_id: str
) -> None:
    registry = _registry()

    assert registry.lookup(person_id).permitted_frontends == _PERSON_FRONTENDS
    assert registry.lookup_public_contract(person_id).permitted_frontends == _PERSON_FRONTENDS
    assert registry.lookup(sibling_id).permitted_frontends == frozenset({_MCP})
    assert registry.lookup_public_contract(sibling_id).permitted_frontends == frozenset({_MCP})
    decision = mcp_admission_decision(person_id)
    assert decision.exclusion_reason is McpExclusionReason.PERSON_PROJECTION
    assert decision.agent_facing_sibling == sibling_id
