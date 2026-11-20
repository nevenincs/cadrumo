"""Declared desktop shell keys for the Operations page.

The page words nothing of what the operation history serves: a run's definition is shown as the
untranslated protocol token it is, and its page is named by the navigation register's own label. These
keys are only its chrome: the title, the notice that the page lists and never runs anything, its
states, and one word per closed value of the lifecycle, the effect and the receipt outcome. Those
members are read from the enums the history read serves, so the window cannot word a list of its own
that drifts from what is served, and a value the product adds is declared with it until its word is
authored.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from cadrumo.core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition


def _members(enum: type[StrEnum]) -> tuple[str, ...]:
    """The served value of each member, in declaration order."""
    return tuple(member.value for member in enum)


DESKTOP_OPERATIONS_FAMILIES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "desktop.operations.lifecycle.": _members(OperationLifecycle),
        "desktop.operations.effect.": _members(OperationEffect),
        "desktop.operations.outcome.": _members(OperationTerminalCondition),
    }
)

_CHROME_KEYS: Final[frozenset[str]] = frozenset(
    {
        "desktop.operations.cancellation_requested",
        "desktop.operations.count",
        "desktop.operations.empty",
        "desktop.operations.error_code",
        "desktop.operations.failed",
        "desktop.operations.field_effect",
        "desktop.operations.field_outcome",
        "desktop.operations.loading",
        "desktop.operations.loading_more",
        "desktop.operations.more_failed",
        "desktop.operations.orientation",
        "desktop.operations.phase",
        "desktop.operations.read_again",
        "desktop.operations.refresh",
        "desktop.operations.refusal_ref",
        "desktop.operations.result_not_stored",
        "desktop.operations.result_stored",
        "desktop.operations.settled",
        "desktop.operations.shown_on",
        "desktop.operations.show_more",
        "desktop.operations.signed_out",
        "desktop.operations.started",
        "desktop.operations.title",
        "desktop.operations.unreadable",
        "desktop.operations.unverifiable",
        "desktop.operations.updated",
    }
)

DESKTOP_OPERATIONS_KEYS: Final[frozenset[str]] = _CHROME_KEYS | frozenset(
    f"{prefix}{member}" for prefix, members in DESKTOP_OPERATIONS_FAMILIES.items() for member in members
)
