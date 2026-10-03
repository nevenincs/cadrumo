"""Registered exact-profile correction of one canonical ledger transaction."""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, ValidationInfo, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.parsing.codes import normalise_iso_4217_currency
from ...core.parsing.dates import parse_iso8601_date
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.models import BucketTransactionRef, Transaction, TransactionCatalogue
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..review.filter import LedgerReviewStatus
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory, require_exact_ledger_action_ports
from .actions_common import display_decimal
from .actions_manual import ledger_transaction_result_payload, update_manual_transaction_fields
from .id_resolution import resolve_transaction_id
from .models import (
    LedgerTransactionResultPayload,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)
from .read_access import resolve_ledger_read_access
from .transaction_projection import LedgerTransactionProjection
from .validation_messages import bounded_validation_messages

LEDGER_UPDATE_OPERATION_DEFINITION_ID = "ledger.update"
LEDGER_UPDATE_PHASE = "ledger.update"
LEDGER_UPDATE_VALIDATION_REFUSAL_CODE = "REFUSED_CLI_VALIDATION_BOUNDARY"
_MAX_UPDATE_EVENT_IDS = 3
_MAX_VALIDATION_MESSAGES = 32
_UPDATE_FIELD_NAMES = frozenset(
    {
        "booked_date",
        "value_date",
        "amount",
        "direction",
        "currency",
        "counterparty",
        "description",
        "taxable_base",
        "iva_rate",
        "iva_amount",
        "irpf_category",
        "notes",
        "group_label",
    }
)
LedgerUpdatePatchField = Literal[
    "booked_date",
    "value_date",
    "amount",
    "direction",
    "currency",
    "counterparty",
    "description",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "irpf_category",
    "notes",
    "group_label",
]
_UpdateFields = Annotated[tuple[LedgerUpdatePatchField, ...], Field(min_length=1, max_length=13)]
_UpdateText = Annotated[str, Field(max_length=4096)]
_DecimalText = Annotated[str, Field(min_length=1, max_length=128)]
_IsoDateText = Annotated[str, Field(min_length=10, max_length=10)]
_TransactionPrefix = Annotated[str, Field(min_length=1, max_length=96)]
_ValidationMessage = Annotated[str, Field(min_length=1, max_length=2048)]
_ValidationMessages = Annotated[tuple[_ValidationMessage, ...], Field(max_length=_MAX_VALIDATION_MESSAGES)]


class LedgerUpdatePatch(BaseModel):
    """Bounded worker request values for the fields exposed by ``ledger update``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    booked_date: _IsoDateText | None = None
    value_date: _IsoDateText | None = None
    amount: _DecimalText | None = None
    direction: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    currency: Annotated[str, Field(min_length=3, max_length=3)] | None = None
    counterparty: _UpdateText | None = None
    description: _UpdateText | None = None
    taxable_base: _DecimalText | None = None
    iva_rate: _DecimalText | None = None
    iva_amount: _DecimalText | None = None
    irpf_category: _UpdateText | None = None
    notes: _UpdateText | None = None
    group_label: Annotated[str, Field(max_length=64)] | None = None

    @field_validator("booked_date", "value_date")
    @classmethod
    def _iso_dates(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = parse_iso8601_date(value)
        except ValueError:
            raise ValueError("ledger update dates must use YYYY-MM-DD") from None
        if parsed is None or parsed.isoformat() != value:
            raise ValueError("ledger update dates must use YYYY-MM-DD")
        return value

    @field_validator("amount", "taxable_base", "iva_rate", "iva_amount")
    @classmethod
    def _canonical_decimal_text(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        field_name = info.field_name or ""
        parsed = try_parse_canonical_decimal(value, signed=field_name != "amount")
        if parsed is None:
            raise ValueError("ledger update decimal values must use canonical decimal text")
        if display_decimal(parsed) != value:
            raise ValueError("ledger update decimal values must use canonical decimal text")
        return value

    @field_validator("direction")
    @classmethod
    def _known_direction(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            TransactionDirection(value)
        except ValueError:
            raise ValueError("ledger update direction must be a canonical transaction direction") from None
        return value

    @field_validator("currency")
    @classmethod
    def _canonical_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalise_iso_4217_currency(value)
        if normalized != value:
            raise ValueError("ledger update currency must be canonical ISO 4217 text")
        return value


class LedgerUpdateRequest(BaseModel):
    """Private exact-profile request; ``transaction_id`` may be a CLI prefix.

    ``patch_fields`` preserves explicit ``None`` clears across JSON serialization.
    Nested defaults serialize as null, so every unselected value must be null;
    that rule makes the mask a safe omission equivalent after worker decode.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: _TransactionPrefix
    patch: LedgerUpdatePatch
    patch_fields: _UpdateFields
    actor: Annotated[str, Field(min_length=1, max_length=64)] | None = None

    @field_validator("patch_fields")
    @classmethod
    def _unique_supported_patch_fields(
        cls,
        value: tuple[LedgerUpdatePatchField, ...],
    ) -> tuple[LedgerUpdatePatchField, ...]:
        if len(set(value)) != len(value) or not set(value) <= _UPDATE_FIELD_NAMES:
            raise ValueError("ledger update patch fields must be unique supported fields")
        return value

    @model_validator(mode="after")
    def _reject_unselected_patch_values(self) -> LedgerUpdateRequest:
        selected = set(self.patch_fields)
        if any(getattr(self.patch, field_name) is not None for field_name in _UPDATE_FIELD_NAMES - selected):
            raise ValueError("ledger update request contains an unselected patch value")
        return self


class LedgerUpdateOperationResult(BaseModel):
    """Bounded success projection or field-safe update validation refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["updated", "validation_error"]
    profile_id: UUID
    transaction: LedgerTransactionProjection | None = None
    review_status: LedgerReviewStatus | None = None
    bucket_event_ids: Annotated[tuple[str, ...], Field(max_length=_MAX_UPDATE_EVENT_IDS)] = ()
    group_label: Annotated[str, Field(max_length=64)] | None = None
    validation_messages: _ValidationMessages = ()

    @model_validator(mode="after")
    def _complete_selected_outcome(self) -> LedgerUpdateOperationResult:
        if self.outcome == "updated":
            _require_updated_result(self)
        else:
            _require_update_refusal_result(self)
        return self


class LedgerUpdateExecutionResult(BaseModel):
    """Encrypted worker operand for either update completion or input refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["updated", "validation_error"]
    profile_id: UUID
    result: LedgerUpdateOperationResult | None = None
    validation_messages: _ValidationMessages = ()

    @model_validator(mode="after")
    def _complete_selected_outcome(self) -> LedgerUpdateExecutionResult:
        if self.outcome == "updated":
            if self.result is None or self.result.outcome != "updated" or self.validation_messages:
                raise ValueError("updated ledger execution requires its result projection")
            if self.result.profile_id != self.profile_id:
                raise ValueError("updated ledger execution result belongs to another profile")
        elif self.result is not None or not self.validation_messages:
            raise ValueError("ledger validation refusal requires only bounded validation messages")
        return self


class LedgerUpdateExecutor:
    """Apply the canonical edit under exact-profile and pinned-authority custody."""

    def __init__(self, ports_factory: LedgerActionPortsFactory) -> None:
        """Retain the exact-profile service composition capability."""
        self._ports_factory = ports_factory

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
        return await _finish_update(payload, result, context=context)


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
    context: OperationExecutorContext,
) -> str:
    projected = _operation_result(payload.profile_id, result)
    await context.events.effect(OperationEffect.UPDATED if result.bucket_event_ids else OperationEffect.NONE)
    result_ref = LedgerUpdateExecutionResult(outcome="updated", profile_id=payload.profile_id, result=projected)
    return await context.operands.put(result_ref, written_at=now())


def _require_updated_result(result: LedgerUpdateOperationResult) -> None:
    if result.transaction is None or result.review_status is None or result.validation_messages:
        raise ValueError("updated ledger result requires its transaction and review status")


def _require_update_refusal_result(result: LedgerUpdateOperationResult) -> None:
    if (
        result.transaction is not None
        or result.review_status is not None
        or result.bucket_event_ids
        or result.group_label is not None
        or not result.validation_messages
    ):
        raise ValueError("validation refusal cannot carry transaction output or an effect")


def _operation_result(profile_id: UUID, result: ManualLedgerTransactionResult) -> LedgerUpdateOperationResult:
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
        transaction=LedgerTransactionProjection.from_payload(canonical.transaction),
        review_status=canonical.review_status,
        bucket_event_ids=result.bucket_event_ids,
        group_label=result.transaction.group_label,
    )


def _validation_messages(error: ValidationError) -> _ValidationMessages:
    """Retain only bounded locations and messages from a Pydantic refusal."""
    return bounded_validation_messages(
        error,
        limit=_MAX_VALIDATION_MESSAGES,
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


def build_ledger_update_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare durable, exact-profile update with a bounded encrypted result."""
    return OperationDefinition(
        definition_id=LEDGER_UPDATE_OPERATION_DEFINITION_ID,
        request_type=LedgerUpdateRequest,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerUpdateRequest,
            executor_type=LedgerUpdateExecutor,
            build=lambda: LedgerUpdateExecutor(ports_factory),
        ),
        result_type=LedgerUpdateExecutionResult,
        phase_codes=(LEDGER_UPDATE_PHASE,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
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
    resolved = resolve_ledger_read_access(
        request,
        context,
        profile_id=request.payload.profile_id,
        periods=frozenset(),
    )
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def build_ledger_update_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact request, bounded result, and profile access resolver."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerUpdateOperationResult,
        result_projector=_project_operation_result,
        access_resolver=resolve_ledger_update_access,
    )


__all__ = [
    "LEDGER_UPDATE_OPERATION_DEFINITION_ID",
    "LEDGER_UPDATE_PHASE",
    "LEDGER_UPDATE_VALIDATION_REFUSAL_CODE",
    "LedgerUpdateExecutionResult",
    "LedgerUpdateExecutor",
    "LedgerUpdateOperationResult",
    "LedgerUpdatePatch",
    "LedgerUpdatePatchField",
    "LedgerUpdateRequest",
    "build_ledger_update_definition",
    "build_ledger_update_registration",
    "resolve_ledger_update_access",
]
