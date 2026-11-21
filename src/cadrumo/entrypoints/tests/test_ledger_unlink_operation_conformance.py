"""The production registry serves the invoice unlink as a public write with the link's contract."""

from __future__ import annotations

import pytest

from ...application.ledger.unlink_operation import (
    LEDGER_UNLINK_OPERATION_DEFINITION_ID,
    LedgerUnlinkRequest,
    LedgerUnlinkResult,
)
from ...application.operations.contract_manifest import load_operation_contract_manifest
from ...core.operations import OperationEffect
from ..operation_composition import build_production_operation_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_the_production_registry_binds_the_public_request_and_result() -> None:
    registry = build_production_operation_registry()

    description = registry.describe_public_definition(LEDGER_UNLINK_OPERATION_DEFINITION_ID)

    assert description.contract.request_schema.schema_id == "ledger.unlink.request"
    assert registry.lookup_public_schema_binding(description.contract.request_schema).model_type is LedgerUnlinkRequest
    assert description.contract.result_schema is not None
    assert registry.lookup_public_schema_binding(description.contract.result_schema).model_type is LedgerUnlinkResult
    properties = description.request_json_schema["properties"]
    assert isinstance(properties, dict)
    assert {"profile_id", "expected_modified_at", "expected_invoice_linked_transaction_ids"} <= set(properties)


def test_the_shipped_manifest_declares_a_write_that_may_refuse_with_the_links_replay_and_baseline() -> None:
    entries = {entry.contract.definition_id: entry.contract for entry in load_operation_contract_manifest().operations}
    unlink = entries[LEDGER_UNLINK_OPERATION_DEFINITION_ID]
    link = entries["ledger.link"]

    assert OperationEffect.UPDATED in unlink.permitted_effects
    assert OperationEffect.NONE in unlink.permitted_effects
    assert unlink.permitted_effects == link.permitted_effects
    assert unlink.replay == link.replay
    assert unlink.baseline == link.baseline
