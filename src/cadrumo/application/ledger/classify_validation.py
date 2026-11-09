"""Bounded, non-sensitive refusal classification for ledger classify inputs."""

from __future__ import annotations

from pydantic import ValidationError

from ...core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
)
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.gross_validation import (
    GROSS_NEEDS_WITHHOLDING_CATEGORY_FIELD,
    GROSS_NEEDS_WITHHOLDING_CATEGORY_MESSAGE_KEY,
)
from ..operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict
from .classify_result_contracts import (
    LEDGER_CLASSIFY_MAX_VALIDATION_MESSAGES,
    LedgerClassifyValidationKind,
    LedgerClassifyValidationMessages,
)
from .validation_messages import bounded_validation_messages, registered_refusal_causes

LEDGER_CLASSIFY_VALIDATION_ERRORS = (ValidationError, TransactionValidationError, RegistryValidationError)

NEEDS_WITHHOLDING_CATEGORY_CONDITION = "ledger.transaction.withholding_category.declared"
"""Failed-condition identity: a substrate above the cash needs a declared IRPF category."""

_NEEDS_WITHHOLDING_CATEGORY_EVIDENCE = "ledger.transaction.withholding_category.observation"


def classify_validation_kind(error: Exception) -> LedgerClassifyValidationKind:
    """Retain the user-actionable refusal categories without raw context."""
    if any(
        cause.translated_message == GROSS_NEEDS_WITHHOLDING_CATEGORY_MESSAGE_KEY
        for cause in registered_refusal_causes(error)
    ):
        return "needs_withholding_category"
    if not isinstance(error, TransactionValidationError):
        return "input"
    context = error.context or {}
    if "required_direction" in context:
        return "m210_incoming_only"
    if "missing" in context:
        return "m210_required_options"
    return "input"


def needs_withholding_category_verdict(*, transaction_id: str) -> PreconditionVerdict:
    """Name the one command that settles a substrate above the cash.

    The verdict records the fact and the action's catalogue identity only. The
    command path and its inputs are read from the reconciled command tree when a
    frontend resolves the verdict, and the category stays for the person to
    supply because only they know which withholding the invoice was settled net of.
    """
    return PreconditionVerdict(
        failed_condition_id=NEEDS_WITHHOLDING_CATEGORY_CONDITION,
        evidence=(
            ConditionEvidence(
                condition_id=NEEDS_WITHHOLDING_CATEGORY_CONDITION,
                evidence_id=_NEEDS_WITHHOLDING_CATEGORY_EVIDENCE,
                provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
                values={"field": GROSS_NEEDS_WITHHOLDING_CATEGORY_FIELD, "declared": False},
            ),
        ),
        action=ActionReference(action_id="operator.ledger.classify.irpf_category"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name=GROSS_NEEDS_WITHHOLDING_CATEGORY_FIELD,
                status=ActionArgumentStatus.MISSING,
            ),
            ActionArgumentBinding(
                argument_name="transaction_id",
                status=ActionArgumentStatus.RESOLVED,
                value=transaction_id,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="transaction_id",
            ),
        ),
        missing_argument_names=(GROSS_NEEDS_WITHHOLDING_CATEGORY_FIELD,),
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )


def classify_validation_messages(error: Exception) -> LedgerClassifyValidationMessages:
    """Retain only bounded field locations and user-actionable messages."""
    return bounded_validation_messages(
        error,
        limit=LEDGER_CLASSIFY_MAX_VALIDATION_MESSAGES,
        fallback="ledger classify values did not satisfy transaction validation",
    )
