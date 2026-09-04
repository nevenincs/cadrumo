"""Real-behaviour conformance for the concept-card search-record emitter.

The emitter loads the REAL bundled Terminology Handbook (the committed
authoring tree under ``src/cadrumo/_data/terminology/concepts/``, run through
the loader's full gate inventory) and projects one
:class:`~dev.docs.terminology._concept_cards.ConceptCardRecord` per concept.
These gates assert one card per concept, that an approved concept carries its
four-language short_descriptions / alias set / resolvable legal-grounding
links, and that draft concepts are emitted but lifecycle-flagged.

No mocks: the Handbook load is real and the legal catalogue is the bundled
registry authority's catalogue (the same one the calculation engine grounds
against). An anti-tautology proof drives a synthetic catalogue that is MISSING
a concept's ``legal_ref`` and asserts the emitter reports it as unresolved
rather than fabricating a dead link.
"""

from __future__ import annotations

import pytest

from cadrumo.core.concept_lifecycle import ConceptLifecycle
from cadrumo.core.external_constants import OutputLanguage

from ...terminology_handbook.enums import TermStatus
from ...terminology_handbook.loader import load_terminology_handbook, terminology_concepts_dir
from .._concept_cards import ConceptCardProjectionStats, ConceptCardRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_FOUR_LANGUAGES = frozenset(OutputLanguage)


@pytest.fixture(scope="module")
def projection() -> tuple[tuple[ConceptCardRecord, ...], ConceptCardProjectionStats]:
    """Project the real bundled Handbook into cards once for the module."""
    from .._concept_cards import project_concept_cards

    return project_concept_cards()


def _bundled_concept_ids() -> set[str]:
    """The concept ids in the bundled authoring tree, read independently."""
    handbook = load_terminology_handbook()
    return {concept.concept_id for concept in handbook.concepts}


def test_one_card_per_bundled_concept(
    projection: tuple[tuple[ConceptCardRecord, ...], ConceptCardProjectionStats],
) -> None:
    """Exact parity: one card per concept in the bundled Handbook.

    The card id set must equal the independently-loaded concept id set --
    every concept projects (drafts included), none is dropped or duplicated.
    """
    cards, _stats = projection
    card_ids = {card.concept_id for card in cards}
    bundled = _bundled_concept_ids()

    assert card_ids == bundled, (
        "concept cards diverge from the bundled Handbook:\n"
        f"  missing: {sorted(bundled - card_ids)}\n"
        f"  surplus: {sorted(card_ids - bundled)}"
    )
    assert len(cards) == len(card_ids)


def test_card_count_matches_curation_split(
    projection: tuple[tuple[ConceptCardRecord, ...], ConceptCardProjectionStats],
) -> None:
    """The approved/draft split equals the Handbook's own lifecycle counts.

    Independently re-derived from the loaded Handbook so the stats are an
    honest projection of the source lifecycle, not a hard-coded number.
    """
    cards, stats = projection
    handbook = load_terminology_handbook()
    approved = sum(1 for c in handbook.concepts if c.lifecycle is ConceptLifecycle.APPROVED)
    draft = sum(1 for c in handbook.concepts if c.lifecycle is ConceptLifecycle.DRAFT)

    assert stats.total_cards == len(handbook.concepts)
    assert stats.approved_cards == approved
    assert stats.draft_cards == draft
    # Sanity: drafts are flagged, not silently approved.
    flagged_drafts = [c for c in cards if c.lifecycle is ConceptLifecycle.DRAFT]
    assert len(flagged_drafts) == draft
    for card in flagged_drafts:
        assert card.is_approved is False


def test_approved_prorrata_card_is_fully_populated(
    projection: tuple[tuple[ConceptCardRecord, ...], ConceptCardProjectionStats],
) -> None:
    """The approved ``prorrata`` card carries its full four-language surface.

    Asserts the worked example end-to-end: an approved concept
    surfaces es+en+ca+hu short_descriptions, its alias set (with the admitted
    synonyms the palette expands), and resolvable legal-grounding links.
    """
    cards, _stats = projection
    prorrata = next((c for c in cards if c.concept_id == "prorrata"), None)
    assert prorrata is not None, "expected the approved 'prorrata' concept card"

    # Four-language short_descriptions (the card text).
    assert set(prorrata.descriptions) == _FOUR_LANGUAGES, (
        f"prorrata missing short_descriptions in: {_FOUR_LANGUAGES - set(prorrata.descriptions)}"
    )
    for language in _FOUR_LANGUAGES:
        assert prorrata.descriptions[language].strip()

    # Alias set: the admitted English "pro rata" and Spanish "prorrateo" the
    # palette must match cross-vocabulary.
    labels_by_language = {(alias.language, alias.label): alias.term_status for alias in prorrata.aliases}
    assert (OutputLanguage.EN, "pro rata") in labels_by_language
    assert labels_by_language[(OutputLanguage.EN, "pro rata")] is TermStatus.PREFERRED
    assert (OutputLanguage.ES, "prorrateo") in labels_by_language
    assert labels_by_language[(OutputLanguage.ES, "prorrateo")] is TermStatus.ADMITTED

    # Legal-grounding links resolve to BOE permalinks.
    refs = {link.legal_ref for link in prorrata.legal_links}
    assert {"ley-37-1992:art-102", "ley-37-1992:art-104"}.issubset(refs)
    for link in prorrata.legal_links:
        assert link.permalink.startswith("https://www.boe.es/")
        if link.corpus_ref is not None:
            assert link.corpus_ref.endswith(".html#a102") or link.corpus_ref.endswith(".html#a104")
    assert prorrata.is_approved is True


def test_self_hosted_architectural_vocabulary_is_deprecated_not_glossary_facing(
    projection: tuple[tuple[ConceptCardRecord, ...], ConceptCardProjectionStats],
) -> None:
    """These self-hosted architecture terms project to cards but are DEPRECATED.

    These concepts document the search/calculation machinery itself, not a
    taxpayer-facing AEAT surface, so the glossary-enrolment policy excludes
    them from the APPROVED tier: they stay enrolled and resolvable for the
    dev/agent RAG
    (they still project to cards, with their content intact) but are
    `deprecated`, so the approved-only glossary and the shipped Pagefind
    injection drop them.
    """
    required = {
        "manual-terminologia": "Terminology Handbook",
        "barrido-rag": "RAG sweep",
        "proyeccion-busqueda": "search projection",
        "mapa-relevancia": "relevance mapping",
        "gancho-preprocesado": "preprocess hook",
        "depuracion-licencia": "licence laundering",
        "clases-registro-busqueda": "search record kinds",
    }
    cards, _stats = projection
    by_id = {card.concept_id: card for card in cards}

    assert required.keys() <= by_id.keys()
    for concept_id, english_label in required.items():
        card = by_id[concept_id]
        # Internal machinery: enrolled and projected, but NOT taxpayer-facing.
        assert card.is_approved is False
        assert card.lifecycle is ConceptLifecycle.DEPRECATED
        assert OutputLanguage.ES in card.descriptions
        assert OutputLanguage.EN in card.descriptions
        aliases = {(alias.language, alias.label) for alias in card.aliases}
        assert (OutputLanguage.EN, english_label) in aliases
        es_definition = next(
            definition.definition for definition in card.definitions if definition.language is OutputLanguage.ES
        )
        assert es_definition


def test_every_card_has_a_spanish_short_description(
    projection: tuple[tuple[ConceptCardRecord, ...], ConceptCardProjectionStats],
) -> None:
    """Spanish is the invariant: every card (draft or approved) has an es card text.

    The Handbook schema requires a ``short_description`` on every authored
    language section and an ``es`` section is the floor, so every projected
    card must carry an ``es`` description -- the minimum a palette card needs.
    """
    cards, _stats = projection
    for card in cards:
        assert OutputLanguage.ES in card.descriptions, f"{card.concept_id}: no es short_description"
        assert card.descriptions[OutputLanguage.ES].strip()
        assert set(card.descriptions).issubset(_FOUR_LANGUAGES)


def test_all_legal_refs_resolve_against_the_real_catalogue(
    projection: tuple[tuple[ConceptCardRecord, ...], ConceptCardProjectionStats],
) -> None:
    """No card ships a dead legal link: the real-catalogue run reports zero unresolved.

    The Handbook loader's ``legal_refs_resolve_validator`` gates this on
    load, so an unresolved ref against the same catalogue is a contradiction.
    """
    _cards, stats = projection
    assert stats.unresolved_legal_refs == (), (
        f"legal_refs failed to resolve against the bundled catalogue: {stats.unresolved_legal_refs}"
    )


def test_legal_link_resolution_reports_a_missing_ref() -> None:
    """Anti-tautology: a catalogue MISSING a concept's legal_ref reports it unresolved.

    Drives the emitter with a synthetic catalogue that omits ``prorrata``'s
    ``ley-37-1992:art-104`` ref. The emitter must NOT fabricate a link for the
    missing ref; it must surface the id in ``unresolved_legal_refs`` and emit
    only the resolved one. If this test ever passes with both links present,
    the resolver is silently inventing targets.
    """
    from .._concept_cards import project_concept_cards

    handbook = load_terminology_handbook(terminology_concepts_dir())

    class _Entry:
        def __init__(self, permalink: str) -> None:
            self.permalink = permalink
            self.corpus_ref = None
            self.document_id = None
            self.notes = None

    # A catalogue that resolves art-102 but NOT art-104 (the omission under test).
    synthetic = {
        "ley-37-1992:art-102": _Entry("https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a102"),
    }

    cards, stats = project_concept_cards(handbook, legal_catalogue=synthetic)
    prorrata = next(c for c in cards if c.concept_id == "prorrata")

    resolved_refs = {link.legal_ref for link in prorrata.legal_links}
    assert resolved_refs == {"ley-37-1992:art-102"}, (
        "expected only the resolvable ref on the card; the missing ref must not be fabricated"
    )
    assert "ley-37-1992:art-104" in stats.unresolved_legal_refs


def test_card_records_are_frozen(
    projection: tuple[tuple[ConceptCardRecord, ...], ConceptCardProjectionStats],
) -> None:
    """The strict-frozen contract: a projected card rejects mutation."""
    from pydantic import ValidationError

    cards, _stats = projection
    with pytest.raises(ValidationError):
        cards[0].lifecycle = ConceptLifecycle.RETIRED  # type: ignore[misc]
