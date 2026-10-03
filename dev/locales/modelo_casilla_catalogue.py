"""Delta-keyed casilla resolution, audits, collapse, and authored-change verification."""

from __future__ import annotations

import shutil
from collections import defaultdict
from collections.abc import Callable, Mapping
from pathlib import Path

from cadrumo.domain.calculations.registry.modelo_localization import (
    encode_modelo_locale_segment,
    modelo_localization_source,
)
from cadrumo.domain.calculations.registry.schema_surfaces import (
    CasillaContinuidadEvolutionDefinition,
)

from ._casilla_keys import is_lineage_key
from ._paths import LOCALES_DIR, PENDING_CASILLA_INSTALL_DIR
from .casilla_authoring_verification import (
    _add_declared_casilla_label_link,
    _apply_authored_casilla_locale,
    _record_authored_casilla_change,
    _record_introduced_casilla_segment_drift,
    _refuse_unknown_authored_casilla_keys,
)
from .casilla_catalogue_install import _discard, resume_install
from .casilla_catalogue_models import (
    CasillaOccurrence,
    CatalogueFindings,
    CollapsePlan,
    CollapseResult,
    CollapseVerificationError,
    Coordinate,
    Values,
)
from .casilla_collapse_stages import _lift_casilla_lineage_key, _remove_casilla_structural_leaf
from .casilla_content_analysis import (
    _record_casilla_lineage_locale_drift,
    _record_casilla_rendering_segments,
    _record_casilla_segment_renderings,
    _record_dropped_casilla_content,
    _record_stale_casilla_translation,
)
from .casilla_findings import (
    _record_casilla_content_and_segment_drift,
    _record_casilla_fallback_translations,
    _record_casilla_glossary_artifacts,
    _record_casilla_key_findings,
    _record_casilla_lineage_translation_drift,
    _record_casilla_placeholders,
    _record_casilla_plan_findings,
    _record_casilla_truncation,
    _record_casilla_unresolved_spanish,
    _record_casilla_whitespace,
    _record_derived_casilla_help,
)
from .casilla_resolution import _served_locale
from .casilla_reviewed_wording import (
    REVIEWED_EQUIVALENT_SPANISH,
    REVIEWED_SEGMENT_RENDERINGS,
    REVIEWED_SHARED_SEGMENTS,
    REVIEWED_SHARED_TRANSLATIONS,
)
from .casilla_source_inventory import _published_surface, load_casilla_values
from .casilla_text_comparison import (
    _abbreviated_wording,
    _normalised,
    _plain_wording,
)
from .casilla_text_policy import (
    _FIELDS,
    _REVISION_SCOPED,
    SOURCE_LOCALE,
)
from .manager import LocaleManager


class ModeloCasillaCatalogue:
    """The casilla surface as the runtime resolves it, with delta-keyed edits."""

    def __init__(
        self,
        occurrences: tuple[CasillaOccurrence, ...],
        values: Values,
        *,
        label_evolutions: Mapping[str, tuple[CasillaContinuidadEvolutionDefinition, ...]] | None = None,
    ) -> None:
        """Index occurrence chains and optional typed evidence for label changes."""
        self.occurrences = occurrences
        self.values = values
        self.label_evolutions = {} if label_evolutions is None else label_evolutions
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
        occurrences, evolutions = _published_surface()
        return cls(occurrences, load_casilla_values(locales_dir), label_evolutions=evolutions)

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
            _record_casilla_key_findings(self, locale, found, leaves)
            _record_derived_casilla_help(self, locale, found, leaves)
            _record_casilla_placeholders(self, locale, found, leaves)
            _record_casilla_glossary_artifacts(self, locale, found, leaves)
            _record_casilla_truncation(self, locale, found, leaves)
            _record_casilla_whitespace(self, locale, found, leaves)
            _record_casilla_plan_findings(self, locale, found, plan)
        _record_casilla_unresolved_spanish(self, found)
        _record_casilla_fallback_translations(self, found)
        _record_casilla_content_and_segment_drift(self, found)
        _record_casilla_lineage_translation_drift(self, found)
        return found

    def dropped_source_content(self, locale: str, values: Values | None = None) -> dict[str, tuple[str, ...]]:
        """Return, per serving key, the source tokens a translation lost.

        A label's or a help text's numbers, box references and comparison symbols are the legal
        content an operator acts on: a cap of 500 euros, the transitional
        provisions a deduction rests on, the box an amount is carried from. A
        translation that renders the prose but drops those states something the
        Spanish does not. Number formatting differs between languages, so
        digits are compared with separators removed.
        """
        lookup = self.lookup_for(self.values if values is None else values)
        dropped: dict[str, tuple[str, ...]] = {}
        for index, occurrence in enumerate(self.occurrences):
            for field_name in _FIELDS:
                _record_dropped_casilla_content(self, index, occurrence, field_name, locale, values, lookup, dropped)
        return dropped

    def shared_translations(self, locale: str, values: Values | None = None) -> dict[str, tuple[str, ...]]:
        """Return translations one modelo renders for more than one Spanish label or help wording.

        Two Spanish labels that differ only in case, accents or punctuation say
        one thing, so one translation serves both. A difference in wording may
        still be equivalent, which a reviewer records in
        :data:`REVIEWED_SHARED_TRANSLATIONS`; anything else is two concepts
        wearing one translation, as a reused box number produced in Modelo 200.
        """
        grouped: dict[tuple[str, str], set[str]] = defaultdict(set)
        for index, occurrence in enumerate(self.occurrences):
            for field_name in _FIELDS:
                spanish = self.resolve(index, field_name, SOURCE_LOCALE, values)
                text = self.resolve(index, field_name, locale, values)
                if spanish is None or text is None:
                    continue
                if _served_locale(self, index, field_name, locale, values) != locale:
                    continue
                grouped[(occurrence.modelo, text)].add(spanish)
        shared: dict[str, tuple[str, ...]] = {}
        for (modelo, text), spanish_texts in grouped.items():
            if len({_plain_wording(spanish) for spanish in spanish_texts}) < 2:
                continue
            if (locale, modelo, text) in REVIEWED_SHARED_TRANSLATIONS:
                continue
            shared[text] = tuple(sorted(spanish_texts))
        return shared

    def segment_drift(self, locale: str, values: Values | None = None) -> dict[str, tuple[str, ...]]:
        """Return the composed segments this locale renders more than one way.

        AEAT composes a long label from segments joined by ``" - "``: a heading,
        a regime, a year, the state of the amount. A segment repeated across
        labels states the same thing each time, so its translation repeats too,
        the way the registry's delta keying stores one text for one meaning.
        Two renderings of one segment are a defect of a kind whole-value drift
        cannot see, since the surrounding labels differ: the meaning may even
        invert, as ``Sin reiteración`` rendered as a repeated donation.
        A reviewer records a segment whose context genuinely forces two
        renderings in :data:`REVIEWED_SEGMENT_RENDERINGS` with its reason.
        """
        view = self.values if values is None else values
        rendered: dict[str, set[str]] = defaultdict(set)
        for key, spanish_texts in self.served_sources(locale).items():
            _record_casilla_segment_renderings(key, spanish_texts, locale, view, rendered)
        return {
            segment: tuple(sorted(renderings))
            for segment, renderings in rendered.items()
            if len(renderings) > 1 and segment not in REVIEWED_SEGMENT_RENDERINGS.get(locale, {})
        }

    def shared_segments(self, locale: str, values: Values | None = None) -> dict[str, tuple[str, ...]]:
        """Return the renderings this locale gives to more than one Spanish segment.

        The mirror of :meth:`segment_drift`: one rendering standing for two
        segments hides a distinction the Spanish draws, as the Basque
        ``Concierto económico`` and the Navarrese ``Convenio económico`` once
        shared one English rendering. AEAT states one segment several ways
        across editions, abbreviating it or dropping its prepositions, and
        those wordings share one rendering correctly; a reviewer records each
        such pair in :data:`REVIEWED_SHARED_SEGMENTS` with the difference seen.
        """
        view = self.values if values is None else values
        rendered: dict[str, set[str]] = defaultdict(set)
        for key, spanish_texts in self.served_sources(locale).items():
            _record_casilla_rendering_segments(key, spanish_texts, locale, view, rendered)
        reviewed = REVIEWED_SHARED_SEGMENTS.get(locale, {})
        return {
            rendering: tuple(sorted(sources))
            for rendering, sources in rendered.items()
            if len({_abbreviated_wording(source) for source in sources}) > 1 and rendering not in reviewed
        }

    def translation_drift(self, values: Values | None = None) -> dict[str, tuple[str, ...]]:
        """Return, per locale, the lineages rendering one Spanish label or help more than one way.

        A lineage is the continuity key when the casilla declares one, else the
        casilla identity within its modelo. Divergent Spanish text is a genuine
        edition difference and is not drift.
        """
        groups: dict[tuple[str, str, str, str], list[int]] = defaultdict(list)
        for index, occurrence in enumerate(self.occurrences):
            lineage = occurrence.continuidad_id or f"casilla:{occurrence.casilla}"
            for field_name in _FIELDS:
                spanish = self.resolve(index, field_name, SOURCE_LOCALE, values)
                if spanish is not None:
                    groups[(occurrence.modelo, lineage, field_name, spanish)].append(index)
        drift: dict[str, tuple[str, ...]] = {}
        for locale in self.locales:
            _record_casilla_lineage_locale_drift(self, locale, groups, values, drift)
        return drift

    def copied_translations(self, locale: str) -> dict[str, str]:
        """Return the ``locale`` keys that serve a label or help identical to its resolved Spanish."""
        copied: dict[str, str] = {}
        lookup = self.lookup_for(self.values)
        for index, occurrence in enumerate(self.occurrences):
            for field_name in _FIELDS:
                source = modelo_localization_source(occurrence.chain(field_name), locale=locale, lookup=lookup)
                if source is None or source[1] != locale:
                    continue
                text = self.values[locale][source[0]]
                if text is not None and text == self.resolve(index, field_name, SOURCE_LOCALE):
                    copied[source[0]] = text
        return copied

    def stale_translations(
        self,
        locale: str,
        excused: Mapping[tuple[str, str, str], str] = REVIEWED_EQUIVALENT_SPANISH,
    ) -> tuple[str, ...]:
        """Return lineages where one translation renders two different Spanish texts.

        The official wording changed and the translation did not follow, so a
        filer reads text that no longer matches the Spanish label or help.
        """
        lookup = self.lookup_for(self.values)
        spanish_by_translation: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        for index, occurrence in enumerate(self.occurrences):
            for field_name in _FIELDS:
                _record_stale_casilla_translation(
                    self, index, occurrence, field_name, locale, lookup, spanish_by_translation
                )
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
        translated: set[tuple[str, str, str, str]] = set()
        untranslated: list[tuple[tuple[str, str, str, str], str]] = []
        for index, occurrence in enumerate(self.occurrences):
            for field_name in _FIELDS:
                spanish = self.resolve(index, field_name, SOURCE_LOCALE)
                if spanish is None:
                    continue
                lineage = occurrence.continuidad_id or f"casilla:{occurrence.casilla}"
                group = (occurrence.modelo, lineage, field_name, spanish)
                source = modelo_localization_source(occurrence.chain(field_name), locale=locale, lookup=lookup)
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
                _remove_casilla_structural_leaf(self, locale, key, value, working, plan)
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
                lifted += _lift_casilla_lineage_key(self, working, baseline, plan, lifted_keys, locale, key)
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
        manifest: Mapping[str, Mapping[str, str | None]],
        locales_dir: Path = LOCALES_DIR,
        pending_dir: Path = PENDING_CASILLA_INSTALL_DIR,
    ) -> dict[str, int]:
        """Install authored casilla values and removals, proving they are the only source of change.

        A ``None`` value removes the key, so an edition falls back to the text a
        less specific key provides; that text's key must be named in the manifest.

        Every coordinate whose resolved text differs afterwards must be served
        by one of the manifest's keys in its own locale, or, for a Spanish
        change, by a manifest key read through the Spanish fallback. Any other
        change means the manifest reached text it did not declare, and the
        install is refused. New inconsistent composed-segment renderings are
        refused before cutover. Returns how many coordinates changed per locale.

        Raises:
            CollapseVerificationError: An install is pending, a key is not a
                casilla key any chain reads, or a change is not attributable.
        """
        _refuse_unknown_authored_casilla_keys(self, manifest)
        if pending_dir.exists():
            raise CollapseVerificationError(f"an install is pending at {pending_dir}; resume it first")
        before = self.resolution()
        staged = pending_dir / "locales"
        shutil.copytree(locales_dir, staged)
        try:
            manager = LocaleManager(src_dir=staged, locales_dir=staged)
            for locale, values in sorted(manifest.items()):
                _apply_authored_casilla_locale(manager, locale, values)
            proof = ModeloCasillaCatalogue(self.occurrences, load_casilla_values(staged))
            after = proof.resolution()
            changed: dict[str, int] = defaultdict(int)
            unattributed: list[Coordinate] = []
            for coordinate, text in after.items():
                _record_authored_casilla_change(self, proof, before, manifest, coordinate, text, changed, unattributed)
            affected_locales = self.locales if SOURCE_LOCALE in manifest else tuple(manifest)
            introduced_drift: list[tuple[str, str, tuple[str, ...]]] = []
            for locale in affected_locales:
                _record_introduced_casilla_segment_drift(self, proof, locale, introduced_drift)
            if introduced_drift:
                raise CollapseVerificationError(
                    f"authored values introduce inconsistent composed-segment renderings: {introduced_drift[:5]}"
                )
        except BaseException:
            _discard(pending_dir)
            raise
        if unattributed:
            _discard(pending_dir)
            raise CollapseVerificationError(f"{len(unattributed)} changed texts are not served by the manifest")
        split = self._continuity_splits(before, after)
        if split:
            _discard(pending_dir)
            raise CollapseVerificationError(
                "Spanish text would diverge between editions that render one text today, which the registry "
                f"refuses without a continuity evolution: {split[:5]}"
            )
        resume_install(locales_dir, pending_dir)
        return dict(changed)

    def _continuity_splits(
        self,
        before: Mapping[Coordinate, str | None],
        after: Mapping[Coordinate, str | None],
    ) -> tuple[str, ...]:
        """Return the boxes whose editions agree on Spanish text before and disagree after.

        The registry compares a casilla's label across the editions that declare
        it and refuses an undeclared difference, so an authored edition-specific
        Spanish text must come with a continuity evolution in the registry. Help
        is not one of the fields it compares, so edition-specific help needs no
        evolution and is not judged here.
        """
        editions: dict[tuple[str, str], list[int]] = defaultdict(list)
        for index, occurrence in enumerate(self.occurrences):
            if not occurrence.casilla.startswith("construct:"):
                editions[(occurrence.modelo, occurrence.casilla)].append(index)
        split: list[str] = []
        for (modelo, casilla), members in sorted(editions.items()):
            old: dict[str | None, list[int]] = defaultdict(list)
            for index in members:
                old[before.get((index, "label", SOURCE_LOCALE))].append(index)
            if any(not self._declared_label_split(modelo, group, after) for group in old.values()):
                split.append(f"{modelo}/{casilla}")
        return tuple(split)

    def _declared_label_split(self, modelo: str, members: list[int], after: Mapping[Coordinate, str | None]) -> bool:
        """Require grounded label transitions to connect every distinct resulting text.

        Editions retaining the same text share a node. This allows an unchanged
        later edition to inherit an evidenced change without a copied evolution.
        Revision identifiers are opaque; neither years nor filename order decide
        whether two editions are connected.
        """
        texts = {after.get((index, "label", SOURCE_LOCALE)) for index in members}
        if len(texts) <= 1:
            return True
        occurrences = {self.occurrences[index].revision: index for index in members}
        links: dict[str | None, set[str | None]] = defaultdict(set)
        for evolution in self.label_evolutions.get(modelo, ()):
            _add_declared_casilla_label_link(self, evolution, occurrences, after, links)
        pending = [next(iter(texts))]
        reached: set[str | None] = set()
        while pending:
            text = pending.pop()
            if text not in reached:
                reached.add(text)
                pending.extend(links[text] - reached)
        return reached == texts

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


def _specificity(key: str) -> tuple[int, str]:
    """Order occurrence keys before lineage keys so the shared value survives."""
    return (1 if is_lineage_key(key) else 0, key)
