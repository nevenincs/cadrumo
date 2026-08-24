"""Typed refusal outcomes owned by the aggregation application boundary."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum

from ...core import ActionEvidenceProvenance, NoRecoveryOutcome
from ..operator_actions import PreconditionVerdict, no_action_precondition_verdict


class AggregationPreconditionCondition(StrEnum):
    """Closed failed-condition identities for aggregation refusals."""

    INVOICE_LEDGER_COMPLETE = "aggregation.invoice_ledger.complete"
    PER_MODELO_MODELO_SUPPORTED = "aggregation.per_modelo.modelo.supported"
    RETENCIONES_OBSERVATIONS_PRESENT = "aggregation.retenciones.observations.present"


def aggregation_no_recovery_verdict(
    condition: AggregationPreconditionCondition,
    *,
    facts: Mapping[str, str | int | bool | Decimal],
    outcome: NoRecoveryOutcome = NoRecoveryOutcome.OPERATOR_DECISION,
) -> PreconditionVerdict:
    """Return the observed failure and explicit absence of a bound recovery.

    Aggregation can identify the incompatibility in its inputs, but it cannot
    safely construct an executable recovery invocation from those facts. The
    terminal verdict keeps that boundary machine-readable without retaining
    presentation recovery prose.
    """
    return no_action_precondition_verdict(
        condition_id=condition.value,
        facts=facts,
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=outcome,
    )


__all__ = ["AggregationPreconditionCondition", "aggregation_no_recovery_verdict"]
