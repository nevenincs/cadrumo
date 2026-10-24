"""A settled result that names exactly one transaction or invoice carries the view link that selects it."""

from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

import pytest
from pydantic import BaseModel, JsonValue

from cadrumo.application.invoices.catalogue_add_contracts import InvoiceAddResult
from cadrumo.application.invoices.catalogue_intake_contracts import InvoiceWizardOutcome
from cadrumo.application.invoices.catalogue_update_operation import InvoiceUpdateResult
from cadrumo.application.ledger.classify_result_contracts import LedgerClassifyOperationResult
from cadrumo.application.ledger.invoice_evidence_confirm_operation import LedgerEvidenceConfirmProjection
from cadrumo.application.ledger.ledger_add_contracts import LedgerAddOperationResult
from cadrumo.application.ledger.update_contracts import LedgerUpdateOperationResult
from cadrumo.application.operations.contract_manifest import load_operation_contract_manifest
from cadrumo.application.operations.frontend_requests import OperationResultProjectionRequestV1
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.operations.registry_schema_validation import strict_model_json_schema
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.core.hashing import sha256_hex
from cadrumo_client.contracts.navigation import load_navigation_register
from cadrumo_client.transport.frontend_client import FrontendClient

from ..record_links import RECORD_VIEWS, record_link
from ..runtime_adapter import RuntimeMcpAdapter
from ..server import build_server
from .session import connected_server_and_client_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_TRANSACTION = "0123456789abcdef" * 4
_INVOICE = "fedcba9876543210" * 4

_RESULT_MODELS: dict[str, type[BaseModel]] = {
    "ledger.add.result": LedgerAddOperationResult,
    "ledger.update.result": LedgerUpdateOperationResult,
    "ledger.classify.single.result": LedgerClassifyOperationResult,
    "ledger.invoice.add.result": InvoiceAddResult,
    "ledger.invoice.update.result": InvoiceUpdateResult,
    "ledger.invoice.wizard.result": InvoiceWizardOutcome,
    "ledger.evidence.confirm.result": LedgerEvidenceConfirmProjection,
}
"""The public result model behind each linked schema id; the manifest's fingerprint proves the pairing."""

_KIND_BY_VIEW = {"ledger/movements": "transaction", "ledger/invoices": "invoice"}


def _registered_result_schemas() -> dict[str, dict[str, Any]]:
    return {
        entry.contract.result_schema.schema_id: entry.contract.result_schema.model_dump(mode="json")
        for entry in load_operation_contract_manifest().operations
        if entry.contract.result_schema is not None
    }


def _field_at(schema: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    """Follow ``path`` through a model's JSON schema, through references and optional unions."""
    definitions = schema.get("$defs", {})

    def resolved(node: dict[str, Any]) -> dict[str, Any]:
        if "$ref" in node:
            return resolved(definitions[node["$ref"].rpartition("/")[2]])
        present = [option for option in node.get("anyOf", ()) if option.get("type") != "null"]
        return resolved(present[0]) if len(present) == 1 else node

    node = schema
    for key in path:
        node = resolved(resolved(node)["properties"][key])
    return node


def test_each_linked_result_is_a_registered_result_naming_one_record_where_the_table_says() -> None:
    registered = _registered_result_schemas()
    register = load_navigation_register()
    assert set(RECORD_VIEWS) == set(_RESULT_MODELS)
    for schema_id, record in RECORD_VIEWS.items():
        model = _RESULT_MODELS[schema_id]
        declared = registered[schema_id]
        identity = OperationSchemaIdentityV1.from_model(
            schema_id=schema_id, schema_version=declared["schema_version"], model_type=model
        )
        assert identity.schema_fingerprint == declared["schema_fingerprint"], schema_id
        field = _field_at(strict_model_json_schema(model), record.path)
        assert field.get("type") == "string", (schema_id, field)
        element = register.element(record.view_id)
        assert element is not None
        assert element.params == {"select": _KIND_BY_VIEW[record.view_id]}, schema_id


def test_no_link_for_a_result_that_did_not_succeed_or_carries_no_well_formed_id() -> None:
    succeeded = {"outcome": "success", "projection": {"invoice": {"invoice_id": _INVOICE}}}
    assert record_link("ledger.invoice.add.result", succeeded) == {
        "view": "ledger/invoices",
        "params": {"select": _INVOICE},
        "link": f"cadrumo://view/ledger/invoices?select={_INVOICE}",
    }
    assert record_link("ledger.invoice.add.result", succeeded | {"outcome": "refused"}) is None
    assert record_link("ledger.invoice.add.result", {"outcome": "success", "projection": {"invoice": None}}) is None
    assert (
        record_link("ledger.invoice.add.result", {"outcome": "success", "projection": {"invoice": {"invoice_id": "F"}}})
        is None
    )
    # A result that names several records, or none a view selects, carries no link.
    assert record_link("ledger.invoice.import.result", succeeded) is None
    assert record_link("ledger.link.result", succeeded) is None


class _SettledClient:
    """A lease whose operation settled with one document, read as the runtime releases it."""

    def __init__(self, document: dict[str, JsonValue]) -> None:
        self.profile_id = uuid4()
        self.frontend = OperationFrontendProjection.EXTERNAL_CLIENT
        self.session_id = uuid4()
        self.document = document
        self.closed = False

    def read_result_document(
        self, result: OperationResultProjectionRequestV1, *, deadline: float
    ) -> dict[str, JsonValue]:
        return self.document

    def close(self) -> None:
        self.closed = True


def _request(schema_id: str) -> dict[str, Any]:
    declared = _registered_result_schemas()[schema_id]
    return OperationResultProjectionRequestV1(
        operation_id=sha256_hex(b"mcp-record-link-operation"),
        terminal_revision=3,
        definition_contract_digest=sha256_hex(b"mcp-record-link-contract"),
        result_schema=OperationSchemaIdentityV1.model_validate(declared),
    ).model_dump(mode="json")


async def _result(schema_id: str, document: dict[str, JsonValue]) -> dict[str, Any]:
    client = _SettledClient(document)
    adapter = RuntimeMcpAdapter(profile_id=client.profile_id, client=cast(FrontendClient, client))
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            reply = await sdk.call_tool("result", {"result": _request(schema_id)})
    finally:
        await adapter.close()
    assert reply.structured_content is not None
    return reply.structured_content


@pytest.mark.anyio
async def test_a_created_movement_result_carries_the_link_that_selects_it() -> None:
    document: dict[str, JsonValue] = {
        "outcome": "success",
        "projection": {"outcome": "created", "transaction": {"transaction_id": _TRANSACTION}},
    }
    released = await _result("ledger.add.result", document)

    assert released["outcome"] == "reply"
    assert released["document"] == document
    assert released["record"] == {
        "view": "ledger/movements",
        "params": {"select": _TRANSACTION},
        "link": f"cadrumo://view/ledger/movements?select={_TRANSACTION}",
    }


@pytest.mark.anyio
async def test_a_wizard_invoice_result_carries_the_link_that_selects_the_invoice() -> None:
    document: dict[str, JsonValue] = {
        "outcome": "success",
        "projection": {"outcome": "succeeded", "result": {"invoice": {"invoice_id": _INVOICE}}},
    }
    released = await _result("ledger.invoice.wizard.result", document)
    assert released["record"]["link"] == f"cadrumo://view/ledger/invoices?select={_INVOICE}"


@pytest.mark.anyio
async def test_a_result_of_an_operation_without_one_selectable_record_carries_no_link() -> None:
    document: dict[str, JsonValue] = {"outcome": "success", "projection": {"created_invoice_ids": [_INVOICE]}}
    released = await _result("ledger.invoice.import.result", document)
    assert released["outcome"] == "reply"
    assert "record" not in released
