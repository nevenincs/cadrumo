"""A stopped executor's public error detail, settled and read over real durable operation storage.

The journal keeps only a refusal's code or a failure's code and opaque digest.
The bounded public detail a frontend renders -- the registered code, its
catalogue key, the envelope's scrubbed context and the typed verdict, or a
record fault naming the record and broken rule -- is stored as an encrypted
operand and released only through the settled result read under its own
public schema identity.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.errors import AggregationUnsupportedModeloError
from cadrumo.application.cli_exception_preconditions import (
    CliExceptionPrecondition,
    cli_exception_no_recovery_verdict,
)
from cadrumo.application.operations.capabilities import OperationOwnedResource
from cadrumo.application.operations.error_detail import (
    OperationErrorDetailKind,
    OperationErrorDetailV1,
    operation_error_detail_schema,
)
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRefusalCode,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.projection_services import OperationResultProjectionService
from cadrumo.application.operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.i18n.translatable import Translatable
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition

from .supervision_support import run_to_settlement
from .test_supervisor import (
    _SENSITIVE_EXCEPTION_DETAIL,
    SupervisorRequest,
    SupervisorResult,
    UnexpectedFailureExecutor,
    _assert_sensitive_detail_absent_from_operation_bytes,
    _capabilities,
    _registry,
    _repositories,
    _request,
    _supervisor,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

#: A distinctive context value: it reaches the encrypted detail and never the journal bytes.
_ROW_IDENTITY = "ledger-row-7f3a9c"
#: An offending record value: it reaches neither the detail nor the journal.
_OFFENDING_VALUE = "SE556677889901-" + "x" * 80
#: The catalogue key the refusing site supplies, distinct from its registry fallback key.
_REFUSAL_MESSAGE_KEY = "aggregation.grouping.errors.unsupported_modelo"
#: What the envelope's redaction leaves of a secret-looking context key.
_REDACTED_VALUE = "<redacted>"


class _BoundedRecord(BaseModel):
    """A record the application builds with a declared bound."""

    model_config = STRICT_FROZEN_CONFIG

    actor: str = Field(max_length=64)


class _ContextualRefusalExecutor:
    """Refuse with a registered error carrying context, a catalogue key and a typed verdict."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request, context
        raise AggregationUnsupportedModeloError(
            Translatable(_REFUSAL_MESSAGE_KEY),
            context={"modelo": "111", "transaction_id": _ROW_IDENTITY, "api_token": "never-shown"},
            precondition_verdict=cli_exception_no_recovery_verdict(
                CliExceptionPrecondition.REFUSAL_RETRIED, facts={"boundary_error_type": "probe"}
            ),
        )


class _RecordFaultExecutor:
    """Fail by building an application record that breaks its own contract."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request, context
        _BoundedRecord(actor=_OFFENDING_VALUE)
        return None


class _SettledCase:
    """One operation settled over real storage, with its detail read through the public service."""

    def __init__(self, terminal: OperationPersistedSnapshot, storage_root: Path, detail: object) -> None:
        self.terminal = terminal
        self.storage_root = storage_root
        self.detail = detail


def _settle_and_read(
    tmp_path: Path, registry: OperationRegistry, *, result_schema: object | None = None
) -> _SettledCase:
    storage_root = tmp_path / "durable-state"
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(storage_root=storage_root, profile_objects=profile.repository)
        supervisor = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))
        terminal = asyncio.run(run_to_settlement(supervisor, operation_id))
        contract = registry.lookup_public_contract(terminal.identity.definition_id)
        service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)
        detail = asyncio.run(
            service.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=operation_error_detail_schema() if result_schema is None else result_schema,
                ),
                OperationErrorDetailV1,
            )
        )
    return _SettledCase(terminal, storage_root, detail)


def _opted_in(registry: OperationRegistry) -> OperationRegistry:
    """The same supervisor test definition, opted in to recording its public error detail."""
    item = registry.lookup("operation.supervisor.test").model_copy(update={"public_error_detail": True})
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=item,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.test.request", schema_version=1, model_type=SupervisorRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.test.result", schema_version=1, model_type=SupervisorResult
        ),
    )
    return OperationRegistry(definitions=(item,), public_registrations=(registration,))


def _executor_registry(executor_type: type[object], build: Callable[[], object]) -> OperationRegistry:
    return _opted_in(_registry(executor_type=executor_type, build=build))


def test_a_registered_refusal_releases_its_code_key_scrubbed_context_and_verdict(tmp_path: Path) -> None:
    """The refusal a frontend renders is the executor's own, without the journal learning it."""
    case = _settle_and_read(tmp_path, _executor_registry(_ContextualRefusalExecutor, _ContextualRefusalExecutor))

    receipt = case.terminal.terminal_receipt
    assert case.terminal.terminal_condition is OperationTerminalCondition.REFUSED
    assert receipt is not None and receipt.error_detail_ref is not None
    registered = get_registered_error_code(AggregationUnsupportedModeloError)
    assert receipt.refusal_ref == registered.code
    assert isinstance(case.detail, OperationResultProjectionSuccessV1)
    detail = case.detail.projection
    assert isinstance(detail, OperationErrorDetailV1)
    assert detail.kind is OperationErrorDetailKind.REGISTERED_ERROR
    assert detail.error_code == registered.code
    assert detail.message_key == _REFUSAL_MESSAGE_KEY
    context = detail.context_mapping()
    assert context["modelo"] == "111"
    assert context["transaction_id"] == _ROW_IDENTITY
    # The envelope's own redaction applies before the detail is stored.
    assert context["api_token"] == _REDACTED_VALUE
    verdict = detail.precondition_verdict()
    assert verdict is not None
    assert verdict.failed_condition_id == CliExceptionPrecondition.REFUSAL_RETRIED.value
    # The context value is in the encrypted detail, never the credential-free journal.
    journal_bytes = b"".join(path.read_bytes() for path in case.storage_root.rglob("*") if path.is_file())
    assert _ROW_IDENTITY.encode() not in journal_bytes


def test_an_application_record_fault_releases_the_record_and_rule_but_never_the_value(tmp_path: Path) -> None:
    """A record the application built that broke its contract is named, with the value withheld."""
    case = _settle_and_read(tmp_path, _executor_registry(_RecordFaultExecutor, _RecordFaultExecutor))

    receipt = case.terminal.terminal_receipt
    assert case.terminal.terminal_condition is OperationTerminalCondition.FAILED
    assert receipt is not None and receipt.failure_error_code is None and receipt.error_detail_ref is not None
    assert isinstance(case.detail, OperationResultProjectionSuccessV1)
    detail = case.detail.projection
    assert isinstance(detail, OperationErrorDetailV1)
    assert detail.kind is OperationErrorDetailKind.RECORD_VALIDATION
    assert detail.error_code is None and detail.message_key is None
    context = detail.context_mapping()
    assert context["failing_record"] == "_BoundedRecord"
    assert "String should have at most 64 characters" in context["violations"]
    assert _OFFENDING_VALUE not in detail.model_dump_json()
    assert _OFFENDING_VALUE[:20] not in detail.model_dump_json()
    journal_bytes = b"".join(path.read_bytes() for path in case.storage_root.rglob("*") if path.is_file())
    assert _OFFENDING_VALUE.encode() not in journal_bytes


def test_an_unexpected_failure_records_no_detail_and_keeps_its_prose_out_of_storage(tmp_path: Path) -> None:
    """An exception with no public facts leaves only the opaque correlation the journal already had."""
    executor = UnexpectedFailureExecutor()
    registry = _opted_in(
        _registry(
            executor_type=UnexpectedFailureExecutor,
            build=lambda: executor,
            capabilities=_capabilities(
                owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK}),
                permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            ),
        )
    )
    case = _settle_and_read(tmp_path, registry)

    receipt = case.terminal.terminal_receipt
    assert case.terminal.terminal_condition is OperationTerminalCondition.FAILED
    assert receipt is not None and receipt.error_detail_ref is None and receipt.diagnostic_ref is not None
    assert isinstance(case.detail, OperationResultProjectionRefusalV1)
    assert case.detail.code is OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE
    assert _SENSITIVE_EXCEPTION_DETAIL not in case.terminal.model_dump_json()
    _assert_sensitive_detail_absent_from_operation_bytes(case.storage_root)


def test_the_detail_is_read_only_under_its_own_schema_identity(tmp_path: Path) -> None:
    """Asking for the detail under any other schema refuses rather than releasing it."""
    registry = _executor_registry(_ContextualRefusalExecutor, _ContextualRefusalExecutor)
    result_schema = registry.lookup_public_contract("operation.supervisor.test").result_schema
    case = _settle_and_read(tmp_path, registry, result_schema=result_schema)

    assert case.terminal.terminal_receipt is not None
    assert case.terminal.terminal_receipt.error_detail_ref is not None
    assert isinstance(case.detail, OperationResultProjectionRefusalV1)
    assert case.detail.code is OperationResultProjectionRefusalCode.OPERATION_NOT_SUCCESSFUL


def test_a_definition_that_does_not_opt_in_records_no_detail(tmp_path: Path) -> None:
    """Without the opt-in, the same refusal keeps only its registered code, as before."""
    registry = _registry(executor_type=_ContextualRefusalExecutor, build=_ContextualRefusalExecutor)
    case = _settle_and_read(tmp_path, registry)

    receipt = case.terminal.terminal_receipt
    assert case.terminal.terminal_condition is OperationTerminalCondition.REFUSED
    assert receipt is not None and receipt.error_detail_ref is None
    assert receipt.refusal_ref == get_registered_error_code(AggregationUnsupportedModeloError).code
    assert isinstance(case.detail, OperationResultProjectionRefusalV1)
