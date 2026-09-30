"""The workbench's closed visual vocabulary: one glyph, one colour role and words per state.

Every field shows exactly one origin (where its value stands) and at most one
attention mark (a staged change, or a verification blocker). A state is always
a glyph from the pinned terminal font together with its words, and colour only
reinforces it, so a greyscale screenshot and a colour one read the same.

The tables are total over the application's closed enums and every glyph is
distinct, which the module refuses at import rather than leaving two states to
look alike on screen.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from .....application.modelo.work_form_models import ModeloFormEditability, ModeloFormOrigin


class ColourRole(StrEnum):
    """The colour a state reinforces its glyph and words with."""

    MUTED = "muted"
    VALUE = "value"
    ENTERED = "entered"
    WARNING = "warning"
    ERROR = "error"
    STAGED = "staged"


class Attention(StrEnum):
    """What draws the eye to a field beyond its origin."""

    STAGED = "staged"
    BLOCKED = "blocked"


ORIGIN_GLYPHS: Final[Mapping[ModeloFormOrigin, str]] = MappingProxyType(
    {
        ModeloFormOrigin.NOT_APPLICABLE: "-",
        ModeloFormOrigin.OVERRIDES_SOURCE: "≠",
        ModeloFormOrigin.CALCULATED: "=",
        ModeloFormOrigin.NOT_CALCULATED_YET: "◌",
        ModeloFormOrigin.CALCULATION_FAILED: "×",
        ModeloFormOrigin.INFORMATIONAL: "◇",
        ModeloFormOrigin.NEEDS_INPUT: "!",
        ModeloFormOrigin.IMPORTED: "↓",
        ModeloFormOrigin.NOT_IMPORTED_YET: "⇣",
        ModeloFormOrigin.OPTIONAL_EMPTY: "○",
        ModeloFormOrigin.CLEARED: "□",
        ModeloFormOrigin.DEFAULT_TO_CONFIRM: "◐",
        ModeloFormOrigin.ENTERED: "●",
    }
)
"""One mark per origin, every one present in the pinned font."""

ORIGIN_ROLES: Final[Mapping[ModeloFormOrigin, ColourRole]] = MappingProxyType(
    {
        ModeloFormOrigin.NOT_APPLICABLE: ColourRole.MUTED,
        ModeloFormOrigin.OVERRIDES_SOURCE: ColourRole.WARNING,
        ModeloFormOrigin.CALCULATED: ColourRole.VALUE,
        ModeloFormOrigin.NOT_CALCULATED_YET: ColourRole.MUTED,
        ModeloFormOrigin.CALCULATION_FAILED: ColourRole.ERROR,
        ModeloFormOrigin.INFORMATIONAL: ColourRole.MUTED,
        ModeloFormOrigin.NEEDS_INPUT: ColourRole.ERROR,
        ModeloFormOrigin.IMPORTED: ColourRole.VALUE,
        ModeloFormOrigin.NOT_IMPORTED_YET: ColourRole.MUTED,
        ModeloFormOrigin.OPTIONAL_EMPTY: ColourRole.MUTED,
        ModeloFormOrigin.CLEARED: ColourRole.MUTED,
        ModeloFormOrigin.DEFAULT_TO_CONFIRM: ColourRole.WARNING,
        ModeloFormOrigin.ENTERED: ColourRole.ENTERED,
    }
)

ATTENTION_GLYPHS: Final[Mapping[Attention, str]] = MappingProxyType({Attention.STAGED: "Δ", Attention.BLOCKED: "▲"})
ATTENTION_ROLES: Final[Mapping[Attention, ColourRole]] = MappingProxyType(
    {Attention.STAGED: ColourRole.STAGED, Attention.BLOCKED: ColourRole.ERROR}
)

#: Origins that ask the filer to act before the declaration is ready.
NEEDS_ATTENTION: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {
        ModeloFormOrigin.NEEDS_INPUT,
        ModeloFormOrigin.DEFAULT_TO_CONFIRM,
        ModeloFormOrigin.CALCULATION_FAILED,
        ModeloFormOrigin.NOT_IMPORTED_YET,
    }
)

#: Editabilities under which the filer may stage a typed value on the field itself.
TYPED_EDITABILITIES: Final[frozenset[ModeloFormEditability]] = frozenset(
    {
        ModeloFormEditability.EDITABLE_VALUE,
        ModeloFormEditability.EDITABLE_OVERRIDE,
        ModeloFormEditability.OVERRIDABLE_SOURCE,
    }
)


def origin_words_key(origin: ModeloFormOrigin) -> str:
    """The catalogue key naming one origin in a few words."""
    return f"tui.modelo.workbench.origin.{origin.value}"


def editability_words_key(editability: ModeloFormEditability) -> str:
    """The catalogue key explaining what may be done about a field."""
    return f"tui.modelo.workbench.editability.{editability.value}"


def attention_words_key(attention: Attention) -> str:
    """The catalogue key naming one attention mark."""
    return f"tui.modelo.workbench.attention.{attention.value}"


def _require_closed_and_distinct() -> None:
    """Refuse a vocabulary that misses a state or lets two states share a mark."""
    if set(ORIGIN_GLYPHS) != set(ModeloFormOrigin) or set(ORIGIN_ROLES) != set(ModeloFormOrigin):
        raise ValueError("every origin needs exactly one glyph and one colour role")
    if set(ATTENTION_GLYPHS) != set(Attention) or set(ATTENTION_ROLES) != set(Attention):
        raise ValueError("every attention mark needs exactly one glyph and one colour role")
    glyphs = [*ORIGIN_GLYPHS.values(), *ATTENTION_GLYPHS.values()]
    if len(set(glyphs)) != len(glyphs):
        raise ValueError("two workbench states share a glyph")


_require_closed_and_distinct()


__all__ = [
    "ATTENTION_GLYPHS",
    "ATTENTION_ROLES",
    "NEEDS_ATTENTION",
    "ORIGIN_GLYPHS",
    "ORIGIN_ROLES",
    "TYPED_EDITABILITIES",
    "Attention",
    "ColourRole",
    "attention_words_key",
    "editability_words_key",
    "origin_words_key",
]
