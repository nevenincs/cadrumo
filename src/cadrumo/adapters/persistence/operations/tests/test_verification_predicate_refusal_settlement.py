"""A malformed registry verification predicate settles as a refusal over real durable operation storage.

The executor evaluates a malformed predicate through the real modelo
verification evaluator. The supervisor must settle the stop as ``REFUSED``
with the registered refusal code, and the opted-in public error detail must
carry the refusal kind, operator and route the evaluator reported.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.action_errors import ModeloVerificationPredicateMalformedError
from cadrumo.application.modelo.verification_predicates import (
    VerificationPredicateRefusal,
    VerificationPredicateRoute,
    evaluate_advisory_predicate_fires,
)
from cadrumo.application.operations.error_detail import (
    OperationErrorDetailKind,
    OperationErrorDetailV1,
    operation_error_detail_schema,
)
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.projection_services import OperationResultProjectionService
from cadrumo.application.operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.domain.calculations.registry.schema_verification import VerificationPredicateOperator

from .supervision_support import run_to_settlement
from .supervisor_test_support import (
    SupervisorRequest,
    SupervisorResult,
    operation_repositories,
    operation_supervisor,
    supervisor_registry,
    supervisor_request,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_REGISTERED = get_registered_error_code(ModeloVerificationPredicateMalformedError)


class _MalformedPredicateExecutor:
    """Evaluate an ADVISORY ``equals_sum`` predicate that names too few addends."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del request, context
        evaluate_advisory_predicate_fires(
            'equals_sum(["01", "02"])',
            {validated_casilla_id("01"): Decimal("1"), validated_casilla_id("02"): Decimal("1")},
        )
        return None


def _opted_in_registry() -> OperationRegistry:
    base = supervisor_registry(executor_type=_MalformedPredicateExecutor, build=_MalformedPredicateExecutor)
    item = base.lookup("operation.supervisor.test").model_copy(update={"public_error_detail": True})
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


def test_a_malformed_predicate_settles_refused_with_its_code_and_refusal_reason(tmp_path: Path) -> None:
    registry = _opted_in_registry()
    storage_root = tmp_path / "durable-state"
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = operation_repositories(
            storage_root=storage_root, profile_objects=profile.repository
        )
        supervisor = operation_supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
        )
        operation_id = asyncio.run(supervisor.submit(supervisor_request(), operation_id="3" * 64))
        terminal = asyncio.run(run_to_settlement(supervisor, operation_id))
        contract = registry.lookup_public_contract(terminal.identity.definition_id)
        service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)
        projected = asyncio.run(
            service.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=operation_error_detail_schema(),
                ),
                OperationErrorDetailV1,
            )
        )

    receipt = terminal.terminal_receipt
    assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
    assert receipt is not None
    assert _REGISTERED.code == "REFUSED_MODELO_VERIFICATION_PREDICATE_MALFORMED"
    assert receipt.refusal_ref == _REGISTERED.code
    assert receipt.failure_error_code is None
    assert receipt.error_detail_ref is not None
    assert isinstance(projected, OperationResultProjectionSuccessV1)
    detail = projected.projection
    assert isinstance(detail, OperationErrorDetailV1)
    assert detail.kind is OperationErrorDetailKind.REGISTERED_ERROR
    assert detail.error_code == _REGISTERED.code
    assert detail.message_key == _REGISTERED.message_key
    context = detail.context_mapping()
    assert context["predicate_refusal"] == VerificationPredicateRefusal.ARITY.value
    assert context["predicate_operator"] == VerificationPredicateOperator.EQUALS_SUM.value
    assert context["predicate_route"] == VerificationPredicateRoute.ADVISORY.value
