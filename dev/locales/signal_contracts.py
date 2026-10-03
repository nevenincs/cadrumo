"""Contracts for the authoritative locale audit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypedDict


class DictionaryLike(Protocol):
    """A dictionary that can accept or reject one authored prose word."""

    def lookup(self, word: str) -> bool:
        """Return whether the dictionary contains the word."""
        ...


class TranslationBacklogItem(TypedDict, total=False):
    """One required translation cell and its repair or review action."""

    domain: str
    key: str
    locale: str
    state: str
    reason: str | None
    next_action: str
    unknown_words: list[str]


class TranslationCells(TypedDict):
    """Non-overlapping totals for required locale cells and their readiness states."""

    required: int
    defined: int
    ready: int
    missing: int
    needs_value: int
    needs_repair: int
    needs_review: int


class TranslationMatrix(TypedDict):
    """Required cell totals, actionable backlog, and blocking translation findings."""

    backlog: list[TranslationBacklogItem]
    findings: list[dict[str, object]]
    cells: TranslationCells


class LocaleSignalDetails(TypedDict):
    """Source keys, dynamic-family evidence, and the full actionable findings."""

    backlog: list[TranslationBacklogItem]
    findings: list[dict[str, object]]
    required_keys: list[str]
    dynamic_key_families: dict[str, object]


class LocaleSignal(TypedDict):
    """A locale audit outcome with its headline, inventory summary, and evidence."""

    outcome: str
    headline: str
    summary: dict[str, object]
    details: LocaleSignalDetails


class SpellingInventory(TypedDict):
    """Dictionary coverage, structural exclusions, and unknown authored prose counts."""

    spellchecked_cells: int
    spelling_cells: int
    spelling_cells_by_locale: dict[str, int]
    spelling_prose_cells: int
    spelling_prose_cells_by_locale: dict[str, int]
    spelling_structural_only_cells: int
    spelling_structural_only_cells_by_locale: dict[str, int]
    spelling_unknown_cells: int
    spelling_unknown_words: int
    spelling_tool_failures: int
    excluded_structural_tokens: int
    excluded_structural_tokens_by_surface_locale: dict[str, int]


class ExcludedStructuralInventory(TypedDict):
    """Transport-syntax exclusions grouped by surface and locale."""

    excluded_structural_tokens: int
    excluded_structural_tokens_by_surface_locale: dict[str, int]


@dataclass
class DocumentationEchoDictionaries:
    """Load exact-echo dictionaries once, retaining an unavailable result."""

    loaded: dict[str, object] | None = None
    unavailable: bool = False
