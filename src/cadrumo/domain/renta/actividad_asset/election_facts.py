"""The facts an election states for each depreciation method, read from the election model.

Which facts a method admits or requires is declared once, beside the election's
validator.  This module reads those declarations together with the model's field
types, so a form can offer a method with exactly the facts the election will
accept, and can tell a method it has no way to state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .election import (
    ELECTION_FACT_ADMISSION,
    ELECTION_REQUIRED_FACTS,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
)
from .fact_leaves import FactKind, fact_leaves

_STATED_ELSEWHERE = frozenset({"regime", "method"})
"""Election fields every method has, which the form states before any method fact."""


@dataclass(frozen=True, slots=True)
class MethodFact:
    """One leaf fact an election of a method states.

    ``required`` means the election is refused without it.  ``required_with_group``
    means the fact's group is optional for the method, and the election is refused
    when the group is stated without this fact.
    """

    path: tuple[str, ...]
    kind: FactKind
    tokens: type[StrEnum] | None
    required: bool
    required_with_group: bool


def method_facts(method: AmortizationMethod) -> tuple[MethodFact, ...]:
    """List the leaf facts an election of the method states, required or optional, in model order."""
    required_groups = ELECTION_REQUIRED_FACTS.get(method, ())
    facts: list[MethodFact] = []
    for leaf in fact_leaves(ActivityAssetAmortizationElection, descend_rows=False):
        group = leaf.path[0]
        if group in _STATED_ELSEWHERE:
            continue
        required_group = group in required_groups
        if not required_group and method not in ELECTION_FACT_ADMISSION.get(group, frozenset()):
            continue
        nested = len(leaf.path) > 1
        facts.append(
            MethodFact(
                path=leaf.path,
                kind=leaf.kind,
                tokens=leaf.tokens,
                required=required_group and (not nested or not leaf.optional),
                required_with_group=nested and not required_group and not leaf.optional,
            )
        )
    return tuple(facts)


def method_is_statable(method: AmortizationMethod) -> bool:
    """Say whether every fact the method requires is one a form states as a single value.

    A repeated group of facts, such as an approved plan's yearly amounts, has no such form.
    """
    return not any(fact.required and fact.kind is FactKind.ROWS for fact in method_facts(method))


__all__ = ["MethodFact", "method_facts", "method_is_statable"]
