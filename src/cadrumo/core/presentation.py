"""Layer-neutral immutable presentation contracts shared by entrypoints."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class FormFieldKind(StrEnum):
    """Editing mode for one immutable form field."""

    TEXT = "text"
    MULTI_CHOICE = "multi_choice"
    SINGLE_CHOICE = "single_choice"


@dataclass(frozen=True, slots=True)
class FormChoice:
    """One selectable value and its operator-facing label."""

    value: str
    label: str


@dataclass(frozen=True, slots=True)
class FormField:
    """Immutable field descriptor supplied by a form presenter."""

    key: str
    label: str
    value: str = ""
    kind: FormFieldKind = FormFieldKind.TEXT
    choices: tuple[FormChoice, ...] = ()
    hint: str = ""
    validate: Callable[[str], str | None] | None = None
    secret: bool = False


@dataclass(frozen=True, slots=True)
class NoticePresentation:
    """Already-resolved notice facts safe for inert presentation widgets."""

    severity: str
    message: str
    action_target: str | None = None


__all__ = [
    "FormChoice",
    "FormField",
    "FormFieldKind",
    "NoticePresentation",
]
