"""Where one way out of a refusal leads, and the seam a host resolves ways out through.

Kept apart from the router so that a screen showing a refusal never imports
the destinations the router reads, several of which show refusals themselves.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from ....application.operator_actions.projection import ActionArgumentSnapshot
from ....core.identifier_grammar import NamespacedId
from ..navigation import TuiNavigationTargetV1
from .served import RefusalWayV1

type RefusalIntentKindV1 = Literal["form", "follow"]


@dataclass(frozen=True, slots=True)
class RefusalIntentV1:
    """Where one way out leads, and the arguments the verdict served for it.

    ``form`` opens the destination's form for ``missing_argument_names``;
    ``follow`` opens the destination with ``argument_bindings`` holding every
    argument the action takes.
    """

    kind: RefusalIntentKindV1
    action_id: NamespacedId
    target_command_key: str
    target: TuiNavigationTargetV1
    argument_bindings: tuple[ActionArgumentSnapshot, ...]
    missing_argument_names: tuple[str, ...]

    def navigation_target(self) -> TuiNavigationTargetV1:
        """Return the destination target carrying the served arguments as its request prefill."""
        target = self.target
        return TuiNavigationTargetV1(
            destination=target.destination,
            focus=target.focus,
            action_candidate_id=target.action_candidate_id,
            request_prefill=self.argument_bindings,
        )


type RefusalRouterV1 = Callable[[RefusalWayV1], RefusalIntentV1 | None]
"""Resolve one way out to its TUI destination, or ``None`` when no admitted destination hosts it."""


def no_route(_way: RefusalWayV1) -> RefusalIntentV1 | None:
    """Route nothing: the router of a host that admits no destination."""
    return None


__all__ = ["RefusalIntentKindV1", "RefusalIntentV1", "RefusalRouterV1", "no_route"]
