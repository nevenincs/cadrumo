"""A Ledger workspace refuses an action wired to the wrong command.

``require_canonical_ledger_actions`` exists because the route factory and the
controller each validated injected actions separately and had already drifted:
the factory refused a ``review_action`` that did not resolve to
``ledger.review`` and the controller did not check it at all, so every caller
constructing the controller directly skipped that refusal. Consolidating the
guard closed the gap — and nothing in the tree exercised the guard itself.

What a miswired action costs is not a crash. The workspace would offer a
button labelled for one operation and dispatch another: a "classify" affordance
running the link command, against a taxpayer's ledger. The refusal is what
makes that unrepresentable, so it is worth holding.

An absent optional action is a supported state — the area is simply not
offered — and is deliberately distinct from a supplied one that is miswired.
"""

from __future__ import annotations

import pytest

from .....application.operator_actions.models import ActionReference
from ..action_guards import _REQUIRED_TARGETS, require_canonical_ledger_actions

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REVIEW = ActionReference(action_id="operator.ledger.review")
_CLASSIFY = ActionReference(action_id="operator.ledger.classify")
_EVIDENCE = ActionReference(action_id="operator.ledger.evidence.review.list")
_LINK = ActionReference(action_id="operator.ledger.link")

#: Each optional slot paired with an action belonging to a DIFFERENT slot.
_MISWIRINGS = [
    pytest.param("classify_action", _LINK, id="classify-wired-to-link"),
    pytest.param("evidence_action", _CLASSIFY, id="evidence-wired-to-classify"),
    pytest.param("link_action", _EVIDENCE, id="link-wired-to-evidence"),
]


def test_the_fully_wired_workspace_is_accepted() -> None:
    """The supported path, so every refusal below is not vacuous."""
    require_canonical_ledger_actions(
        review_action=_REVIEW,
        classify_action=_CLASSIFY,
        evidence_action=_EVIDENCE,
        link_action=_LINK,
    )


def test_a_review_only_workspace_is_accepted() -> None:
    """Absent optional actions mean those areas are not offered, not misconfigured."""
    require_canonical_ledger_actions(review_action=_REVIEW)


def test_a_review_action_wired_to_another_command_is_refused() -> None:
    """The mandatory slot, and the exact drift that motivated the guard."""
    with pytest.raises(ValueError, match="review"):
        require_canonical_ledger_actions(review_action=_CLASSIFY)


@pytest.mark.parametrize(("slot", "wrong_action"), _MISWIRINGS)
def test_each_optional_slot_refuses_another_slots_action(slot: str, wrong_action: ActionReference) -> None:
    """Every optional slot is checked separately.

    One case would pass while the other two accepted anything, which is the
    shape the split guard had before it was consolidated.
    """
    with pytest.raises(ValueError):
        require_canonical_ledger_actions(review_action=_REVIEW, **{slot: wrong_action})


def test_every_declared_slot_is_actually_enforced() -> None:
    """No slot may sit in the table without the guard reading it.

    The table drives the loop, so an entry added but never supplied to the
    function would look enforced and refuse nothing.
    """
    enforced = {attribute for attribute, _command_key, _refusal in _REQUIRED_TARGETS}

    assert enforced == {"review_action", "classify_action", "evidence_action", "link_action"}


def test_each_slot_names_a_distinct_command() -> None:
    """Two slots sharing a command key would let one accept the other's action."""
    command_keys = [command_key for _attribute, command_key, _refusal in _REQUIRED_TARGETS]

    assert len(command_keys) == len(set(command_keys))
