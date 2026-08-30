"""Redaction rules resolve by NAME, so a name is the thing that can rot.

A rule does not apply because it exists. It applies because some policy
NAMES it in ``redaction_rules``, and :func:`default_rules_for` looks that
name up. Two mistakes follow from that indirection, they are different
bugs, and neither is visible at runtime:

* **Dormant** -- a rule is declared and enrolled nowhere. It looks like
  protection in the source and redacts nothing.
* **Unresolvable** -- a policy names a rule that does not exist. A typo
  in the tuple silently disables that arm of the policy.

The second was the sharper one, because the lookup SKIPPED what it could
not find: the failure mode was "sensitive data flows through unredacted",
with no error and no warning. That is fail-open, which is the one
direction a confidentiality boundary may not fail, and
:func:`default_rules_for` now refuses instead. These gates are the other
half of that fix -- the refusal catches a bad name in a running process,
and these catch one in the shipped tables, at CI, where a typo
realistically enters. Elsewhere this codebase makes declared-but-unrouted
things fail loudly for the same reason.

Both directions are checked here, and each is proved to bite against a
constructed table rather than by editing the shipped one, so no window
ever exists in which the real policies are wrong.

These two are the whole of it, and deliberately so. A rule record used
to carry an ``applies_to`` tuple as well -- a second declaration of where
it applied, which resolution never read. That field is gone rather than
guarded: a duplicate nothing consults can only drift into a lie, and a
gate pinning it to the policy table would have been machinery protecting
a fact that did not need to be stated twice. Enrolment is now the only
declaration, so there is nothing left for it to disagree with.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ..classification import (
    ClassificationPolicy,
    OutputSensitivityClass,
    RedactionRule,
    RedactionStrategy,
    SensitivityClass,
    default_output_policy_for,
    default_policy_for,
)
from ..errors.hierarchy import RedactionError
from ..redaction import default_rules, default_rules_for, default_rules_for_class

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

if TYPE_CHECKING:
    from collections.abc import Mapping


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


def _rule(name: str) -> RedactionRule:
    """One syntactically valid rule, for the constructed tables below."""
    return RedactionRule(
        name=name,
        pattern=r"\bx\b",
        strategy=RedactionStrategy.SHA256_PREFIX,
    )


# ── the shipped tables ───────────────────────────────────────────────────


def test_every_name_a_policy_enrols_resolves_to_a_real_rule() -> None:
    """A policy naming a rule that does not exist must be caught here first.

    Resolution refuses such a name now, but that refusal fires wherever
    the policy is used -- which for a shipped table means somewhere an
    operator is standing. Catching it in CI is the difference between a
    typo that never ships and one that surfaces as a broken command.
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


def _policy_naming(*names: str) -> ClassificationPolicy:
    """The shipped IDENTITY policy with its rule names swapped.

    Derived from the real policy rather than assembled here, so these
    cases cannot drift from the shape the table actually uses: only the
    field under test differs from something in production.
    """
    return default_policy_for(SensitivityClass.IDENTITY).model_copy(update={"redaction_rules": names})


def test_resolving_a_policy_that_names_an_unknown_rule_refuses() -> None:
    """The runtime half: resolution must stop rather than narrow itself.

    The gates above catch a bad name in CI. This catches one that reaches
    a running process anyway — a policy assembled somewhere the gate does
    not walk — and it is the difference between failing closed and
    leaking. Skipping the name would return a SHORTER rule tuple and
    redact less, reporting nothing.
    """
    with pytest.raises(RedactionError) as refusal:
        default_rules_for(_policy_naming("nif-hash", "nif-hsah"))

    message = str(refusal.value)
    assert "nif-hsah" in message, f"the refusal must name the rule that did not resolve: {message}"
    assert "nif-hash" in message, f"the refusal must list what it does know, to make the typo obvious: {message}"


def test_resolving_a_policy_whose_names_all_resolve_returns_them_in_order() -> None:
    """The negative half: refusal must be scoped to names that do not exist.

    Without this the guard could be satisfied by refusing every policy,
    which would take redaction down entirely rather than making it strict.
    Order is asserted because callers apply the rules in sequence.
    """
    resolved = default_rules_for(_policy_naming("cif-hash", "nif-hash"))
    assert [rule.name for rule in resolved] == ["cif-hash", "nif-hash"]


def test_every_shipped_sensitivity_class_still_resolves_through_the_refusing_path() -> None:
    """The real tables must pass the stricter resolver, not merely the gate.

    A refusal that the shipped policies themselves tripped would be found
    the moment anything redacted; this asserts the two halves agree, so
    the strictness cannot have been bought by breaking live resolution.
    """
    for sensitivity in SensitivityClass:
        default_rules_for_class(sensitivity)
