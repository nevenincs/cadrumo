"""No mutating command escapes the declared risk table (the H3 no-silent-default gate).

The safety guarantee of the declared risk model: every command whose family mutates local state carries EXACTLY ONE declared
risk row, so a new mutating verb cannot slip in unclassified and auto-approve -
the failure mode the leaf-name frozensets had. This gate fails the build the
moment a mutating-family command has no row, and it fails if a row references a
command key that no longer exists (a stale declaration). Driven over the real
exposed command surface - no mocks.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from ....application.operator_surface import (
    COMMAND_RISK,
    CommandClassification,
    OperatorMutability,
    classify_command,
    command_classification,
    declared_risk,
)
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _exposed_keys() -> set[str]:
    return {descriptor.command_key for descriptor in build_tool_descriptors()}


def _unassessed(classifications: Iterable[CommandClassification]) -> list[str]:
    """Return the keys whose judgment axes were defaulted rather than assessed."""
    return sorted(item.command_key for item in classifications if not item.risk_declared)


def _live_writers(classifications: Iterable[CommandClassification]) -> list[str]:
    """Return the keys declaring a live AEAT write."""
    return sorted(item.command_key for item in classifications if item.live_write)


def test_every_mutating_family_command_carries_a_declared_row() -> None:
    # A command is "mutating" iff its family is not read-only; such a command MUST
    # carry a declared row, else it silently classifies all-false and auto-approves.
    missing = sorted(
        key for key in _exposed_keys() if not command_classification(key).read_only and declared_risk(key) is None
    )
    assert missing == [], f"mutating commands with no declared risk row (H3 no-silent-default): {missing}"


def test_no_declared_row_references_a_dead_command_key() -> None:
    exposed = _exposed_keys()
    stale = sorted(key for key in COMMAND_RISK if key not in exposed)
    assert stale == [], f"risk rows referencing command keys that no longer exist: {stale}"


def test_a_new_unclassified_mutating_verb_would_be_caught() -> None:
    # Anti-tautology: a synthetic new mutating verb with no row classifies
    # all-false at runtime (not read-only) and has no declared row, so the
    # no-silent-default gate above would list it - the exact hole the frozensets left.
    key = "ledger.brand_new_wipe_verb"
    classification = classify_command(key, mutability=OperatorMutability.LOCAL_STATE_MUTATING)
    assert not classification.read_only
    assert not classification.destructive  # all-false at runtime...
    assert declared_risk(key) is None  # ...but undeclared, so the gate refuses it


def test_no_exposed_command_declares_an_aeat_live_write() -> None:
    """No verb on the operator surface declares a live AEAT write, and each was assessed.

    Live submission is forbidden outright, so ``live_write`` is False for every
    command and must stay that way. That universality is precisely what makes
    the value worthless as a check on its own: an invariant holding for
    everything cannot distinguish a verb someone judged safe from a verb nobody
    has looked at.

    The two halves are therefore asserted TOGETHER, deliberately.
    ``risk_declared`` supplies the precondition - the judgment axes were
    assessed rather than defaulted - and only under it does ``not live_write``
    carry a claim. Its assessment half overlaps
    ``test_every_mutating_family_command_carries_a_declared_row`` (the
    conditions are equivalent under today's family-derived ``read_only``); that
    is the point, not redundancy to remove. Split apart, the precondition could
    be deleted and nothing would show that the remaining half had quietly
    stopped meaning anything.

    Scope is the MCP-exposable surface, which is every executable leaf. The
    three registered keys outside it - ``root.app``, ``root.config`` and
    ``root.status`` - are root-level result schemas rather than verbs that act,
    and report no assessment for that reason.
    """
    classifications = [command_classification(key) for key in sorted(_exposed_keys())]
    assert _unassessed(classifications) == [], (
        f"exposed commands with no risk assessment: {_unassessed(classifications)}"
    )
    assert _live_writers(classifications) == [], (
        f"commands declaring an AEAT live write: {_live_writers(classifications)}"
    )


def test_the_gate_predicates_discriminate_on_a_planted_command() -> None:
    # Anti-tautology for the gate above. Both halves are empty across the real
    # surface, so their teeth cannot be shown from live data - an assertion that
    # has never seen a positive is indistinguishable from one that cannot fail.
    # Drive the same two predicates with classifications that DO exhibit each
    # condition and confirm both are flagged.
    submitting = CommandClassification(
        command_key="live.planted_submit_verb",
        read_only=False,
        destructive=False,
        idempotent=False,
        handoff=False,
        live_write=True,
        open_world=True,
        risk_declared=True,
    )
    unjudged = submitting.model_copy(
        update={"command_key": "ledger.planted_unassessed_verb", "live_write": False, "risk_declared": False},
    )
    assert _live_writers([submitting]) == ["live.planted_submit_verb"]
    assert _unassessed([unjudged]) == ["ledger.planted_unassessed_verb"]
    # ...and neither predicate fires on a command that is assessed and submits nothing.
    clean = submitting.model_copy(update={"command_key": "overview.clean", "live_write": False})
    assert _live_writers([clean]) == []
    assert _unassessed([clean]) == []
