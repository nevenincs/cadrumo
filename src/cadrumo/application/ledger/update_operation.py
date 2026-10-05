"""Registered exact-profile correction of one canonical ledger transaction.

Core types: :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from pydantic import BaseModel, ValidationError

from ...core.async_cleanup import await_cancellation_complete
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.parsing.dates import parse_iso8601_date
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.models import BucketTransactionRef, Transaction, TransactionCatalogue
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory, require_exact_ledger_action_ports
from .actions_common import require_registered_own_account
from .actions_manual import ledger_transaction_result_payload, update_manual_transaction_fields
from .id_resolution import resolve_transaction_id
from .models import (
    LedgerTransactionResultPayload,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)
from .own_account_ports import OwnAccountRepositoryFactory
from .read_access import resolve_ledger_commit_access
from .transaction_projection import LedgerTransactionProjection
from .update_contracts import (
    LEDGER_UPDATE_MAX_VALIDATION_MESSAGES,
    LEDGER_UPDATE_OPERATION_DEFINITION_ID,
    LEDGER_UPDATE_PHASE,
    LEDGER_UPDATE_VALIDATION_REFUSAL_CODE,
    LedgerUpdateExecutionResult,
    LedgerUpdateOperationResult,
    LedgerUpdateRequest,
    LedgerUpdateValidationMessages,
)
from .validation_messages import bounded_validation_messages


class LedgerUpdateExecutor:
    """Apply the canonical edit under exact-profile and pinned-authority custody."""

    def __init__(
        self,
        ports_factory: LedgerActionPortsFactory,
        own_account_repository_factory: OwnAccountRepositoryFactory,
    ) -> None:
        """Retain the exact-profile service and own-account register capabilities."""
        self._ports_factory = ports_factory
        self._own_account_repository_factory = own_account_repository_factory

    async def execute(
        self,
        request: OperationRequest[LedgerUpdateRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Resolve a current prefix and commit one canonical update."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_UPDATE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(LEDGER_UPDATE_PHASE)
        commit = _commit_update(
            payload,
            bucket_id=bucket_id,
            operation=context.authority_operation,
            ports_factory=self._ports_factory,
            own_account_repository_factory=self._own_account_repository_factory,
            context=context,
        )
        return await await_cancellation_complete(commit, task_name="ledger-update-commit")


def _prepare_update(
    payload: LedgerUpdateRequest,
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    ports_factory: LedgerActionPortsFactory,
) -> tuple[LedgerActionPorts, TransactionCatalogue, str, ManualLedgerTransactionPatch]:
    ports = ports_factory(bucket_id=bucket_id, operation=operation)
    require_exact_ledger_action_ports(ports, bucket_id=bucket_id, operation=operation)
    catalogue = ports.transaction_repository.load()
    transaction_id = resolve_transaction_id(payload.transaction_id, catalogue.transactions)
    patch_values = _manual_patch_values(payload)
    patch = ManualLedgerTransactionPatch.model_validate(patch_values)
    return ports, catalogue, transaction_id, patch


def _manual_patch_values(payload: LedgerUpdateRequest) -> dict[str, object]:
    patch_values: dict[str, object] = {name: getattr(payload.patch, name) for name in payload.patch_fields}
    _normalise_update_dates(patch_values)
    _normalise_update_amounts(patch_values)
    _normalise_update_direction(patch_values)
    return patch_values


def _normalise_update_dates(patch_values: dict[str, object]) -> None:
    for field_name in ("booked_date", "value_date"):
        raw_date = patch_values.get(field_name)
        if isinstance(raw_date, str):
            parsed_date = parse_iso8601_date(raw_date)
            if parsed_date is None:
                raise ValueError("ledger update dates must use YYYY-MM-DD")
            patch_values[field_name] = parsed_date
        elif raw_date is not None:
            raise ValueError("ledger update dates must use YYYY-MM-DD")


def _normalise_update_amounts(patch_values: dict[str, object]) -> None:
    for field_name in ("amount", "taxable_base", "iva_rate", "iva_amount"):
        if field_name in patch_values and patch_values[field_name] is not None:
            raw_value = patch_values[field_name]
            value = try_parse_canonical_decimal(str(raw_value), signed=field_name != "amount")
            if value is None:
                raise ValueError("ledger update decimal values must use canonical decimal text")
            patch_values[field_name] = value


def _normalise_update_direction(patch_values: dict[str, object]) -> None:
    if "direction" not in patch_values or patch_values["direction"] is None:
        return
    raw_direction = patch_values["direction"]
    if not isinstance(raw_direction, str):
        raise ValueError("ledger update direction must be canonical transaction text")
    patch_values["direction"] = TransactionDirection(raw_direction)


async def _commit_update(
    payload: LedgerUpdateRequest,
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
    ports_factory: LedgerActionPortsFactory,
    own_account_repository_factory: OwnAccountRepositoryFactory,
    context: OperationExecutorContext,
) -> str | OperationRefusalEvidence:
    async with context.cancellation.irreversible_section():
        ports, catalogue, transaction_id, patch = await asyncio.to_thread(
            _prepare_update,
            payload,
            bucket_id=bucket_id,
            operation=operation,
            ports_factory=ports_factory,
        )
        if patch.own_account_id is not None:
            own_accounts = await asyncio.to_thread(own_account_repository_factory(bucket_id=bucket_id).load)
            require_registered_own_account(own_accounts, patch.own_account_id)
        current: Transaction = catalogue.transactions[transaction_id]
        _validate_update_projection(
            payload.profile_id,
            bucket_id=bucket_id,
            transaction_id=transaction_id,
            current=current,
        )
        await context.events.effect(OperationEffect.UNKNOWN)
        try:
            result = await asyncio.to_thread(
                update_manual_transaction_fields,
                bucket_id=bucket_id,
                transaction_id=transaction_id,
                patch=patch,
                actor=payload.actor or bucket_id or "operator",
                source_command="aeat app ledger update",
                ports=ports,
                catalogue=catalogue,
                expected_current=current,
            )
        except ValidationError as exc:
            return await _refuse_invalid_update(payload, exc, context=context)
        return await _finish_update(payload, result, source_transaction_id=transaction_id, context=context)


def _validate_update_projection(
    profile_id: UUID,
    *,
    bucket_id: str,
    transaction_id: str,
    current: Transaction,
) -> None:
    _operation_result(
        profile_id,
        ManualLedgerTransactionResult(
            ref=BucketTransactionRef(bucket_id=bucket_id, transaction_id=transaction_id),
            transaction=current,
            bucket_event_ids=(),
        ),
        source_transaction_id=transaction_id,
    )


async def _refuse_invalid_update(
    payload: LedgerUpdateRequest,
    error: ValidationError,
    *,
    context: OperationExecutorContext,
) -> OperationRefusalEvidence:
    # The canonical action validates its replacement before its catalogue/event
    # commit. Restore the known no-effect fact and keep only bounded field messages.
    await context.events.effect(OperationEffect.NONE)
    detail = LedgerUpdateExecutionResult(
        outcome="validation_error",
        profile_id=payload.profile_id,
        validation_messages=_validation_messages(error),
    )
    detail_ref = await context.operands.put(detail, written_at=now())
    return OperationRefusalEvidence(refusal_code=LEDGER_UPDATE_VALIDATION_REFUSAL_CODE, detail_ref=detail_ref)


async def _finish_update(
    payload: LedgerUpdateRequest,
    result: ManualLedgerTransactionResult,
    *,
    source_transaction_id: str,
    context: OperationExecutorContext,
) -> str:
    projected = _operation_result(payload.profile_id, result, source_transaction_id=source_transaction_id)
    await context.events.effect(OperationEffect.UPDATED if result.bucket_event_ids else OperationEffect.NONE)
    result_ref = LedgerUpdateExecutionResult(outcome="updated", profile_id=payload.profile_id, result=projected)
    return await context.operands.put(result_ref, written_at=now())


def _operation_result(
    profile_id: UUID, result: ManualLedgerTransactionResult, *, source_transaction_id: str
) -> LedgerUpdateOperationResult:
    """Validate identity and the complete canonical display projection."""
    canonical: LedgerTransactionResultPayload = ledger_transaction_result_payload(result)
    if (
        canonical.bucket_id != str(profile_id)
        or result.ref.bucket_id != canonical.bucket_id
        or result.ref.transaction_id != canonical.transaction_id
        or result.ref.transaction_id != result.transaction.transaction_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return LedgerUpdateOperationResult(
        outcome="updated",
        profile_id=profile_id,
        source_transaction_id=source_transaction_id,
        transaction=LedgerTransactionProjection.from_payload(canonical.transaction),
        review_status=canonical.review_status,
        bucket_event_ids=result.bucket_event_ids,
        group_label=result.transaction.group_label,
        own_account_id=result.transaction.own_account_id,
    )


def _validation_messages(error: ValidationError) -> LedgerUpdateValidationMessages:
    """Retain only bounded locations and messages from a Pydantic refusal."""
    return bounded_validation_messages(
        error,
        limit=LEDGER_UPDATE_MAX_VALIDATION_MESSAGES,
        fallback="ledger update values did not satisfy transaction validation",
    )


def _project_operation_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release the matching success projection or field-safe refusal details."""
    if (
        type(result) is not LedgerUpdateExecutionResult
        or receipt.identity.definition_id != LEDGER_UPDATE_OPERATION_DEFINITION_ID
    ):
        raise ValueError("invalid ledger update result or terminal receipt")
    if receipt.identity.subject_ref != profile_operation_subject(str(result.profile_id)):
        raise ValueError("ledger update result belongs to another subject")
    if result.outcome == "updated":
        projected = result.result
        return _require_update_success_receipt(receipt, projected=projected)
    _require_update_refusal_receipt(receipt)
    return LedgerUpdateOperationResult(
        outcome="validation_error",
        profile_id=result.profile_id,
        validation_messages=result.validation_messages,
    )


def _require_update_success_receipt(
    receipt: OperationTerminalReceipt,
    *,
    projected: LedgerUpdateOperationResult | None,
) -> LedgerUpdateOperationResult:
    projected = _require_update_success_projection(receipt, projected=projected)
    expected_effect = OperationEffect.UPDATED if projected.bucket_event_ids else OperationEffect.NONE
    if receipt.effect is not expected_effect:
        raise ValueError("ledger update success has an incompatible terminal receipt")
    return projected


def _require_update_success_projection(
    receipt: OperationTerminalReceipt,
    *,
    projected: LedgerUpdateOperationResult | None,
) -> LedgerUpdateOperationResult:
    if (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.diagnostic_ref is not None
        or projected is None
    ):
        raise ValueError("ledger update success has an incompatible terminal receipt")
    return projected


def _require_update_refusal_receipt(receipt: OperationTerminalReceipt) -> None:
    if (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.refusal_ref != LEDGER_UPDATE_VALIDATION_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
        or receipt.diagnostic_ref is not None
        or receipt.effect is not OperationEffect.NONE
    ):
        raise ValueError("ledger update validation refusal has an incompatible terminal receipt")


def build_ledger_update_definition(
    ports_factory: LedgerActionPortsFactory,
    own_account_repository_factory: OwnAccountRepositoryFactory,
) -> OperationDefinition:
    """Declare durable, exact-profile update with a bounded encrypted result."""
    return build_single_phase_definition(
        definition_id=LEDGER_UPDATE_OPERATION_DEFINITION_ID,
        request_type=LedgerUpdateRequest,
        result_type=LedgerUpdateExecutionResult,
        executor_type=LedgerUpdateExecutor,
        build=lambda: LedgerUpdateExecutor(ports_factory, own_account_repository_factory),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        refusal_detail_codes=frozenset({LEDGER_UPDATE_VALIDATION_REFUSAL_CODE}),
    )


def resolve_ledger_update_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile disclosure and COMMIT for every transaction update."""
    if request.definition_id != LEDGER_UPDATE_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerUpdateRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_commit_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_ledger_update_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request, bounded result, and profile access resolver."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerUpdateOperationResult,
        result_projector=_project_operation_result,
        access_resolver=resolve_ledger_update_access,
    )


__all__ = [
    "LedgerUpdateExecutor",
    "build_ledger_update_definition",
    "build_ledger_update_registration",
    "resolve_ledger_update_access",
]
