"""Real-behaviour conformance for the concept-card search-record emitter (ADR D4).

The emitter loads the REAL bundled Terminology Handbook (the committed
authoring tree under ``src/aeat/_data/terminology/concepts/``, run through
the loader's full ADR-D8 gate inventory) and projects one
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

from aeat.core.external_constants import OutputLanguage
from aeat.terminology import (
    ConceptLifecycle,
    TermStatus,
    load_terminology_handbook,
    terminology_concepts_dir,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_FOUR_LANGUAGES = frozenset(OutputLanguage)


@pytest.fixture(scope="module")
def projection() -> tuple[tuple[object, ...], object]:
    """Project the real bundled Handbook into cards once for the module."""
    from dev.docs.terminology._concept_cards import project_concept_cards

    return project_concept_cards()


def _bundled_concept_ids() -> set[str]:
    """The concept ids in the bundled authoring tree, read independently."""
    handbook = load_terminology_handbook()
    return {concept.concept_id for concept in handbook.concepts}


def test_one_card_per_bundled_concept(
    projection: tuple[tuple[object, ...], object],
) -> None:
    """Exact parity: one card per concept in the bundled Handbook.

    The card id set must equal the independently-loaded concept id set --
    every concept projects (drafts included), none is dropped or duplicated.
    """
    cards, _stats = projection
    card_ids = {card.concept_id for card in cards}  # type: ignore[attr-defined]
    bundled = _bundled_concept_ids()

    assert card_ids == bundled, (
        "concept cards diverge from the bundled Handbook:\n"
        f"  missing: {sorted(bundled - card_ids)}\n"
        f"  surplus: {sorted(card_ids - bundled)}"
    )
    assert len(cards) == len(card_ids)


def test_card_count_matches_curation_split(
    projection: tuple[tuple[object, ...], object],
) -> None:
    """The approved/draft split equals the Handbook's own lifecycle counts.

    Independently re-derived from the loaded Handbook so the stats are an
    honest projection of the source lifecycle, not a hard-coded number.
    """
    cards, stats = projection
    handbook = load_terminology_handbook()
    approved = sum(1 for c in handbook.concepts if c.lifecycle is ConceptLifecycle.APPROVED)
    draft = sum(1 for c in handbook.concepts if c.lifecycle is ConceptLifecycle.DRAFT)

    assert stats.total_cards == len(handbook.concepts)  # type: ignore[attr-defined]
    assert stats.approved_cards == approved  # type: ignore[attr-defined]
    assert stats.draft_cards == draft  # type: ignore[attr-defined]
    # Sanity: drafts are flagged, not silently approved.
    flagged_drafts = [c for c in cards if c.lifecycle is ConceptLifecycle.DRAFT]  # type: ignore[attr-defined]
    assert len(flagged_drafts) == draft
    for card in flagged_drafts:
        assert card.is_approved is False  # type: ignore[attr-defined]


def test_approved_prorrata_card_is_fully_populated(
    projection: tuple[tuple[object, ...], object],
) -> None:
    """The approved ``prorrata`` card carries its full four-language surface.

    Asserts the worked example from the ADR end-to-end: an approved concept
    surfaces es+en+ca+hu short_descriptions, its alias set (with the admitted
    synonyms the palette expands), and resolvable legal-grounding links.
    """
    cards, _stats = projection
    prorrata = next((c for c in cards if c.concept_id == "prorrata"), None)  # type: ignore[attr-defined]
    assert prorrata is not None, "expected the approved 'prorrata' concept card"

    # Four-language short_descriptions (the card text).
    assert set(prorrata.descriptions) == _FOUR_LANGUAGES, (  # type: ignore[attr-defined]
        f"prorrata missing short_descriptions in: {_FOUR_LANGUAGES - set(prorrata.descriptions)}"  # type: ignore[attr-defined]
    )
    for language in _FOUR_LANGUAGES:
        assert prorrata.descriptions[language].strip()  # type: ignore[attr-defined]

    # Alias set: the admitted English "pro rata" and Spanish "prorrateo" the
    # palette must match cross-vocabulary.
    labels_by_language = {
        (alias.language, alias.label): alias.term_status  # type: ignore[attr-defined]
        for alias in prorrata.aliases  # type: ignore[attr-defined]
    }
    assert (OutputLanguage.EN, "pro rata") in labels_by_language
    assert labels_by_language[(OutputLanguage.EN, "pro rata")] is TermStatus.PREFERRED
    assert (OutputLanguage.ES, "prorrateo") in labels_by_language
    assert labels_by_language[(OutputLanguage.ES, "prorrateo")] is TermStatus.ADMITTED

    # Legal-grounding links resolve to BOE permalinks.
    refs = {link.legal_ref for link in prorrata.legal_links}  # type: ignore[attr-defined]
    assert {"ley-37-1992:art-102", "ley-37-1992:art-104"}.issubset(refs)
    for link in prorrata.legal_links:  # type: ignore[attr-defined]
        assert link.permalink.startswith("https://www.boe.es/")
        if link.corpus_ref is not None:
            assert link.corpus_ref.endswith(".html#a102") or link.corpus_ref.endswith(".html#a104")
    assert prorrata.is_approved is True  # type: ignore[attr-defined]


def test_every_card_has_a_spanish_short_description(
    projection: tuple[tuple[object, ...], object],
) -> None:
    """Spanish is the invariant: every card (draft or approved) has an es card text.

    The Handbook schema requires a ``short_description`` on every authored
    language section and an ``es`` section is the floor, so every projected
    card must carry an ``es`` description -- the minimum a palette card needs.
    """
    cards, _stats = projection
    for card in cards:
        assert OutputLanguage.ES in card.descriptions, f"{card.concept_id}: no es short_description"  # type: ignore[attr-defined]
        assert card.descriptions[OutputLanguage.ES].strip()  # type: ignore[attr-defined]
        assert set(card.descriptions).issubset(_FOUR_LANGUAGES)  # type: ignore[attr-defined]


def test_all_legal_refs_resolve_against_the_real_catalogue(
    projection: tuple[tuple[object, ...], object],
) -> None:
    """No card ships a dead legal link: the real-catalogue run reports zero unresolved.

    The Handbook loader's ``legal_refs_resolve_validator`` gates this on
    load, so an unresolved ref against the same catalogue is a contradiction.
    """
    _cards, stats = projection
    assert stats.unresolved_legal_refs == (), (  # type: ignore[attr-defined]
        f"legal_refs failed to resolve against the bundled catalogue: {stats.unresolved_legal_refs}"  # type: ignore[attr-defined]
    )


def test_legal_link_resolution_reports_a_missing_ref() -> None:
    """Anti-tautology: a catalogue MISSING a concept's legal_ref reports it unresolved.

    Drives the emitter with a synthetic catalogue that omits ``prorrata``'s
    ``ley-37-1992:art-104`` ref. The emitter must NOT fabricate a link for the
    missing ref; it must surface the id in ``unresolved_legal_refs`` and emit
    only the resolved one. If this test ever passes with both links present,
    the resolver is silently inventing targets.
    """
    from dev.docs.terminology._concept_cards import project_concept_cards

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
    projection: tuple[tuple[object, ...], object],
) -> None:
    """The strict-frozen contract: a projected card rejects mutation."""
    from pydantic import ValidationError

    cards, _stats = projection
    with pytest.raises(ValidationError):
        cards[0].lifecycle = ConceptLifecycle.RETIRED  # type: ignore[attr-defined,misc]
