"""A rule's declared party facts must be exactly the ones its predicate reads.

Each row of the IVA classification table declares, in ``consumes``, which
:class:`PartyFact` values its branch turns on. That declaration is what a
producer demands from an operator: ask for the identifying State only where a
branch actually reads it, and for nothing more. So the declaration is a claim
about the predicate, and the predicate is what must honour it.

**The two failure directions are different defects and both are gated here.** A
declared fact no predicate reads is the carried-but-unread shape: the operator
is asked for evidence that changes no outcome. A fact a predicate reads without
declaring it is the inverse: the producer stops demanding an identification for
an operation that turns on one, and the branch silently decides on a value
nobody was asked to supply.

**The actual set is derived from the predicate SOURCE, never from a second
declaration.** A gate comparing one declaration against another proves only that
the two agree and says nothing about the code. The extractor walks each
predicate's AST for reads of its own criteria parameter, following module-local
helpers the predicate hands criteria or a criteria attribute to, because that is
where the identification reads live. The attribute-to-fact mapping is checked
exhaustive against the criteria model's own fields, so adding a field to the
model forces a decision here rather than defaulting to "no fact".

**A row the extractor cannot read FAILS.** Contributing an empty set instead
would let a predicate drop out of the comparison and pass by absence, which is
the shape that lets a sweep examine part of a corpus and report success over the
whole of it.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Callable
from typing import Any

import pytest

from .. import _classification
from .._classification import (
    IvaInvoiceClassificationCriteria,
    PartyFact,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Which party fact each criteria attribute carries, or ``None`` where the
#: attribute is not a fact about a party at all. Keyed by the criteria model's
#: own field names and asserted exhaustive against them below, so this cannot
#: silently fall behind the model it describes.
_FACT_BY_CRITERIA_ATTRIBUTE: dict[str, PartyFact | None] = {
    "issuer_residency": PartyFact.TERRITORIAL_ESTABLISHMENT,
    "customer_residency": PartyFact.TERRITORIAL_ESTABLISHMENT,
    "issuer_identification_state": PartyFact.VAT_IDENTIFICATION_STATE,
    "customer_identification_state": PartyFact.VAT_IDENTIFICATION_STATE,
    "transaction_date": None,
    "customer_tax_status": None,
    "kind": None,
    "direction": None,
    "rate_tier": None,
}

#: A floor, not a count. The table governs the whole classification surface, so
#: a collapse to a handful of rows means the extraction found the wrong object;
#: an ordinary new rule must not have to edit this number.
_MINIMUM_RULES = 15


class _PredicateUnreadableError(AssertionError):
    """Raised when a predicate's reads cannot be determined from its source."""


def _criteria_attributes_read(
    predicate: Callable[..., Any],
    *,
    seen: frozenset[str] = frozenset(),
) -> set[str]:
    """Return the criteria attributes ``predicate`` reads, following its helpers.

    Raises:
        _PredicateUnreadableError: When the source cannot be retrieved or
            parsed. Refusing beats returning an empty set, which would read as
            "this row declares nothing and reads nothing" and pass.
    """
    name = getattr(predicate, "__name__", repr(predicate))
    if name in seen:
        return set()
    try:
        source = inspect.getsource(predicate)
        tree = ast.parse(source.lstrip())
    except (OSError, TypeError, SyntaxError) as exc:  # pragma: no cover - defended, not expected
        raise _PredicateUnreadableError(
            f"the reads of {name} cannot be determined from its source ({exc}); a row the "
            f"extractor cannot read must fail rather than contribute an empty set"
        ) from exc

    parameters = list(inspect.signature(predicate).parameters)
    if not parameters:
        raise _PredicateUnreadableError(f"{name} takes no criteria parameter, so its reads cannot be attributed")
    subject = parameters[0]

    def _is_subject(node: ast.expr) -> bool:
        return isinstance(node, ast.Name) and node.id == subject

    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and _is_subject(node.value):
            found.add(node.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            helper = getattr(_classification, node.func.id, None)
            if not inspect.isfunction(helper):
                continue
            # Only a helper handed the criteria, or one of its attributes, can
            # be reading a party fact on the predicate's behalf.
            handed_criteria = any(
                _is_subject(argument) or (isinstance(argument, ast.Attribute) and _is_subject(argument.value))
                for argument in node.args
            )
            if handed_criteria:
                found |= _criteria_attributes_read(helper, seen=seen | {name})
    return found


def _facts_read_by(predicate: Callable[..., Any]) -> set[PartyFact]:
    """Return the party facts a predicate's reads amount to."""
    attributes = _criteria_attributes_read(predicate)
    if not attributes:
        raise _PredicateUnreadableError(
            f"{getattr(predicate, '__name__', predicate)} reads no criteria attribute at all; a "
            f"predicate that inspects nothing cannot be a decision row, so this is an extraction "
            f"failure rather than a row consuming nothing"
        )
    unknown = attributes - set(_FACT_BY_CRITERIA_ATTRIBUTE)
    if unknown:
        raise _PredicateUnreadableError(
            f"{getattr(predicate, '__name__', predicate)} reads criteria attribute(s) "
            f"{sorted(unknown)} that the fact mapping does not cover"
        )
    return {fact for attribute in attributes if (fact := _FACT_BY_CRITERIA_ATTRIBUTE[attribute]) is not None}


def test_the_fact_mapping_covers_the_criteria_model_exactly() -> None:
    """The mapping is derived from the model, so a new field cannot default to "no fact".

    Without this, adding an identification-bearing field to the criteria model
    would leave every predicate reading it classified as reading nothing, and
    the honesty comparison below would go quiet in exactly the direction it
    exists to catch.
    """
    assert set(_FACT_BY_CRITERIA_ATTRIBUTE) == set(IvaInvoiceClassificationCriteria.model_fields)


def test_the_rule_table_is_populated() -> None:
    """Non-vacuity: the comparison below is over nothing if the table is empty."""
    assert len(_classification._CLASSIFICATION_RULES) >= _MINIMUM_RULES, (
        f"the rule table exposes only {len(_classification._CLASSIFICATION_RULES)} row(s), below the "
        f"floor of {_MINIMUM_RULES}; the extraction is looking at the wrong object rather than at a "
        f"table that shrank"
    )


def test_every_rule_reads_at_least_one_criteria_attribute() -> None:
    """Non-vacuity per row, which the table-level floor cannot give.

    A row contributing an empty attribute set would satisfy the equality below
    against an empty declaration and pass while asserting nothing about itself.
    This makes that state an error rather than a silent pass.
    """
    for rule in _classification._CLASSIFICATION_RULES:
        try:
            attributes = _criteria_attributes_read(rule.predicate)
        except _PredicateUnreadableError as exc:
            raise AssertionError(f"{rule.rule_id}: {exc}") from exc
        assert attributes, f"{rule.rule_id}: no criteria attribute extracted from its predicate"


def test_every_rule_declares_exactly_the_facts_its_predicate_reads() -> None:
    """Both directions at once: nothing declared unread, nothing read undeclared."""
    undeclared: list[str] = []
    unread: list[str] = []
    for rule in _classification._CLASSIFICATION_RULES:
        try:
            actual = _facts_read_by(rule.predicate)
        except _PredicateUnreadableError as exc:
            raise AssertionError(f"{rule.rule_id}: {exc}") from exc
        declared = set(rule.consumes)
        for fact in sorted(actual - declared, key=lambda item: item.value):
            undeclared.append(f"{rule.rule_id} reads {fact.value} without declaring it")
        for fact in sorted(declared - actual, key=lambda item: item.value):
            unread.append(f"{rule.rule_id} declares {fact.value} but its predicate never reads it")

    assert undeclared == [], (
        "a predicate turns on a party fact its row does not declare, so the producer stops "
        f"demanding evidence the branch decides on: {undeclared}"
    )
    assert unread == [], (
        "a row declares a party fact its predicate never reads, so an operator is asked for "
        f"evidence that changes no outcome: {unread}"
    )


def test_the_identification_reads_are_actually_reached() -> None:
    """An anchor on the extractor itself, not on the table.

    Every assertion above would pass identically if the extractor never found an
    identification read anywhere -- declared and actual would simply both come
    out as establishment-only. The intra-community rows read the identifying
    State through a module-local helper, which is precisely the path a naive
    walk of the predicate body misses, so this pins that the helper-following
    branch is doing work rather than being dead.
    """
    identifying = {
        rule.rule_id
        for rule in _classification._CLASSIFICATION_RULES
        if PartyFact.VAT_IDENTIFICATION_STATE in _facts_read_by(rule.predicate)
    }
    assert identifying, (
        "the extractor found no rule reading the identifying State. Either the helper-following "
        "branch stopped working, or the intra-community rows stopped reading identification -- "
        "the equality gate cannot tell those apart, so it is asserted here"
    )
