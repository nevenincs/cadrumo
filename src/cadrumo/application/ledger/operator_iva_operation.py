"""Execute, authorize, and register operator-selected IVA derivation."""

from __future__ import annotations

import asyncio

from pydantic import (
    BaseModel,
)

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.iva_category_catalogue import require_iva_category
from ...domain.iva.schema import IvaCategory
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import Transaction
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import ALL_OPERATION_FRONTENDS, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory, require_exact_ledger_action_ports
from .classify_result_contracts import (
    LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE,
)
from .classify_result_projection import classification_result_from_action
from .classify_validation import LEDGER_CLASSIFY_VALIDATION_ERRORS, classify_validation_messages
from .id_resolution import resolve_transaction_id
from .llm_classification import derive_operator_iva_substrate
from .llm_classification_ports import OperatorIvaDerivationResult
from .operator_iva_contracts import (
    LEDGER_OPERATOR_IVA_DEFINITION_ID,
    LedgerOperatorIvaExecutionResult,
    LedgerOperatorIvaRequest,
    LedgerOperatorIvaResult,
)
from .operator_iva_projection import project_operator_iva_result
from .persistence_ports import LedgerPersistenceConflictError
from .read_access import resolve_ledger_commit_access


class LedgerOperatorIvaExecutor:
    """Delegate operator-selected IVA derivation to its existing guarded writer."""

    def __init__(self, ports_factory: LedgerActionPortsFactory) -> None:
        """Retain the canonical exact-profile service composition."""
        self._ports_factory = ports_factory

    async def execute(
        self, request: OperationRequest[LedgerOperatorIvaRequest], context: OperationExecutorContext
    ) -> str | OperationRefusalEvidence:
        """Resolve and derive inside the existing COMMIT guard."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_OPERATOR_IVA_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        ports = self._ports_factory(bucket_id=bucket_id, operation=context.authority_operation)
        require_exact_ledger_action_ports(ports, bucket_id=bucket_id, operation=context.authority_operation)
        await context.events.phase(LEDGER_OPERATOR_IVA_DEFINITION_ID)

        async def refuse(error: Exception, transaction_id: str) -> OperationRefusalEvidence:
            result = LedgerOperatorIvaResult(
                profile_id=payload.profile_id,
                outcome="validation_error",
                transaction_id=transaction_id,
                iva_category=payload.iva_category,
                derivable=False,
                validation_messages=classify_validation_messages(error),
            )
            detail_ref = await context.operands.put(
                LedgerOperatorIvaExecutionResult(request=payload, result=result), written_at=now()
            )
            return OperationRefusalEvidence(refusal_code=LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE, detail_ref=detail_ref)

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():

                def prepare() -> tuple[str, Transaction, IvaCategory]:
                    with validating_governed_facts(context.authority_operation):
                        catalogue = ports.transaction_repository.load()
                        transaction_id = resolve_transaction_id(payload.transaction_id, catalogue.transactions)
                        baseline = catalogue.transactions[transaction_id]
                        category = require_iva_category(
                            payload.iva_category,
                            effective_date=baseline.raw.value_date or baseline.raw.booked_date,
                            authority=context.authority_operation,
                        )
                        if category.value != payload.iva_category:
                            raise TransactionValidationError("operator IVA category must be canonical")
                        return transaction_id, baseline, category

                try:
                    transaction_id, baseline, category = await asyncio.to_thread(prepare)
                except LEDGER_CLASSIFY_VALIDATION_ERRORS as error:
                    return await refuse(error, payload.transaction_id)
                await context.events.effect(OperationEffect.UNKNOWN)

                def derive() -> OperatorIvaDerivationResult:
                    with validating_governed_facts(context.authority_operation):
                        return derive_operator_iva_substrate(
                            bucket_id=bucket_id,
                            transaction_id=transaction_id,
                            iva_category=category,
                            actor=payload.actor or bucket_id,
                            source_command="aeat app ledger classify --iva-category --saturate",
                            ports=ports,
                            expected_current=baseline,
                        )

                try:
                    derivation = await asyncio.to_thread(derive)
                except TransactionValidationError as error:
                    await context.events.effect(OperationEffect.NONE)
                    return await refuse(error, transaction_id)
                except LedgerPersistenceConflictError:
                    await context.events.effect(OperationEffect.NONE)
                    raise
                await context.events.effect(
                    OperationEffect.UPDATED
                    if derivation.result is not None and derivation.result.bucket_event_ids
                    else OperationEffect.NONE
                )
                result = LedgerOperatorIvaResult(
                    profile_id=payload.profile_id,
                    transaction_id=transaction_id,
                    iva_category=derivation.iva_category.value,
                    derivable=derivation.derivable,
                    iva_rate=format(derivation.iva_rate, "f") if derivation.iva_rate is not None else None,
                    taxable_base=format(derivation.taxable_base, "f") if derivation.taxable_base is not None else None,
                    iva_amount=format(derivation.iva_amount, "f") if derivation.iva_amount is not None else None,
                    note=derivation.note,
                    classification=classification_result_from_action(payload.profile_id, derivation.result)
                    if derivation.result is not None
                    else None,
                )
                return await context.operands.put(
                    LedgerOperatorIvaExecutionResult(request=payload, result=result), written_at=now()
                )

        return await await_cancellation_complete(commit(), task_name="ledger-operator-iva-commit")


def resolve_ledger_operator_iva_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact-profile ledger disclosure and COMMIT for IVA derivation."""
    if request.definition_id != LEDGER_OPERATOR_IVA_DEFINITION_ID or not isinstance(
        request.payload, LedgerOperatorIvaRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_commit_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_operator_iva_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Register the existing derivation with immutable profile custody and COMMIT."""
    return build_single_phase_definition(
        definition_id=LEDGER_OPERATOR_IVA_DEFINITION_ID,
        request_type=LedgerOperatorIvaRequest,
        result_type=LedgerOperatorIvaExecutionResult,
        executor_type=LedgerOperatorIvaExecutor,
        build=lambda: LedgerOperatorIvaExecutor(ports_factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
        refusal_detail_codes=frozenset({LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE}),
    )


def build_ledger_operator_iva_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the bounded operator IVA request/result and exact access policy."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerOperatorIvaResult,
        result_projector=project_operator_iva_result,
        access_resolver=resolve_ledger_operator_iva_access,
    )
