"""Reusable, state-free Textual widgets for Cadrumo surfaces."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, override

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.geometry import Size
from textual.widgets import Button, Collapsible, DataTable, Static

from ....core.presentation import NoticePresentation


class ContentScroll(VerticalScroll, can_focus=False):
    """The scroll host every Cadrumo surface puts its content column in."""


class ContentDataTable[CellType](DataTable[CellType]):
    """A table that expands to its rows inside the shared scroll host."""

    def watch_virtual_size(self, size: Size) -> None:
        """Keep the layout box equal to the current rows and header."""
        self.styles.height = max(1, size.height)


_NOTICE_GLYPH: Final[dict[str, str]] = {
    "info": "ⓘ",
    "warning": "⚠",
}


class NoticeBand(Vertical, can_focus=False):
    """Render already-resolved notices without adding interaction state."""

    def __init__(self, notices: Sequence[NoticePresentation], *, id: str | None = None) -> None:
        """Store the immutable notice projection for rendering."""
        super().__init__(id=id)
        self._notices = tuple(notices)

    @override
    def compose(self) -> ComposeResult:
        for index, notice in enumerate(self._notices):
            glyph = _NOTICE_GLYPH.get(notice.severity, "•")
            yield Static(
                f"{glyph} {notice.message}",
                classes=f"cadrumo-notice cadrumo-notice-{notice.severity}",
                id=f"notice-{index}",
                markup=False,
            )
            action_target = notice.action_target
            if action_target is not None:
                yield Static(
                    action_target,
                    classes="cadrumo-notice-action",
                    id=f"notice-{index}-action",
                    markup=False,
                )


class StageNavigationStrip(Horizontal, can_focus=False):
    """Render-only linear stage strip: which stage is current, done, or ahead.

    Route and focus are presentation state owned by the host screen; this
    widget only shows where the operator currently is in a fixed, ordered
    sequence of stages. It carries
    no navigation of its own and mounts no button -- a host wanting a
    clickable strip composes its own controls around this render.
    """

    def __init__(self, stages: Sequence[str], *, current_index: int, id: str | None = None) -> None:
        """Store the ordered, already-localized stage labels and current position."""
        if not stages:
            raise ValueError("a stage navigation strip requires at least one stage")
        if not 0 <= current_index < len(stages):
            raise ValueError("current_index must name a declared stage")
        super().__init__(id=id)
        self._stages = tuple(stages)
        self._current_index = current_index

    @property
    def current_index(self) -> int:
        """Return the stage currently marked as active."""
        return self._current_index

    def set_current_index(self, current_index: int) -> None:
        """Advance the strip's own position and recompose in place.

        A host tracking its own cursor (a wizard, a guided flow) updates
        the SAME mounted strip instance rather than tearing it down and
        remounting a fresh one each step -- `refresh(recompose=True)` is
        the sync, in-place primitive for exactly that.
        """
        if not 0 <= current_index < len(self._stages):
            raise ValueError("current_index must name a declared stage")
        self._current_index = current_index
        self.refresh(recompose=True)

    @override
    def compose(self) -> ComposeResult:
        for index, label in enumerate(self._stages):
            if index < self._current_index:
                glyph, state = "✓", "done"
            elif index == self._current_index:
                glyph, state = "▸", "current"
            else:
                glyph, state = "·", "upcoming"
            yield Static(
                f"{glyph} {label}",
                classes=f"cadrumo-stage cadrumo-stage-{state}",
                id=f"stage-{index}",
                markup=False,
            )


class DisclosureGroup(Collapsible):
    """A titled, collapsible task section -- the shared `Show optional` primitive.

    A thin, named extension of Textual's own `Collapsible` rather than a
    parallel reimplementation: every Cadrumo surface that needs a collapsed
    optional-detail or completed-group section (the `Required` stage's task
    sections, `Show optional`, `Show not applicable`) composes this one
    widget instead of each host reaching for `Collapsible` under its own
    title and defaults.
    """

    def __init__(self, *children, title: str, collapsed: bool = True, id: str | None = None) -> None:
        """Store the group's already-localized title and initial disclosure state."""
        super().__init__(*children, title=title, collapsed=collapsed, id=id)


class RequirementStatus(StrEnum):
    """The non-colour-safe requirement states a badge can render.

    Named for the reader, not the palette: two operators comparing a
    screenshot in greyscale and one in colour must reach the same
    conclusion, so every state carries its own glyph and label rather than
    only a colour class.
    """

    REQUIRED_MISSING = "required_missing"
    REQUIRED_PRESENT = "required_present"
    NEEDS_APPLICABILITY = "needs_applicability"
    OPTIONAL = "optional"
    NOT_APPLICABLE = "not_applicable"


_REQUIREMENT_GLYPH: Final[dict[RequirementStatus, str]] = {
    RequirementStatus.REQUIRED_MISSING: "✖",
    RequirementStatus.REQUIRED_PRESENT: "✓",
    RequirementStatus.NEEDS_APPLICABILITY: "?",
    RequirementStatus.OPTIONAL: "○",
    RequirementStatus.NOT_APPLICABLE: "—",
}


class RequirementBadge(Static, can_focus=False):
    """One field's requirement state, rendered by glyph and label together.

    Never colour alone: `_REQUIREMENT_GLYPH` gives every
    :class:`RequirementStatus` its own distinguishing mark, so a non-colour
    terminal or a colour-blind operator reads the same state a sighted
    colour-terminal operator does.
    """

    def __init__(self, label: str, status: RequirementStatus, *, id: str | None = None) -> None:
        """Store the already-localized field label and its settled status."""
        glyph = _REQUIREMENT_GLYPH[status]
        super().__init__(
            f"{glyph} {label}",
            classes=f"cadrumo-requirement cadrumo-requirement-{status.value}",
            id=id,
            markup=False,
        )
        self._status = status

    @property
    def status(self) -> RequirementStatus:
        """Return the settled requirement status this badge renders."""
        return self._status


@dataclass(frozen=True, slots=True)
class CredentialRequirement:
    """One resolved credential-requirement fact, present or absent as a unit.

    A label without a status, or a status without a label, is not a weaker
    fact -- it is not a fact at all, and the card cannot render half of one.
    Carrying the pair in one record makes that state unexpressible instead
    of relying on callers to honour it: the previous shape was two
    independent optional fields whose dependency lived only in prose, so a
    half-populated descriptor silently rendered NO badge and raised nothing,
    dropping a resolved requirement on an operator-facing surface with no
    signal at all.
    """

    label: str
    status: RequirementStatus


@dataclass(frozen=True, slots=True)
class SourceActionDescriptor:
    """One `Get data` source: what it is, and the action that starts it.

    ``credential_requirement`` is an optional pre-resolved requirement fact;
    this widget classifies nothing itself. When present, the card renders it
    through the shared :class:`RequirementBadge`, the same primitive
    `Required` uses, rather than inventing a second requirement
    presentation for sources.
    """

    title: str
    description: str
    action_label: str
    credential_requirement: CredentialRequirement | None = None


class SourceActionCard(Vertical):
    """A focusable card for one disclosed data source and its start action.

    Renders only; starting the described operation is the host screen's
    concern; the card is not what dispatches. Composes a real `Button` so
    the card is reachable and actionable by keyboard alone, per this
    Wave's focus-order proof.
    """

    DEFAULT_CSS = """
    SourceActionCard {
        height: auto;
    }
    """
    """`Vertical`'s own default is `height: 1fr` (an expanding container),
    which is fine standing alone but stretches a card to fill whatever
    space several 1fr siblings divide -- overriding to `auto` sizes the
    card to its own three children instead."""

    def __init__(self, descriptor: SourceActionDescriptor, *, id: str | None = None) -> None:
        """Store the already-localized source description."""
        super().__init__(id=id, classes="cadrumo-source-card")
        self._descriptor = descriptor

    @override
    def compose(self) -> ComposeResult:
        yield Static(self._descriptor.title, classes="cadrumo-source-card-title", markup=False)
        yield Static(self._descriptor.description, classes="cadrumo-source-card-description", markup=False)
        requirement = self._descriptor.credential_requirement
        if requirement is not None:
            yield RequirementBadge(requirement.label, requirement.status, id="source-credential-requirement")
        yield Button(self._descriptor.action_label, id="btn-source-action", classes="cadrumo-source-card-action")


__all__ = [
    "ContentDataTable",
    "ContentScroll",
    "CredentialRequirement",
    "DisclosureGroup",
    "NoticeBand",
    "RequirementBadge",
    "RequirementStatus",
    "SourceActionCard",
    "SourceActionDescriptor",
    "StageNavigationStrip",
]
