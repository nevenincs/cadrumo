"""Tier-A external seed importers for the Terminology Handbook.

External terminology sources contribute the missing-language translations
and aliases that hand-curation is slow to produce: a reader's en / ca / hu
query matches more concept cards when a Spanish concept carries its declared
translations. This module reads a Tier-A source export into a strict typed
intermediate, maps each entry onto an EXISTING concept by matching the
source's Spanish term against the concept's ``es`` ``preferred`` label, and
ADDS the missing-language terms / short_descriptions while stamping
``seed_provenance`` with the licence-required attribution.

Licence discipline (hard gate, not honor-system)
------------------------------------------------
Only Tier-A sources may be ingested, and only from their downloaded export
file (never website / API scraping):

* **IATE** (Interactive Terminology for Europe) -- permissive reuse WITH
  attribution, for the downloaded TBX file only.
* **UBTERM** *Diccionari de fiscalitat* (Universitat de Barcelona) --
  CC BY 3.0, the cleanest trilingual ca/es/en fiscal source.
* **EuroVoc** SKOS labels -- ingestible ONLY after the download-page licence
  is confirmed; until then it is treated as unverified and refused.

Sources that are CC BY-ND (no derivatives), CC BY-NC, or carry no confirmed
licence are EXCLUDED and refused by :func:`assert_source_ingestible`:
TERMCAT Terminologia Oberta (CC BY-ND), the TERMCAT/UOC Catalan-IATE export
(no confirmed licence), RAE DPEJ (no download permitted), and Microsoft
Terminology (no redistribution guarantee). Reformatting an ND source into
Handbook records is itself a derivative, so the refusal is categorical.

Seeds never auto-approve
------------------------
A seed adds translations / aliases, NOT an ``es`` grounded definition with a
source citation, so it does not satisfy the approved-completeness gate: a
seeded ``draft`` stays ``draft``. Lifecycle promotion is human curation. Every
seeded value stamps :class:`~dev.docs.terminology_handbook.schema.SeedProvenance`; a seed with no
attribution is refused at the schema boundary (``attribution`` is
``min_length=1``).

The actual third-party export files are placed later at an operator-chosen
path; the importers are the durable deliverable. The parsers are proven
end-to-end against committed fixture exports under
``dev/docs/terminology_handbook/tests/fixtures/`` -- minimal, clearly-labelled valid
samples -- never against fabricated production data.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, StringConstraints, model_validator

from cadrumo.core.external_constants import UTF_8_ENCODING, OutputLanguage
from cadrumo.core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

from ._serialize import serialise_concept
from .enums import TermStatus
from .errors import TerminologyError, TerminologyValidationError
from .loader import TerminologyHandbook, load_terminology_handbook, terminology_concepts_dir
from .schema import ConceptRecord, LanguageSection, SeedProvenance, TermSection
from .validators import default_handbook_validators

__all__ = [
    "SeedApplyResult",
    "SeedEntry",
    "SeedImportError",
    "SeedLicenceError",
    "SeedSource",
    "SeedTerm",
    "apply_seed_entries",
    "assert_source_ingestible",
    "parse_iate_tbx",
    "parse_ubterm_csv",
    "source_attribution",
]


class SeedImportError(TerminologyError):
    """Raised when a seed export cannot be parsed into the typed intermediate."""


class SeedLicenceError(TerminologyError):
    """Raised when an excluded (ND / NC / unlicensed) source is offered for ingest.

    The licence gate is structural, not advisory: an excluded source is
    refused before any value is read, so no ND-derived data can reach the
    Handbook even by mistake.
    """


class SeedSource(StrEnum):
    """The external terminology sources this module recognises.

    Tier-A sources (``IATE``, ``UBTERM``, ``EUROVOC``) are ingestible under
    their stated licences; the excluded members are present so the licence
    gate can refuse them by name rather than relying on a caller to know they
    are forbidden.
    """

    # Tier-A — ingestible under licence.
    IATE = "iate"
    UBTERM = "ubterm"
    EUROVOC = "eurovoc"
    # Excluded — refused by the licence gate.
    TERMCAT_OBERTA = "termcat-oberta"
    TERMCAT_UOC_IATE = "termcat-uoc-iate"
    RAE_DPEJ = "rae-dpej"
    MICROSOFT_TERMINOLOGY = "microsoft-terminology"


#: Sources that MAY be ingested. EuroVoc is conditionally ingestible: it is in
#: this set only when its download-page licence has been confirmed by the
#: operator and the confirmed attribution is supplied. The importers default to
#: refusing it (see :data:`_EUROVOC_LICENCE_CONFIRMED`) until that happens.
_TIER_A_INGESTIBLE: frozenset[SeedSource] = frozenset({SeedSource.IATE, SeedSource.UBTERM})

#: EuroVoc download-page licence verification flag. Held False until
#: the operator confirms the Publications Office download-page licence; while
#: False, EuroVoc is refused by the licence gate. Flipping this to True is a
#: deliberate, reviewed change paired with the confirmed attribution string.
_EUROVOC_LICENCE_CONFIRMED: bool = False

#: The licence-required attribution string stamped on every value seeded from
#: each ingestible source. The string is the contractual attribution the
#: source's licence demands; it rides into every seeded concept's
#: ``seed_provenance.attribution``.
_SOURCE_ATTRIBUTION: dict[SeedSource, str] = {
    SeedSource.IATE: "IATE - Interactive Terminology for Europe (c) European Union, reuse with attribution",
    SeedSource.UBTERM: ("UBTERM Diccionari de fiscalitat, Universitat de Barcelona (Serveis Linguistics), CC BY 3.0"),
    SeedSource.EUROVOC: "EuroVoc, Publications Office of the European Union (c) European Union, reuse with attribution",
}

#: Human-readable refusal reasons for the excluded sources, surfaced in the
#: :class:`SeedLicenceError` so a caller learns WHY a source is forbidden.
_EXCLUDED_REASON: dict[SeedSource, str] = {
    SeedSource.TERMCAT_OBERTA: "CC BY-ND 3.0 (no derivatives; reformatting into Handbook records is a derivative)",
    SeedSource.TERMCAT_UOC_IATE: "no confirmed licence",
    SeedSource.RAE_DPEJ: "lookup-only, no download permitted",
    SeedSource.MICROSOFT_TERMINOLOGY: "IT-domain, no redistribution guarantee",
}

_SpanishKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
_Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
_ShortDescription = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]


class SeedTerm(BaseModel):
    """One source-provided term in one language (the typed intermediate tier).

    ``term_status`` is the normative status the seed asserts; an external
    source's preferred/main form maps to ``PREFERRED`` and its synonyms to
    ``ADMITTED``. ``short_description`` is the source's gloss where one is
    provided (UBTERM definitions, IATE term notes) -- optional, never
    fabricated.
    """

    model_config = _STRICT_FROZEN

    language: OutputLanguage
    label: _Label
    term_status: TermStatus
    short_description: _ShortDescription | None = None


class SeedEntry(BaseModel):
    """One source entry: a Spanish key plus its per-language terms (intermediate).

    ``spanish_key`` is the surface Spanish term the entry is matched on (lower
    folded against a concept's ``es`` ``preferred`` label). ``terms`` carries
    one or more :class:`SeedTerm` across languages; the Spanish term that
    forms the key is included so its alias status is explicit. ``source`` and
    ``source_entry_id`` carry the provenance the mapper stamps.
    """

    model_config = _STRICT_FROZEN

    source: SeedSource
    spanish_key: _SpanishKey
    terms: tuple[SeedTerm, ...]
    source_entry_id: str | None = None

    @model_validator(mode="after")
    def _validate_entry(self) -> Self:
        if not self.terms:
            raise SeedImportError(f"seed entry {self.spanish_key!r}: no terms")
        if self.source not in _SOURCE_ATTRIBUTION:
            raise SeedImportError(f"seed entry {self.spanish_key!r}: source {self.source.value!r} has no attribution")
        return self


def source_attribution(source: SeedSource) -> str:
    """Return the licence-required attribution string for an ingestible source.

    Raises:
        SeedLicenceError: ``source`` is not Tier-A ingestible.
    """
    assert_source_ingestible(source)
    return _SOURCE_ATTRIBUTION[source]


def assert_source_ingestible(source: SeedSource) -> None:
    """Refuse an excluded or unverified source before any value is read.

    IATE and UBTERM are always ingestible. EuroVoc is ingestible only when
    :data:`_EUROVOC_LICENCE_CONFIRMED` is True (the download-page licence has
    been verified). Every other member is excluded by licence.

    Raises:
        SeedLicenceError: The source may not be ingested, with the reason.
    """
    if source in _TIER_A_INGESTIBLE:
        return
    if source is SeedSource.EUROVOC:
        if _EUROVOC_LICENCE_CONFIRMED:
            return
        raise SeedLicenceError(
            "EuroVoc refused: download-page licence not yet verified. "
            "Confirm the Publications Office licence and supply the attribution before ingesting.",
        )
    reason = _EXCLUDED_REASON.get(source, "not a Tier-A ingestible source")
    raise SeedLicenceError(f"source {source.value!r} refused: {reason}")


# ---------------------------------------------------------------------------
# Parsers — export file -> typed intermediate
# ---------------------------------------------------------------------------

_TBX_LANGS: dict[str, OutputLanguage] = {
    "es": OutputLanguage.ES,
    "en": OutputLanguage.EN,
    "ca": OutputLanguage.CA,
    "hu": OutputLanguage.HU,
}


def _read_xml(path: Path, source: SeedSource) -> ElementTree.Element[str]:
    """Parse an XML export file into its root element, refusing on failure.

    Raises:
        SeedImportError: The file is missing or not well-formed XML.
    """
    if not path.is_file():
        raise SeedImportError(f"{path}: {source.value} export not found")
    try:
        tree = ElementTree.parse(path)  # noqa: S314 — local fixture/operator file, not untrusted network input
    except ElementTree.ParseError as exc:
        raise SeedImportError(f"{path}: malformed {source.value} XML: {exc}") from exc
    return tree.getroot()


def parse_iate_tbx(
    path: Path,
    *,
    min_reliability: int = 3,
    domains: frozenset[str] | None = None,
) -> tuple[SeedEntry, ...]:
    """Parse an IATE TBX export into typed seed entries.

    Reads the TBX ``<termEntry>`` / ``<langSet>`` / ``<tig>`` three-tier
    structure: each ``langSet`` is a language, each ``tig`` a term carrying a
    ``termType`` (fullForm / abbreviation / synonym) and a reliability code.
    An entry is kept only when it has a Spanish term whose reliability is at
    least ``min_reliability`` and (when ``domains`` is given) its subject
    field is in the allow-set -- the tax / law / finance domain filter.

    The Spanish ``fullForm`` becomes the ``spanish_key`` and a ``PREFERRED``
    Spanish term; other-language full forms become ``PREFERRED`` terms in
    their language; synonyms become ``ADMITTED`` terms.

    Args:
        path: The downloaded IATE TBX file (never a scraped page).
        min_reliability: Minimum IATE reliability code to keep (>= 3).
        domains: Optional allow-set of subject-field strings; when given an
            entry must declare at least one matching ``descrip`` of type
            ``subjectField``.

    Returns:
        Typed :class:`SeedEntry` records, one per kept term entry.

    Raises:
        SeedImportError: The file is missing or not well-formed TBX.
    """
    root = _read_xml(path, SeedSource.IATE)
    entries: list[SeedEntry] = []
    for term_entry in root.iter("termEntry"):
        subject_fields = _tbx_subject_fields(term_entry)
        if domains is not None and not (subject_fields & domains):
            continue
        terms, spanish_key = _tbx_terms(term_entry, min_reliability)
        if spanish_key is None or not terms:
            continue
        entry_id = term_entry.get("id")
        entries.append(
            SeedEntry(
                source=SeedSource.IATE,
                spanish_key=spanish_key,
                terms=tuple(terms),
                source_entry_id=entry_id,
            ),
        )
    return tuple(entries)


def _tbx_subject_fields(term_entry: ElementTree.Element[str]) -> frozenset[str]:
    fields: set[str] = set()
    for descrip in term_entry.iter("descrip"):
        if descrip.get("type") == "subjectField" and descrip.text:
            fields.add(descrip.text.strip().lower())
    return frozenset(fields)


def _tbx_terms(
    term_entry: ElementTree.Element[str],
    min_reliability: int,
) -> tuple[list[SeedTerm], str | None]:
    terms: list[SeedTerm] = []
    spanish_key: str | None = None
    for lang_set in term_entry.iter("langSet"):
        code = _lang_set_code(lang_set)
        language = _TBX_LANGS.get(code)
        if language is None:
            continue
        for tig in lang_set.iter("tig"):
            term_el = tig.find("term")
            if term_el is None or not (term_el.text and term_el.text.strip()):
                continue
            reliability = _tbx_reliability(tig)
            if reliability is not None and reliability < min_reliability:
                continue
            label = term_el.text.strip()
            status = _tbx_term_status(tig)
            terms.append(SeedTerm(language=language, label=label, term_status=status))
            if language is OutputLanguage.ES and status is TermStatus.PREFERRED and spanish_key is None:
                spanish_key = label
    return terms, spanish_key


def _lang_set_code(lang_set: ElementTree.Element[str]) -> str:
    # TBX carries the language on xml:lang; ElementTree expands the namespace.
    for key, value in lang_set.attrib.items():
        if key.endswith("lang"):
            return value.strip().lower()
    return ""


def _tbx_reliability(tig: ElementTree.Element[str]) -> int | None:
    for descrip in tig.iter("descrip"):
        if descrip.get("type") == "reliabilityCode" and descrip.text:
            try:
                return int(descrip.text.strip())
            except ValueError:
                return None
    return None


def _tbx_term_status(tig: ElementTree.Element[str]) -> TermStatus:
    for termnote in tig.iter("termNote"):
        if termnote.get("type") == "termType" and termnote.text:
            value = termnote.text.strip().lower()
            if value in ("fullform", "full-form", "main"):
                return TermStatus.PREFERRED
            if value in ("synonym", "shortform", "abbreviation", "variant"):
                return TermStatus.ADMITTED
    return TermStatus.ADMITTED


def parse_ubterm_csv(path: Path) -> tuple[SeedEntry, ...]:
    """Parse a UBTERM *Diccionari de fiscalitat* CSV export into seed entries.

    The expected CSV columns are ``es``, ``ca``, ``en`` (the trilingual
    fiscal entry) plus an optional ``definition_es`` gloss. The Spanish term
    is the key and a ``PREFERRED`` es term; the Catalan and English terms
    become ``PREFERRED`` terms in their languages; a Spanish definition, when
    present, seeds the es ``short_description`` (a source gloss, not
    fabricated prose).

    Args:
        path: The downloaded UBTERM CSV (CC BY 3.0).

    Returns:
        Typed :class:`SeedEntry` records, one per row with a Spanish term.

    Raises:
        SeedImportError: The file is missing or has no recognisable header.
    """
    import csv

    if not path.is_file():
        raise SeedImportError(f"{path}: UBTERM export not found")
    entries: list[SeedEntry] = []
    with path.open("r", encoding=UTF_8_ENCODING, newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "es" not in {name.strip() for name in reader.fieldnames}:
            raise SeedImportError(f"{path}: UBTERM CSV missing required 'es' column")
        for row in reader:
            entry = _ubterm_row(row)
            if entry is not None:
                entries.append(entry)
    return tuple(entries)


def _ubterm_row(row: dict[str, str | None]) -> SeedEntry | None:
    cleaned = {(key or "").strip(): (value or "").strip() for key, value in row.items()}
    spanish = cleaned.get("es", "")
    if not spanish:
        return None
    short_es = cleaned.get("definition_es") or None
    terms: list[SeedTerm] = [
        SeedTerm(
            language=OutputLanguage.ES,
            label=spanish,
            term_status=TermStatus.PREFERRED,
            short_description=short_es,
        ),
    ]
    for code, language in (("ca", OutputLanguage.CA), ("en", OutputLanguage.EN)):
        label = cleaned.get(code, "")
        if label:
            terms.append(SeedTerm(language=language, label=label, term_status=TermStatus.PREFERRED))
    return SeedEntry(
        source=SeedSource.UBTERM,
        spanish_key=spanish,
        terms=tuple(terms),
    )


# ---------------------------------------------------------------------------
# Mapper — seed entries onto existing concepts
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SeedApplyResult:
    """Outcome of applying a batch of seed entries to the Handbook."""

    matched_concepts: tuple[str, ...]
    unmatched_keys: tuple[str, ...]
    languages_added: int
    aliases_added: int
    written_paths: tuple[Path, ...] = field(default=())

    @property
    def applied_count(self) -> int:
        """How many concepts gained at least one seeded value."""
        return len(self.matched_concepts)


def apply_seed_entries(
    entries: tuple[SeedEntry, ...],
    *,
    concepts_dir: Path | None = None,
    today: date | None = None,
    write: bool = True,
) -> SeedApplyResult:
    """Map seed entries onto existing concepts and stamp provenance.

    Each entry is matched against an existing concept whose ``es``
    ``preferred`` term equals the entry's ``spanish_key`` (case-folded). On a
    match, every missing-language term is ADDED as an ``ADMITTED`` alias (or
    ``PREFERRED`` when the language has no preferred term yet), a missing
    ``short_description`` is seeded from the source gloss where one exists,
    and ``seed_provenance`` is stamped with the source's required attribution
    when the concept does not already carry provenance. Existing curated
    values are NEVER overwritten (the msgmerge PRESERVE contract): a seed only
    ever fills a gap.

    Lifecycle is untouched: a seeded ``draft`` stays ``draft`` (a seed never
    satisfies the approved-completeness gate, so it never auto-approves).

    After every write the whole tree is re-validated with
    :func:`default_handbook_validators`; a mutation that would invalidate the
    tree is refused.

    Args:
        entries: Typed seed entries (already licence-gated at parse time;
            the source attribution lookup re-asserts ingestibility).
        concepts_dir: Handbook concepts directory; defaults to the bundled
            tree.
        today: Override for the ``updated_at`` stamp (test determinism).
        write: When False, compute the result without writing (a dry-run
            used to report what a seed run WOULD do).

    Returns:
        A :class:`SeedApplyResult` recording matched concepts, unmatched
        keys, and the count of languages / aliases added.

    Raises:
        SeedLicenceError: An entry names a non-ingestible source.
    """
    target_dir = concepts_dir if concepts_dir is not None else terminology_concepts_dir()
    handbook = load_terminology_handbook(target_dir)
    by_preferred_es = _index_by_preferred_es(handbook)

    stamp = today if today is not None else _today()
    matched: list[str] = []
    unmatched: list[str] = []
    languages_added = 0
    aliases_added = 0
    written: list[Path] = []

    for entry in entries:
        attribution = source_attribution(entry.source)
        concept = by_preferred_es.get(entry.spanish_key.casefold())
        if concept is None:
            unmatched.append(entry.spanish_key)
            continue
        updated, langs_delta, alias_delta = _merge_entry_into_concept(concept, entry, attribution, stamp)
        if updated is concept:
            # Nothing new (everything the seed offers already present) — a no-op.
            matched.append(concept.concept_id)
            continue
        matched.append(concept.concept_id)
        languages_added += langs_delta
        aliases_added += alias_delta
        if write:
            written.append(_commit_seeded_concept(handbook, updated, target_dir))
        # Reflect the update in the in-memory index so a later entry targeting
        # the same concept sees the merged state.
        by_preferred_es[entry.spanish_key.casefold()] = updated

    return SeedApplyResult(
        matched_concepts=tuple(matched),
        unmatched_keys=tuple(unmatched),
        languages_added=languages_added,
        aliases_added=aliases_added,
        written_paths=tuple(written),
    )


def _index_by_preferred_es(handbook: TerminologyHandbook) -> dict[str, ConceptRecord]:
    index: dict[str, ConceptRecord] = {}
    for concept in handbook.concepts:
        es = _section(concept, OutputLanguage.ES)
        if es is None:
            continue
        for term in es.terms:
            if term.term_status is TermStatus.PREFERRED:
                index[term.label.casefold()] = concept
                break
    return index


def _merge_entry_into_concept(
    concept: ConceptRecord,
    entry: SeedEntry,
    attribution: str,
    stamp: date,
) -> tuple[ConceptRecord, int, int]:
    """Return ``(updated_concept, languages_added, aliases_added)``.

    Fills only gaps: a new language section is created with the seed's
    preferred term; an existing section gains the seed's terms as aliases (or
    its preferred term when none exists yet) and a short_description only when
    it currently has none. Returns ``concept`` unchanged when nothing is new.
    """
    sections = {section.language: section for section in concept.languages}
    languages_added = 0
    aliases_added = 0
    changed = False

    for language in _entry_languages(entry):
        seed_terms = [term for term in entry.terms if term.language is language]
        existing = sections.get(language)
        if existing is None:
            new_section, alias_delta = _new_section_from_seed(language, seed_terms)
            if new_section is None:
                continue
            sections[language] = new_section
            languages_added += 1
            aliases_added += alias_delta
            changed = True
        else:
            merged, alias_delta, section_changed = _augment_section(existing, seed_terms)
            if section_changed:
                sections[language] = merged
                aliases_added += alias_delta
                changed = True

    if not changed:
        return concept, 0, 0

    languages = _ordered_sections(concept, sections)
    update: dict[str, object] = {"languages": languages, "updated_at": stamp}
    if concept.seed_provenance is None:
        update["seed_provenance"] = SeedProvenance(
            source=entry.source.value,
            attribution=attribution,
            source_entry_id=entry.source_entry_id,
        )
    updated = concept.model_copy(update=update)
    return updated, languages_added, aliases_added


def _entry_languages(entry: SeedEntry) -> tuple[OutputLanguage, ...]:
    seen: list[OutputLanguage] = []
    for term in entry.terms:
        if term.language not in seen:
            seen.append(term.language)
    return tuple(seen)


def _new_section_from_seed(
    language: OutputLanguage,
    seed_terms: list[SeedTerm],
) -> tuple[LanguageSection | None, int]:
    if not seed_terms:
        return None, 0
    # The required short_description: use a source gloss when one exists,
    # otherwise the seed's preferred label as the minimal card text (a source
    # value, never invented prose). A bare placeholder keeps the section a
    # visible curation marker when neither exists.
    preferred = next((term for term in seed_terms if term.term_status is TermStatus.PREFERRED), seed_terms[0])
    short = next((term.short_description for term in seed_terms if term.short_description), None)
    short_description = short or preferred.label
    terms = tuple(TermSection(label=term.label, term_status=term.term_status) for term in _dedupe_terms(seed_terms))
    section = LanguageSection(
        language=language,
        short_description=short_description,
        terms=terms,
    )
    return section, len(terms)


def _augment_section(
    section: LanguageSection,
    seed_terms: list[SeedTerm],
) -> tuple[LanguageSection, int, bool]:
    existing_labels = {term.label.casefold() for term in section.terms}
    has_preferred = any(term.term_status is TermStatus.PREFERRED for term in section.terms)
    additions: list[TermSection] = []
    for term in _dedupe_terms(seed_terms):
        if term.label.casefold() in existing_labels:
            continue
        # A section without a preferred term may receive the seed's preferred;
        # otherwise the seed contributes an admitted alias (never a second
        # preferred — the schema forbids it).
        if term.term_status is TermStatus.PREFERRED and not has_preferred:
            status = TermStatus.PREFERRED
            has_preferred = True
        else:
            status = TermStatus.ADMITTED
        additions.append(TermSection(label=term.label, term_status=status))
        existing_labels.add(term.label.casefold())
    if not additions:
        return section, 0, False
    merged = section.model_copy(update={"terms": (*section.terms, *additions)})
    return merged, len(additions), True


def _dedupe_terms(seed_terms: list[SeedTerm]) -> list[SeedTerm]:
    seen: set[str] = set()
    unique: list[SeedTerm] = []
    for term in seed_terms:
        folded = term.label.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        unique.append(term)
    return unique


def _ordered_sections(
    concept: ConceptRecord,
    sections: dict[OutputLanguage, LanguageSection],
) -> tuple[LanguageSection, ...]:
    # Preserve the concept's existing section order; append genuinely new
    # languages in the canonical output-language order for stable serialisation.
    ordered: list[LanguageSection] = []
    for section in concept.languages:
        ordered.append(sections[section.language])
    existing_langs = {section.language for section in concept.languages}
    for language in OutputLanguage:
        if language not in existing_langs and language in sections:
            ordered.append(sections[language])
    return tuple(ordered)


def _commit_seeded_concept(
    handbook: TerminologyHandbook,
    new_concept: ConceptRecord,
    concepts_dir: Path,
) -> Path:
    # Re-validate the mutated record through the strict schema, then the whole
    # tree through the full gate inventory; refuse rather than write an
    # invalid tree (the curation write-path contract).
    revalidated = _revalidate_record(new_concept)
    by_id = dict(handbook.by_id)
    by_id[revalidated.concept_id] = revalidated
    candidate = TerminologyHandbook(concepts=tuple(by_id.values()))
    _validate_or_refuse(candidate)
    path = concepts_dir / f"{revalidated.concept_id}.toml"
    path.write_text(serialise_concept(revalidated), encoding=UTF_8_ENCODING, newline="\n")
    return path


def _revalidate_record(record: ConceptRecord) -> ConceptRecord:
    from pydantic import ValidationError

    try:
        return ConceptRecord.model_validate(record.model_dump(mode="python"))
    except (ValidationError, TerminologyValidationError) as exc:
        raise SeedImportError(f"refused: seed would invalidate the concept: {exc}") from exc


def _validate_or_refuse(handbook: TerminologyHandbook) -> None:
    try:
        for validate in default_handbook_validators():
            validate(handbook)
    except TerminologyValidationError as exc:
        raise SeedImportError(f"refused: seed would invalidate the handbook: {exc}") from exc


def _section(concept: ConceptRecord, language: OutputLanguage) -> LanguageSection | None:
    for section in concept.languages:
        if section.language is language:
            return section
    return None


def _today() -> date:
    from cadrumo.core.time.clock import now

    return now().date()
