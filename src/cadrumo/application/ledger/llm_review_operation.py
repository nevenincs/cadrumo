"""Registered review and guarded commit of existing ledger classification services."""

from __future__ import annotations

import asyncio
import json
import secrets
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import Settings
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.hashing import content_hash_hex, reject_duplicate_json_members, reject_json_constant, sha256_hex
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...core.type_guards import is_str_keyed_dict
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.transactions.errors import TransactionNotFoundError, TransactionValidationError
from ...domain.transactions.models import Transaction
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.interactions import OperationInteractionRequest, OperationResponseIntentValue
from ..operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext, OperationResumeCheckpoint
from ..operations.persistence.journal import serialize_operation_operand
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
    operation_public_schema_reference,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts
from .actions_common import display_decimal
from .actions_manual import ledger_transaction_result_payload
from .classify_operation import LedgerClassifyOperationResult
from .id_resolution import normalise_transaction_id_prefix, resolve_transaction_id
from .llm_classification import (
    saturate_llm_classification,
    suggest_evidence_split,
    suggest_llm_classification,
)
from .llm_classification_ports import (
    LLMClassificationPorts,
    LLMClassificationSuggestion,
    LLMSaturatedSuggestion,
    LLMSplitApplyResult,
    LLMSplitSuggestion,
    LLMSuggestionRejectionResult,
)
from .llm_review_workflow import LlmReviewDecision, LlmReviewInvocationOrigin, execute_reviewed_decision
from .models import ManualLedgerTransactionResult
from .persistence_ports import LedgerPersistenceConflictError
from .read_access import resolve_ledger_read_access
from .transaction_projection import LedgerTransactionProjection

LEDGER_CLASSIFY_REVIEW_DEFINITION_ID = "ledger.classify.review"
LEDGER_SPLIT_REVIEW_DEFINITION_ID = "ledger.split.review"
_DEFINITION_IDS = frozenset({LEDGER_CLASSIFY_REVIEW_DEFINITION_ID, LEDGER_SPLIT_REVIEW_DEFINITION_ID})
_ShortText = Annotated[str, Field(max_length=256)]
_LongText = Annotated[str, Field(max_length=8192)]
_DecimalText = Annotated[str, Field(min_length=1, max_length=128)]
_Suggestion = LLMSaturatedSuggestion | LLMClassificationSuggestion | LLMSplitSuggestion
_MAX_PROJECTION_BYTES = 262_144
_DomainJson = Annotated[str, Field(min_length=1, max_length=4_194_304, repr=False)]


class LedgerLlmReviewRequest(BaseModel):
    """Immutable profile and explicit options for one existing suggestion service."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: Annotated[str, Field(min_length=1, max_length=96)]
    mode: Literal["classification", "saturated", "auto_split", "split"]
    origin: LlmReviewInvocationOrigin
    business_pct: _DecimalText | None = None
    actor: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    read_evidence: bool = False
    vision_model: _ShortText | None = None
    reason: _LongText = ""
    preview: bool = False

    @field_validator("transaction_id")
    @classmethod
    def _canonical_transaction_prefix(cls, value: str) -> str:
        return normalise_transaction_id_prefix(value)

    @field_validator("business_pct")
    @classmethod
    def _canonical_percentage(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = try_parse_canonical_decimal(value, signed=False)
            if parsed is None or display_decimal(parsed) != value or not Decimal("0") <= parsed <= Decimal("1"):
                raise ValueError("business percentage must use canonical decimal text within 0..1")
        return value

    @model_validator(mode="after")
    def _matching_origin(self) -> LedgerLlmReviewRequest:
        allowed = {
            "classification": {
                LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
                LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT,
            },
            "saturated": {
                LlmReviewInvocationOrigin.CLASSIFY_LLM_SATURATE_APPLY,
                LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT,
            },
            "auto_split": {
                LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT,
                LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT,
            },
            "split": {LlmReviewInvocationOrigin.SPLIT_LLM},
        }
        if self.origin not in allowed[self.mode]:
            raise ValueError("review mode and invocation origin disagree")
        return self


class LedgerLlmChildProjection(BaseModel):
    """Bounded display facts copied from an existing grounded split proposal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    proportion: _DecimalText
    amount: _DecimalText
    description: _LongText
    category: _ShortText | None
    iva_category: _ShortText | None
    iva_rate: _DecimalText | None
    taxable_base: _DecimalText | None
    iva_amount: _DecimalText | None
    rate_derivable: bool
    derivation_note: _LongText
    evidence_citation: _LongText


class LedgerLlmSuggestionProjection(BaseModel):
    """JSON-stable review values without reconstructing domain authority in a frontend."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["classification", "saturated", "split"]
    transaction_id: Annotated[str, Field(min_length=1, max_length=96)]
    provenance: Annotated[str, Field(min_length=1, max_length=256)]
    reason: _LongText
    evidence_id: _ShortText | None
    classification: _ShortText | None = None
    category: _ShortText | None = None
    confidence: _DecimalText | None = None
    multiple_components: bool | None = None
    business_pct: _DecimalText | None = None
    iva_category: _ShortText | None = None
    iva_rate: _DecimalText | None = None
    taxable_base: _DecimalText | None = None
    iva_amount: _DecimalText | None = None
    rate_derivable: bool = False
    derivation_note: _LongText = ""
    evidence_advisory: _LongText = ""
    parent_amount: _DecimalText | None = None
    children: Annotated[tuple[LedgerLlmChildProjection, ...], Field(max_length=128)] = ()


class LedgerLlmReviewProjection(BaseModel):
    """Exact digest-bound private REVIEW projection released under disclosure policy."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection_version: Literal[1] = 1
    profile_id: UUID
    reviewed_proposal_digest: ContentDigest
    suggestion: LedgerLlmSuggestionProjection


class LedgerLlmReviewResponse(BaseModel):
    """Authority-free intent; the supervisor owns the bound response capability."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    response_version: Literal[1]
    intent: OperationResponseIntentValue


def _definition_id(request: LedgerLlmReviewRequest) -> str:
    """Bind the split-only request to its sole registered definition."""
    return LEDGER_SPLIT_REVIEW_DEFINITION_ID if request.mode == "split" else LEDGER_CLASSIFY_REVIEW_DEFINITION_ID


def _require_invocation(identity: OperationIdentity, request: LedgerLlmReviewRequest) -> None:
    """Refuse any invocation whose definition or profile differs from its operand."""
    if identity.definition_id != _definition_id(request) or identity.subject_ref != profile_operation_subject(
        str(request.profile_id)
    ):
        raise ValueError("ledger review invocation and request disagree")


class LedgerLlmReviewedOperand(BaseModel):
    """Encrypted immutable input, proposal, and generation for detached continuation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    identity: OperationIdentity
    request: LedgerLlmReviewRequest
    baseline_json: _DomainJson
    authority_generation: ContentDigest
    suggestion_json: _DomainJson
    suggestion: LedgerLlmSuggestionProjection

    @model_validator(mode="after")
    def _same_transaction(self) -> LedgerLlmReviewedOperand:
        _require_invocation(self.identity, self.request)
        baseline = json.loads(
            self.baseline_json, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        suggestion = json.loads(
            self.suggestion_json, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        if not is_str_keyed_dict(baseline) or not is_str_keyed_dict(suggestion):
            raise ValueError("reviewed domain JSON must contain model objects")
        if (
            baseline.get("transaction_id") != self.suggestion.transaction_id
            or suggestion.get("transaction_id") != self.suggestion.transaction_id
            or suggestion.get("provenance") != self.suggestion.provenance
        ):
            raise ValueError("reviewed proposal belongs to another ledger row")
        resolve_transaction_id(self.request.transaction_id, (self.suggestion.transaction_id,))
        expected_kind = "split" if self.request.mode in {"split", "auto_split"} else self.request.mode
        if self.suggestion.kind != expected_kind:
            raise ValueError("review mode and stored proposal kind disagree")
        _bounded(self.suggestion)
        return self

    @classmethod
    def capture(
        cls,
        *,
        identity: OperationIdentity,
        request: LedgerLlmReviewRequest,
        baseline: Transaction,
        authority_generation: ContentDigest,
        suggestion: _Suggestion,
    ) -> Self:
        """Store exact domain JSON and its bounded authority-free review facts."""
        return cls(
            identity=identity,
            request=request,
            baseline_json=baseline.model_dump_json(),
            authority_generation=authority_generation,
            suggestion_json=suggestion.model_dump_json(),
            suggestion=_suggestion_projection(suggestion),
        )

    def decode(self, operation: PinnedAuthorityOperation) -> tuple[Transaction, _Suggestion]:
        """Reconstruct and cross-check domain values only under their pinned generation."""
        if self.authority_generation != operation.generation.logical_generation:
            raise LedgerPersistenceConflictError("ledger review authority generation changed")
        with validating_governed_facts(operation):
            baseline = Transaction.model_validate_json(self.baseline_json)
            if self.suggestion.kind == "split":
                suggestion: _Suggestion = LLMSplitSuggestion.model_validate_json(self.suggestion_json)
            elif self.suggestion.kind == "saturated":
                suggestion = LLMSaturatedSuggestion.model_validate_json(self.suggestion_json)
            else:
                suggestion = LLMClassificationSuggestion.model_validate_json(self.suggestion_json)
            if (
                baseline.transaction_id != suggestion.transaction_id
                or baseline.model_dump_json() != self.baseline_json
                or suggestion.model_dump_json() != self.suggestion_json
                or _suggestion_projection(suggestion) != self.suggestion
            ):
                raise LedgerPersistenceConflictError("ledger reviewed domain values and projection disagree")
        if self.request.mode in {"split", "auto_split"}:
            if not isinstance(suggestion, LLMSplitSuggestion):
                raise ValueError("split review requires its split proposal")
        elif self.request.mode == "saturated":
            if not isinstance(suggestion, LLMSaturatedSuggestion):
                raise ValueError("saturated review requires its grounded proposal")
        elif type(suggestion) is not LLMClassificationSuggestion:
            raise ValueError("classification review requires its classification proposal")
        return baseline, suggestion


class LedgerLlmOperationResult(BaseModel):
    """Settled preview or writer outcome and the exact captured proposal identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    reviewed_proposal_digest: ContentDigest
    outcome: Literal["preview", "classified", "split", "rejected"]
    transaction_id: Annotated[str, Field(min_length=1, max_length=96)]
    preview: LedgerLlmReviewProjection | None = None
    classification: LedgerClassifyOperationResult | None = None
    split_group_id: _ShortText | None = None
    child_transaction_ids: Annotated[tuple[_ShortText, ...], Field(max_length=128)] = ()
    classified_child_count: Annotated[int, Field(ge=0, le=128)] = 0
    bucket_event_id: _ShortText | None = None
    suggestion_kind: _ShortText | None = None
    provenance: _ShortText
    operator_reason: _LongText = ""

    @model_validator(mode="after")
    def _complete_outcome(self) -> LedgerLlmOperationResult:
        if self.outcome == "preview":
            if (
                self.preview is None
                or self.preview.profile_id != self.profile_id
                or self.preview.reviewed_proposal_digest != self.reviewed_proposal_digest
                or self.preview.suggestion.transaction_id != self.transaction_id
                or self.preview.suggestion.provenance != self.provenance
            ):
                raise ValueError("preview requires its exact captured proposal")
            if (
                self.classification is not None
                or self.split_group_id is not None
                or self.child_transaction_ids
                or self.classified_child_count
                or self.bucket_event_id is not None
                or self.suggestion_kind is not None
                or self.operator_reason
            ):
                raise ValueError("preview cannot carry mutation or rejection facts")
            return self
        if self.preview is not None:
            raise ValueError("writer outcome cannot carry a preview")
        if self.outcome == "classified":
            if (
                self.classification is None
                or self.classification.outcome != "classified"
                or self.classification.profile_id != self.profile_id
            ):
                raise ValueError("classified review requires its exact-profile result")
            if (
                self.classification.transaction is None
                or self.classification.transaction.transaction_id != self.transaction_id
            ):
                raise ValueError("classified review result belongs to another row")
            if (
                self.split_group_id is not None
                or self.child_transaction_ids
                or self.classified_child_count
                or self.bucket_event_id is not None
                or self.suggestion_kind is not None
                or self.operator_reason
            ):
                raise ValueError("classified review cannot carry split or rejection facts")
        elif self.outcome == "split":
            if (
                not self.split_group_id
                or len(self.child_transaction_ids) < 2
                or len(set(self.child_transaction_ids)) != len(self.child_transaction_ids)
                or self.transaction_id in self.child_transaction_ids
                or self.classified_child_count != len(self.child_transaction_ids)
            ):
                raise ValueError("split review requires its persisted children")
            if (
                self.classification is not None
                or self.bucket_event_id is not None
                or self.suggestion_kind is not None
                or self.operator_reason
            ):
                raise ValueError("split review cannot carry classification or rejection facts")
        else:
            if not self.bucket_event_id or self.suggestion_kind not in {"classification", "split"}:
                raise ValueError("rejected review requires its audit outcome")
            if (
                self.classification is not None
                or self.split_group_id is not None
                or self.child_transaction_ids
                or self.classified_child_count
            ):
                raise ValueError("rejected review cannot carry mutation facts")
        return self


class LedgerLlmExecutionResult(BaseModel):
    """Secure invocation binding for the distinct public terminal projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    identity: OperationIdentity
    request: LedgerLlmReviewRequest
    response: OperationResponseIntentValue | Literal["preview"]
    result: LedgerLlmOperationResult

    @model_validator(mode="after")
    def _matching_invocation(self) -> Self:
        _require_invocation(self.identity, self.request)
        if self.result.profile_id != self.request.profile_id:
            raise ValueError("ledger result belongs to another profile")
        resolve_transaction_id(self.request.transaction_id, (self.result.transaction_id,))
        if (self.response == "preview") != self.request.preview or (
            self.result.outcome == "preview"
        ) != self.request.preview:
            raise ValueError("ledger preview request and terminal outcome disagree")
        if self.request.preview:
            expected_kind = "split" if self.request.mode in {"split", "auto_split"} else self.request.mode
            if self.result.preview is None or self.result.preview.suggestion.kind != expected_kind:
                raise ValueError("preview result has another proposal kind")
        if (self.response == "reject") != (self.result.outcome == "rejected"):
            raise ValueError("ledger result disagrees with the reviewed decision")
        if self.response == "apply" and self.request.origin is LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT:
            raise ValueError("rejection invocation cannot publish a mutation")
        if self.request.mode == "split" and self.result.outcome == "classified":
            raise ValueError("split invocation cannot publish an in-place classification")
        if self.request.mode not in {"split", "auto_split"} and self.result.outcome == "split":
            raise ValueError("classification invocation cannot publish a split")
        expected_kind = "split" if self.request.mode in {"split", "auto_split"} else "classification"
        if self.result.outcome == "rejected" and self.result.suggestion_kind != expected_kind:
            raise ValueError("rejection result has another proposal kind")
        return self


@dataclass(frozen=True, slots=True)
class LedgerLlmOperationPorts:
    """One exact-profile composition of the existing ledger and suggestion services."""

    ledger: LedgerActionPorts
    llm: LLMClassificationPorts
    settings: Settings


class LedgerLlmOperationPortsFactory(Protocol):
    """Compose providers only inside the immutable profile worker."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerLlmOperationPorts:
        """Return exact-profile ledger services and lazy suggestion ports."""
        ...


def _bounded[ModelT: BaseModel](projection: ModelT) -> ModelT:
    """Refuse a public projection exceeding the declared serialized byte bound."""
    if len(projection.model_dump_json().encode("utf-8")) > _MAX_PROJECTION_BYTES:
        raise TransactionValidationError("ledger review projection exceeds its declared bound")
    return projection


def _wire_decimal(value: Decimal) -> str:
    """Preserve the original finite domain Decimal without display trimming."""
    if not value.is_finite():
        raise TransactionValidationError("ledger review requires finite decimal facts")
    return format(value, "f")


def _suggestion_projection(suggestion: _Suggestion) -> LedgerLlmSuggestionProjection:
    """Copy grounded values while preserving each Decimal's original scale."""
    if isinstance(suggestion, LLMSplitSuggestion):
        return _bounded(
            LedgerLlmSuggestionProjection(
                kind="split",
                transaction_id=suggestion.transaction_id,
                provenance=suggestion.provenance,
                reason=suggestion.reason,
                evidence_id=suggestion.evidence_id,
                parent_amount=_wire_decimal(suggestion.parent_amount),
                children=tuple(
                    LedgerLlmChildProjection(
                        proportion=_wire_decimal(child.proportion),
                        amount=_wire_decimal(child.amount),
                        description=child.description,
                        category=child.category.value if child.category else None,
                        iva_category=child.iva_category.value if child.iva_category else None,
                        iva_rate=_wire_decimal(child.iva_rate) if child.iva_rate is not None else None,
                        taxable_base=_wire_decimal(child.taxable_base) if child.taxable_base is not None else None,
                        iva_amount=_wire_decimal(child.iva_amount) if child.iva_amount is not None else None,
                        rate_derivable=child.rate_derivable,
                        derivation_note=child.derivation_note,
                        evidence_citation=child.evidence_citation,
                    )
                    for child in suggestion.children
                ),
            )
        )
    basic = LedgerLlmSuggestionProjection(
        kind="classification",
        transaction_id=suggestion.transaction_id,
        provenance=suggestion.provenance,
        reason=suggestion.reason,
        evidence_id=suggestion.evidence_id,
        classification=suggestion.classification.value,
        category=suggestion.category.value if suggestion.category else None,
        confidence=_wire_decimal(suggestion.confidence),
        multiple_components=suggestion.multiple_components,
    )
    if isinstance(suggestion, LLMSaturatedSuggestion):
        basic = LedgerLlmSuggestionProjection.model_validate(
            {
                **basic.model_dump(),
                "kind": "saturated",
                "business_pct": _wire_decimal(suggestion.business_pct) if suggestion.business_pct is not None else None,
                "iva_category": suggestion.iva_category.value if suggestion.iva_category else None,
                "iva_rate": _wire_decimal(suggestion.iva_rate) if suggestion.iva_rate is not None else None,
                "taxable_base": _wire_decimal(suggestion.taxable_base) if suggestion.taxable_base is not None else None,
                "iva_amount": _wire_decimal(suggestion.iva_amount) if suggestion.iva_amount is not None else None,
                "rate_derivable": suggestion.rate_derivable,
                "derivation_note": suggestion.derivation_note,
                "evidence_advisory": suggestion.evidence_advisory,
            }
        )
    return _bounded(basic)


def _schemas(definition_id: str) -> tuple[OperationSchemaBindingV1, OperationSchemaBindingV1]:
    """Bind the closed review and authority-free response model pair."""
    return (
        OperationSchemaBindingV1.bind(
            schema_id=definition_id + ".projection", schema_version=1, model_type=LedgerLlmReviewProjection
        ),
        OperationSchemaBindingV1.bind(
            schema_id=definition_id + ".response", schema_version=1, model_type=LedgerLlmReviewResponse
        ),
    )


def _review_projector(operand: BaseModel, interaction: OperationInteractionRequest) -> BaseModel:
    """Release only this invocation's digest-bound authority-free review facts."""
    if not isinstance(operand, LedgerLlmReviewedOperand) or operand.request.preview:
        raise ValueError("invalid ledger reviewed operand")
    _, response = _schemas(_definition_id(operand.request))
    if (
        interaction.identity != operand.identity
        or interaction.kind is not OperationInteractionKind.REVIEW
        or interaction.presentation_code != "ledger.llm.review-ready"
        or interaction.response_schema_ref != operation_public_schema_reference(response.identity)
    ):
        raise ValueError("ledger review belongs to another invocation or response contract")
    return _proposal_projection(operand)


def _proposal_projection(operand: LedgerLlmReviewedOperand) -> LedgerLlmReviewProjection:
    """Copy one captured proposal without granting response authority."""
    return _bounded(
        LedgerLlmReviewProjection(
            profile_id=operand.request.profile_id,
            reviewed_proposal_digest=sha256_hex(serialize_operation_operand(operand)),
            suggestion=operand.suggestion,
        )
    )


class LedgerLlmReviewExecutor:
    """Acquire once and resume existing writers from the persisted reviewed operand."""

    def __init__(self, factory: LedgerLlmOperationPortsFactory) -> None:
        """Retain the trusted profile-worker composition."""
        self._factory = factory

    def _ports(
        self, request: OperationRequest[LedgerLlmReviewRequest], context: OperationExecutorContext
    ) -> LedgerLlmOperationPorts:
        """Require every dependent ledger repository to retain the exact profile."""
        payload = request.payload
        profile = str(payload.profile_id)
        expected_id = (
            LEDGER_SPLIT_REVIEW_DEFINITION_ID if payload.mode == "split" else LEDGER_CLASSIFY_REVIEW_DEFINITION_ID
        )
        if (
            request.definition_id != expected_id
            or context.identity.definition_id != expected_id
            or request.subject_ref != profile_operation_subject(profile)
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != profile
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        ports = self._factory(bucket_id=profile, operation=context.authority_operation)
        if (
            ports.ledger.operation is not context.authority_operation
            or ports.ledger.transaction_repository.bucket_id != profile
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        for repository in (
            ports.ledger.invoice_repository,
            ports.ledger.work_unit_repository,
            ports.ledger.calculation_repository,
        ):
            if getattr(repository, "bucket_id", None) != profile:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        if any(record.bucket_id != profile for record in ports.ledger.purchase_invoice_evidence_records):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return ports

    async def execute(
        self, request: OperationRequest[LedgerLlmReviewRequest], context: OperationExecutorContext
    ) -> str | None:
        """Capture once, then settle a preview or publish the secure REVIEW checkpoint."""
        ports = self._ports(request, context)
        payload = request.payload
        await context.events.phase("ledger.llm.acquire")

        def acquire() -> LedgerLlmReviewedOperand:
            with validating_governed_facts(context.authority_operation):
                catalogue = ports.ledger.transaction_repository.load()
                transaction_id = resolve_transaction_id(payload.transaction_id, catalogue.transactions)
                baseline = catalogue.transactions[transaction_id]
                suggest = (
                    suggest_evidence_split
                    if payload.mode in {"split", "auto_split"}
                    else saturate_llm_classification
                    if payload.mode == "saturated"
                    else suggest_llm_classification
                )
                suggestion = suggest(
                    bucket_id=str(payload.profile_id),
                    transaction_id=transaction_id,
                    operation=context.authority_operation,
                    transaction_repository=ports.ledger.transaction_repository,
                    read_evidence=payload.read_evidence,
                    vision_model=payload.vision_model,
                    settings=ports.settings,
                    ports=ports.llm,
                    reviewed_transaction=baseline,
                )
                _suggestion_projection(suggestion)
                return LedgerLlmReviewedOperand.capture(
                    identity=context.identity,
                    request=payload,
                    baseline=baseline,
                    suggestion=suggestion,
                    authority_generation=context.authority_operation.generation.logical_generation,
                )

        operand = await asyncio.to_thread(acquire)
        if payload.preview:
            digest = sha256_hex(serialize_operation_operand(operand))
            stored = await context.operands.put(operand, written_at=now())
            if stored != digest:
                raise ValueError("preview operand storage returned another proposal")
            projection = _proposal_projection(operand)
            result = _bounded(
                LedgerLlmOperationResult(
                    profile_id=payload.profile_id,
                    reviewed_proposal_digest=digest,
                    outcome="preview",
                    transaction_id=operand.suggestion.transaction_id,
                    preview=projection,
                    provenance=operand.suggestion.provenance,
                )
            )
            await context.events.effect(OperationEffect.NONE)
            return await context.operands.put(
                LedgerLlmExecutionResult(identity=context.identity, request=payload, response="preview", result=result),
                written_at=now(),
            )
        await context.events.phase("ledger.llm.review")
        _, response = _schemas(request.definition_id)
        digest = sha256_hex(serialize_operation_operand(operand))
        await context.interactions.publish_review(
            interaction_id=secrets.token_hex(32),
            identity=context.identity,
            revision=context.revision + 1,
            presentation_code="ledger.llm.review-ready",
            response_schema_ref=operation_public_schema_reference(response.identity),
            continuation_digest=content_hash_hex({"operation_id": context.identity.operation_id, "proposal": digest}),
            expires_at=None,
            reviewed_operand=operand,
            baseline_digest=sha256_hex(operand.baseline_json.encode("utf-8")),
            proposed_effect_digest=digest,
        )

    async def resume(
        self,
        request: OperationRequest[LedgerLlmReviewRequest],
        checkpoint: OperationResumeCheckpoint,
        context: OperationExecutorContext,
    ) -> str | None:
        """Validate the consumed continuation and invoke its original guarded writer."""
        if request.payload.preview:
            raise ValueError("terminal preview has no resumable response")
        if not checkpoint.consumed:
            return None
        digest = checkpoint.reviewed_proposal_digest
        with validating_governed_facts(context.authority_operation):
            operand = await context.operands.resolve(digest, LedgerLlmReviewedOperand)
        if (
            operand.request != request.payload
            or operand.identity != context.identity
            or operand.authority_generation != context.authority_operation.generation.logical_generation
        ):
            raise LedgerPersistenceConflictError("ledger review request or authority generation changed")
        if sha256_hex(serialize_operation_operand(operand)) != digest:
            raise LedgerPersistenceConflictError("ledger reviewed operand digest changed")
        response_action = checkpoint.response_action
        if response_action is None or response_action not in {"apply", "reject"}:
            raise TransactionValidationError("ledger review response has no declared intent")
        if response_action == "apply" and operand.request.origin is LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT:
            raise TransactionValidationError("explicit rejection invocation cannot apply a proposal")
        baseline, suggestion = operand.decode(context.authority_operation)
        ports = self._ports(request, context)
        decision = (
            LlmReviewDecision.REJECT
            if response_action == "reject"
            else LlmReviewDecision.SPLIT
            if isinstance(suggestion, LLMSplitSuggestion) and suggestion.recommends_split
            else LlmReviewDecision.APPLY
        )
        await context.events.phase("ledger.llm.commit")

        async def commit() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)

                def write() -> BaseModel:
                    with validating_governed_facts(context.authority_operation):
                        return execute_reviewed_decision(
                            suggestion,
                            origin=operand.request.origin,
                            decision=decision,
                            bucket_id=str(operand.request.profile_id),
                            business_pct=Decimal(operand.request.business_pct)
                            if operand.request.business_pct is not None
                            else None,
                            reason=operand.request.reason,
                            actor=operand.request.actor or str(operand.request.profile_id),
                            ports=ports.ledger,
                            settings=ports.settings,
                            expected_current=baseline,
                        )

                try:
                    written = await asyncio.to_thread(write)
                except (LedgerPersistenceConflictError, TransactionNotFoundError, TransactionValidationError):
                    await context.events.effect(OperationEffect.NONE)
                    raise
                effect = _writer_effect(written, operand=operand, baseline=baseline, decision=decision)
                await context.events.effect(effect)

                def project() -> LedgerLlmOperationResult:
                    with validating_governed_facts(context.authority_operation):
                        return _writer_projection(written, operand=operand, baseline=baseline, digest=digest)

                result = await asyncio.to_thread(project)
                execution = LedgerLlmExecutionResult(
                    identity=context.identity,
                    request=operand.request,
                    response=response_action,
                    result=result,
                )
                return await context.operands.put(execution, written_at=now())

        return await await_cancellation_complete(commit(), task_name="ledger-llm-reviewed-commit")


def _writer_effect(
    result: BaseModel,
    *,
    operand: LedgerLlmReviewedOperand,
    baseline: Transaction,
    decision: LlmReviewDecision,
) -> OperationEffect:
    """Validate settled writer identity before publishing its truthful effect."""
    profile = str(operand.request.profile_id)
    transaction_id = baseline.transaction_id
    if isinstance(result, ManualLedgerTransactionResult) and decision is LlmReviewDecision.APPLY:
        if (
            result.ref.bucket_id != profile
            or result.ref.transaction_id != transaction_id
            or result.transaction.transaction_id != transaction_id
        ):
            raise ValueError("classification writer returned another profile or transaction")
        return OperationEffect.UPDATED if result.bucket_event_ids else OperationEffect.NONE
    if isinstance(result, LLMSplitApplyResult) and decision is LlmReviewDecision.SPLIT:
        if (
            result.bucket_id != profile
            or result.parent_transaction_id != transaction_id
            or result.provenance != operand.suggestion.provenance
        ):
            raise ValueError("split writer returned another profile, transaction, or proposal")
        return OperationEffect.UPDATED
    if isinstance(result, LLMSuggestionRejectionResult) and decision is LlmReviewDecision.REJECT:
        expected_kind = "split" if operand.request.mode in {"split", "auto_split"} else "classification"
        if (
            result.bucket_id != profile
            or result.transaction_id != transaction_id
            or result.provenance != operand.suggestion.provenance
            or result.suggestion_kind != expected_kind
            or result.operator_reason != operand.request.reason
        ):
            raise ValueError("rejection writer returned another profile, transaction, or proposal")
        return OperationEffect.UPDATED
    raise ValueError("ledger review writer returned an incompatible decision result")


def _writer_projection(
    result: BaseModel,
    *,
    operand: LedgerLlmReviewedOperand,
    baseline: Transaction,
    digest: ContentDigest,
) -> LedgerLlmOperationResult:
    """Project after durable outcome recognition without resetting the effect on failure."""
    common = {
        "profile_id": operand.request.profile_id,
        "reviewed_proposal_digest": digest,
        "transaction_id": baseline.transaction_id,
        "provenance": operand.suggestion.provenance,
    }
    if isinstance(result, ManualLedgerTransactionResult):
        payload = ledger_transaction_result_payload(result)
        classification = LedgerClassifyOperationResult(
            outcome="classified",
            profile_id=operand.request.profile_id,
            transaction=LedgerTransactionProjection.from_payload(payload.transaction),
            deduction_fact_kind=result.transaction.deduction_fact_kind.value
            if result.transaction.deduction_fact_kind
            else None,
            investment_asset_id=result.transaction.investment_asset_id,
            review_status=payload.review_status,
            bucket_event_ids=result.bucket_event_ids,
        )
        return _bounded(
            LedgerLlmOperationResult.model_validate(
                {**common, "outcome": "classified", "classification": classification}
            )
        )
    if isinstance(result, LLMSplitApplyResult):
        return _bounded(
            LedgerLlmOperationResult.model_validate(
                {
                    **common,
                    "outcome": "split",
                    "split_group_id": result.split_group_id,
                    "child_transaction_ids": result.child_transaction_ids,
                    "classified_child_count": result.classified_child_count,
                }
            )
        )
    if isinstance(result, LLMSuggestionRejectionResult):
        return _bounded(
            LedgerLlmOperationResult.model_validate(
                {
                    **common,
                    "outcome": "rejected",
                    "bucket_event_id": result.bucket_event_id,
                    "suggestion_kind": result.suggestion_kind,
                    "operator_reason": result.operator_reason,
                }
            )
        )
    raise ValueError("ledger review writer returned an incompatible result")


def resolve_ledger_llm_review_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind ordinary operation actions; RESPOND's capability is supervisor-owned."""
    if request.definition_id not in _DEFINITION_IDS or not isinstance(request.payload, LedgerLlmReviewRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if request.definition_id != _definition_id(request.payload):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    disclosures = resolved.policy.disclosures
    if context.action in {AccessAction.REVIEW, AccessAction.RESPOND}:
        schema = context.contract.review_projection_schema
        if schema is None or context.contract.interaction_response_schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosures = frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=schema.schema_id,
                    category=DisclosureCategory.TAX_VALUES,
                ),
            )
        )
    policy = OperationAccessPolicy.model_validate(
        {
            **dict(resolved.policy),
            "actions": resolved.policy.actions | {AccessAction.COMMIT, AccessAction.REVIEW, AccessAction.RESPOND},
            "disclosures": disclosures,
            "transaction_authority_required": False,
        }
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def _result_projector(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
    """Match the complete private invocation to its exact settled public receipt."""
    if not isinstance(result, LedgerLlmExecutionResult):
        raise ValueError("invalid ledger review terminal result")
    validated = LedgerLlmExecutionResult.model_validate(result.model_dump())
    projection = validated.result
    expected_effect = (
        OperationEffect.NONE
        if projection.outcome == "preview"
        or (projection.classification is not None and not projection.classification.bucket_event_ids)
        else OperationEffect.UPDATED
    )
    if (
        receipt.identity != validated.identity
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref != sha256_hex(serialize_operation_operand(validated))
        or receipt.effect is not expected_effect
    ):
        raise ValueError("ledger review result and terminal receipt disagree")
    return _bounded(projection)


def build_ledger_llm_review_definition(
    definition_id: str, factory: LedgerLlmOperationPortsFactory
) -> OperationDefinition:
    """Declare the existing suggestion/review/writer workflow with secure continuation."""
    if definition_id not in _DEFINITION_IDS:
        raise ValueError("unknown ledger LLM review definition")
    return OperationDefinition(
        definition_id=definition_id,
        request_type=LedgerLlmReviewRequest,
        result_type=LedgerLlmExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerLlmReviewRequest,
            executor_type=LedgerLlmReviewExecutor,
            build=lambda: LedgerLlmReviewExecutor(factory),
        ),
        phase_codes=("ledger.llm.acquire", "ledger.llm.review", "ledger.llm.commit"),
        interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RESUMABLE,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.RESUMABLE,
            baseline=OperationBaselinePolicy.EXACT_APPROVAL,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def build_ledger_llm_review_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Register distinct private outcome and strict public projection models."""
    if (
        definition.definition_id not in _DEFINITION_IDS
        or definition.request_type is not LedgerLlmReviewRequest
        or definition.result_type is not LedgerLlmExecutionResult
    ):
        raise ValueError("invalid ledger LLM review definition binding")
    review, response = _schemas(definition.definition_id)
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=LedgerLlmReviewRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=LedgerLlmOperationResult
        ),
        review_projection_schema=review,
        interaction_response_schema=response,
        reviewed_operand_type=LedgerLlmReviewedOperand,
        review_projector=_review_projector,
        result_projector=_result_projector,
        access_resolver=resolve_ledger_llm_review_access,
    )
