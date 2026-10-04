"""Registered exact-profile manual creation of one ledger transaction."""

from __future__ import annotations

import asyncio
from typing import Literal

from pydantic import BaseModel, ValidationError

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.errors import TransactionValidationError
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..prorrata_register.ports import ProrrataRegisterRepositoryFactory
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPortsFactory, require_exact_ledger_action_ports
from .actions_common import require_registered_own_account
from .actions_manual import create_manual_transaction
from .ledger_add_command import (
    SourceJurisdictionRequiredError,
    prepare_ledger_add_command,
    resolve_ledger_add_prorrata_advisory_facts,
)
from .ledger_add_contracts import (
    LEDGER_ADD_OPERATION_DEFINITION_ID,
    LEDGER_ADD_VALIDATION_REFUSAL_CODE,
    LedgerAddExecutionResult,
    LedgerAddOperationResult,
    LedgerAddRequest,
)
from .ledger_add_results import (
    build_ledger_add_operation_result,
    build_ledger_add_validation_messages,
    project_ledger_add_result,
)
from .own_account_ports import OwnAccountRepositoryFactory
from .read_access import resolve_ledger_commit_access

LEDGER_ADD_PHASE = "ledger.add"


class LedgerAddExecutor:
    """Create one canonical transaction under exact-profile COMMIT custody."""

    def __init__(
        self,
        ports_factory: LedgerActionPortsFactory,
        prorrata_register_repository_factory: ProrrataRegisterRepositoryFactory,
        own_account_repository_factory: OwnAccountRepositoryFactory,
    ) -> None:
        """Retain exact-bucket ledger, prorrata and own-account repository factories."""
        self._ports_factory = ports_factory
        self._prorrata_register_repository_factory = prorrata_register_repository_factory
        self._own_account_repository_factory = own_account_repository_factory

    async def execute(
        self,
        request: OperationRequest[LedgerAddRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Validate, resolve advisory state, and perform one guarded canonical add."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_ADD_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_ADD_PHASE)

        async def refuse(
            error: Exception,
            *,
            code: Literal[
                "source_jurisdiction_required_irnr",
                "source_jurisdiction_required_beckham",
                "invalid_command",
            ] = "invalid_command",
        ) -> OperationRefusalEvidence:
            detail = LedgerAddExecutionResult(
                outcome="validation_error",
                profile_id=payload.profile_id,
                validation_code=code,
                validation_messages=build_ledger_add_validation_messages(error),
            )
            detail_ref = await context.operands.put(detail, written_at=now())
            return OperationRefusalEvidence(
                refusal_code=LEDGER_ADD_VALIDATION_REFUSAL_CODE,
                detail_ref=detail_ref,
            )

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                operation: PinnedAuthorityOperation = context.authority_operation
                try:
                    ports = await asyncio.to_thread(self._ports_factory, bucket_id=bucket_id, operation=operation)
                    require_exact_ledger_action_ports(ports, bucket_id=bucket_id, operation=operation)
                    command = await asyncio.to_thread(prepare_ledger_add_command, payload, operation)
                    if command.own_account_id is not None:
                        own_accounts = await asyncio.to_thread(
                            self._own_account_repository_factory(bucket_id=bucket_id).load
                        )
                        require_registered_own_account(own_accounts, command.own_account_id)
                    advisory_input_inert, advisory_sector_unmatched = await asyncio.to_thread(
                        resolve_ledger_add_prorrata_advisory_facts,
                        payload,
                        command,
                        self._prorrata_register_repository_factory,
                        operation,
                    )
                except SourceJurisdictionRequiredError as refusal:
                    return await refuse(refusal, code=refusal.code)
                except (TransactionValidationError, ValidationError, ValueError) as error:
                    return await refuse(error)

                # From this point the canonical service may have durably committed
                # the transaction/event even if a later attachment back-reference
                # or projection step fails. Preserve that uncertainty.
                await context.events.effect(OperationEffect.UNKNOWN)
                from ...application.exchange_rate_provider import exchange_rate_provider
                from ...domain.currency.service import CurrencyNormalizationService

                result = await asyncio.to_thread(
                    create_manual_transaction,
                    command,
                    ports=ports,
                    currency_normalizer=CurrencyNormalizationService(rate_provider=exchange_rate_provider()),
                    require_revision_guard=True,
                )
                projected = build_ledger_add_operation_result(
                    payload.profile_id,
                    result,
                    advisory_input_inert=advisory_input_inert,
                    advisory_sector_unmatched=advisory_sector_unmatched,
                    advisory_input_classification=payload.input_classification,
                    advisory_sector_id=payload.prorrata_sector,
                )
                await context.events.effect(
                    OperationEffect.UPDATED if result.bucket_event_ids else OperationEffect.NONE
                )
                execution = LedgerAddExecutionResult(
                    outcome="created",
                    profile_id=payload.profile_id,
                    result=projected,
                )
                return await context.operands.put(
                    execution,
                    written_at=now(),
                )

        return await await_cancellation_complete(commit(), task_name="ledger-add-commit")


def build_ledger_add_definition(
    ports_factory: LedgerActionPortsFactory,
    prorrata_register_repository_factory: ProrrataRegisterRepositoryFactory,
    own_account_repository_factory: OwnAccountRepositoryFactory,
) -> OperationDefinition:
    """Build the private worker definition for exact-profile manual creation."""
    return build_single_phase_definition(
        definition_id=LEDGER_ADD_OPERATION_DEFINITION_ID,
        request_type=LedgerAddRequest,
        result_type=LedgerAddExecutionResult,
        executor_type=LedgerAddExecutor,
        build=lambda: LedgerAddExecutor(
            ports_factory, prorrata_register_repository_factory, own_account_repository_factory
        ),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        refusal_detail_codes=frozenset({LEDGER_ADD_VALIDATION_REFUSAL_CODE}),
    )


def resolve_ledger_add_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Admit only the submitted manual add bound to its exact profile."""
    if request.definition_id != LEDGER_ADD_OPERATION_DEFINITION_ID or not isinstance(request.payload, LedgerAddRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_commit_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_add_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the bounded public request/result wire contracts to the worker."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerAddOperationResult,
        result_projector=project_ledger_add_result,
        access_resolver=resolve_ledger_add_access,
    )


__all__ = [
    "LEDGER_ADD_PHASE",
    "LedgerAddExecutor",
    "build_ledger_add_definition",
    "build_ledger_add_registration",
    "resolve_ledger_add_access",
]
