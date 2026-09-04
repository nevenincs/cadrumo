"""One home for the Ledger workspace's injected-action checks.

The route factory and the workspace controller each validated the injected
actions against the same canonical command keys. Writing the guard twice let
the two copies drift, and they had: the factory rejected a ``review_action``
that does not resolve to ``ledger.review``, while the controller did not check
it at all. Every caller constructing the controller directly -- the devtools
workbench fixture and the flow tests -- therefore skipped that refusal.

Consolidating the guard closes that gap by construction: there is one place a
check can be added, so a new one cannot land on a single path.
"""

from __future__ import annotations

from typing import Final

from ....application.operator_actions.catalogue import lookup_action
from ....application.operator_actions.models import ActionReference

#: Injected action attribute -> the command key it must resolve to, and the
#: refusal wording the surface already used for it.
_REQUIRED_TARGETS: Final[tuple[tuple[str, str, str], ...]] = (
    ("review_action", "ledger.review", "injected Ledger review action does not resolve to the canonical review query"),
    (
        "classify_action",
        "ledger.classify",
        "injected Ledger classification action does not resolve to the canonical command",
    ),
    (
        "evidence_action",
        "ledger.evidence.review.list",
        "injected Ledger evidence action does not resolve to the canonical review query",
    ),
    ("link_action", "ledger.link", "injected Ledger link action does not resolve to the canonical command"),
)


def require_canonical_ledger_actions(
    *,
    review_action: ActionReference,
    classify_action: ActionReference | None = None,
    evidence_action: ActionReference | None = None,
    link_action: ActionReference | None = None,
) -> None:
    """Refuse an injected action that does not resolve to its canonical command.

    ``review_action`` is mandatory; the rest are checked only when supplied,
    because an absent action means the area is not offered rather than
    misconfigured.

    Args:
        review_action: The Ledger review query action.
        classify_action: The classification action, when the area is offered.
        evidence_action: The evidence review action, when the area is offered.
        link_action: The link action, when the area is offered.

    Raises:
        ValueError: If a supplied action resolves to a different command.
    """
    supplied = {
        "review_action": review_action,
        "classify_action": classify_action,
        "evidence_action": evidence_action,
        "link_action": link_action,
    }
    for attribute, command_key, refusal in _REQUIRED_TARGETS:
        action = supplied[attribute]
        if action is None:
            continue
        if lookup_action(action.action_id).target_command_key != command_key:
            raise ValueError(refusal)


__all__ = ["require_canonical_ledger_actions"]
