"""Typed casilla occurrences, resolved coordinates, audit findings, and edit plans."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CasillaOccurrence:
    """One casilla in one materialised edition, with its published key chain."""

    modelo: str
    revision: str
    casilla: str
    number: str
    continuidad_id: str | None
    inherited_from: str | None
    label_chain: tuple[str, ...]
    carries_help: bool = True
    """Casillas carry label and help; a construct carries only its title, read as its label."""

    def chain(self, field_name: str) -> tuple[str, ...]:
        """Return the ordered chain for ``label`` or ``help``."""
        if field_name == "label":
            return self.label_chain
        if not self.carries_help:
            return ()
        return tuple(f"{key.removesuffix('.label')}.help" for key in self.label_chain)


type Values = dict[str, dict[str, str | None]]
"""``values[locale][key]`` for every casilla leaf present in a catalogue."""


type Coordinate = tuple[int, str, str]
"""``(occurrence index, field, locale)``."""


@dataclass(slots=True)
class CatalogueFindings:
    """Measured state of the casilla surface; every tuple is sorted."""

    orphan_keys: dict[str, tuple[str, ...]] = field(default_factory=dict)
    undeclared_revision_keys: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, keys under a revision id the registry does not declare: a rename to move, never to delete."""
    null_leaves: dict[str, tuple[str, ...]] = field(default_factory=dict)
    redundant_values: dict[str, tuple[str, ...]] = field(default_factory=dict)
    lineage_lifts: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, empty lineage keys that could carry text now stored per edition."""
    derived_help: dict[str, tuple[str, ...]] = field(default_factory=dict)
    placeholders: dict[str, tuple[str, ...]] = field(default_factory=dict)
    glossary_artifacts: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, translations a word-by-word glossary pass produced."""
    truncated_text: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, values cut short and closed with an ellipsis."""
    irregular_whitespace: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, values with repeated spaces or surrounding whitespace copied from a source."""
    dropped_source_content: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, translations that lost a box reference, amount or comparison the Spanish states."""
    shared_translations: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, one translation rendering more than one Spanish wording of a modelo."""
    segment_drift: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, composed segments whose one Spanish wording is rendered more than one way."""
    shared_segments: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, one rendering standing for more than one Spanish segment."""
    unresolved_spanish: tuple[str, ...] = ()
    untranslated: dict[str, int] = field(default_factory=dict)
    translation_drift: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, lineages whose one Spanish text is translated more than one way."""
    stranded_translations: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, rows rendering Spanish although their lineage translates that text."""
    stale_translations: dict[str, tuple[str, ...]] = field(default_factory=dict)
    """Per locale, lineages rendering two different Spanish texts with one translation."""

    def counts(self) -> dict[str, object]:
        """Summarise every finding family as counts."""

        def total(family: Mapping[str, tuple[str, ...]]) -> dict[str, int]:
            return {locale: len(keys) for locale, keys in sorted(family.items()) if keys}

        return {
            "orphan_keys": total(self.orphan_keys),
            "undeclared_revision_keys": total(self.undeclared_revision_keys),
            "null_leaves": total(self.null_leaves),
            "redundant_values": total(self.redundant_values),
            "lineage_lifts": total(self.lineage_lifts),
            "derived_help": total(self.derived_help),
            "placeholders": total(self.placeholders),
            "glossary_artifacts": total(self.glossary_artifacts),
            "truncated_text": total(self.truncated_text),
            "irregular_whitespace": total(self.irregular_whitespace),
            "dropped_source_content": total(self.dropped_source_content),
            "shared_translations": total(self.shared_translations),
            "segment_drift": total(self.segment_drift),
            "shared_segments": total(self.shared_segments),
            "unresolved_spanish": len(self.unresolved_spanish),
            "untranslated": dict(sorted(self.untranslated.items())),
            "translation_drift": total(self.translation_drift),
            "stranded_translations": total(self.stranded_translations),
            "stale_translations": total(self.stale_translations),
        }

    @property
    def structurally_pure(self) -> bool:
        """Whether every stored leaf is a canonical, non-derived, readable value."""
        return not any(
            (
                any(self.orphan_keys.values()),
                any(self.undeclared_revision_keys.values()),
                any(self.null_leaves.values()),
                any(self.redundant_values.values()),
                any(self.lineage_lifts.values()),
                any(self.derived_help.values()),
            )
        )

    @property
    def pure(self) -> bool:
        """Whether the surface carries no delete target and no Spanish gap."""
        return not any(
            (
                any(self.orphan_keys.values()),
                any(self.undeclared_revision_keys.values()),
                any(self.null_leaves.values()),
                any(self.redundant_values.values()),
                any(self.lineage_lifts.values()),
                any(self.derived_help.values()),
                any(self.placeholders.values()),
                any(self.glossary_artifacts.values()),
                any(self.truncated_text.values()),
                any(self.irregular_whitespace.values()),
                any(self.dropped_source_content.values()),
                any(self.shared_translations.values()),
                any(self.segment_drift.values()),
                any(self.shared_segments.values()),
                any(self.translation_drift.values()),
                any(self.stranded_translations.values()),
                any(self.stale_translations.values()),
                self.unresolved_spanish,
            )
        )


@dataclass(slots=True)
class CollapsePlan:
    """Catalogue edits that keep every resolved text except the named repairs."""

    removals: dict[str, dict[str, str]] = field(default_factory=lambda: defaultdict(dict))
    """Per locale, each key to delete and why."""
    settings: dict[str, dict[str, tuple[str, str]]] = field(default_factory=lambda: defaultdict(dict))
    """Per locale, each key to write with its value and why."""
    _displaced: dict[str, dict[str, str]] = field(default_factory=lambda: defaultdict(dict))

    @property
    def reasons(self) -> Counter[str]:
        """Count the scheduled edits by kind and reason."""
        counts: Counter[str] = Counter()
        for removals in self.removals.values():
            counts.update(f"remove:{reason}" for reason in removals.values())
        for settings in self.settings.values():
            counts.update(f"set:{reason}" for _value, reason in settings.values())
        return counts

    def remove(self, locale: str, key: str, reason: str) -> None:
        """Schedule deletion of one leaf; dropping a value this plan assigned cancels the assignment."""
        if key in self.settings[locale]:
            del self.settings[locale][key]
            displaced = self._displaced[locale].pop(key, None)
            if displaced is not None:
                self.removals[locale][key] = displaced
            return
        self.removals[locale].setdefault(key, reason)

    def assign(self, locale: str, key: str, value: str, reason: str) -> None:
        """Schedule one leaf value, remembering any removal it replaces."""
        displaced = self.removals[locale].pop(key, None)
        if displaced is not None:
            self._displaced[locale][key] = displaced
        self.settings[locale][key] = (value, reason)


class CollapseVerificationError(RuntimeError):
    """A collapse could not be proven lossless or installed as proven."""


@dataclass(slots=True)
class CollapseResult:
    """A collapse plan with the evidence it was computed against."""

    plan: CollapsePlan
    working: Values
    baseline: Mapping[Coordinate, str | None]
