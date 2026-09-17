"""Delta-keyed maintenance of the Modelo casilla locale surface.

The registry stores Modelo editions as deltas: an edition states only the rows
that changed, and inherited rows resolve their text through the key chain the
loader enrols on every casilla -- the row's own occurrence key, the key of the
edition that stated it, then its lineage (``continuidad_id``) key. The casilla
locale catalogue follows the same discipline:

- a value is stored once, at the least specific key of the chains that read it
  that still yields the same resolved text in every locale;
- a key no chain reads, a null leaf, and a value whose removal changes no
  resolution are all delete targets;
- help text generated from the label carries nothing of its own and is removed;
- a translation is authored only for Spanish text that has none; Spanish text
  already translated elsewhere in the same lineage is carried, not retyped.

Everything here reads the published authority and the runtime resolution rule
(:func:`~cadrumo.domain.calculations.registry.modelo_localization.modelo_localization_source`)
through the ``cadrumo`` package only, so the check measures exactly what
operators are served. Writes go through :class:`~dev.locales.manager.LocaleManager`.
"""

from __future__ import annotations

import re
import shutil
import time
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import yaml

from cadrumo.core.atomic_write import atomic_write_text
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.modelo_localization import (
    encode_modelo_locale_segment,
    modelo_localization_source,
)

from ._casilla_keys import is_delta_keyed_leaf, is_lineage_key
from ._paths import LOCALES_DIR, PENDING_CASILLA_INSTALL_DIR
from .manager import LocaleManager, _flatten_raw_locale_leaves, discover_locale_codes

__all__ = [
    "CasillaOccurrence",
    "CatalogueFindings",
    "CollapsePlan",
    "CollapseResult",
    "CollapseVerificationError",
    "ModeloCasillaCatalogue",
    "casilla_occurrences",
    "edition_text_gaps",
    "load_casilla_values",
    "resume_install",
]

SOURCE_LOCALE: Final = "es"
_FIELDS: Final = ("label", "help")
#: Help renderings generated from the label; they state nothing the label does not.
_DERIVED_HELP: Final = (
    re.compile(r"^Indique o revise «.*» para completar esta autoliquidación\.$", re.S),
    re.compile(r"^Consulte la información correspondiente a la casilla: .*$", re.S),
    re.compile(r"^Información fiscal sobre .*de la casilla .*$", re.S),
    re.compile(r"^Información de la casilla\b.*$", re.S),
    re.compile(r"^Dato del modelo \S+, ejercicio \S+.*$", re.S),
)
_REVISION_SCOPED: Final = re.compile(r"^modelo\.schema\.(?P<modelo>[^.]+)\.revision\.(?P<revision>[^.]+)\.")
#: Scaffold renderings standing in for a label that was never authored. Help text may
#: legitimately open with its box number, so only labels are judged.
_PLACEHOLDER: Final = re.compile(
    r"^(?:Casilla|Casella|Box)\s+\S+:\s|^Casella . informaci"
    r"|^(?:Casilla|Casella|Box)\b[^—]{0,40}—|^[^—]{0,40}\brovat\s+—"
    r"|^(?:Informació fiscal de la casella|Tax information for this field|Az űrlap adóadata)\.?$",
    re.IGNORECASE,
)

#: A value that a length limit cut mid-text and closed with an ellipsis.
_TRUNCATED: Final = re.compile(r"\w(?:\.\.\.|…)\s*$")
#: Per locale, the marks a word-by-word glossary pass leaves: Hungarian suffix
#: alternations standing alone, and Spanish function words left untranslated.
_GLOSSARY_ARTIFACT: Final[dict[str, re.Pattern[str]]] = {
    "hu": re.compile(
        r"-(?:ban/-ben|nak/-nek|ra/-re|ról/-ről|ba/-be|val/-vel|tól/-től|hoz/-hez|ból/-ből|ként)\b"
        r"|\ba\(z\) [a-záéíóöőúüű]+ -|\b(?:Aplicado|esta)\b"
    ),
    "en": re.compile(r"\b(?:Aplicado|esta|otros|otras|excepto|según|cuyo|cuya)\b"),
    "ca": re.compile(r"\b(?:Aplicado|esta|otros|otras|excepto|según|cuyo|cuya)\b"),
}


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


def casilla_occurrences() -> tuple[CasillaOccurrence, ...]:
    """Enumerate every casilla and construct occurrence of the published generation.

    A construct is carried as an occurrence whose label chain is its title chain,
    so both delta-keyed surfaces share one resolution, collapse and audit.
    """
    found: list[CasillaOccurrence] = []
    with bundled_indexed_authority().operation() as operation:
        for modelo_id in operation.modelo_ids():
            for metadata in operation.modelo_directory(modelo_id).revisions:
                revision = operation.revision(modelo_id, str(metadata.id))
                found.extend(
                    CasillaOccurrence(
                        modelo=str(modelo_id),
                        revision=str(metadata.id),
                        casilla=str(casilla.id),
                        number=str(casilla.number),
                        continuidad_id=None if casilla.continuidad_id is None else str(casilla.continuidad_id),
                        inherited_from=None if casilla.inherited_from is None else str(casilla.inherited_from),
                        label_chain=tuple(casilla.localization_keys),
                    )
                    for casilla in revision.casillas
                )
                found.extend(
                    CasillaOccurrence(
                        modelo=str(modelo_id),
                        revision=str(metadata.id),
                        casilla=f"construct:{construct.id}",
                        number="",
                        continuidad_id=None,
                        inherited_from=None,
                        label_chain=tuple(construct.localization_keys),
                        carries_help=False,
                    )
                    for construct in revision.constructs
                )
    return tuple(found)


type Values = dict[str, dict[str, str | None]]
"""``values[locale][key]`` for every casilla leaf present in a catalogue."""


def load_casilla_values(locales_dir: Path = LOCALES_DIR) -> Values:
    """Read every casilla leaf of every locale's Modelo schema shards."""
    values: Values = {}
    for locale in sorted(discover_locale_codes(locales_dir)):
        leaves: dict[str, str | None] = {}
        for shard in sorted((locales_dir / locale / "modelo" / "schema").glob("*.yml")):
            raw = yaml.safe_load(shard.read_text(encoding="utf-8")) or {}
            for key, value in _flatten_raw_locale_leaves(raw).items():
                if is_delta_keyed_leaf(key):
                    leaves[key] = None if value is None else str(value)
        values[locale] = leaves
    return values


_EDITION_TEXT: Final = re.compile(r"^modelo\.schema\.[^.]+\.revision\.[^.]+\.field\.label$")
#: Scaffold renderings standing in for revision or construct text that was never authored.
_EDITION_TEXT_PLACEHOLDER: Final = re.compile(r"^(?:Casilla|Casella)\s*—|—\s*(?:tax|informaci|adóügyi)")


def edition_text_gaps(locales_dir: Path = LOCALES_DIR) -> dict[str, tuple[str, ...]]:
    """Return, per locale, revision labels that are null or a scaffold placeholder.

    A revision label is edition-specific text with no inheritance chain, so every
    declared revision needs its own authored value in every locale. Construct
    titles are delta-keyed and judged through resolution with casilla labels.
    """
    gaps: dict[str, tuple[str, ...]] = {}
    for locale in sorted(discover_locale_codes(locales_dir)):
        found: list[str] = []
        for shard in sorted((locales_dir / locale / "modelo" / "schema").glob("*.yml")):
            raw = yaml.safe_load(shard.read_text(encoding="utf-8")) or {}
            for key, value in _flatten_raw_locale_leaves(raw).items():
                if _EDITION_TEXT.match(key) and (
                    value is None or _EDITION_TEXT_PLACEHOLDER.search(str(value)) is not None
                ):
                    found.append(key)
        gaps[locale] = tuple(sorted(found))
    return gaps


#: Lineages whose Spanish wording changed between editions without changing meaning, so one
#: translation correctly renders every edition. Keyed per (locale, modelo, lineage), each with
#: the reviewer's reason; never widened by modelo or prefix.
REVIEWED_EQUIVALENT_SPANISH: Final[dict[tuple[str, str, str], str]] = {
    **{
        (locale, "202", lineage): "The later edition only spells out abbreviations ('op.', 'Tit.') of the same text."
        for locale in ("ca", "en", "hu")
        for lineage in (
            "importe-excluido-aumento-capital-art-17-2-lis",
            "importe-integrado-cuota-quita-espera-cooperativas",
            "renta-exenta-cap-xiv-tit-vii-lis",
        )
    },
    ("en", "100", "irpf-ed-suministros"): "'Electricity' renders both 'luz' and 'electricidad'.",
}


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


class ModeloCasillaCatalogue:
    """The casilla surface as the runtime resolves it, with delta-keyed edits."""

    def __init__(self, occurrences: tuple[CasillaOccurrence, ...], values: Values) -> None:
        """Index every key by the coordinates whose chains read it."""
        self.occurrences = occurrences
        self.values = values
        self.locales = tuple(sorted(values))
        self.dependents: dict[str, list[tuple[int, str]]] = defaultdict(list)
        self.declared_revisions = frozenset(
            (encode_modelo_locale_segment(occurrence.modelo), encode_modelo_locale_segment(occurrence.revision))
            for occurrence in occurrences
        )
        for index, occurrence in enumerate(occurrences):
            for field_name in _FIELDS:
                for key in occurrence.chain(field_name):
                    self.dependents[key].append((index, field_name))

    @classmethod
    def published(cls, locales_dir: Path = LOCALES_DIR) -> ModeloCasillaCatalogue:
        """Build the view from the published generation and the on-disk catalogue."""
        return cls(casilla_occurrences(), load_casilla_values(locales_dir))

    # -- resolution -------------------------------------------------------

    def lookup_for(self, values: Values) -> Callable[[str, str], str | None]:
        """Return a runtime-shaped lookup over ``values``."""

        def lookup(key: str, locale: str) -> str | None:
            return values.get(locale, {}).get(key)

        return lookup

    def resolve(self, index: int, field_name: str, locale: str, values: Values | None = None) -> str | None:
        """Resolve one coordinate with the runtime selection rule."""
        view = self.values if values is None else values
        chain = self.occurrences[index].chain(field_name)
        source = modelo_localization_source(chain, locale=locale, lookup=self.lookup_for(view))
        return None if source is None else view[source[1]][source[0]]

    def resolution(self, values: Values | None = None) -> dict[Coordinate, str | None]:
        """Resolve every coordinate."""
        return {
            (index, field_name, locale): self.resolve(index, field_name, locale, values)
            for index in range(len(self.occurrences))
            for field_name in _FIELDS
            for locale in self.locales
        }

    # -- findings ---------------------------------------------------------

    def findings(self) -> CatalogueFindings:
        """Measure every delete target and gap on the current catalogue."""
        found = CatalogueFindings()
        plan = self.collapse_plan(include_redundant=True)
        for locale in self.locales:
            leaves = self.values[locale]
            found.orphan_keys[locale] = tuple(
                sorted(key for key in leaves if key not in self.dependents and not self._undeclared_revision(key))
            )
            found.undeclared_revision_keys[locale] = tuple(
                sorted(key for key in leaves if self._undeclared_revision(key))
            )
            found.null_leaves[locale] = tuple(
                sorted(key for key, value in leaves.items() if value is None and key in self.dependents)
            )
            found.derived_help[locale] = tuple(
                sorted(key for key, value in leaves.items() if value is not None and _is_derived_help(key, value))
            )
            found.placeholders[locale] = tuple(
                sorted(
                    key
                    for key, value in leaves.items()
                    if value is not None
                    and (
                        (key.endswith(".label") and _PLACEHOLDER.search(value))
                        or (key.endswith(".title") and _EDITION_TEXT_PLACEHOLDER.search(value))
                    )
                )
            )
            artifact = _GLOSSARY_ARTIFACT.get(locale)
            found.glossary_artifacts[locale] = (
                ()
                if artifact is None
                else tuple(sorted(key for key, value in leaves.items() if value and artifact.search(value)))
            )
            found.truncated_text[locale] = tuple(
                sorted(key for key, value in leaves.items() if value and _TRUNCATED.search(value))
            )
            found.redundant_values[locale] = tuple(
                sorted(key for key, reason in plan.plan.removals.get(locale, {}).items() if reason == "redundant")
            )
            found.lineage_lifts[locale] = tuple(sorted(plan.plan.settings.get(locale, {})))
        found.unresolved_spanish = tuple(
            sorted(
                f"{occurrence.modelo}/{occurrence.revision}/{occurrence.casilla}"
                for index, occurrence in enumerate(self.occurrences)
                if self.resolve(index, "label", SOURCE_LOCALE) is None
            )
        )
        found.untranslated = {
            locale: sum(
                1
                for index in range(len(self.occurrences))
                if self.resolve(index, "label", locale) is not None
                and _served_locale(self, index, "label", locale) != locale
            )
            for locale in self.locales
            if locale != SOURCE_LOCALE
        }
        found.translation_drift = self.translation_drift()
        found.stale_translations = {
            locale: self.stale_translations(locale) for locale in self.locales if locale != SOURCE_LOCALE
        }
        found.stranded_translations = {
            locale: self.stranded_translations(locale) for locale in self.locales if locale != SOURCE_LOCALE
        }
        return found

    def translation_drift(self, values: Values | None = None) -> dict[str, tuple[str, ...]]:
        """Return, per locale, the lineages rendering one Spanish text more than one way.

        A lineage is the continuity key when the casilla declares one, else the
        casilla identity within its modelo. Divergent Spanish text is a genuine
        edition difference and is not drift.
        """
        groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
        for index, occurrence in enumerate(self.occurrences):
            lineage = occurrence.continuidad_id or f"casilla:{occurrence.casilla}"
            spanish = self.resolve(index, "label", SOURCE_LOCALE, values)
            if spanish is not None:
                groups[(occurrence.modelo, lineage, spanish)].append(index)
        drift: dict[str, tuple[str, ...]] = {}
        for locale in self.locales:
            if locale == SOURCE_LOCALE:
                continue
            drift[locale] = tuple(
                sorted(
                    f"{modelo}/{lineage}"
                    for (modelo, lineage, _spanish), members in groups.items()
                    if len(
                        {
                            text
                            for index in members
                            if _served_locale(self, index, "label", locale, values) == locale
                            and (text := self.resolve(index, "label", locale, values)) is not None
                        }
                    )
                    > 1
                )
            )
        return drift

    def copied_translations(self, locale: str) -> dict[str, str]:
        """Return the ``locale`` keys that serve a label identical to its resolved Spanish text."""
        copied: dict[str, str] = {}
        lookup = self.lookup_for(self.values)
        for index, occurrence in enumerate(self.occurrences):
            source = modelo_localization_source(occurrence.chain("label"), locale=locale, lookup=lookup)
            if source is None or source[1] != locale:
                continue
            text = self.values[locale][source[0]]
            if text is not None and text == self.resolve(index, "label", SOURCE_LOCALE):
                copied[source[0]] = text
        return copied

    def stale_translations(
        self,
        locale: str,
        excused: Mapping[tuple[str, str, str], str] = REVIEWED_EQUIVALENT_SPANISH,
    ) -> tuple[str, ...]:
        """Return lineages where one translation renders two different Spanish texts.

        The official wording changed and the translation did not follow, so a
        filer reads text that no longer matches the Spanish label.
        """
        lookup = self.lookup_for(self.values)
        spanish_by_translation: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        for index, occurrence in enumerate(self.occurrences):
            source = modelo_localization_source(occurrence.chain("label"), locale=locale, lookup=lookup)
            spanish = self.resolve(index, "label", SOURCE_LOCALE)
            if source is None or source[1] != locale or spanish is None:
                continue
            translation = self.values[locale][source[0]]
            if translation is None:
                continue
            lineage = occurrence.continuidad_id or f"casilla:{occurrence.casilla}"
            spanish_by_translation[(occurrence.modelo, lineage, translation)].add(spanish)
        return tuple(
            sorted(
                {
                    f"{modelo}/{lineage}"
                    for (modelo, lineage, _translation), spanish in spanish_by_translation.items()
                    if len({_normalised(text) for text in spanish}) > 1 and (locale, modelo, lineage) not in excused
                }
            )
        )

    def stranded_translations(self, locale: str) -> tuple[str, ...]:
        """Return rows rendering Spanish although their lineage translates that exact Spanish text.

        The translation exists; it is only stored where these rows do not read
        it. Such rows are derivable, never new translation work.
        """
        lookup = self.lookup_for(self.values)
        translated: set[tuple[str, str, str]] = set()
        untranslated: list[tuple[tuple[str, str, str], str]] = []
        for index, occurrence in enumerate(self.occurrences):
            spanish = self.resolve(index, "label", SOURCE_LOCALE)
            if spanish is None:
                continue
            group = (occurrence.modelo, occurrence.continuidad_id or f"casilla:{occurrence.casilla}", spanish)
            source = modelo_localization_source(occurrence.chain("label"), locale=locale, lookup=lookup)
            if source is not None and source[1] == locale:
                translated.add(group)
            else:
                untranslated.append((group, f"{occurrence.modelo}/{occurrence.revision}/{occurrence.casilla}"))
        return tuple(sorted(label for group, label in untranslated if group in translated))

    def served_sources(self, locale: str) -> dict[str, frozenset[str]]:
        """Return, for each ``locale`` key that serves a text, the Spanish texts it renders."""
        lookup = self.lookup_for(self.values)
        sources: dict[str, set[str]] = defaultdict(set)
        for index, occurrence in enumerate(self.occurrences):
            for field_name in _FIELDS:
                source = modelo_localization_source(occurrence.chain(field_name), locale=locale, lookup=lookup)
                spanish = self.resolve(index, field_name, SOURCE_LOCALE)
                if source is not None and source[1] == locale and spanish is not None:
                    sources[source[0]].add(spanish)
        return {key: frozenset(texts) for key, texts in sources.items()}

    # -- collapse ---------------------------------------------------------

    def collapse_plan(self, *, include_redundant: bool = True) -> CollapseResult:
        """Compute removals and lineage lifts that preserve every resolved text.

        Derived help, null leaves and orphan keys are removed first; they are
        delete targets whatever they resolve to. Lineage lifts then place a
        value on a continuity key when every chain reading that key already
        resolves to it in that locale, which changes no resolution. Finally
        every remaining value is tested for redundancy most-specific first: it
        is dropped when removing it changes no coordinate that reads its key.
        """
        working: Values = {locale: dict(leaves) for locale, leaves in self.values.items()}
        plan = CollapsePlan()
        for locale in self.locales:
            for key, value in list(working[locale].items()):
                if self._undeclared_revision(key):
                    continue
                if key not in self.dependents:
                    plan.remove(locale, key, "orphan")
                elif value is None:
                    plan.remove(locale, key, "null")
                elif _is_derived_help(key, value):
                    plan.remove(locale, key, "derived-help")
                else:
                    continue
                del working[locale][key]
        baseline = self.resolution(working)
        # A stale lineage value blocks a lift until the redundancy pass removes
        # it, and a lift makes more occurrence values redundant, so the two
        # passes alternate until neither changes the catalogue.
        lifted_keys: dict[str, set[str]] = defaultdict(set)
        progressing = True
        while progressing:
            lifted = self._lift_to_lineage(working, baseline, plan, lifted_keys)
            removed = self._remove_redundant(working, baseline, plan) if include_redundant else 0
            progressing = bool(lifted or removed)
        return CollapseResult(plan=plan, working=working, baseline=baseline)

    def _remove_redundant(
        self,
        working: Values,
        baseline: Mapping[Coordinate, str | None],
        plan: CollapsePlan,
    ) -> int:
        """Drop every value whose removal changes no resolution; return how many."""
        removed = 0
        # Spanish goes first: removing a Spanish value lowers the Spanish tier,
        # which is what lets a translation move down to the shared key. The
        # pass repeats to a fixed point because each removal can enable another.
        changed = True
        while changed:
            changed = False
            for locale in (SOURCE_LOCALE, *[loc for loc in self.locales if loc != SOURCE_LOCALE]):
                for key in sorted(working[locale], key=_specificity):
                    if self._undeclared_revision(key):
                        continue
                    value = working[locale].pop(key)
                    if self._unchanged(key, locale, working, baseline):
                        plan.remove(locale, key, "redundant")
                        removed += 1
                        changed = True
                    else:
                        working[locale][key] = value
        return removed

    def _undeclared_revision(self, key: str) -> bool:
        """Return whether ``key`` sits under a revision id no occurrence declares."""
        match = _REVISION_SCOPED.match(key)
        return match is not None and (match["modelo"], match["revision"]) not in self.declared_revisions

    def _affected_locales(self, locale: str) -> tuple[str, ...]:
        return self.locales if locale == SOURCE_LOCALE else (locale,)

    def _unchanged(self, key: str, locale: str, working: Values, baseline: Mapping[Coordinate, str | None]) -> bool:
        return all(
            self.resolve(index, field_name, affected, working) == baseline[(index, field_name, affected)]
            for index, field_name in self.dependents.get(key, ())
            for affected in self._affected_locales(locale)
        )

    def _lift_to_lineage(
        self,
        working: Values,
        baseline: Mapping[Coordinate, str | None],
        plan: CollapsePlan,
        lifted_keys: dict[str, set[str]],
    ) -> int:
        """Place agreed text on empty lineage keys where no resolution changes; return how many.

        A key this plan already lifted once is never lifted again: if the
        redundancy pass dropped it, lifting it back would only cycle.
        """
        lifted = 0
        lineage_keys = sorted(key for key in self.dependents if is_lineage_key(key))
        for locale in (SOURCE_LOCALE, *[loc for loc in self.locales if loc != SOURCE_LOCALE]):
            for key in lineage_keys:
                if working[locale].get(key) is not None or key in lifted_keys[locale]:
                    continue
                texts = {baseline[(index, field_name, locale)] for index, field_name in self.dependents[key]}
                if len(texts) != 1:
                    continue
                (text,) = texts
                if text is None:
                    continue
                working[locale][key] = text
                if self._unchanged(key, locale, working, baseline):
                    plan.assign(locale, key, text, "lineage-lift")
                    lifted_keys[locale].add(key)
                    lifted += 1
                else:
                    del working[locale][key]
        return lifted

    # -- application ------------------------------------------------------

    def apply(
        self,
        result: CollapseResult,
        locales_dir: Path = LOCALES_DIR,
        pending_dir: Path = PENDING_CASILLA_INSTALL_DIR,
    ) -> dict[str, int]:
        """Install ``result`` into ``locales_dir`` only after a staged copy proves it.

        The plan is written into a staged copy kept at ``pending_dir``, and that
        copy must resolve every coordinate exactly as ``result.baseline`` does.
        The changed Modelo schema shards are then copied into place, and the
        staged copy is discarded only when every shard is installed. An
        interrupted install leaves ``pending_dir`` behind: planning refuses while
        it exists, because a partly installed catalogue is not a baseline, and
        :func:`resume_install` finishes the verified install instead.

        Raises:
            CollapseVerificationError: An install is already pending, the staged
                catalogue resolves differently, or a shard could not be installed.
        """
        if pending_dir.exists():
            raise CollapseVerificationError(f"an install is pending at {pending_dir}; resume it first")
        staged = pending_dir / "locales"
        shutil.copytree(locales_dir, staged)
        try:
            written = self._write_plan(result.plan, staged)
            proof = ModeloCasillaCatalogue(self.occurrences, load_casilla_values(staged))
            changed = sum(1 for coordinate, text in proof.resolution().items() if result.baseline[coordinate] != text)
        except BaseException:
            _discard(pending_dir)
            raise
        if changed:
            _discard(pending_dir)
            raise CollapseVerificationError(f"the staged catalogue resolves {changed} texts differently")
        resume_install(locales_dir, pending_dir)
        return written

    def author(
        self,
        manifest: Mapping[str, Mapping[str, str]],
        locales_dir: Path = LOCALES_DIR,
        pending_dir: Path = PENDING_CASILLA_INSTALL_DIR,
    ) -> dict[str, int]:
        """Install authored casilla values, proving they are the only source of change.

        Every coordinate whose resolved text differs afterwards must be served
        by one of the manifest's keys in its own locale, or, for a Spanish
        change, by a manifest key read through the Spanish fallback. Any other
        change means the manifest reached text it did not declare, and the
        install is refused. Returns how many coordinates changed per locale.

        Raises:
            CollapseVerificationError: An install is pending, a key is not a
                casilla key any chain reads, or a change is not attributable.
        """
        unknown = sorted(
            f"{locale}:{key}"
            for locale, values in manifest.items()
            for key in values
            if locale not in self.locales or key not in self.dependents
        )
        if unknown:
            raise CollapseVerificationError(f"manifest names keys no casilla chain reads: {unknown[:5]}")
        if pending_dir.exists():
            raise CollapseVerificationError(f"an install is pending at {pending_dir}; resume it first")
        before = self.resolution()
        staged = pending_dir / "locales"
        shutil.copytree(locales_dir, staged)
        try:
            manager = LocaleManager(src_dir=staged, locales_dir=staged)
            for locale, values in sorted(manifest.items()):
                if values:
                    manager.set_locale_values(locale, dict(values))
            proof = ModeloCasillaCatalogue(self.occurrences, load_casilla_values(staged))
            after = proof.resolution()
            changed: dict[str, int] = defaultdict(int)
            unattributed: list[Coordinate] = []
            for coordinate, text in after.items():
                if before[coordinate] == text:
                    continue
                index, field_name, locale = coordinate
                source = modelo_localization_source(
                    self.occurrences[index].chain(field_name), locale=locale, lookup=proof.lookup_for(proof.values)
                )
                if source is None or source[0] not in manifest.get(source[1], {}):
                    unattributed.append(coordinate)
                changed[locale] += 1
        except BaseException:
            _discard(pending_dir)
            raise
        if unattributed:
            _discard(pending_dir)
            raise CollapseVerificationError(f"{len(unattributed)} changed texts are not served by the manifest")
        resume_install(locales_dir, pending_dir)
        return dict(changed)

    def _write_plan(self, plan: CollapsePlan, locales_dir: Path) -> dict[str, int]:
        manager = LocaleManager(src_dir=locales_dir, locales_dir=locales_dir)
        written: dict[str, int] = {}
        for locale in self.locales:
            settings: dict[str, str | None] = {
                key: value for key, (value, _reason) in plan.settings.get(locale, {}).items()
            }
            removals = sorted(set(plan.removals.get(locale, {})) - set(settings))
            if settings:
                manager.set_locale_values(locale, settings)
            if removals:
                manager.remove_locale_values(locale, removals)
            written[locale] = len(settings) + len(removals)
        return written


class CollapseVerificationError(RuntimeError):
    """A collapse could not be proven lossless or installed as proven."""


_INSTALL_ATTEMPTS: Final = 60
_INSTALL_BACKOFF_SECONDS: Final = 0.5


def resume_install(locales_dir: Path = LOCALES_DIR, pending_dir: Path = PENDING_CASILLA_INSTALL_DIR) -> None:
    """Install a verified staged catalogue and discard it once every shard is in place.

    Raises:
        CollapseVerificationError: No install is pending, or a shard could not be written.
    """
    staged = pending_dir / "locales"
    if not staged.is_dir():
        raise CollapseVerificationError(f"no install is pending at {pending_dir}")
    failed = _install_shards(staged, locales_dir)
    if failed:
        raise CollapseVerificationError(f"verified shards could not be installed, resume again: {failed}")
    _discard(pending_dir)


def _discard(pending_dir: Path) -> None:
    """Remove a staged catalogue, tolerating lock sidecars that vanish while it is walked."""

    def ignore_vanished(function: Callable[..., object], path: str, error: BaseException) -> None:
        if not isinstance(error, FileNotFoundError):
            raise error

    shutil.rmtree(pending_dir, onexc=ignore_vanished)


def _install_shards(staged: Path, locales_dir: Path) -> tuple[str, ...]:
    """Copy every changed Modelo schema shard from ``staged``; return the ones that failed."""
    failed: list[str] = []
    for source in sorted(staged.glob("*/modelo/schema/*.yml")):
        relative = source.relative_to(staged)
        target = locales_dir / relative
        payload = source.read_bytes()
        if target.is_file() and target.read_bytes() == payload:
            continue
        for _attempt in range(_INSTALL_ATTEMPTS):
            try:
                atomic_write_text(target, payload.decode("utf-8"))
                break
            except OSError:
                time.sleep(_INSTALL_BACKOFF_SECONDS)
        else:
            failed.append(relative.as_posix())
    return tuple(failed)


@dataclass(slots=True)
class CollapseResult:
    """A collapse plan with the evidence it was computed against."""

    plan: CollapsePlan
    working: Values
    baseline: Mapping[Coordinate, str | None]


def _specificity(key: str) -> tuple[int, str]:
    """Order occurrence keys before lineage keys so the shared value survives."""
    return (1 if is_lineage_key(key) else 0, key)


def _normalised(text: str) -> str:
    """Fold case, accents and punctuation so only a wording change counts."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    letters = "".join(character for character in decomposed if not unicodedata.combining(character))
    return " ".join(re.sub(r"[^\w]+", " ", letters).split())


def _is_derived_help(key: str, value: str) -> bool:
    return key.endswith(".help") and any(pattern.match(value) for pattern in _DERIVED_HELP)


def _served_locale(
    catalogue: ModeloCasillaCatalogue,
    index: int,
    field_name: str,
    locale: str,
    values: Values | None = None,
) -> str | None:
    source = modelo_localization_source(
        catalogue.occurrences[index].chain(field_name),
        locale=locale,
        lookup=catalogue.lookup_for(catalogue.values if values is None else values),
    )
    return None if source is None else source[1]
