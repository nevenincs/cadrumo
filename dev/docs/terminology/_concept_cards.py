"""Concept-card projection compiler for the docs search index.

Projects every curated :class:`~dev.docs.terminology_handbook.schema.ConceptRecord` from the
Terminology Handbook into a strict
:class:`~dev.docs.terminology._concept_cards.ConceptCardRecord` -- the
first-class "term card" the Ctrl-K command palette surfaces ahead of nav
titles and full text. A reader typing "pro rata" or "prorrata" gets the
concept's meaning (per-language short_description and definition), its
four-language alias set, and resolvable links to the legal grounding the
code itself is grounded against.

The card record extends the shared
:class:`~dev.docs.terminology.search_record.SearchRecordBase` authored by
the sibling casilla-projection compiler, reusing the ``kind`` discriminator
(``SearchRecordKind.CONCEPT``) and the four-language localised-description
map (here the per-language ``short_description``).

Legal grounding (the calculation-grounding contract)
----------------------------------------------------
Each concept's ``legal_refs`` are resolved through the SAME legal
catalogue the registry calculation engine grounds against -- the validated
authority's ``catalogues.legal`` mapping -- into typed
:class:`~dev.docs.terminology._concept_cards.LegalGroundingLink` entries
carrying the BOE permalink and the anchored corpus reference. A ``legal_ref``
that does not resolve is reported, never echoed as a dead id: the Handbook
loader's ``legal_refs_resolve_validator`` already gates this on load, so an
unresolved ref here is a build-time contradiction worth surfacing.

The Handbook is consumed AS A WHOLE including ``draft`` concepts: the
``lifecycle`` rides onto every card so the downstream Pagefind injection can
choose to surface approved-only cards as first-class results while flagging
drafts.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core.concept_lifecycle import ConceptLifecycle
from cadrumo.core.external_constants import OutputLanguage

from ..terminology_handbook.enums import ConceptDomain, TermStatus
from ..terminology_handbook.loader import TerminologyHandbook, load_terminology_handbook
from ..terminology_handbook.schema import ConceptRecord
from ..terminology_handbook.validators import default_handbook_validators
from .search_record import SearchRecordBase, SearchRecordKind

__all__ = [
    "ConceptCardProjectionStats",
    "ConceptCardRecord",
    "LegalGroundingLink",
    "LocalisedDefinition",
    "TermAlias",
    "project_concept_cards",
]

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class LegalGroundingLink(BaseModel):
    """A resolved legal-grounding link for a concept card.

    The ``legal_ref`` id resolved against the legal catalogue into a
    BOE permalink plus the anchored corpus reference -- the same grounding
    the calculation engine cites. Carries the catalogue notes (the human
    summary of the provision) so the palette card can render a meaningful
    label rather than a bare id.
    """

    model_config = _STRICT_FROZEN

    legal_ref: str = Field(min_length=1, max_length=128)
    permalink: str = Field(min_length=1, max_length=512)
    corpus_ref: str | None = Field(default=None, min_length=1, max_length=512)
    document_id: str | None = Field(default=None, min_length=1, max_length=64)
    notes: str | None = Field(default=None, min_length=1, max_length=2000)


class LocalisedDefinition(BaseModel):
    """A concept's longer definition in one language.

    ``short_description`` is the card/tooltip text (always present on every
    authored language section); ``definition`` is the longer grounded prose
    where authored (es always, others where curated).
    """

    model_config = _STRICT_FROZEN

    language: OutputLanguage
    short_description: str = Field(min_length=1, max_length=240)
    definition: str | None = Field(default=None, min_length=1, max_length=2000)
    scope_note: str | None = Field(default=None, min_length=1, max_length=1000)


class TermAlias(BaseModel):
    """One alias of a concept in one language.

    Carries the surface ``label``, its normative ``term_status``, the
    ``language`` it belongs to, and the unaccented / misspelt
    ``hidden_search_forms`` that match in search but never render -- the
    declarative cross-vocabulary synonym surface the palette expands.
    """

    model_config = _STRICT_FROZEN

    language: OutputLanguage
    label: str = Field(min_length=1, max_length=160)
    term_status: TermStatus
    hidden_search_forms: tuple[str, ...] = ()


class ConceptCardRecord(SearchRecordBase):
    """A first-class search record for one Handbook concept.

    The ``descriptions`` map (inherited) carries the per-language
    ``short_description`` -- the card text the palette renders. The richer
    per-language definitions, the four-language alias set, and the resolved
    legal-grounding links ride alongside. ``lifecycle`` lets the downstream
    Pagefind injection surface approved-only cards first-class while flagging
    drafts.
    """

    kind: SearchRecordKind = SearchRecordKind.CONCEPT
    #: The immutable Spanish-stem concept id (e.g. ``prorrata``).
    concept_id: str = Field(min_length=2, max_length=64)
    domain: ConceptDomain
    lifecycle: ConceptLifecycle
    #: Per-language longer definitions, one per authored language section.
    definitions: tuple[LocalisedDefinition, ...] = Field(min_length=1)
    #: Every alias across every language (preferred, admitted, deprecated,
    #: forbidden) -- the declarative four-language synonym surface.
    aliases: tuple[TermAlias, ...] = Field(default=())
    #: Resolved legal-grounding links (may be empty for a concept with no
    #: ``legal_refs`` -- e.g. a CLI-verb or period concept).
    legal_links: tuple[LegalGroundingLink, ...] = Field(default=())
    #: Shallow SKOS relations carried for palette cross-navigation.
    broader: tuple[str, ...] = ()
    related: tuple[str, ...] = ()

    @property
    def is_approved(self) -> bool:
        """Whether the concept is curation-complete and shippable first-class."""
        return self.lifecycle is ConceptLifecycle.APPROVED


@dataclass(frozen=True, slots=True)
class ConceptCardProjectionStats:
    """Counts for one concept-card projection run."""

    total_cards: int
    approved_cards: int
    draft_cards: int
    cards_with_legal_links: int
    unresolved_legal_refs: tuple[str, ...]


def project_concept_cards(
    handbook: TerminologyHandbook | None = None,
    *,
    legal_catalogue: object | None = None,
) -> tuple[tuple[ConceptCardRecord, ...], ConceptCardProjectionStats]:
    """Project every Handbook concept into a search card.

    Args:
        handbook: The compiled Handbook to project; defaults to a fresh
            validated load of the bundled authoring tree (the loader's full
            gate inventory runs, so a malformed Handbook fails here rather
            than shipping a half-mapped card set). Injectable so a test can
            drive a narrowed handbook deterministically.
        legal_catalogue: A mapping of legal-ref id to a catalogue entry
            exposing ``permalink`` / ``corpus_ref`` / ``document_id`` /
            ``notes``. Defaults to the bundled registry authority's legal
            catalogue -- the same catalogue the calculation engine grounds
            against. Injectable for tests.

    Returns:
        A ``(cards, stats)`` pair: cards sorted by ``concept_id`` and the
        projection counts (approved / draft split, legal-link coverage, and
        any legal_ref that failed to resolve).
    """
    resolved_handbook = handbook if handbook is not None else _load_validated_handbook()
    catalogue = legal_catalogue if legal_catalogue is not None else _bundled_legal_catalogue()

    cards: list[ConceptCardRecord] = []
    approved = 0
    draft = 0
    with_links = 0
    unresolved: list[str] = []

    for concept in sorted(resolved_handbook.concepts, key=lambda c: c.concept_id):
        legal_links, missing = _resolve_legal_links(concept, catalogue)
        unresolved.extend(missing)
        card = _build_card(concept, legal_links)
        cards.append(card)
        if card.lifecycle is ConceptLifecycle.APPROVED:
            approved += 1
        elif card.lifecycle is ConceptLifecycle.DRAFT:
            draft += 1
        if legal_links:
            with_links += 1

    stats = ConceptCardProjectionStats(
        total_cards=len(cards),
        approved_cards=approved,
        draft_cards=draft,
        cards_with_legal_links=with_links,
        unresolved_legal_refs=tuple(sorted(set(unresolved))),
    )
    return tuple(cards), stats


def _build_card(
    concept: ConceptRecord,
    legal_links: tuple[LegalGroundingLink, ...],
) -> ConceptCardRecord:
    descriptions: dict[OutputLanguage, str] = {}
    definitions: list[LocalisedDefinition] = []
    aliases: list[TermAlias] = []
    for section in concept.languages:
        descriptions[section.language] = section.short_description
        definitions.append(
            LocalisedDefinition(
                language=section.language,
                short_description=section.short_description,
                definition=section.definition,
                scope_note=section.scope_note,
            ),
        )
        for term in section.terms:
            aliases.append(
                TermAlias(
                    language=section.language,
                    label=term.label,
                    term_status=term.term_status,
                    hidden_search_forms=tuple(term.hidden_search_forms),
                ),
            )
    return ConceptCardRecord(
        kind=SearchRecordKind.CONCEPT,
        descriptions=descriptions,
        concept_id=concept.concept_id,
        domain=concept.domain,
        lifecycle=concept.lifecycle,
        definitions=tuple(definitions),
        aliases=tuple(aliases),
        legal_links=legal_links,
        broader=tuple(concept.broader),
        related=tuple(concept.related),
    )


def _resolve_legal_links(
    concept: ConceptRecord,
    catalogue: object,
) -> tuple[tuple[LegalGroundingLink, ...], list[str]]:
    """Resolve a concept's ``legal_refs`` into typed grounding links.

    Returns the resolved links plus the list of ``legal_ref`` ids that did
    not resolve in the catalogue (reported by the caller, never shipped as a
    dead link).
    """
    links: list[LegalGroundingLink] = []
    missing: list[str] = []
    for ref in concept.legal_refs:
        entry = _catalogue_get(catalogue, ref)
        if entry is None:
            missing.append(ref)
            continue
        permalink = _attr_str(entry, "permalink")
        if not permalink:
            missing.append(ref)
            continue
        links.append(
            LegalGroundingLink(
                legal_ref=ref,
                permalink=permalink,
                corpus_ref=_attr_str(entry, "corpus_ref") or None,
                document_id=_attr_str(entry, "document_id") or None,
                notes=_attr_str(entry, "notes") or None,
            ),
        )
    return tuple(links), missing


def _catalogue_get(catalogue: object, ref: str) -> object | None:
    getter = getattr(catalogue, "get", None)
    if callable(getter):
        return getter(ref)
    return None


def _attr_str(entry: object, name: str) -> str:
    value = getattr(entry, name, None)
    if value is None:
        return ""
    return str(value).strip()


def _load_validated_handbook() -> TerminologyHandbook:
    return load_terminology_handbook(validators=default_handbook_validators())


def _bundled_legal_catalogue() -> object:
    from cadrumo.domain.calculations.registry.authority import bundled_authority

    return bundled_authority().catalogues.legal
