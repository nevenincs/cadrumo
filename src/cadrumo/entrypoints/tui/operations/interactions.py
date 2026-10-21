"""Pending interaction rendering and separately authorized APPLY/REJECT controls.

A pending REVIEW renders its registered safe projection beside the response
controls that answer it. A pending ``INPUT`` or ``CHOICE`` renders what the
public observation says about it: its kind, its presentation code and its
expiry. The public response surface answers a REVIEW only, on every frontend,
so no answer control is drawn for the other two kinds.

These are runtime render states rather than wire contracts (a bound response
control cannot cross a process boundary), so they are plain immutable
dataclasses rather than pydantic models; the wire-safe fields they carry
(``interaction``, ``projection``) are already-validated public contract
models.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal, assert_never

from pydantic import BaseModel

from ....application.operations.frontend_contracts import OperationReviewProjectionResultV1
from ....application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
    OperationReviewAvailableInteractionV1,
    OperationUnsupportedInteractionV1,
)
from ....application.operations.frontend_requests import (
    OperationResponseControlSuccessV1,
    OperationReviewProjectionSuccessV1,
)
from ....application.operations.interactions import OperationResponseIntentValue
from ....core.i18n.render import tr
from ....core.operations import OperationInteractionKind
from .controller_port import OperationControllerPort, OperationResponseControlPort


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
    control: OperationResponseControlPort
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
    """A pending INPUT or CHOICE, which the public response surface cannot answer."""

    interaction: OperationUnsupportedInteractionV1
    disposition: Literal["unsupported"] = field(default="unsupported", init=False)


type OperationModalInteractionStateV1[ReviewProjectionT: BaseModel] = (
    OperationModalNoInteractionV1
    | OperationModalReviewInteractionV1[ReviewProjectionT]
    | OperationModalReviewUnavailableV1
    | OperationModalUnsupportedInteractionV1
)


async def resolve_modal_interaction_state[ReviewProjectionT: BaseModel](
    controller: OperationControllerPort,
    projection: OperationPublicProjectionV1,
    projection_type: type[ReviewProjectionT],
    *,
    current: OperationModalInteractionStateV1[ReviewProjectionT] | None = None,
) -> OperationModalInteractionStateV1[ReviewProjectionT]:
    """Resolve the exact modal interaction state for the current projection.

    ``current`` retains the original control binding for the same pending
    REVIEW. Reuse that binding and inspect its current permissions on each
    poll; polling must never consume or reconstruct the response bearer.
    Callers pass their current state so that only a new interaction binds a
    new control.
    """
    # Dispatch over the closed pending-interaction union rather than re-testing
    # the member the two arms above already excluded: `assert_never` makes a new
    # member break the build instead of reaching a narrowing that cannot hold.
    match projection.pending_interaction:
        case OperationNoPendingInteractionV1():
            return OperationModalNoInteractionV1()
        case OperationUnsupportedInteractionV1() as unsupported:
            return OperationModalUnsupportedInteractionV1(interaction=unsupported)
        case OperationReviewAvailableInteractionV1() as pending:
            pass
        case _:
            assert_never(projection.pending_interaction)
    if (
        isinstance(current, OperationModalReviewInteractionV1)
        and current.interaction.interaction_id == pending.interaction_id
        and current.interaction.revision == pending.revision
    ):
        # Keep the original bearer binding, but never cache its permission.
        # Inspection is non-consuming and rechecks expiry/current authority.
        availability = await current.control.inspect()
        permitted = (
            availability.permitted_intents
            if isinstance(availability, OperationResponseControlSuccessV1)
            else frozenset[OperationResponseIntentValue]()
        )
        return replace(current, apply_enabled="apply" in permitted, reject_enabled="reject" in permitted)
    resolved: OperationReviewProjectionResultV1[ReviewProjectionT] = await controller.resolve_review(
        pending.review_reference,
        projection_type,
    )
    if not isinstance(resolved, OperationReviewProjectionSuccessV1):
        return OperationModalReviewUnavailableV1(interaction=pending)
    control = await controller.response_control(
        interaction_id=pending.interaction_id,
        revision=pending.revision,
    )
    availability = await control.inspect()
    permitted: frozenset[OperationResponseIntentValue] = (
        availability.permitted_intents
        if isinstance(availability, OperationResponseControlSuccessV1)
        else frozenset[OperationResponseIntentValue]()
    )
    return OperationModalReviewInteractionV1[ReviewProjectionT](
        interaction=pending,
        projection=resolved.projection,
        control=control,
        apply_enabled="apply" in permitted,
        reject_enabled="reject" in permitted,
    )


def unanswerable_interaction_text(interaction: OperationUnsupportedInteractionV1) -> str:
    """Word a pending INPUT or CHOICE from the public facts its observation carries."""
    kind = (
        tr("tui.operations.interaction.kind.input")
        if interaction.interaction_kind is OperationInteractionKind.INPUT
        else tr("tui.operations.interaction.kind.choice")
    )
    lines = [
        kind,
        f"{tr('tui.operations.interaction.presentation')}: {interaction.presentation_code}",
    ]
    if interaction.expires_at is not None:
        lines.append(f"{tr('tui.operations.interaction.expires')}: {interaction.expires_at.isoformat()}")
    lines.append(tr("tui.operations.interaction.no_answer"))
    return "\n".join(lines)


__all__ = [
    "OperationModalInteractionStateV1",
    "OperationModalNoInteractionV1",
    "OperationModalReviewInteractionV1",
    "OperationModalReviewUnavailableV1",
    "OperationModalUnsupportedInteractionV1",
    "resolve_modal_interaction_state",
    "unanswerable_interaction_text",
]
