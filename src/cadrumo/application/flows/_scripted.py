"""The scripted intent driver: canonical answers in flow order, no frontend.

Non-interactive callers (``--quiet`` / accept-defaults CLI modes, the
headless test harness) drive the engine with a pre-supplied ordered
queue of canonical tokens. Each visible page consumes the leftmost
token; the driver walks the engine's own visible sequence, so branching
and validation are identical to every interactive frontend by
construction.

Drift detection carries the one-shot wizard's discipline forward: an
exhausted queue raises the underflow error naming the starved page, and
finishing with unconsumed tokens raises the overflow error carrying
counts only — canonical tokens can contain secrets and never ride in
diagnostics.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping

from ...core.flows import FlowMode
from ._definition import FlowDefinition
from ._engine import FlowState, answer, jump_to, next_page, start_flow, visible_sequence
from ._errors import FlowAnswerError
from ._review import ReviewProjection, assert_submit_eligible


def run_scripted_flow(
    definition: FlowDefinition,
    tokens: Iterable[str],
    *,
    mode: FlowMode,
    defaults: Mapping[str, str] | None = None,
) -> tuple[FlowState, ReviewProjection]:
    """Walk the whole flow against an ordered canonical-token queue.

    The driver visits the visible sequence from the top; visibility is
    re-evaluated after every commit, so a token that reveals later pages
    (a gate, a repeating-group count) extends the walk exactly as an
    interactive run would. ``defaults`` supplies per-page fallbacks
    consumed when the queue would otherwise starve an *optional* page —
    the accept-defaults mode; a required page always consumes a real
    token.

    Returns the final state plus the passing review projection: a
    scripted run that cannot submit is a caller/runtime drift and raises
    rather than returning a half-answered state.

    Raises:
        FlowAnswerError: On queue underflow (naming the starved page and
            counts only) or on unconsumed tokens at flow end.
    """
    queue: deque[str] = deque(tokens)
    defaults_map = dict(defaults or {})
    state = start_flow(definition, mode=mode)
    consumed = 0

    while True:
        target = _first_unanswered(definition, state)
        if target is None:
            break
        if queue:
            raw = queue.popleft()
            consumed += 1
        elif not _page_required(definition, state, target) and target in defaults_map:
            raw = defaults_map[target]
        elif not _page_required(definition, state, target):
            raw = ""
        else:
            raise FlowAnswerError(
                translated_message="application.flows.errors.scripted_queue_underflow",
                context={"page_key": target, "consumed_count": consumed},
            )
        state = jump_to(definition, state, target)
        state = answer(definition, state, target, raw)
        if target in state.verdicts:
            raise FlowAnswerError(
                translated_message="application.flows.errors.scripted_answer_rejected",
                context={
                    "page_key": target,
                    "message_keys": tuple(
                        verdict.message_key for verdict in state.verdicts[target] if verdict.message_key
                    ),
                },
            )
        state = next_page(definition, state)

    if queue:
        raise FlowAnswerError(
            translated_message="application.flows.errors.scripted_queue_overflow",
            context={"remaining_count": len(queue), "consumed_count": consumed},
        )
    projection = assert_submit_eligible(definition, state)
    return state, projection


def _first_unanswered(definition: FlowDefinition, state: FlowState) -> str | None:
    for entry in visible_sequence(definition, state):
        if entry.key not in state.answers:
            return entry.key
    return None


def _page_required(definition: FlowDefinition, state: FlowState, page_key: str) -> bool:
    for entry in visible_sequence(definition, state):
        if entry.key == page_key:
            return entry.page.required
    return False


__all__ = ["run_scripted_flow"]
