"""A ``layout_authority`` claim is checked against the file, never trusted.

``evidence_tier = "layout_authority"`` says the cited document is where a
modelo's record layout comes from. Nothing verified it, so a two-article BOE
excerpt -- approval plus filing deadline, no annex, closing with its own
sentence "Pending operator re-verification." -- carried the claim at
``review_status = "reviewed"`` across a whole cohort of modelos. Several of
those excerpts *name* the annex they omit ("que figura en el anexo de esta
orden"), which is the clearest possible statement that the layout is elsewhere.

These tests pin the property, never a tally. The cohort size is a fact about
today's corpus and will change as sources are retiered or replaced; asserting it
would train the next author to update a constant and would detect nothing. What
must hold is the implication: a layout-authority claim over norm-text HTML is
reported unless its file carries annex or record-layout content.

The anti-vacuity proof is the load-bearing one. Every BOE document opens with
"I. DISPOSICIONES GENERALES", so a ``posiciones`` substring match without the
negative lookbehind accepts documents on boilerplate alone -- a check that
inspects real files, reports plausibly, and cannot fail for the reason it
claims to.
"""

from __future__ import annotations

import re

import pytest

from .....core.resources import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from ..schema_references import SourceReference
from .._validate_layout_authority_content import (
    _ANNEX_BLOCK,
    _ANNEX_HEADING,
    _LAYOUT_VOCABULARY,
    _carries_layout_content,
    validate_layout_authority_content,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: One member of the cohort this gate was built for, used as a fixture anchor.
#: The companion test re-derives that it still carries the properties it is
#: named for, so a retier or a replaced file makes the anchor fail loudly
#: instead of making every assertion below pass vacuously.
#: Re-anchored 2026-08-15: the original anchor (enrolled-modelo-233-layout)
#: was retiered to official_source_guidance along with the other nine
#: confirmed-unpublished cohort members. modelo-186 is the one remaining
#: false layout-authority claim in this shape -- filed as its own item,
#: deliberately untouched pending its own resolution -- so it is the stable
#: anchor until that lands, at which point this constant needs another swap.
_ANCHOR_SOURCE_ID = "enrolled-modelo-186-layout"

#: A source whose file is a genuine consolidated orden carrying its annex.
_HONEST_SOURCE_ID = "boe-modelo-714-layout"

_BOE_BOILERPLATE = "<html><body><p>I. DISPOSICIONES GENERALES MINISTERIO DE HACIENDA</p></body></html>"
_ANNEX_HEADING_DOC = "<html><body><h5 class='anexo'>ANEXO I</h5><p>Contenido.</p></body></html>"
_ANNEX_CROSS_REFERENCE_DOC = (
    "<html><body><p>Se aprueba el modelo, que figura en el anexo de esta orden.</p></body></html>"
)


def _bundled_sources() -> dict[str, SourceReference]:
    _modelos, catalogues = bundled_registry_tree()
    return {str(ref): source for ref, source in catalogues.sources.items()}


def _norm_text_layout_claims() -> dict[str, SourceReference]:
    return {
        source_id: source
        for source_id, source in _bundled_sources().items()
        if source.evidence_tier == "layout_authority"
        and source.corpus_path.startswith("corpus/normatives/")
        and source.corpus_path.endswith(".html")
    }


def test_the_last_false_layout_authority_claim_has_been_retiered() -> None:
    """``enrolled-modelo-186-layout`` was the cohort's final member, and it is resolved.

    This asserted the anchor still claimed ``layout_authority``, so that
    retiering it could not quietly turn the cohort assertions into statements
    about an empty set. The anchor's own comment named the condition: it was the
    one remaining false claim, held as the anchor "until that lands, at which
    point this constant needs another swap". It has landed.

    There is nothing to swap to, because the cohort is now EMPTY -- which is the
    outcome the gate existed to drive, not a failure. So this records the
    resolution and the sibling below asserts the emptiness; the vacuity the
    anchor guarded against is covered instead by
    ``test_every_acceptance_is_driven_by_content_the_file_actually_carries``,
    which strips the evidence from every accepted file and requires each to flip
    to refused across the whole population rather than one specimen.
    """
    source = _bundled_sources()[_ANCHOR_SOURCE_ID]
    assert source.evidence_tier == "official_source_guidance", (
        "the last false layout-authority claim was retiered; if it is claiming "
        "layout authority again, the retier has been reverted"
    )
    assert source.corpus_path.startswith("corpus/normatives/")
    assert source.corpus_path.endswith(".html")


def test_every_reported_claim_is_one_whose_file_carries_no_layout() -> None:
    """The reported set equals the set whose file fails the content predicate.

    Both directions in one assertion, over the real corpus: nothing is reported
    whose file does carry layout content, and nothing that fails the predicate
    escapes the report.
    """
    claims = _norm_text_layout_claims()
    reported = {
        source_id
        for source_id in claims
        for failure in validate_layout_authority_content({source_id: claims[source_id]}, source_root=bundled_path())
        if failure
    }
    unbacked = set()
    for source_id, source in claims.items():
        path = bundled_path() / source.corpus_path
        if not path.is_file():
            continue
        if not _carries_layout_content(path.read_text(encoding="utf-8", errors="replace")):
            unbacked.add(source_id)
    assert reported == unbacked


def test_the_gate_reports_the_cohort_it_was_built_for() -> None:
    """No norm-text claim now stands over an excerpt, and the message still says what to do.

    The cohort this gate was built for is empty: 78 norm-text layout-authority
    claims, none reported. The report's WORDING is still pinned, because an empty
    cohort would otherwise let the guidance rot unnoticed -- so it is driven over
    a constructed claim rather than a corpus member that no longer exists.
    """
    claims = _norm_text_layout_claims()
    assert claims, "no norm-text layout-authority claims at all; the gate is measuring nothing"
    assert validate_layout_authority_content(claims, source_root=bundled_path()) == []

    honest = claims[_HONEST_SOURCE_ID]
    over_an_excerpt = honest.model_copy(
        update={"corpus_path": _bundled_sources()[_ANCHOR_SOURCE_ID].corpus_path},
    )
    reported = validate_layout_authority_content(
        {_HONEST_SOURCE_ID: over_an_excerpt},
        source_root=bundled_path(),
    )
    assert reported, "a layout-authority claim over an excerpt must still be reported"
    assert "carries no annex section" in reported[0]
    assert "retier this source" in reported[0]


def test_an_honest_layout_authority_is_not_reported() -> None:
    """A consolidated orden carrying its annex satisfies the claim it makes."""
    claims = _norm_text_layout_claims()
    source = claims[_HONEST_SOURCE_ID]
    assert validate_layout_authority_content({_HONEST_SOURCE_ID: source}, source_root=bundled_path()) == []


def test_every_acceptance_is_driven_by_content_the_file_actually_carries() -> None:
    """Strip the evidence from each ACCEPTED file and every one flips to refused.

    The refusals are easy to trust: each names a file and says what is missing.
    The acceptances are the larger claim and the harder one -- most of this
    population passes, and a predicate that silently could not say no, or a read
    that failed and was skipped, would look exactly like a clean bill of health.

    So each accepted file is re-asked with its annex headings, standalone ANEXO
    blocks and layout vocabulary removed in memory. An acceptance surviving that
    was never reading the file. Nothing on disk is touched.
    """
    claims = _norm_text_layout_claims()
    accepted, survived, unreadable = 0, [], []
    for source_id, source in sorted(claims.items()):
        path = bundled_path() / source.corpus_path
        if not path.is_file():
            unreadable.append(source_id)
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        if not _carries_layout_content(raw):
            continue
        accepted += 1
        stripped = _ANNEX_HEADING.sub("<h9>", raw)
        stripped = _ANNEX_BLOCK.sub(" ", stripped)
        stripped = re.sub(r"anexos?", "SECCION", stripped, flags=re.IGNORECASE)
        stripped = _LAYOUT_VOCABULARY.sub("XXX", stripped)
        if _carries_layout_content(stripped):
            survived.append(source_id)

    assert not unreadable, f"claims whose file could not be read, so neither accepted nor refused: {unreadable}"
    assert accepted, "no layout-authority claim was accepted, so this proof would hold vacuously"
    assert not survived, (
        f"these acceptances survive having their layout evidence stripped, so they are not "
        f"reading the file they claim to verify: {survived}"
    )


def test_boe_boilerplate_alone_does_not_satisfy_the_claim() -> None:
    """ "DISPOSICIONES GENERALES" heads every BOE document and proves nothing.

    This is the anti-vacuity proof: drop the negative lookbehind and the
    predicate accepts the header every stub in the corpus already carries.
    """
    assert _carries_layout_content(_BOE_BOILERPLATE) is False


def test_an_annex_heading_satisfies_the_claim_and_a_reference_to_one_does_not() -> None:
    """Containing the annex is the claim; pointing at it is the defect."""
    assert _carries_layout_content(_ANNEX_HEADING_DOC) is True
    assert _carries_layout_content(_ANNEX_CROSS_REFERENCE_DOC) is False


def test_the_gate_yields_nothing_without_a_source_root() -> None:
    """No reachable corpus means no claim can be checked, and none is invented."""
    assert validate_layout_authority_content(_norm_text_layout_claims(), source_root=None) == []
