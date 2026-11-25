"""The production registry serves the evidence check and the purchase-evidence release as public writes."""

from __future__ import annotations

import pytest

from ...application.ledger.evidence_verify_operation import (
    LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID,
    LedgerEvidenceVerifyProjection,
    LedgerEvidenceVerifyRequest,
)
from ...application.ledger.purchase_evidence_release_operation import (
    LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
    LedgerPurchaseEvidenceReleaseRequest,
    LedgerPurchaseEvidenceReleaseResult,
)
from ...application.operations.contract_manifest import load_operation_contract_manifest
from ...core.operations import OperationEffect
from ..operation_composition import build_production_operation_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DEFINITIONS = (
    (LEDGER_EVIDENCE_VERIFY_OPERATION_DEFINITION_ID, LedgerEvidenceVerifyRequest, LedgerEvidenceVerifyProjection),
    (
        LEDGER_PURCHASE_EVIDENCE_RELEASE_OPERATION_DEFINITION_ID,
        LedgerPurchaseEvidenceReleaseRequest,
        LedgerPurchaseEvidenceReleaseResult,
    ),
)


@pytest.mark.parametrize(("definition_id", "request_type", "result_type"), _DEFINITIONS)
def test_the_production_registry_binds_the_public_request_and_result(
    definition_id: str, request_type: type, result_type: type
) -> None:
    registry = build_production_operation_registry()

    description = registry.describe_public_definition(definition_id)

    assert description.contract.request_schema.schema_id == f"{definition_id}.request"
    assert registry.lookup_public_schema_binding(description.contract.request_schema).model_type is request_type
    assert description.contract.result_schema is not None
    assert registry.lookup_public_schema_binding(description.contract.result_schema).model_type is result_type
    properties = description.request_json_schema["properties"]
    assert isinstance(properties, dict)
    assert "profile_id" in properties


@pytest.mark.parametrize(("definition_id", "request_type", "result_type"), _DEFINITIONS)
def test_the_shipped_manifest_declares_each_as_a_write_that_may_refuse(
    definition_id: str, request_type: type, result_type: type
) -> None:
    del request_type, result_type
    (entry,) = (
        entry
        for entry in load_operation_contract_manifest().operations
        if entry.contract.definition_id == definition_id
    )

    assert OperationEffect.UPDATED in entry.contract.permitted_effects
    assert OperationEffect.NONE in entry.contract.permitted_effects
