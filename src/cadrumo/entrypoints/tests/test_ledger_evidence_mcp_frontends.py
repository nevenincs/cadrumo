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
_EVIDENCE_WRITES_CLOSED_TO_MCP = (
    # Adding takes a file on the host, removal and confirmation wait for the person.
    "ledger.evidence.add",
    "ledger.evidence.batch",
    "ledger.evidence.remove",
    "ledger.evidence.confirm",
)
_EVIDENCE_WRITES_OPEN_TO_MCP = (
    # An update edits the record's descriptive fields; the person's command line is its other frontend.
    ("ledger.evidence.update", frozenset({OperationFrontendProjection.CLI, _MCP})),
    # A read on this machine; its resolver refuses an MCP session the read that leaves it.
    ("ledger.evidence.extract", frozenset(OperationFrontendProjection)),
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


@pytest.mark.parametrize("definition_id", _EVIDENCE_WRITES_CLOSED_TO_MCP)
def test_an_evidence_write_that_takes_a_file_or_waits_for_the_person_does_not_list_mcp(definition_id: str) -> None:
    registry = _registry()

    assert _MCP not in registry.lookup(definition_id).permitted_frontends
    assert _MCP not in registry.lookup_public_contract(definition_id).permitted_frontends


@pytest.mark.parametrize(("definition_id", "frontends"), _EVIDENCE_WRITES_OPEN_TO_MCP)
def test_an_evidence_write_an_agent_may_make_lists_mcp_beside_the_persons_frontends(
    definition_id: str, frontends: frozenset[OperationFrontendProjection]
) -> None:
    registry = _registry()

    assert registry.lookup(definition_id).permitted_frontends == frontends
    assert registry.lookup_public_contract(definition_id).permitted_frontends == frontends
    assert not mcp_admission_decision(definition_id).prerequisites


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
