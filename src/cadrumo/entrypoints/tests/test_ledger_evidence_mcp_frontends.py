"""Which purchase-invoice evidence operations the live registry opens to an MCP client."""

from __future__ import annotations

import pytest

from ...application.operations.registry import OperationFrontendProjection
from .test_operation_catalogue import _registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MCP = OperationFrontendProjection.MCP

_METADATA_READS = (
    "ledger.evidence.attachment_queue",
    "ledger.evidence.attachment_view",
    "ledger.evidence.consent.list",
    "ledger.evidence.review.list",
)
_EVIDENCE_WRITES = (
    "ledger.evidence.add",
    "ledger.evidence.batch",
    "ledger.evidence.update",
    "ledger.evidence.remove",
    "ledger.evidence.extract",
    "ledger.evidence.confirm",
)
_READS_WITH_A_HOST_PATH_OR_DOCUMENT_TEXT_OR_A_LIVE_PROBE = (
    "ledger.evidence.list",
    "ledger.evidence.view",
    "ledger.evidence.review.view",
    "ledger.evidence.reader-readiness",
)


@pytest.mark.parametrize("definition_id", _METADATA_READS)
def test_each_evidence_metadata_read_lists_mcp_in_the_live_registry(definition_id: str) -> None:
    registry = _registry()

    assert _MCP in registry.lookup(definition_id).permitted_frontends
    assert _MCP in registry.lookup_public_contract(definition_id).permitted_frontends


@pytest.mark.parametrize("definition_id", _EVIDENCE_WRITES)
def test_no_evidence_write_lists_mcp(definition_id: str) -> None:
    registry = _registry()

    assert _MCP not in registry.lookup(definition_id).permitted_frontends
    assert _MCP not in registry.lookup_public_contract(definition_id).permitted_frontends


@pytest.mark.parametrize("definition_id", _READS_WITH_A_HOST_PATH_OR_DOCUMENT_TEXT_OR_A_LIVE_PROBE)
def test_an_evidence_read_whose_result_or_probe_is_not_agent_safe_does_not_list_mcp(definition_id: str) -> None:
    registry = _registry()

    assert _MCP not in registry.lookup(definition_id).permitted_frontends
    assert _MCP not in registry.lookup_public_contract(definition_id).permitted_frontends
