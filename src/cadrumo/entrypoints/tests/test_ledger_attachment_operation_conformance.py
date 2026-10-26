"""Public schema composition for the paired ledger attachment operations."""

from __future__ import annotations

import pytest

from ...application.ledger.action_ports import LedgerActionPorts, LedgerActionPortsFactory
from ...application.ledger.attachment_mutation_operation import (
    LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    LEDGER_DETACH_OPERATION_DEFINITION_ID,
    LedgerAttachmentOperationResult,
    LedgerAttachRequest,
    LedgerDetachRequest,
    build_ledger_attach_definition,
    build_ledger_attach_registration,
    build_ledger_detach_definition,
    build_ledger_detach_registration,
)
from ...application.operations.registry import OperationRegistry
from ...domain.calculations.registry.authority import PinnedAuthorityOperation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _unused_ports_factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
    """Build schema-bearing definitions without opening profile persistence."""
    _ = bucket_id, operation
    raise AssertionError("schema composition must not construct profile-bound ports")


def test_attach_and_detach_register_as_one_closed_public_schema_set() -> None:
    """The registry validates both definitions and their request/result hooks together."""
    ports_factory: LedgerActionPortsFactory = _unused_ports_factory
    attach = build_ledger_attach_definition(ports_factory)
    detach = build_ledger_detach_definition(ports_factory)
    registry = OperationRegistry(
        definitions=(attach, detach),
        public_registrations=(
            build_ledger_attach_registration(attach),
            build_ledger_detach_registration(detach),
        ),
    )

    assert tuple(definition.definition_id for definition in registry.definitions) == (
        LEDGER_ATTACH_OPERATION_DEFINITION_ID,
        LEDGER_DETACH_OPERATION_DEFINITION_ID,
    )
    for definition_id, request_type in (
        (LEDGER_ATTACH_OPERATION_DEFINITION_ID, LedgerAttachRequest),
        (LEDGER_DETACH_OPERATION_DEFINITION_ID, LedgerDetachRequest),
    ):
        description = registry.describe_public_definition(definition_id)
        assert description.contract.request_schema.schema_id == f"{definition_id}.request"
        assert description.contract.result_schema is not None
        assert description.contract.result_schema.schema_id == f"{definition_id}.result"
        assert registry.lookup_public_schema_binding(description.contract.request_schema).model_type is request_type
        assert (
            registry.lookup_public_schema_binding(description.contract.result_schema).model_type
            is LedgerAttachmentOperationResult
        )
        properties = description.request_json_schema["properties"]
        assert isinstance(properties, dict)
        assert "profile_id" in properties
