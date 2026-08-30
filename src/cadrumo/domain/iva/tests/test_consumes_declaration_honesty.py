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
helpers the predicate hands criteria or a criteria attribute to. The
attribute-to-fact mapping is checked exhaustive against the criteria model's own
fields, so adding a field to the model forces a decision here rather than
defaulting to "no fact".

**The helper-following is for a shape no live row has yet**, and saying so is
the correction of a claim this module used to make. Every current row spells the
attribute out in the call it makes, so the plain walk finds it before any helper
is considered: measured, following changes the extracted set on 0 of 19 rows.
The branch is kept rather than deleted because of an asymmetry in how its
absence fails. A predicate delegating EVERYTHING would extract nothing, which
the unreadable-row refusal already catches out loud. A predicate reading one
attribute inline and delegating the identification extracts that one attribute,
raises nothing, and passes the comparison while turning on a fact it never
declared -- the silent direction, and the one this module exists to catch. Both
shapes are pinned below against synthetic predicates, because making the
production table adopt a shape it does not need in order to cover a gate would
be the gate dictating the code it audits.

**A row the extractor cannot read FAILS.** Contributing an empty set instead
would let a predicate drop out of the comparison and pass by absence, which is
the shape that lets a sweep examine part of a corpus and report success over the
whole of it.
"""

from __future__ import annotations

import ast
import inspect
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any

import pytest

from .. import classification
from ..classification import (
    EUMemberState,
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
    "issuer_identification_state": PartyFact.IVA_IDENTIFICATION_STATE,
    "customer_identification_state": PartyFact.IVA_IDENTIFICATION_STATE,
    "transaction_date": None,
    "customer_tax_status": None,
    "kind": None,
    "direction": None,
    "rate_tier": None,
    # A fact about the SUPPLY, not about a party: which lettered service of
    # Ley 37/1992 art. 69.Dos it is. A row reading it turns on what was
    # supplied, so it demands nothing further about who received it.
    "art_69_dos_service": None,
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
    module: ModuleType = classification,
) -> set[str]:
    """Return the criteria attributes ``predicate`` reads, following its helpers.

    Args:
        predicate: The row's predicate, or a helper reached from one.
        seen: Names already walked, which stops a helper cycle.
        module: Where a called name is looked up to decide whether it is a
            module-local helper. Defaults to the classification module, which is
            the production answer. It is a parameter rather than a constant so
            the helper-following branch can be exercised against a predicate
            declared in this test module -- the branch is inert on every live
            row (each spells the attribute out in its call arguments, which the
            plain walk already finds), so without this seam the only way to
            cover it would be to make the production table adopt a shape it has
            no reason to.

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
            helper = getattr(module, node.func.id, None)
            if not inspect.isfunction(helper):
                continue
            # Only a helper handed the CRITERIA ITSELF may be followed. A helper
            # handed a criteria ATTRIBUTE must not be, and the distinction is
            # not pedantry: this function attributes every read to the callee's
            # FIRST PARAMETER, which for such a helper is the attribute's VALUE
            # rather than the criteria. Following it would record the fields
            # that value happens to expose as though they were criteria
            # attributes, and the exhaustive-mapping check would then refuse an
            # unknown attribute on a CORRECT predicate.
            #
            # Nothing is lost by declining: the attribute handed over is already
            # recorded by the attribute walk above, and the attribute IS the
            # fact. What the branch exists for -- a predicate delegating a read
            # it never spells out -- can only happen when the whole criteria is
            # passed, which is the case still followed.
            if any(_is_subject(argument) for argument in node.args):
                found |= _criteria_attributes_read(helper, seen=seen | {name}, module=module)
    return found


def _facts_read_by(predicate: Callable[..., Any], *, module: ModuleType = classification) -> set[PartyFact]:
    """Return the party facts a predicate's reads amount to.

    Takes ``module`` for the same reason the extractor does, and threading it
    is load-bearing rather than tidiness: a predicate whose helper is not found
    yields its inline reads only, and where those carry no party fact the result
    is an EMPTY fact set that raises nothing -- the attribute list was non-empty,
    so the unreadable-row refusal never fires. Silent, and identical to an
    honest row that turns on no party fact.
    """
    attributes = _criteria_attributes_read(predicate, module=module)
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
    assert len(classification._CLASSIFICATION_RULES) >= _MINIMUM_RULES, (
        f"the rule table exposes only {len(classification._CLASSIFICATION_RULES)} row(s), below the "
        f"floor of {_MINIMUM_RULES}; the extraction is looking at the wrong object rather than at a "
        f"table that shrank"
    )


def test_every_rule_reads_at_least_one_criteria_attribute() -> None:
    """Non-vacuity per row, which the table-level floor cannot give.

    A row contributing an empty attribute set would satisfy the equality below
    against an empty declaration and pass while asserting nothing about itself.
    This makes that state an error rather than a silent pass.
    """
    for rule in classification._CLASSIFICATION_RULES:
        try:
            attributes = _criteria_attributes_read(rule.predicate)
        except _PredicateUnreadableError as exc:
            raise AssertionError(f"{rule.rule_id}: {exc}") from exc
        assert attributes, f"{rule.rule_id}: no criteria attribute extracted from its predicate"


def test_every_rule_declares_exactly_the_facts_its_predicate_reads() -> None:
    """Both directions at once: nothing declared unread, nothing read undeclared."""
    undeclared: list[str] = []
    unread: list[str] = []
    for rule in classification._CLASSIFICATION_RULES:
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
    out as establishment-only. This pins that some row IS found to read the
    identifying State, so the equality gate is comparing something.

    **It does NOT pin the helper-following branch, and used to say it did.**
    Measured over the live table: following changes the extracted set on 0 of 19
    rows, and removing the branch leaves this assertion green. Every row spells
    the attribute out in the call it makes --
    ``_identified_in_another_member_state(criteria.issuer_identification_state)``
    -- and the argument is an attribute OF the subject, which the plain walk
    above already records before any helper is considered. So the branch is
    inert here, and a failure of this assertion can only mean the rows stopped
    reading identification. Naming a second cause it cannot observe made the
    name convince a reader of a coverage the body never had; the branch's own
    guard is :func:`test_the_helper_following_branch_finds_a_read_the_plain_walk_misses`.
    """
    identifying = {
        rule.rule_id
        for rule in classification._CLASSIFICATION_RULES
        if PartyFact.IVA_IDENTIFICATION_STATE in _facts_read_by(rule.predicate)
    }
    assert identifying, (
        "the extractor found no rule reading the identifying State, so the intra-community rows "
        "stopped reading identification and the equality gate above is comparing establishment "
        "against establishment"
    )


# --------------------------------------------------------------------------
# The helper-following branch, guarded against its own deletion.
#
# No live row hands a helper the WHOLE criteria object, so the branch is inert
# on the production table and cannot be covered from it. These declarations are
# the shape it exists for. They are deliberately synthetic: making the real
# table adopt this shape to exercise a gate would be the gate dictating the code
# it audits.
# --------------------------------------------------------------------------


def _reads_the_customer_identification(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """A helper handed the whole criteria, reading a party fact on a caller's behalf."""
    return criteria.customer_identification_state is not None


def _predicate_delegating_everything(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Reads nothing directly; the helper does all of it."""
    return _reads_the_customer_identification(criteria)


def _predicate_reading_some_and_delegating_the_rest(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Reads one attribute inline and delegates the identification to a helper."""
    return criteria.kind is not None and _reads_the_customer_identification(criteria)


def test_the_helper_following_branch_finds_a_read_the_plain_walk_misses() -> None:
    """The branch's real guard, on the shape no live row has yet.

    Both synthetic predicates hand the WHOLE criteria to a helper, which is the
    only shape following can contribute to. Asserted against a helper declared
    in this module rather than by teaching the production table a shape it does
    not need.

    The mixed predicate is the one that makes the branch worth keeping, and the
    reason is a measured asymmetry rather than symmetry with its sibling. Delete
    the branch and the fully-delegating predicate extracts NOTHING, which the
    extractor already refuses out loud as an unreadable row -- fail-closed, and
    visible. The mixed one extracts ``kind`` and stops: non-empty, so no refusal
    fires, and the row passes the honesty comparison while its predicate turns
    on an identification it never declared. That is the silent direction, and it
    is exactly the defect this module exists to catch.
    """
    module = sys.modules[__name__]

    delegating = _criteria_attributes_read(_predicate_delegating_everything, module=module)
    mixed = _criteria_attributes_read(_predicate_reading_some_and_delegating_the_rest, module=module)

    assert delegating == {"customer_identification_state"}, (
        f"following a helper handed the whole criteria found {sorted(delegating)}; the branch is not reaching the read"
    )
    assert mixed == {"kind", "customer_identification_state"}, (
        f"the mixed shape extracted {sorted(mixed)}; the inline read and the delegated one must both "
        "be found, or a row reads an identification it never declares"
    )
    assert PartyFact.IVA_IDENTIFICATION_STATE in _facts_read_by(
        _predicate_reading_some_and_delegating_the_rest,
        module=module,
    )


def _reads_a_field_off_whatever_it_was_handed(state: EUMemberState | None) -> bool:
    """A helper handed a criteria ATTRIBUTE, not the criteria.

    Its parameter is the attribute's VALUE, and ``value`` is a field of the
    enum rather than of the criteria. Nothing about this helper is wrong; it is
    the shape that used to make the extractor wrong. Read as an attribute
    rather than through ``getattr``, because the extractor walks attribute
    ACCESS and a dynamic lookup would leave the branch unexercised -- which the
    first draft of this case did, passing while proving nothing.

    Never called, like its sibling synthetic predicates: it exists to be read.
    """
    return state is not None and bool(state.value)


def _predicate_handing_an_attribute_to_a_helper(criteria: IvaInvoiceClassificationCriteria) -> bool:
    """Reads one criteria attribute and hands its VALUE to a helper."""
    return _reads_a_field_off_whatever_it_was_handed(criteria.customer_identification_state)


def test_a_helper_handed_an_attribute_contributes_only_that_attribute() -> None:
    """The latent fragility this hardening removes, pinned in both directions.

    The extractor attributes every read to the callee's FIRST PARAMETER. For a
    helper handed ``criteria.customer_identification_state`` that parameter is
    the STATE, not the criteria -- so following it recorded ``value``, a field
    of the enum, as though a criteria attribute of that name had been read. The
    exhaustive-mapping check would then refuse an unknown attribute, and the
    author whose predicate it refused would have done nothing wrong.

    That is the loud direction rather than the silent one, which is why this was
    recorded before it was fixed rather than treated as urgent. It still had to
    be fixed: a gate that reds a correct predicate is one an author works around
    rather than trusts, and no shipped helper triggering it today is a fact
    about today.

    Nothing is lost by declining to follow. The handed attribute is already
    recorded by the plain walk, and the attribute IS the fact -- asserted below
    rather than argued, since a fix that also stopped seeing the read would be a
    regression wearing a fix.
    """
    module = sys.modules[__name__]

    extracted = _criteria_attributes_read(_predicate_handing_an_attribute_to_a_helper, module=module)

    assert extracted == {"customer_identification_state"}, (
        f"extracted {sorted(extracted)}; a helper handed an ATTRIBUTE must contribute that attribute "
        "and nothing off the value's own type"
    )
    assert PartyFact.IVA_IDENTIFICATION_STATE in _facts_read_by(
        _predicate_handing_an_attribute_to_a_helper,
        module=module,
    ), "the delegated read must still resolve to the fact it turns on"


def test_without_following_the_mixed_shape_would_pass_while_reading_undeclared() -> None:
    """Why the branch is kept rather than deleted, proved rather than argued.

    Deleting the branch is a defensible reading -- it is dead against every live
    row. This is the measurement that decides against it, and it is a claim
    about a FUTURE row rather than a present one, which is why it is pinned
    rather than left as a comment.

    A plain walk is simulated by looking helpers up in a module that has none,
    which reproduces exactly what deleting the branch would do without editing
    the extractor. The fully-delegating shape then extracts nothing and the
    extractor's own refusal catches it. The mixed shape extracts ``kind``,
    reports establishment-adjacent reads only, and is indistinguishable from an
    honest row -- so the identification read disappears silently and the
    producer stops demanding evidence the branch decides on.
    """

    # A real, empty module rather than a stand-in namespace: the extractor looks
    # helpers up with getattr, so an empty module resolves every call to None and
    # follows nothing, which is precisely the deleted-branch behaviour.
    no_helpers = ModuleType("_no_helpers")

    without = _criteria_attributes_read(_predicate_reading_some_and_delegating_the_rest, module=no_helpers)

    assert without == {"kind"}, f"expected the unfollowed walk to see only the inline read; got {sorted(without)}"
    assert PartyFact.IVA_IDENTIFICATION_STATE not in {
        fact for attribute in without if (fact := _FACT_BY_CRITERIA_ATTRIBUTE[attribute]) is not None
    }, "the unfollowed walk must lose the identification, or this proves nothing about the branch"
    # And it is NOT caught by the extractor's empty-set refusal, which is the
    # whole point: a non-empty wrong answer passes every gate in this module.
    assert without, "a non-empty extraction is what makes the loss silent rather than refused"
