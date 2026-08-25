from __future__ import annotations

from collections import deque
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from ....core.flows import FlowMode
from ...flows.definition import FlowDefinition
from ...flows.engine import FlowState, start_flow, visible_sequence
from ...flows.review import ReviewProjection
from ...flows.scripted import run_scripted_flow
from ..descendant_group import DESCENDANTS_COUNT_PAGE_ID


class EmptyAnswersBase(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


def scripted_run_over_setup_definition(
    definition: FlowDefinition,
    tokens: Sequence[str],
    *,
    mode: FlowMode,
) -> tuple[FlowState, ReviewProjection]:
    """Run a scripted walk over the live setup definition, defaulting the count page.

    The shared individual-declaration token fixtures predate the descendant
    repeating group, so they carry no token for the ``descendientes-count``
    page the live setup definition inserts mid-walk. An injected test runner
    that feeds those raw tokens straight to
    :func:`~cadrumo.application.flows.scripted.run_scripted_flow` would misfeed the next
    token onto the INTEGER count page. This realigns the queue exactly as the
    production ``_project_scripted_answers`` projection does for a canonical
    map that omits the count key: the count page falls to its descriptor
    default (``0`` -> the group stays hidden), and every other visible page
    consumes its fixture token in walk order. A definition without the count
    page is walked unchanged. Returns the same pair
    :func:`~cadrumo.application.flows.scripted.run_scripted_flow` yields.
    """
    queue = deque(tokens)
    aligned: list[str] = []
    answers: dict[str, str] = {}
    base = start_flow(definition, mode=mode)
    while True:
        target = next(
            (
                entry
                for entry in visible_sequence(definition, base.model_copy(update={"answers": dict(answers)}))
                if entry.key not in answers
            ),
            None,
        )
        if target is None:
            break
        if target.page.id == DESCENDANTS_COUNT_PAGE_ID:
            raw = target.page.default or "0"
        elif queue:
            raw = queue.popleft()
        else:
            raw = target.page.default or ""
        aligned.append(raw)
        answers[target.key] = raw
    return run_scripted_flow(definition, aligned, mode=mode)
