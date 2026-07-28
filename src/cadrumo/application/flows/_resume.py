"""Resume: rebuild a live ``FlowState`` from persisted canonical answers.

The facts are the checkpoint, so resume is a *projection*, not a
rehydration: every persisted answer re-validates against the *current*
flow definition, visibility and instance counts recompute from scratch,
and the cursor lands on the first unanswered visible page. A persisted
answer that no longer validates, or whose page no longer exists in the
definition, lands as **stale** on the review surface — a checkpoint is
never blindly trusted and never blocks resume with an opaque failure.

Because nothing derived is stored, a definition change between save and
resume needs no stored fingerprint to detect: the re-validation walk
*is* the detection, and its output is reviewable state rather than an
error.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...core.flows import FlowMode
from ._definition import FlowDefinition, FlowRepeatingGroup
from ._engine import FlowState, VisiblePage, start_flow, visible_sequence
from ._validators import run_answer_validation


def resume_flow(
    definition: FlowDefinition,
    persisted: Mapping[str, str],
    *,
    mode: FlowMode,
) -> FlowState:
    """Project persisted canonical answers into a fresh, re-validated state.

    The walk mirrors an operator re-entering every persisted answer in
    sequence: answers commit only through the current definition's
    validation, gates re-evaluate as answers land (so a persisted gate
    answer reveals its dependents for *their* persisted answers), and
    anything left over — an answer for a page the definition no longer
    declares, or one the current validators reject — is carried as
    stale, visible on review, never dropped and never silently kept as
    a committed answer.
    """
    state = start_flow(definition, mode=mode)
    remaining = dict(persisted)

    # Iterate to a fixed point: committing a gate answer can reveal
    # pages whose persisted answers are still in ``remaining``.
    while True:
        progressed = False
        for entry in visible_sequence(definition, state):
            if entry.key in state.answers or entry.key not in remaining:
                continue
            state = _commit_persisted_answer(definition, state, entry, raw=remaining.pop(entry.key))
            progressed = True
        if not progressed:
            break

    # Answers whose page the current definition never exposed: stale.
    orphaned = frozenset(key for key, value in remaining.items() if value)
    if orphaned:
        state = state.model_copy(update={"stale": frozenset(state.stale | orphaned)})

    cursor = _first_unanswered(definition, state)
    return state.model_copy(update={"cursor": cursor, "visited": (cursor,) if cursor else ()})


def _commit_persisted_answer(
    definition: FlowDefinition,
    state: FlowState,
    entry: VisiblePage,
    *,
    raw: str,
) -> FlowState:
    """Re-enter one persisted answer through the current definition's validation.

    An answer the current validators reject is carried as stale rather than
    committed: it stays visible on review instead of being dropped, and it
    never lands as a committed answer the operator did not re-confirm.
    """
    canonical, verdicts = run_answer_validation(entry.page, raw)
    if any(not verdict.ok for verdict in verdicts):
        return state.model_copy(update={"stale": frozenset(state.stale | {entry.key})})
    new_answers = dict(state.answers)
    new_answers[entry.key] = canonical
    counts = dict(state.instance_counts)
    _seed_counts(definition, entry.key, canonical, counts)
    return state.model_copy(update={"answers": new_answers, "instance_counts": counts})


def _seed_counts(
    definition: FlowDefinition,
    page_key: str,
    canonical: str,
    counts: dict[str, int],
) -> None:
    for section in definition.sections:
        for item in section.items:
            if isinstance(item, FlowRepeatingGroup) and item.count_from == page_key:
                try:
                    declared = int(canonical) if canonical else 0
                except ValueError:
                    declared = 0
                counts[item.id] = max(0, min(declared, item.max_instances))


def _first_unanswered(definition: FlowDefinition, state: FlowState) -> str | None:
    for entry in visible_sequence(definition, state):
        if entry.key not in state.answers:
            return entry.key
    return None


__all__ = ["resume_flow"]
