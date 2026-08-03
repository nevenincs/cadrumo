"""Redaction rules resolve by NAME, so a name is the thing that can rot.

A rule does not apply because it exists. It applies because some policy
NAMES it in ``redaction_rules``, and :func:`default_rules_for` looks that
name up. Two mistakes follow from that indirection, they are different
bugs, and neither is visible at runtime:

* **Dormant** -- a rule is declared and enrolled nowhere. It looks like
  protection in the source and redacts nothing.
* **Unresolvable** -- a policy names a rule that does not exist. A typo
  in the tuple silently disables that arm of the policy.

The second is the sharper one, because the lookup is written
``if name in _DEFAULT_RULES`` and therefore SKIPS what it cannot find. A
mechanism whose failure mode is "sensitive data flows through
unredacted", with no error and no warning, is fail-open -- the opposite
of what a confidentiality boundary may do. Elsewhere this codebase makes
declared-but-unrouted things fail loudly for exactly this reason; this is
the redaction surface's version of that gate.

Both directions are checked here, and each is proved to bite against a
constructed table rather than by editing the shipped one, so no window
ever exists in which the real policies are wrong.

``applies_to`` is checked too, for a different reason: resolution does
not read it. It is a second, independent declaration of the same fact the
policy table already carries, so nothing stops it disagreeing -- a rule
can claim one set of classes while being enrolled in another, and every
reader believes the claim. The gate does not give it teeth it lacks; it
makes it HONEST, which is the least that can be asked of a field the code
ignores. Deleting it, so the fact is declared once, is the alternative
worth taking deliberately rather than by drift.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ..classification import (
    OutputSensitivityClass,
    RedactionRule,
    RedactionStrategy,
    SensitivityClass,
    default_output_policy_for,
    default_policy_for,
)
from ..redaction import default_rules

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _named_by_every_policy() -> dict[str, tuple[str, ...]]:
    """Map each policy to the rule names it enrols.

    Both tables, because both resolve through the same registry and a
    typo is as silent in one as in the other. The output table is where
    operator-facing redaction is decided, so leaving it out would exempt
    the surface the operator actually reads.
    """
    persisted = {f"storage:{s.value}": default_policy_for(s).redaction_rules for s in SensitivityClass}
    output = {f"output:{s.value}": default_output_policy_for(s).redaction_rules for s in OutputSensitivityClass}
    return persisted | output


def _unresolvable(
    rules: Mapping[str, RedactionRule],
    policies: Mapping[str, tuple[str, ...]],
) -> list[str]:
    """Names a policy enrols that the registry cannot resolve."""
    return sorted(f"{label} names {name!r}" for label, names in policies.items() for name in names if name not in rules)


def _dormant(
    rules: Mapping[str, RedactionRule],
    policies: Mapping[str, tuple[str, ...]],
) -> list[str]:
    """Rules that exist but that no policy enrols."""
    enrolled = {name for names in policies.values() for name in names}
    return sorted(set(rules) - enrolled)


def _applies_to_disagreements(rules: Mapping[str, RedactionRule]) -> list[str]:
    """Rules whose declared ``applies_to`` differs from where they are enrolled.

    Compared against the persisted table only. ``applies_to`` is typed as
    :class:`SensitivityClass`, so it cannot describe the output table at
    all -- itself worth knowing about a field that reads as though it
    governs where a rule applies.
    """
    disagreements: list[str] = []
    for name, rule in rules.items():
        enrolled_in = {s for s in SensitivityClass if name in default_policy_for(s).redaction_rules}
        declared = set(rule.applies_to)
        if declared != enrolled_in:
            missing = sorted(s.value for s in enrolled_in - declared)
            surplus = sorted(s.value for s in declared - enrolled_in)
            disagreements.append(f"{name}: enrolled-but-undeclared={missing} declared-but-unenrolled={surplus}")
    return sorted(disagreements)


def _rule(name: str, applies_to: tuple[SensitivityClass, ...] = ()) -> RedactionRule:
    """One syntactically valid rule, for the constructed tables below."""
    return RedactionRule(
        name=name,
        pattern=r"\bx\b",
        strategy=RedactionStrategy.SHA256_PREFIX,
        applies_to=applies_to,
    )


# ── the shipped tables ───────────────────────────────────────────────────


def test_every_name_a_policy_enrols_resolves_to_a_real_rule() -> None:
    """A policy naming a rule that does not exist redacts nothing for it.

    The lookup skips what it cannot find, so a typo here costs an entire
    redaction arm and reports nothing at all. This is the fail-open
    direction and the reason the module exists.
    """
    unresolvable = _unresolvable(default_rules(), _named_by_every_policy())
    assert not unresolvable, (
        "these policies enrol rule names that no rule declares, so that arm of the policy "
        f"silently redacts nothing: {unresolvable}"
    )


def test_every_declared_rule_is_enrolled_by_at_least_one_policy() -> None:
    """A rule enrolled nowhere is inert however carefully it is written.

    The opposite direction, and the one that reads most like protection
    while providing none: the pattern, the strategy and the reasoning are
    all present in the source, and no policy ever asks for them.
    """
    dormant = _dormant(default_rules(), _named_by_every_policy())
    assert not dormant, (
        "these rules are declared but no policy enrols them, so they redact nothing anywhere; "
        f"enrol them or delete them: {dormant}"
    )


def test_declared_applies_to_matches_where_each_rule_is_actually_enrolled() -> None:
    """The unread field must at least not lie.

    Resolution ignores ``applies_to`` entirely, so it can drift from the
    policy table without any behaviour changing -- and a reader deciding
    whether a class is covered would believe it. Pinning the two together
    is what keeps the redundant declaration truthful for as long as it
    survives.
    """
    disagreements = _applies_to_disagreements(default_rules())
    assert not disagreements, (
        "these rules declare an applies_to that disagrees with the policies enrolling them; "
        "applies_to is not consulted by resolution, so the declaration is what is wrong "
        f"unless the enrolment is: {disagreements}"
    )


# ── proof that each direction bites ──────────────────────────────────────


def test_the_unresolvable_check_catches_a_mistyped_rule_name() -> None:
    """Driven with a constructed table, so the shipped policies are never wrong.

    Without this the check above could be satisfied by a predicate that
    finds nothing, which is indistinguishable from a clean table.
    """
    rules = {"nif-hash": _rule("nif-hash")}
    assert _unresolvable(rules, {"storage:identity": ("nif-hash", "nif-hsah")}) == ["storage:identity names 'nif-hsah'"]


def test_the_unresolvable_check_clears_a_table_whose_names_all_resolve() -> None:
    """The negative half: a check that refused either way would prove nothing."""
    rules = {"nif-hash": _rule("nif-hash")}
    assert not _unresolvable(rules, {"storage:identity": ("nif-hash",)})


def test_the_dormant_check_catches_a_rule_no_policy_enrols() -> None:
    """The direction that made the CIF rule inert until it was enrolled."""
    rules = {"nif-hash": _rule("nif-hash"), "cif-hash": _rule("cif-hash")}
    assert _dormant(rules, {"storage:identity": ("nif-hash",)}) == ["cif-hash"]


def test_the_dormant_check_clears_a_rule_that_is_enrolled() -> None:
    """The negative half of the dormant direction."""
    rules = {"nif-hash": _rule("nif-hash")}
    assert not _dormant(rules, {"storage:identity": ("nif-hash",)})


def test_the_applies_to_check_catches_a_declaration_that_understates_its_reach() -> None:
    """A rule enrolled in a class it does not declare.

    Read from the source alone, ``FINANCIAL`` looks uncovered by this
    rule while the policy table enrols it there -- the direction that
    would let a reviewer believe a class is exempt when it is not.
    Exercised against the shipped table, because the enrolment side of
    the comparison is read from it.
    """
    understated = _rule("nif-hash", applies_to=(SensitivityClass.IDENTITY,))
    disagreements = _applies_to_disagreements({"nif-hash": understated})
    assert len(disagreements) == 1, disagreements
    assert disagreements[0].startswith("nif-hash: enrolled-but-undeclared=[")
    assert "financial" in disagreements[0]
    assert "declared-but-unenrolled=[]" in disagreements[0]


def test_the_applies_to_check_catches_a_declaration_that_overstates_its_reach() -> None:
    """The opposite error: a class claimed but never enrolled.

    ``CACHE`` enrols no rules at all, so declaring it here is a claim of
    coverage that does not exist anywhere -- and this half is what stops
    the check being satisfied by simply declaring every class.
    """
    overstated = _rule("nif-hash", applies_to=(*default_rules()["nif-hash"].applies_to, SensitivityClass.CACHE))
    disagreements = _applies_to_disagreements({"nif-hash": overstated})
    assert len(disagreements) == 1, disagreements
    assert "declared-but-unenrolled=['cache']" in disagreements[0]
