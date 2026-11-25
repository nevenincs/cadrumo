"""Doors of the Modelo 145 communication record refusals.

No catalogued action creates, corrects or exports a communication record, so a
refusal caused by the values the operator stated is the operator's decision: the
record is stated again. A refusal caused by the registry's own export design or
contract declarations is authored data no operator action repairs, so it is
terminal.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from ...core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..operator_actions.models import PreconditionVerdict
from ..operator_actions.preconditions import no_action_precondition_verdict

_CONDITION_PREFIX: Final[str] = "modelo.m145_communication"

type _Fact = str | int | bool | Decimal


def m145_record_decision_verdict(reason: str, facts: Mapping[str, _Fact]) -> PreconditionVerdict:
    """The operator's decision on a record whose stated values or stored coordinates the refusal names."""
    return no_action_precondition_verdict(
        condition_id=f"{_CONDITION_PREFIX}.{reason}.admitted",
        facts={**facts, "admitted": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def m145_registry_defect_verdict(reason: str, facts: Mapping[str, _Fact]) -> PreconditionVerdict:
    """The terminal verdict of an export design or contract declaration the registry holds defectively."""
    return no_action_precondition_verdict(
        condition_id=f"{_CONDITION_PREFIX}.{reason}.declared",
        facts={**facts, "declared": False},
        provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
        outcome=NoRecoveryOutcome.TERMINAL,
    )


__all__ = ["m145_record_decision_verdict", "m145_registry_defect_verdict"]
