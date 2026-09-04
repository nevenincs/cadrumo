"""Glossary deep-link anchor parity for the search injection.

Every injected concept search record deep-links to its glossary definition by
the headword-derived anchor Sphinx generates for the ``glossary`` directive
(e.g. the headword "VIES" -> ``term-VIES``), NOT by the concept id
(``term-vies``), which only coincides when the id equals the headword slug.

These gates prove the two stay in lock-step, so a concept result lands on its
definition rather than the glossary top:

- :func:`test_anchor_matches_sphinx_ground_truth` locks
  :func:`glossary_term_anchor` against headword/anchor pairs taken verbatim from
  the rendered glossary, so a drift in the slug algorithm fails loudly.
- :func:`test_injected_concept_anchors_resolve_in_glossary` proves every
  approved concept's injected anchor matches a real glossary term line, so a
  concept whose headword and id diverge can never again ship a dead deep link.
- :func:`test_glossary_renders_concept_legal_grounding` proves the D6
  destination-grounding contract for the concept kind (the analogue of the
  casilla ``test_destination_renders_record_grounding`` gate): a concept card
  carrying ``legal_refs`` whose glossary entry renders none of them is a
  failure.
"""

from __future__ import annotations

import re

import pytest

from ..._paths import REPO_ROOT
from ..glossary_reference import render_glossary
from ..pagefind_inject import _SUMMARY_MAX_CHARS, _summary_for
from ..terminology._concept_cards import project_concept_cards
from ..terminology._glossary_anchor import glossary_term_anchor
from ..terminology.search_record import SearchRecordKind
from ..terminology.unified_record import to_search_record

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT


def _load_handbook():
    from ..terminology_handbook import load_terminology_handbook

    return load_terminology_handbook()


def _glossary_term_anchors() -> set[str]:
    """The anchor set the rendered glossary's term lines will generate.

    A glossary entry's term lines are indented exactly three spaces; its
    definition and grounding lines are indented six. Each surviving term line
    becomes a Sphinx ``:term:`` anchor, so projecting every three-space line
    through :func:`glossary_term_anchor` yields the page's live anchor set.
    """
    rst, _ = render_glossary(_REPO_ROOT, _load_handbook())
    anchors: set[str] = set()
    for line in rst.splitlines():
        if line.startswith("   ") and not line.startswith("      "):
            term = line.strip()
            if term:
                anchors.add(glossary_term_anchor(term))
    return anchors


@pytest.mark.parametrize(
    ("headword", "anchor"),
    [
        ("VIES", "term-VIES"),
        ("IVA", "term-IVA"),
        ("casilla", "term-casilla"),
        ("recargo de equivalencia", "term-recargo-de-equivalencia"),
        ("Impuesto sobre el Valor Añadido", "term-Impuesto-sobre-el-Valor-Anadido"),
        ("Número de Identificación Fiscal", "term-Numero-de-Identificacion-Fiscal"),
        ("autoliquidación de IVA", "term-autoliquidacion-de-IVA"),
        ("sede electrónica", "term-sede-electronica"),
        ("prorrata especial", "term-prorrata-especial"),
    ],
)
def test_anchor_matches_sphinx_ground_truth(headword: str, anchor: str) -> None:
    """The slug helper reproduces the ids Sphinx renders in the live glossary."""
    assert glossary_term_anchor(headword) == anchor


#: A grounding line reads ``Legal basis: `<citation> <url>`__ (``<ref>``)``: the
#: citation carries the meaning and the catalogue id trails it, demoted but
#: still present so the grounding stays traceable to the exact row. This gate
#: reads the id, which is the thing a concept's ``legal_refs`` must match.
_LEGAL_BASIS_RE = re.compile(r"\* Legal basis: `[^`]+ <[^>]+>`__ \(``(?P<ref>[^`]+)``\)")


def _rendered_legal_refs_by_anchor() -> dict[str, set[str]]:
    """Map each glossary entry's term anchor to the legal refs its entry renders.

    Parses the generated glossary RST into entries -- a run of three-space term
    lines followed by their six-space body / grounding lines -- and records, per
    entry, the ``Legal basis`` refs it renders against every term anchor the
    entry claims. This is the concept-kind analogue of the casilla reference's
    ``rendered_legal_refs`` map, read from the real generator output.
    """
    rst, _ = render_glossary(_REPO_ROOT, _load_handbook())
    by_anchor: dict[str, set[str]] = {}
    entry_anchors: list[str] = []
    entry_refs: set[str] = set()
    prev_was_term = False
    started = False

    def _flush() -> None:
        for anchor in entry_anchors:
            by_anchor.setdefault(anchor, set()).update(entry_refs)

    for line in rst.splitlines():
        if not started:
            # Skip the RST header block; entries begin after the directive.
            if line.strip() == ":sorted:":
                started = True
            continue
        is_term = line.startswith("   ") and not line.startswith("      ")
        if is_term:
            if not prev_was_term:
                _flush()
                entry_anchors = []
                entry_refs = set()
            entry_anchors.append(glossary_term_anchor(line.strip()))
            prev_was_term = True
            continue
        prev_was_term = False
        match = _LEGAL_BASIS_RE.search(line)
        if match:
            entry_refs.add(match.group("ref").strip())
    _flush()
    return by_anchor


def test_glossary_renders_concept_legal_grounding() -> None:
    """D6: every concept's ``legal_refs`` render on its glossary entry.

    The concept-kind analogue of the casilla
    ``test_destination_renders_record_grounding`` gate. A concept card carrying
    ``legal_refs`` whose glossary entry renders none of them is a
    destination-grounding breach. The glossary renders each resolvable ref as a
    ``Legal basis`` BOE permalink line on the concept's own entry, so the
    destination is at parity with what the card carries. The assertion runs
    against the real generator output and the real registry-resolved refs -- no
    injected text -- so it cannot pass tautologically.
    """
    rendered_by_anchor = _rendered_legal_refs_by_anchor()
    assert rendered_by_anchor, "glossary rendered no legal grounding"

    cards, _ = project_concept_cards()
    approved = [card for card in cards if card.is_approved]
    assert approved, "no approved concept cards to inject"

    ungrounded: list[str] = []
    grounded = 0
    for card in approved:
        record = to_search_record(card)
        if record.kind is not SearchRecordKind.CONCEPT or not record.metadata.legal_refs:
            continue
        anchor = record.target.split("#", 1)[1]
        rendered = rendered_by_anchor.get(anchor)
        if rendered is None or not set(record.metadata.legal_refs).issubset(rendered):
            ungrounded.append(f"{record.title} ({anchor}): refs {record.metadata.legal_refs} not rendered")
        else:
            grounded += 1

    assert grounded > 0, "no grounded concept entries — the projection carries no legal_refs?"
    assert not ungrounded, "concept entries dropping their legal grounding (D6 breach):\n" + "\n".join(
        f"  - {u}" for u in ungrounded[:40]
    )


def test_injected_concept_anchors_resolve_in_glossary() -> None:
    """Every injected concept deep link targets a real glossary term anchor."""
    glossary_anchors = _glossary_term_anchors()
    assert glossary_anchors, "glossary rendered no term anchors"

    cards, _ = project_concept_cards()
    approved = [card for card in cards if card.is_approved]
    assert approved, "no approved concept cards to inject"

    dead: list[tuple[str, str]] = []
    for card in approved:
        record = to_search_record(card)
        if record.kind is not SearchRecordKind.CONCEPT:
            continue
        anchor = record.target.split("#", 1)[1]
        if anchor not in glossary_anchors:
            dead.append((record.title, anchor))

    assert not dead, f"injected concept anchors with no glossary term line: {dead}"


def test_card_summary_is_clean_single_language() -> None:
    """Every injected card's display summary is one clean line, not the blob.

    The searchable record content folds the title, every alias, and all four
    language descriptions into one string so any surface form matches. That
    string must never reach the operator's eye: the card shows ``_summary_for``,
    a single-language (English, falling back to Spanish) one-liner. This gate
    proves the summary is bounded, single-line, and a real description - never
    the multilingual token soup the palette used to render.
    """
    cards, _ = project_concept_cards()
    approved = [card for card in cards if card.is_approved]
    assert approved, "no approved concept cards to inject"

    for card in approved:
        record = to_search_record(card)
        summary = _summary_for(record)
        assert summary, f"empty summary for {record.id}"
        assert "\n" not in summary, f"multi-line summary for {record.id}"
        assert len(summary) <= _SUMMARY_MAX_CHARS, f"summary over cap for {record.id}"
        # The summary is one language's description verbatim (or its truncation),
        # never the title+aliases+all-descriptions concatenation.
        is_whole = summary in record.descriptions.values()
        is_truncation = summary.endswith("…") and any(
            description.startswith(summary[:-1]) for description in record.descriptions.values()
        )
        assert is_whole or is_truncation, f"summary is not a single description for {record.id}"
