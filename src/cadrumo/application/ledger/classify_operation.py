"""Registered exact-profile classification of one canonical ledger transaction."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Literal, cast
from uuid import UUID

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.country_code import CountryCodeAlpha2
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.parsing.codes import normalise_iso_3166_alpha2_jurisdiction
from ...core.time.clock import now
from ...domain.buckets.event import BucketEventId
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.eu_member_state_catalogue import require_eu_member_state
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.iva_category_catalogue import require_iva_category
from ...domain.calculations.registry.iva_deduction_catalogue import require_iva_deduction_fact_kind
from ...domain.categories.spending_category_catalogue import require_spending_category
from ...domain.iva.schema import IvaCategory
from ...domain.transactions.enums import BusinessClassification, is_classified
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import BucketTransactionRef, Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..review.filter import LedgerReviewStatus
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory
from .actions_common import display_decimal
from .actions_manual import ledger_transaction_result_payload, update_manual_transaction_fields
from .id_resolution import normalise_transaction_id_prefix, resolve_transaction_id
from .llm_classification import derive_operator_iva_substrate
from .llm_classification_ports import OperatorIvaDerivationResult
from .m210_classification import resolve_m210_income_classification
from .models import (
    LedgerTransactionResultPayload,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)
from .persistence_ports import LedgerPersistenceConflictError
from .read_access import resolve_ledger_read_access
from .transaction_projection import LedgerTransactionProjection

LEDGER_CLASSIFY_OPERATION_DEFINITION_ID = "ledger.classify.single"
LEDGER_OPERATOR_IVA_DEFINITION_ID = "ledger.classify.iva-derive"
LEDGER_CLASSIFY_PHASE = "ledger.classify.single"
_MAX_CLASSIFY_EVENT_IDS = 3
_MAX_VALIDATION_MESSAGES = 32
_MAX_RESULT_JSON_BYTES = 262_144

LedgerClassifyPatchField = Literal[
    "business_classification",
    "business_pct",
    "category_id",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "irpf_category",
    "m210_income_classification",
    "iva_category",
    "deduction_fact_kind",
    "investment_asset_id",
    "counterparty_country",
    "counterparty_identification_state",
    "notes",
]
_CLASSIFY_FIELDS = frozenset(
    {
        "business_classification",
        "business_pct",
        "category_id",
        "taxable_base",
        "iva_rate",
        "iva_amount",
        "irpf_category",
        "m210_income_classification",
        "iva_category",
        "deduction_fact_kind",
        "investment_asset_id",
        "counterparty_country",
        "counterparty_identification_state",
        "notes",
    },
)
_ClassifyFields = Annotated[tuple[LedgerClassifyPatchField, ...], Field(min_length=1, max_length=14)]
_DecimalText = Annotated[str, Field(min_length=1, max_length=128)]
_ShortText = Annotated[str, Field(max_length=128)]
_LongText = Annotated[str, Field(max_length=4096)]
_TransactionPrefix = Annotated[str, Field(min_length=1, max_length=96)]
_ValidationMessage = Annotated[str, Field(min_length=1, max_length=2048)]
_ValidationMessages = Annotated[tuple[_ValidationMessage, ...], Field(max_length=_MAX_VALIDATION_MESSAGES)]
_ValidationKind = Literal["none", "input", "m210_incoming_only", "m210_required_options"]


class LedgerClassifyPatch(BaseModel):
    """Bounded JSON-stable values for the manual classification patch."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    business_classification: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    business_pct: _DecimalText | None = None
    category_id: _ShortText | None = None
    taxable_base: _DecimalText | None = None
    iva_rate: _DecimalText | None = None
    iva_amount: _DecimalText | None = None
    irpf_category: _LongText | None = None
    iva_category: _ShortText | None = None
    deduction_fact_kind: _ShortText | None = None
    investment_asset_id: _ShortText | None = None
    counterparty_country: CountryCodeAlpha2 | None = None
    counterparty_identification_state: Annotated[str, Field(max_length=2)] | None = None
    notes: _LongText | None = None

    @field_validator("business_classification")
    @classmethod
    def _manual_classification_only(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            classification = BusinessClassification(value)
        except ValueError:
            raise ValueError("ledger classify requires a canonical business classification") from None
        if not is_classified(classification):
            raise ValueError("ledger classify cannot assign a pipeline-owned disposition")
        return classification.value

    @field_validator("business_pct", "taxable_base", "iva_rate", "iva_amount")
    @classmethod
    def _canonical_decimal_text(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        parsed = try_parse_canonical_decimal(value, signed=False)
        if parsed is None or display_decimal(parsed) != value:
            raise ValueError(f"ledger classify {info.field_name} must use canonical decimal text")
        if info.field_name == "business_pct" and not Decimal("0") <= parsed <= Decimal("1"):
            raise ValueError("ledger classify business_pct must be within 0..1")
        return value

    @field_validator("counterparty_country")
    @classmethod
    def _canonical_country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalise_iso_3166_alpha2_jurisdiction(value)
        if normalized != value:
            raise ValueError("ledger classify counterparty country must be canonical ISO alpha-2 text")
        return value


class LedgerClassifyM210Options(BaseModel):
    """Bounded string-only representation of the explicit CLI M210 options."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    tipo_renta_code: Annotated[str, Field(max_length=32)] | None = None
    gross_income_amount: _DecimalText | None = None
    applicable_rate: _DecimalText | None = None
    payer_mode: Annotated[str, Field(max_length=64)] | None = None
    payer_id: _ShortText | None = None
    asset_or_right_id: _ShortText | None = None

    @field_validator("gross_income_amount", "applicable_rate")
    @classmethod
    def _canonical_m210_decimal(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        parsed = try_parse_canonical_decimal(value, signed=False)
        if parsed is None or display_decimal(parsed) != value:
            raise ValueError(f"M210 {info.field_name} must use canonical decimal text")
        if info.field_name == "applicable_rate" and parsed > Decimal("1"):
            raise ValueError("M210 applicable_rate must be within 0..1")
        return value

    @field_validator("payer_id", "asset_or_right_id")
    @classmethod
    def _normalise_optional_identity(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class LedgerClassifyRequest(BaseModel):
    """Exact-profile single-classify request; optional nulls use an explicit mask."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: _TransactionPrefix
    patch: LedgerClassifyPatch
    patch_fields: _ClassifyFields
    m210: LedgerClassifyM210Options | None = None
    actor: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    reaffirm: bool = False

    @field_validator("patch_fields")
    @classmethod
    def _unique_canonical_patch_fields(
        cls,
        value: tuple[LedgerClassifyPatchField, ...],
    ) -> tuple[LedgerClassifyPatchField, ...]:
        if len(set(value)) != len(value) or not set(value) <= _CLASSIFY_FIELDS:
            raise ValueError("ledger classify fields must be unique supported fields")
        if value != tuple(sorted(value)):
            raise ValueError("ledger classify fields must use canonical sorted order")
        return value

    @model_validator(mode="after")
    def _selected_values_match_mask(self) -> LedgerClassifyRequest:
        selected = set(self.patch_fields)
        if "business_classification" not in selected or self.patch.business_classification is None:
            raise ValueError("ledger classify must select one business classification")
        classification = BusinessClassification(self.patch.business_classification)
        business_pct_selected = "business_pct" in selected and self.patch.business_pct is not None
        if (classification is BusinessClassification.MIXED) != business_pct_selected:
            raise ValueError("mixed classification requires exactly one business percentage")
        patch_values = self.patch.model_dump()
        unselected_fields = _CLASSIFY_FIELDS - {"m210_income_classification"} - selected
        if any(patch_values[name] is not None for name in unselected_fields):
            raise ValueError("ledger classify request contains an unselected patch value")
        m210_selected = "m210_income_classification" in selected
        m210_options_requested = self.m210 is not None and any(
            getattr(self.m210, field_name) is not None
            for field_name in (
                "tipo_renta_code",
                "gross_income_amount",
                "applicable_rate",
                "payer_mode",
                "payer_id",
                "asset_or_right_id",
            )
        )
        if m210_selected != m210_options_requested:
            raise ValueError("ledger classify M210 options and patch selection must agree")
        if (
            self.m210 is not None
            and not any(
                getattr(self.m210, field_name) is not None
                for field_name in ("tipo_renta_code", "gross_income_amount", "applicable_rate", "payer_mode")
            )
            and any((self.m210.payer_id, self.m210.asset_or_right_id))
        ):
            raise ValueError("M210 payer and asset identifiers require the four declaration answers")
        return self


class LedgerClassifyOperationResult(BaseModel):
    """Bounded success projection or field-safe classification refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["classified", "validation_error"]
    profile_id: UUID
    transaction: LedgerTransactionProjection | None = None
    deduction_fact_kind: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    investment_asset_id: _ShortText | None = None
    review_status: LedgerReviewStatus | None = None
    bucket_event_ids: Annotated[tuple[BucketEventId, ...], Field(max_length=_MAX_CLASSIFY_EVENT_IDS)] = ()
    validation_kind: _ValidationKind = "none"
    validation_messages: _ValidationMessages = ()

    @model_validator(mode="after")
    def _complete_selected_outcome(self) -> LedgerClassifyOperationResult:
        if self.outcome == "classified":
            if (
                self.transaction is None
                or self.review_status is None
                or self.validation_kind != "none"
                or self.validation_messages
            ):
                raise ValueError("classified result requires its transaction and review status")
        elif (
            self.transaction is not None
            or self.deduction_fact_kind is not None
            or self.investment_asset_id is not None
            or self.review_status is not None
            or self.bucket_event_ids
            or self.validation_kind == "none"
            or not self.validation_messages
        ):
            raise ValueError("validation refusal cannot carry transaction output or an effect")
        return self


class LedgerClassifyExecutionResult(BaseModel):
    """Encrypted worker result for success or bounded input refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["classified", "validation_error"]
    profile_id: UUID
    result: LedgerClassifyOperationResult | None = None
    validation_kind: _ValidationKind = "none"
    validation_messages: _ValidationMessages = ()

    @model_validator(mode="after")
    def _complete_selected_outcome(self) -> LedgerClassifyExecutionResult:
        if self.outcome == "classified":
            if (
                self.result is None
                or self.result.outcome != "classified"
                or self.validation_kind != "none"
                or self.validation_messages
            ):
                raise ValueError("classified execution requires its result projection")
            if self.result.profile_id != self.profile_id:
                raise ValueError("classified execution result belongs to another profile")
        elif self.result is not None or self.validation_kind == "none" or not self.validation_messages:
            raise ValueError("ledger classify validation refusal requires only bounded messages")
        return self


@dataclass(frozen=True, slots=True)
class _LoadedCatalogueView:
    """Expose the already-loaded COMMIT snapshot to the canonical M210 resolver."""

    bucket_id: str
    catalogue: TransactionCatalogue

    def load(self) -> TransactionCatalogue:
        """Return the exact catalogue snapshot already held by the executor."""
        return self.catalogue


class LedgerClassifyExecutor:
    """Apply one manual classify through the canonical ledger action."""

    def __init__(self, ports_factory: LedgerActionPortsFactory) -> None:
        """Retain the exact-profile ledger service composition."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[LedgerClassifyRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Resolve current state, validate, and commit inside one COMMIT section."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        subject = profile_operation_subject(bucket_id)
        if (
            request.definition_id != LEDGER_CLASSIFY_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(LEDGER_CLASSIFY_PHASE)

        def prepare() -> tuple[LedgerActionPorts, TransactionCatalogue, str, ManualLedgerTransactionPatch]:
            operation: PinnedAuthorityOperation = context.authority_operation
            ports = self._ports_factory(bucket_id=bucket_id, operation=operation)
            _require_exact_ports(ports, bucket_id=bucket_id, operation=operation)
            catalogue = ports.transaction_repository.load()
            transaction_id = resolve_transaction_id(payload.transaction_id, catalogue.transactions)
            current = catalogue.transactions[transaction_id]
            patch = _patch_from_request(
                payload,
                bucket_id=bucket_id,
                transaction_id=transaction_id,
                current=current,
                operation=operation,
                catalogue=catalogue,
            )
            # Validate the full pre-write projection now. Every request value that
            # can change the projection is bounded by the request schema and its
            # canonical domain validator, so the same projection cannot first fail
            # after the durable update.
            _operation_result(
                payload.profile_id,
                ManualLedgerTransactionResult(
                    ref=BucketTransactionRef(bucket_id=bucket_id, transaction_id=transaction_id),
                    transaction=current,
                    bucket_event_ids=(),
                ),
            )
            return ports, catalogue, transaction_id, patch

        async def refuse(error: Exception) -> OperationRefusalEvidence:
            detail = LedgerClassifyExecutionResult(
                outcome="validation_error",
                profile_id=payload.profile_id,
                validation_kind=_validation_kind(error),
                validation_messages=_validation_messages(error),
            )
            detail_ref = await context.operands.put(detail, written_at=now())
            return OperationRefusalEvidence(
                refusal_code=LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE,
                detail_ref=detail_ref,
            )

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                try:
                    ports, catalogue, transaction_id, patch = await asyncio.to_thread(prepare)
                except _CLASSIFY_VALIDATION_ERRORS as exc:
                    return await refuse(exc)
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    result = await asyncio.to_thread(
                        update_manual_transaction_fields,
                        bucket_id=bucket_id,
                        transaction_id=transaction_id,
                        patch=patch,
                        actor=payload.actor or bucket_id or "operator",
                        source_command="aeat app ledger classify",
                        reaffirm=payload.reaffirm,
                        ports=ports,
                        catalogue=catalogue,
                        expected_current=catalogue.transactions[transaction_id],
                    )
                except _CLASSIFY_VALIDATION_ERRORS as exc:
                    # The action validates its replacement before its atomic
                    # catalogue/event commit, so this caught input refusal has
                    # a known no-write effect.
                    await context.events.effect(OperationEffect.NONE)
                    return await refuse(exc)
                projection = _operation_result(payload.profile_id, result)
                await context.events.effect(
                    OperationEffect.UPDATED if result.bucket_event_ids else OperationEffect.NONE
                )
                execution_result = LedgerClassifyExecutionResult(
                    outcome="classified",
                    profile_id=payload.profile_id,
                    result=projection,
                )
                return await context.operands.put(execution_result, written_at=now())

        return await await_cancellation_complete(commit(), task_name="ledger-classify-commit")


def _patch_from_request(
    payload: LedgerClassifyRequest,
    *,
    bucket_id: str,
    transaction_id: str,
    current: Transaction,
    operation: PinnedAuthorityOperation,
    catalogue: TransactionCatalogue,
) -> ManualLedgerTransactionPatch:
    """Rebuild the typed canonical patch under the selected registry authority."""
    if not isinstance(current, Transaction):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    patch_values: dict[str, object] = {}
    for field_name in payload.patch_fields:
        if field_name == "m210_income_classification":
            continue
        value = getattr(payload.patch, field_name)
        if field_name == "business_classification" and value is not None:
            value = BusinessClassification(value)
        elif field_name in {"business_pct", "taxable_base", "iva_rate", "iva_amount"} and value is not None:
            parsed = try_parse_canonical_decimal(value, signed=False)
            if parsed is None:
                raise TransactionValidationError(f"ledger classify {field_name} must be canonical decimal text")
            value = parsed
        elif field_name == "category_id" and value is not None:
            normalized = value.strip()
            value = require_spending_category(normalized, authority=operation).value if normalized else None
        elif field_name == "iva_category" and value is not None:
            value = require_iva_category(
                value,
                effective_date=current.raw.booked_date,
                authority=operation,
            )
        elif field_name == "deduction_fact_kind" and value is not None:
            value = require_iva_deduction_fact_kind(value, authority=operation)
        elif field_name == "counterparty_identification_state" and value is not None:
            value = require_eu_member_state(value, authority=operation)
        patch_values[field_name] = value

    if payload.m210 is not None:
        m210 = payload.m210
        gross_income_amount = _decimal_option(m210.gross_income_amount, "gross_income_amount")
        applicable_rate = _decimal_option(m210.applicable_rate, "applicable_rate")
        snapshot = cast(
            TransactionCatalogueRepositoryProtocol,
            _LoadedCatalogueView(bucket_id=bucket_id, catalogue=catalogue),
        )
        with validating_governed_facts(operation):
            classification = resolve_m210_income_classification(
                bucket_id=bucket_id,
                transaction_id=transaction_id,
                tipo_renta_code=m210.tipo_renta_code,
                gross_income_amount=gross_income_amount,
                applicable_rate=applicable_rate,
                payer_mode=m210.payer_mode,
                payer_id=m210.payer_id,
                asset_or_right_id=m210.asset_or_right_id,
                transaction_repository=snapshot,
            )
        if classification is not None:
            patch_values["m210_income_classification"] = classification

    patch = ManualLedgerTransactionPatch.model_validate(patch_values)
    expected_fields = set(payload.patch_fields)
    if set(patch.model_fields_set) != expected_fields:
        raise TransactionValidationError(
            "ledger classify request omission mask does not match its canonical patch",
            context={"transaction_id": transaction_id},
        )
    return patch


def _decimal_option(value: str | None, field_name: str) -> Decimal | None:
    """Decode one optional canonical decimal wire value."""
    if value is None:
        return None
    parsed = try_parse_canonical_decimal(value, signed=False)
    if parsed is None:
        raise TransactionValidationError(f"M210 {field_name} must be canonical decimal text")
    return parsed


def _require_exact_ports(
    ports: LedgerActionPorts,
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
) -> None:
    """Refuse ports whose profile or authority escaped the request."""
    if ports.operation is not operation or ports.transaction_repository.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    for repository in (ports.invoice_repository, ports.work_unit_repository, ports.calculation_repository):
        if getattr(repository, "bucket_id", None) != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _operation_result(profile_id: UUID, result: ManualLedgerTransactionResult) -> LedgerClassifyOperationResult:
    """Validate exact identity, project canonical output, and enforce its byte bound."""
    canonical: LedgerTransactionResultPayload = ledger_transaction_result_payload(result)
    if (
        canonical.bucket_id != str(profile_id)
        or result.ref.bucket_id != canonical.bucket_id
        or result.ref.transaction_id != canonical.transaction_id
        or result.ref.transaction_id != result.transaction.transaction_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    projected = LedgerClassifyOperationResult(
        outcome="classified",
        profile_id=profile_id,
        transaction=LedgerTransactionProjection.from_payload(canonical.transaction),
        deduction_fact_kind=(
            result.transaction.deduction_fact_kind.value if result.transaction.deduction_fact_kind else None
        ),
        investment_asset_id=result.transaction.investment_asset_id,
        review_status=canonical.review_status,
        bucket_event_ids=result.bucket_event_ids,
    )
    if len(projected.model_dump_json().encode("utf-8")) > _MAX_RESULT_JSON_BYTES:
        raise TransactionValidationError(
            "ledger classify result exceeds its registered projection bound",
            context={"max_result_bytes": str(_MAX_RESULT_JSON_BYTES)},
        )
    return projected


LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE = "REFUSED_CLI_VALIDATION_BOUNDARY"
_CLASSIFY_VALIDATION_ERRORS = (ValidationError, TransactionValidationError, RegistryValidationError)


def _validation_kind(error: Exception) -> _ValidationKind:
    """Retain the two user-actionable M210 refusal categories without raw context."""
    if not isinstance(error, TransactionValidationError):
        return "input"
    context = error.context or {}
    if "required_direction" in context:
        return "m210_incoming_only"
    if "missing" in context:
        return "m210_required_options"
    return "input"


def _validation_messages(error: Exception) -> _ValidationMessages:
    """Retain only bounded field locations and user-actionable messages."""
    messages: list[str] = []
    if isinstance(error, ValidationError):
        for item in error.errors(include_input=False, include_context=False, include_url=False)[
            :_MAX_VALIDATION_MESSAGES
        ]:
            location = item.get("loc", ())
            field_path = ".".join(str(part) for part in location if part != "__root__")
            message = str(item.get("msg", "")).removeprefix("Value error, ").strip()
            detail = f"{field_path}: {message}" if field_path else message
            if detail:
                messages.append(detail[:2048])
    else:
        detail = str(error).strip()
        if detail:
            messages.append(detail[:2048])
    if not messages:
        messages.append("ledger classify values did not satisfy transaction validation")
    return tuple(messages[:_MAX_VALIDATION_MESSAGES])


def _project_operation_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release a matching success projection or bounded validation detail."""
    if (
        type(result) is not LedgerClassifyExecutionResult
        or receipt.identity.definition_id != LEDGER_CLASSIFY_OPERATION_DEFINITION_ID
    ):
        raise ValueError("invalid ledger classify result or terminal receipt")
    if receipt.identity.subject_ref != profile_operation_subject(str(result.profile_id)):
        raise ValueError("ledger classify result belongs to another subject")
    if result.outcome == "classified":
        projected = result.result
        if (
            receipt.condition is not OperationTerminalCondition.SUCCEEDED
            or receipt.result_ref is None
            or receipt.refusal_ref is not None
            or receipt.refusal_detail_ref is not None
            or receipt.failure_error_code is not None
            or receipt.diagnostic_ref is not None
            or projected is None
            or receipt.effect is not (OperationEffect.UPDATED if projected.bucket_event_ids else OperationEffect.NONE)
        ):
            raise ValueError("ledger classify success has an incompatible terminal receipt")
        return projected
    if (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.refusal_ref != LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
        or receipt.result_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or receipt.effect is not OperationEffect.NONE
    ):
        raise ValueError("ledger classify validation refusal has an incompatible terminal receipt")
    return LedgerClassifyOperationResult(
        outcome="validation_error",
        profile_id=result.profile_id,
        validation_kind=result.validation_kind,
        validation_messages=result.validation_messages,
    )


def build_ledger_classify_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare a durable exact-profile classification with bounded secure result."""
    return OperationDefinition(
        definition_id=LEDGER_CLASSIFY_OPERATION_DEFINITION_ID,
        request_type=LedgerClassifyRequest,
        result_type=LedgerClassifyExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerClassifyRequest,
            executor_type=LedgerClassifyExecutor,
            build=lambda: LedgerClassifyExecutor(ports_factory),
        ),
        phase_codes=(LEDGER_CLASSIFY_PHASE,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        refusal_detail_codes=frozenset({LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE}),
    )


def resolve_ledger_classify_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile disclosure and COMMIT for single classify."""
    if request.definition_id != LEDGER_CLASSIFY_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, LedgerClassifyRequest
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


def build_ledger_classify_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Enroll the exact classify request, bounded result, and access resolver."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=LedgerClassifyRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=LedgerClassifyOperationResult,
        ),
        result_projector=_project_operation_result,
        access_resolver=resolve_ledger_classify_access,
    )


class LedgerOperatorIvaRequest(BaseModel):
    """Exact-profile operator-selected IVA category, without frontend tax resolution."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: _TransactionPrefix
    iva_category: Annotated[str, Field(min_length=1, max_length=128)]
    actor: Annotated[str, Field(min_length=1, max_length=64)] | None = None

    @field_validator("transaction_id")
    @classmethod
    def _canonical_transaction_prefix(cls, value: str) -> str:
        return normalise_transaction_id_prefix(value)


class LedgerOperatorIvaResult(BaseModel):
    """Existing grounded IVA outcome, including a truthful non-derivable result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    outcome: Literal["derived", "validation_error"] = "derived"
    transaction_id: Annotated[str, Field(min_length=1, max_length=96)]
    iva_category: Annotated[str, Field(min_length=1, max_length=128)]
    derivable: bool
    iva_rate: _DecimalText | None = None
    taxable_base: _DecimalText | None = None
    iva_amount: _DecimalText | None = None
    note: _LongText = ""
    classification: LedgerClassifyOperationResult | None = None
    validation_messages: _ValidationMessages = ()

    @model_validator(mode="after")
    def _complete_derivation(self) -> LedgerOperatorIvaResult:
        values = (self.iva_rate, self.taxable_base, self.iva_amount, self.classification)
        if self.outcome == "validation_error":
            if (
                self.derivable
                or any(value is not None for value in values)
                or not self.validation_messages
                or self.note
            ):
                raise ValueError("operator IVA validation refusal requires only its bounded validation details")
            return self
        if self.validation_messages:
            raise ValueError("derived IVA result cannot carry validation refusal details")
        if self.derivable:
            if any(value is None for value in values):
                raise ValueError("derivable IVA result requires its complete substrate")
            if (
                self.classification is None
                or self.classification.profile_id != self.profile_id
                or self.classification.transaction is None
                or self.classification.transaction.transaction_id != self.transaction_id
            ):
                raise ValueError("derived IVA result belongs to another profile or row")
        elif any(value is not None for value in values):
            raise ValueError("non-derivable IVA result cannot carry a write result")
        return self


class LedgerOperatorIvaExecutionResult(BaseModel):
    """Encrypted exact-request wrapper for the operator IVA result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    request: LedgerOperatorIvaRequest
    result: LedgerOperatorIvaResult


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
        if (
            request.definition_id != LEDGER_OPERATOR_IVA_DEFINITION_ID
            or context.identity.definition_id != request.definition_id
            or request.subject_ref != profile_operation_subject(bucket_id)
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        ports = self._ports_factory(bucket_id=bucket_id, operation=context.authority_operation)
        _require_exact_ports(ports, bucket_id=bucket_id, operation=context.authority_operation)
        await context.events.phase(LEDGER_OPERATOR_IVA_DEFINITION_ID)

        async def refuse(error: Exception, transaction_id: str) -> OperationRefusalEvidence:
            result = LedgerOperatorIvaResult(
                profile_id=payload.profile_id,
                outcome="validation_error",
                transaction_id=transaction_id,
                iva_category=payload.iva_category,
                derivable=False,
                validation_messages=_validation_messages(error),
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
                except _CLASSIFY_VALIDATION_ERRORS as error:
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
                    classification=_operation_result(payload.profile_id, derivation.result)
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
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def _project_operator_iva_result(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
    if not isinstance(result, LedgerOperatorIvaExecutionResult):
        raise ValueError("invalid operator IVA execution result")
    payload, projection = result.request, result.result
    expected_effect = (
        OperationEffect.UPDATED
        if projection.classification is not None and projection.classification.bucket_event_ids
        else OperationEffect.NONE
    )
    if (
        receipt.identity.definition_id != LEDGER_OPERATOR_IVA_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(payload.profile_id))
        or projection.profile_id != payload.profile_id
        or not projection.transaction_id.startswith(payload.transaction_id)
        or projection.iva_category != payload.iva_category
        or receipt.effect is not expected_effect
    ):
        raise ValueError("operator IVA result does not match its request and terminal receipt")
    if projection.outcome == "validation_error":
        if (
            receipt.condition is not OperationTerminalCondition.REFUSED
            or receipt.refusal_ref != LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE
            or receipt.refusal_detail_ref is None
            or receipt.result_ref is not None
            or receipt.failure_error_code is not None
            or receipt.diagnostic_ref is not None
        ):
            raise ValueError("operator IVA validation detail has an incompatible terminal receipt")
    elif (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("operator IVA success has an incompatible terminal receipt")
    return projection


def build_ledger_operator_iva_definition(ports_factory: LedgerActionPortsFactory) -> OperationDefinition:
    """Register the existing derivation with immutable profile custody and COMMIT."""
    return OperationDefinition(
        definition_id=LEDGER_OPERATOR_IVA_DEFINITION_ID,
        request_type=LedgerOperatorIvaRequest,
        result_type=LedgerOperatorIvaExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerOperatorIvaRequest,
            executor_type=LedgerOperatorIvaExecutor,
            build=lambda: LedgerOperatorIvaExecutor(ports_factory),
        ),
        phase_codes=(LEDGER_OPERATOR_IVA_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
        refusal_detail_codes=frozenset({LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE}),
    )


def build_ledger_operator_iva_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the bounded operator IVA request/result and exact access policy."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=LedgerOperatorIvaRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=LedgerOperatorIvaResult
        ),
        result_projector=_project_operator_iva_result,
        access_resolver=resolve_ledger_operator_iva_access,
    )


__all__ = [
    "LEDGER_CLASSIFY_OPERATION_DEFINITION_ID",
    "LEDGER_CLASSIFY_PHASE",
    "LEDGER_CLASSIFY_VALIDATION_REFUSAL_CODE",
    "LEDGER_OPERATOR_IVA_DEFINITION_ID",
    "LedgerClassifyExecutionResult",
    "LedgerClassifyExecutor",
    "LedgerClassifyM210Options",
    "LedgerClassifyOperationResult",
    "LedgerClassifyPatch",
    "LedgerClassifyPatchField",
    "LedgerClassifyRequest",
    "LedgerOperatorIvaExecutionResult",
    "LedgerOperatorIvaExecutor",
    "LedgerOperatorIvaRequest",
    "LedgerOperatorIvaResult",
    "build_ledger_classify_definition",
    "build_ledger_classify_registration",
    "build_ledger_operator_iva_definition",
    "build_ledger_operator_iva_registration",
    "resolve_ledger_classify_access",
    "resolve_ledger_operator_iva_access",
]
