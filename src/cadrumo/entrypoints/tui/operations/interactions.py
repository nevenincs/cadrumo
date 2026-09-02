"""Safe REVIEW rendering and separately authorized APPLY/REJECT controls.

Only the registered safe REVIEW projection and the response-control
authorization are ever rendered. Public ``INPUT`` and ``CHOICE`` interaction
kinds are treated as unsupported: no later contract has enrolled a TUI
renderer for them yet, so this module never attempts to draw one.

These are runtime render states rather than wire contracts (a bound response
control cannot cross a process boundary), so they are plain immutable
dataclasses rather than pydantic models; the wire-safe fields they carry
(``interaction``, ``projection``) are already-validated public contract
models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from ....application.operations.frontend_contracts import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
    OperationResponseControlSuccessV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionResultV1,
    OperationReviewProjectionSuccessV1,
    OperationUnsupportedInteractionV1,
)
from .controller import OperationBoundResponseControl, OperationController


@dataclass(frozen=True, slots=True)
class OperationModalNoInteractionV1:
    """The modal has no interaction to render."""

    disposition: Literal["none"] = "none"


@dataclass(frozen=True, slots=True)
class OperationModalReviewInteractionV1[ReviewProjectionT: BaseModel]:
    """A registered safe REVIEW projection with its already-bound controls.

    ``control`` is bound exactly once per pending REVIEW (the underlying
    response capability is single-use), so this same instance answers both
    the availability check and the eventual APPLY or REJECT.
    """

    interaction: OperationReviewAvailableInteractionV1
    projection: ReviewProjectionT
    control: OperationBoundResponseControl
    apply_enabled: bool
    reject_enabled: bool
    disposition: Literal["review_available"] = field(default="review_available", init=False)

    def __post_init__(self) -> None:
        """Confirm the rendered interaction reproduces its own safe reference."""
        if self.interaction.revision != self.interaction.review_reference.revision:
            raise ValueError("modal REVIEW interaction does not match its own safe reference")


@dataclass(frozen=True, slots=True)
class OperationModalReviewUnavailableV1:
    """A pending REVIEW whose safe projection could not currently be resolved."""

    interaction: OperationReviewAvailableInteractionV1
    disposition: Literal["review_unavailable"] = field(default="review_unavailable", init=False)


@dataclass(frozen=True, slots=True)
class OperationModalUnsupportedInteractionV1:
    """A pending interaction this modal cannot yet render (INPUT or CHOICE)."""

    interaction: OperationUnsupportedInteractionV1
    disposition: Literal["unsupported"] = field(default="unsupported", init=False)


type OperationModalInteractionStateV1[ReviewProjectionT: BaseModel] = (
    OperationModalNoInteractionV1
    | OperationModalReviewInteractionV1[ReviewProjectionT]
    | OperationModalReviewUnavailableV1
    | OperationModalUnsupportedInteractionV1
)


async def resolve_modal_interaction_state[ReviewProjectionT: BaseModel](
    controller: OperationController,
    projection: OperationPublicProjectionV1,
    *,
    current: OperationModalInteractionStateV1[ReviewProjectionT] | None = None,
) -> OperationModalInteractionStateV1[ReviewProjectionT]:
    """Resolve the exact modal interaction state for the current projection.

    ``current`` is the state a repeating caller already holds. When the same
    REVIEW is still pending at the same revision it is returned unchanged,
    because the response capability behind it is single-use: binding a second
    control for an interaction already bound consumes the authority and every
    later availability check refuses, which switches the operator's APPLY and
    REJECT controls off while the operation is still waiting for exactly that
    answer. A caller that polls therefore MUST pass what it holds.
    """
    pending = projection.pending_interaction
    if isinstance(pending, OperationNoPendingInteractionV1):
        return OperationModalNoInteractionV1()
    if isinstance(pending, OperationUnsupportedInteractionV1):
        return OperationModalUnsupportedInteractionV1(interaction=pending)
    assert isinstance(pending, OperationReviewAvailableInteractionV1)
    if (
        isinstance(current, OperationModalReviewInteractionV1)
        and current.interaction.interaction_id == pending.interaction_id
        and current.interaction.revision == pending.revision
    ):
        return current
    resolved: OperationReviewProjectionResultV1[ReviewProjectionT] = await controller.resolve_review(
        pending.review_reference
    )
    if not isinstance(resolved, OperationReviewProjectionSuccessV1):
        return OperationModalReviewUnavailableV1(interaction=pending)
    control = await controller.response_control(
        interaction_id=pending.interaction_id,
        revision=pending.revision,
    )
    availability = await control.inspect()
    permitted: frozenset[Literal["apply", "reject"]] = (
        availability.permitted_intents if isinstance(availability, OperationResponseControlSuccessV1) else frozenset()
    )
    return OperationModalReviewInteractionV1[ReviewProjectionT](
        interaction=pending,
        projection=resolved.projection,
        control=control,
        apply_enabled="apply" in permitted,
        reject_enabled="reject" in permitted,
    )


__all__ = [
    "OperationModalInteractionStateV1",
    "OperationModalNoInteractionV1",
    "OperationModalReviewInteractionV1",
    "OperationModalReviewUnavailableV1",
    "OperationModalUnsupportedInteractionV1",
    "resolve_modal_interaction_state",
]
