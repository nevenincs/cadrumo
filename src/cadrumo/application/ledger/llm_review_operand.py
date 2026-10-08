"""Canonical encrypted continuation operand and its bounded review projection."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator

from ...core.hashing import reject_duplicate_json_members, reject_json_constant
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.type_guards import is_str_keyed_dict
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import Transaction
from ..operations.models import OperationIdentity
from .id_resolution import resolve_transaction_id
from .llm_classification_ports import (
    LLMClassificationSuggestion,
    LLMSaturatedSuggestion,
    LLMSplitChildSuggestion,
    LLMSplitSuggestion,
)
from .llm_review_contracts import (
    LedgerLlmChildProjection,
    LedgerLlmReviewRequest,
    LedgerLlmSuggestion,
    LedgerLlmSuggestionProjection,
    bound_ledger_llm_projection,
    require_ledger_llm_invocation,
)
from .persistence_ports import LedgerPersistenceConflictError

LedgerLlmDomainJson = Annotated[str, Field(min_length=1, max_length=4_194_304, repr=False)]


class LedgerLlmReviewedOperand(BaseModel):
    """Encrypted immutable input, proposal, and generation for detached continuation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    identity: OperationIdentity
    request: LedgerLlmReviewRequest
    baseline_json: LedgerLlmDomainJson
    authority_generation: ContentDigest
    suggestion_json: LedgerLlmDomainJson
    suggestion: LedgerLlmSuggestionProjection

    @model_validator(mode="after")
    def _same_transaction(self) -> LedgerLlmReviewedOperand:
        require_ledger_llm_invocation(self.identity, self.request)
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
        bound_ledger_llm_projection(self.suggestion)
        return self

    @classmethod
    def capture(
        cls,
        *,
        identity: OperationIdentity,
        request: LedgerLlmReviewRequest,
        baseline: Transaction,
        authority_generation: ContentDigest,
        suggestion: LedgerLlmSuggestion,
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

    def decode(self, operation: PinnedAuthorityOperation) -> tuple[Transaction, LedgerLlmSuggestion]:
        """Reconstruct and cross-check domain values only under their pinned generation."""
        if self.authority_generation != operation.generation.logical_generation:
            raise LedgerPersistenceConflictError("ledger review authority generation changed")
        with validating_governed_facts(operation):
            baseline, suggestion = _decode_reviewed_values(self)
        _require_reviewed_suggestion_mode(self.request.mode, suggestion)
        return baseline, suggestion


def _wire_decimal(value: Decimal) -> str:
    """Preserve the original finite domain Decimal without display trimming."""
    if not value.is_finite():
        raise TransactionValidationError("ledger review requires finite decimal facts")
    return format(value, "f")


def _decode_suggestion(suggestion_json: str, kind: str) -> LedgerLlmSuggestion:
    if kind == "split":
        return LLMSplitSuggestion.model_validate_json(suggestion_json)
    if kind == "saturated":
        return LLMSaturatedSuggestion.model_validate_json(suggestion_json)
    return LLMClassificationSuggestion.model_validate_json(suggestion_json)


def _require_reviewed_value_round_trip(
    operand: LedgerLlmReviewedOperand,
    baseline: Transaction,
    suggestion: LedgerLlmSuggestion,
) -> None:
    if (
        baseline.transaction_id != suggestion.transaction_id
        or baseline.model_dump_json() != operand.baseline_json
        or suggestion.model_dump_json() != operand.suggestion_json
        or _suggestion_projection(suggestion) != operand.suggestion
    ):
        raise LedgerPersistenceConflictError("ledger reviewed domain values and projection disagree")


def _decode_reviewed_values(
    operand: LedgerLlmReviewedOperand,
) -> tuple[Transaction, LedgerLlmSuggestion]:
    baseline = Transaction.model_validate_json(operand.baseline_json)
    suggestion = _decode_suggestion(operand.suggestion_json, operand.suggestion.kind)
    _require_reviewed_value_round_trip(operand, baseline, suggestion)
    return baseline, suggestion


def _require_reviewed_suggestion_mode(mode: str, suggestion: LedgerLlmSuggestion) -> None:
    if mode in {"split", "auto_split"} and not isinstance(suggestion, LLMSplitSuggestion):
        raise ValueError("split review requires its split proposal")
    if mode == "saturated" and not isinstance(suggestion, LLMSaturatedSuggestion):
        raise ValueError("saturated review requires its grounded proposal")
    if mode not in {"split", "auto_split", "saturated"} and type(suggestion) is not LLMClassificationSuggestion:
        raise ValueError("classification review requires its classification proposal")


def _project_split_child(child: LLMSplitChildSuggestion) -> LedgerLlmChildProjection:
    return LedgerLlmChildProjection(
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


def _project_split_suggestion(suggestion: LLMSplitSuggestion) -> LedgerLlmSuggestionProjection:
    return bound_ledger_llm_projection(
        LedgerLlmSuggestionProjection(
            kind="split",
            transaction_id=suggestion.transaction_id,
            provenance=suggestion.provenance,
            reason=suggestion.reason,
            evidence_id=suggestion.evidence_id,
            parent_amount=_wire_decimal(suggestion.parent_amount),
            children=tuple(_project_split_child(child) for child in suggestion.children),
        )
    )


def _project_classification_suggestion(
    suggestion: LLMClassificationSuggestion | LLMSaturatedSuggestion,
) -> LedgerLlmSuggestionProjection:
    return LedgerLlmSuggestionProjection(
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


def _project_saturated_suggestion(
    basic: LedgerLlmSuggestionProjection,
    suggestion: LLMSaturatedSuggestion,
) -> LedgerLlmSuggestionProjection:
    return LedgerLlmSuggestionProjection.model_validate(
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


def _suggestion_projection(suggestion: LedgerLlmSuggestion) -> LedgerLlmSuggestionProjection:
    """Copy grounded values while preserving each Decimal's original scale."""
    if isinstance(suggestion, LLMSplitSuggestion):
        return _project_split_suggestion(suggestion)
    basic = _project_classification_suggestion(suggestion)
    if isinstance(suggestion, LLMSaturatedSuggestion):
        basic = _project_saturated_suggestion(basic, suggestion)
    return bound_ledger_llm_projection(basic)
