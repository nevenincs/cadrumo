"""The pure flow engine: immutable state plus typed transitions.

The engine is the single flow authority. It owns every flow semantic —
visibility, navigation, answer commitment, staleness, deferral, reset,
restart — as pure functions over an immutable :class:`FlowState`.
Frontends (full-screen TUI, line mode, scripted driver, non-interactive
flags) project the state and dispatch intents; they contain zero flow
logic, so every interaction surface is consistent by construction.

Two invariants are load-bearing:

* **Staleness, never silent deletion.** Changing an answer whose value
  gates later pages marks the dependent answers ``STALE`` (they surface
  on the review projection and block submission) rather than deleting
  them. Shrinking a repeating group likewise marks the orphaned
  instance answers stale.
* **Deferral never resolves silently.** A ``COMPARE_SELECT`` page
  answered with the reserved defer token stays ``DEFERRED`` until the
  operator revisits it; submission refuses while any deferral remains.

Visibility is recomputed from the canonical answer map on every
transition; nothing is cached across transitions.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.flows import (
    DEFER_TOKEN,
    REPEATING_INSTANCE_SEPARATOR,
    FlowMode,
    PageStatus,
)
from .definition import (
    FlowCondition,
    FlowDefinition,
    FlowPage,
    FlowRepeatingGroup,
    FlowSection,
    iter_flow_conditions,
)
from .errors import FlowAnswerError, FlowNavigationError
from .validators import ValidationVerdict, resolve_cross_field_validator, run_answer_validation

SECTION_VERDICT_PREFIX = "section:"
"""Key prefix under which section-exit verdicts land in ``FlowState.verdicts``."""


class VisiblePage(BaseModel):
    """One entry in the currently-visible page sequence.

    ``key`` is the canonical answer-map key: the bare page id for a
    top-level page, ``<group>#<index>.<page>`` for a repeating-group
    instance page.
    """

    model_config = STRICT_FROZEN_CONFIG

    key: str
    page: FlowPage
    section_id: str
    group_id: str | None = None
    instance_index: int | None = None


class FlowState(BaseModel):
    """Immutable engine state; every transition returns a new instance.

    ``answers`` holds canonical tokens keyed by visible-page key.
    ``verdicts`` holds the failing validation verdicts currently
    blocking a page (keyed by page key) or a section exit (keyed
    ``section:<id>``). ``stale`` holds page keys whose committed answer
    outlived a gating change. ``instance_counts`` holds the live
    instance count per repeating group, seeded from the group's
    ``count_from`` answer and adjustable from review.

    Immutability convention: ``frozen=True`` blocks field reassignment;
    the dict-typed fields are additionally never mutated in place —
    every transition builds fresh containers and returns a
    ``model_copy``. Callers must follow the same convention.
    """

    model_config = STRICT_FROZEN_CONFIG

    flow_id: str = Field(min_length=1)
    mode: FlowMode
    answers: dict[str, str] = Field(default_factory=dict)
    verdicts: dict[str, tuple[ValidationVerdict, ...]] = Field(default_factory=dict)
    stale: frozenset[str] = frozenset()
    instance_counts: dict[str, int] = Field(default_factory=dict)
    cursor: str | None = None
    visited: tuple[str, ...] = ()


def start_flow(definition: FlowDefinition, *, mode: FlowMode) -> FlowState:
    """Return the initial state with the cursor on the first visible page."""
    state = FlowState(flow_id=definition.id, mode=mode)
    sequence = visible_sequence(definition, state)
    cursor = sequence[0].key if sequence else None
    return state.model_copy(update={"cursor": cursor, "visited": (cursor,) if cursor else ()})


def visible_sequence(definition: FlowDefinition, state: FlowState) -> tuple[VisiblePage, ...]:
    """Compute the currently-visible page sequence from the answer map.

    Repeating groups expand to their live instance count (the
    ``count_from`` answer unless review adjusted it). A gated page is
    visible when any of its clauses holds against the answers; clause
    targets resolve instance-locally first so a group page may gate on
    a sibling within the same instance.
    """
    result: list[VisiblePage] = []
    for section in definition.sections:
        for item in section.items:
            if isinstance(item, FlowPage):
                if _page_visible(item, state.answers, instance_prefix=None):
                    result.append(VisiblePage(key=item.id, page=item, section_id=section.id))
                continue
            result.extend(_visible_group_pages(item, state, section_id=section.id))
    return tuple(result)


def _visible_group_pages(
    group: FlowRepeatingGroup,
    state: FlowState,
    *,
    section_id: str,
) -> list[VisiblePage]:
    """Expand one repeating group into its live instances' visible pages.

    Each instance carries its own answer prefix, so a page inside instance
    ``n`` gates against instance ``n``'s siblings rather than the group's
    first instance.
    """
    pages: list[VisiblePage] = []
    for index in range(_instance_count(group, state)):
        prefix = f"{group.id}{REPEATING_INSTANCE_SEPARATOR}{index}"
        pages.extend(
            VisiblePage(
                key=f"{prefix}.{page.id}",
                page=page,
                section_id=section_id,
                group_id=group.id,
                instance_index=index,
            )
            for page in group.pages
            if _page_visible(page, state.answers, instance_prefix=prefix)
        )
    return pages


def answer(definition: FlowDefinition, state: FlowState, page_key: str, raw: str) -> FlowState:
    """Commit ``raw`` to the page at ``page_key`` and return the new state.

    A failing validation leaves the previous answer in place and records
    the verdicts under ``page_key`` so the frontend renders them in
    place. A passing commit stores the canonical token, clears the
    page's verdicts, marks dependents of a *changed* gating answer
    stale, and refreshes the owning repeating group's instance count
    when the page is a declared count source.
    """
    visible = _visible_by_key(definition, state)
    entry = visible.get(page_key)
    if entry is None:
        raise FlowAnswerError(
            translated_message="application.flows.errors.answer_target_not_visible",
            context={"page_key": page_key, "flow_id": definition.id},
        )
    canonical, verdicts = run_answer_validation(entry.page, raw)
    if any(not verdict.ok for verdict in verdicts):
        new_verdicts = dict(state.verdicts)
        new_verdicts[page_key] = tuple(verdict for verdict in verdicts if not verdict.ok)
        return state.model_copy(update={"verdicts": new_verdicts})

    previous = state.answers.get(page_key)
    new_answers = dict(state.answers)
    new_answers[page_key] = canonical
    new_verdicts = {key: value for key, value in state.verdicts.items() if key != page_key}
    new_stale = set(state.stale) - {page_key}
    if previous is not None and previous != canonical:
        new_stale |= _answered_dependents(definition, state, page_key, new_answers)

    new_counts = dict(state.instance_counts)
    count_stale = _refresh_instance_counts(definition, page_key, canonical, new_answers, new_counts)
    new_stale |= count_stale

    return state.model_copy(
        update={
            "answers": new_answers,
            "verdicts": new_verdicts,
            "stale": frozenset(new_stale),
            "instance_counts": new_counts,
        },
    )


def next_page(definition: FlowDefinition, state: FlowState) -> FlowState:
    """Advance the cursor to the next visible page.

    Crossing out of a section runs that section's exit validators; any
    failure records the verdicts under ``section:<id>`` and leaves the
    cursor in place, blocking forward navigation with a rendered,
    typed result. Moving backwards is never gated.
    """
    sequence = visible_sequence(definition, state)
    position = _cursor_position(sequence, state.cursor)
    if position is None or position + 1 >= len(sequence):
        return state
    current = sequence[position]
    target = sequence[position + 1]
    if target.section_id != current.section_id:
        failures = _run_section_exit(definition, current.section_id, state.answers)
        if failures:
            new_verdicts = dict(state.verdicts)
            new_verdicts[f"{SECTION_VERDICT_PREFIX}{current.section_id}"] = failures
            return state.model_copy(update={"verdicts": new_verdicts})
    cleared = {
        key: value for key, value in state.verdicts.items() if key != f"{SECTION_VERDICT_PREFIX}{current.section_id}"
    }
    return state.model_copy(
        update={
            "cursor": target.key,
            "visited": (*state.visited, target.key),
            "verdicts": cleared,
        },
    )


def back_page(definition: FlowDefinition, state: FlowState) -> FlowState:
    """Move the cursor to the previous visible page; never gated."""
    sequence = visible_sequence(definition, state)
    position = _cursor_position(sequence, state.cursor)
    if position is None or position == 0:
        return state
    target = sequence[position - 1]
    return state.model_copy(update={"cursor": target.key, "visited": (*state.visited, target.key)})


def jump_to(definition: FlowDefinition, state: FlowState, page_key: str) -> FlowState:
    """Set the cursor onto any currently-visible page (the review jump)."""
    visible = _visible_by_key(definition, state)
    if page_key not in visible:
        raise FlowNavigationError(
            translated_message="application.flows.errors.jump_target_not_visible",
            context={"page_key": page_key, "flow_id": definition.id},
        )
    return state.model_copy(update={"cursor": page_key, "visited": (*state.visited, page_key)})


def reset_page(definition: FlowDefinition, state: FlowState, page_key: str) -> FlowState:
    """Clear one page's answer back to undeclared and mark its dependents stale.

    The committed answer is removed (the page's descriptor default is a
    render-time prefill, not a committed answer), the page's verdicts
    and staleness clear, and — exactly as with a changed gating answer —
    every answered dependent of the cleared page is marked stale rather
    than deleted.
    """
    visible = _visible_by_key(definition, state)
    if page_key not in visible and page_key not in state.answers:
        raise FlowNavigationError(
            translated_message="application.flows.errors.reset_target_unknown",
            context={"page_key": page_key, "flow_id": definition.id},
        )
    had_answer = page_key in state.answers
    new_answers = {key: value for key, value in state.answers.items() if key != page_key}
    new_verdicts = {key: value for key, value in state.verdicts.items() if key != page_key}
    new_stale = set(state.stale) - {page_key}
    if had_answer:
        new_stale |= _answered_dependents(definition, state, page_key, new_answers)
    return state.model_copy(
        update={
            "answers": new_answers,
            "verdicts": new_verdicts,
            "stale": frozenset(new_stale),
        },
    )


def restart_flow(definition: FlowDefinition, state: FlowState) -> FlowState:
    """Wipe the whole state and return to the first page (confirmed upstream).

    The confirmation is a frontend responsibility; the engine transition
    itself is unconditional.
    """
    return start_flow(definition, mode=state.mode)


def page_status(state: FlowState, page_key: str) -> PageStatus:
    """Return the review status of one page key."""
    if page_key in state.verdicts:
        return PageStatus.INVALID
    if page_key in state.stale:
        return PageStatus.STALE
    committed = state.answers.get(page_key)
    if committed is None or committed == "":
        return PageStatus.UNANSWERED
    if committed == DEFER_TOKEN:
        return PageStatus.DEFERRED
    return PageStatus.ANSWERED


def set_instance_count(definition: FlowDefinition, state: FlowState, group_id: str, count: int) -> FlowState:
    """Adjust a repeating group's live instance count from the review surface.

    Growing exposes fresh unanswered instances; shrinking marks the
    orphaned instances' committed answers stale — they stay listed on
    review until explicitly reset, never silently dropped.
    """
    group = _group_by_id(definition, group_id)
    if group is None:
        raise FlowNavigationError(
            translated_message="application.flows.errors.unknown_repeating_group",
            context={"group_id": group_id, "flow_id": definition.id},
        )
    bounded = max(0, min(count, group.max_instances))
    new_counts = dict(state.instance_counts)
    new_counts[group_id] = bounded
    orphaned = _orphaned_instance_keys(group, bounded, state.answers)
    return state.model_copy(
        update={
            "instance_counts": new_counts,
            "stale": frozenset(set(state.stale) | orphaned),
        },
    )


def _page_visible(
    page: FlowPage,
    answers: Mapping[str, str],
    *,
    instance_prefix: str | None,
) -> bool:
    if page.visible_when is None:
        return True
    return any(
        _clause_satisfied(clause, answers, instance_prefix=instance_prefix)
        for clause in iter_flow_conditions(page.visible_when)
    )


def _clause_satisfied(
    clause: FlowCondition,
    answers: Mapping[str, str],
    *,
    instance_prefix: str | None,
) -> bool:
    parent = None
    if instance_prefix is not None:
        parent = answers.get(f"{instance_prefix}.{clause.page_id}")
    if parent is None:
        parent = answers.get(clause.page_id)
    if parent is None:
        return False
    if clause.contains is not None:
        tokens = {token.strip() for token in parent.split(",") if token.strip()}
        return clause.contains in tokens
    return parent == clause.equals


def _instance_count(group: FlowRepeatingGroup, state: FlowState) -> int:
    explicit = state.instance_counts.get(group.id)
    if explicit is not None:
        return min(explicit, group.max_instances)
    raw = state.answers.get(group.count_from, "")
    try:
        declared = int(raw) if raw else 0
    except ValueError:
        declared = 0
    return max(0, min(declared, group.max_instances))


def _visible_by_key(definition: FlowDefinition, state: FlowState) -> dict[str, VisiblePage]:
    return {entry.key: entry for entry in visible_sequence(definition, state)}


def _cursor_position(sequence: tuple[VisiblePage, ...], cursor: str | None) -> int | None:
    if cursor is None:
        return None
    for index, entry in enumerate(sequence):
        if entry.key == cursor:
            return index
    return None


def _answered_dependents(
    definition: FlowDefinition,
    state: FlowState,
    changed_key: str,
    answers: Mapping[str, str],
) -> set[str]:
    """Return the answered page keys gated (directly) on the changed page.

    The changed key resolves both bare (top-level pages gate on bare
    ids) and instance-scoped (a group page gating on a sibling): for an
    instance-scoped change ``g#2.x``, dependents inside instance
    ``g#2`` gating on ``x`` are matched.
    """
    bare_id, instance_prefix = _split_instance_key(changed_key)
    dependents: set[str] = set()
    for entry in visible_sequence(definition, state):
        for clause in iter_flow_conditions(entry.page.visible_when):
            if clause.page_id != bare_id:
                continue
            if (
                instance_prefix is not None
                and entry.group_id is not None
                and not entry.key.startswith(f"{instance_prefix}.")
            ):
                continue
            committed = answers.get(entry.key)
            if committed:
                dependents.add(entry.key)
    return dependents


def _split_instance_key(key: str) -> tuple[str, str | None]:
    if REPEATING_INSTANCE_SEPARATOR not in key:
        return key, None
    prefix, _, page_id = key.rpartition(".")
    return page_id, prefix or None


def _refresh_instance_counts(
    definition: FlowDefinition,
    page_key: str,
    canonical: str,
    answers: Mapping[str, str],
    counts: dict[str, int],
) -> set[str]:
    """Seed group counts from a committed count-source answer.

    Returns the orphaned instance keys of any group that shrank.
    """
    orphaned: set[str] = set()
    for section in definition.sections:
        for item in section.items:
            if not isinstance(item, FlowRepeatingGroup) or item.count_from != page_key:
                continue
            try:
                declared = int(canonical) if canonical else 0
            except ValueError:
                declared = 0
            bounded = max(0, min(declared, item.max_instances))
            counts[item.id] = bounded
            orphaned |= _orphaned_instance_keys(item, bounded, answers)
    return orphaned


def _orphaned_instance_keys(
    group: FlowRepeatingGroup,
    live_count: int,
    answers: Mapping[str, str],
) -> set[str]:
    prefix_root = f"{group.id}{REPEATING_INSTANCE_SEPARATOR}"
    orphaned: set[str] = set()
    for key, value in answers.items():
        if not key.startswith(prefix_root) or not value:
            continue
        instance_part = key[len(prefix_root) :].split(".", 1)[0]
        if instance_part.isdigit() and int(instance_part) >= live_count:
            orphaned.add(key)
    return orphaned


def _run_section_exit(
    definition: FlowDefinition,
    section_id: str,
    answers: Mapping[str, str],
) -> tuple[ValidationVerdict, ...]:
    section = _section_by_id(definition, section_id)
    if section is None:
        return ()
    failures: list[ValidationVerdict] = []
    for validator_id in section.exit_validator_ids:
        for verdict in resolve_cross_field_validator(validator_id)(answers):
            if not verdict.ok:
                failures.append(verdict)
    return tuple(failures)


def _section_by_id(definition: FlowDefinition, section_id: str) -> FlowSection | None:
    for section in definition.sections:
        if section.id == section_id:
            return section
    return None


def _group_by_id(definition: FlowDefinition, group_id: str) -> FlowRepeatingGroup | None:
    for section in definition.sections:
        for item in section.items:
            if isinstance(item, FlowRepeatingGroup) and item.id == group_id:
                return item
    return None


__all__ = [
    "SECTION_VERDICT_PREFIX",
    "FlowState",
    "VisiblePage",
    "answer",
    "back_page",
    "jump_to",
    "next_page",
    "page_status",
    "reset_page",
    "restart_flow",
    "set_instance_count",
    "start_flow",
    "visible_sequence",
]
