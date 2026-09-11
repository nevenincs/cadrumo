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

from pathlib import Path

import pytest
from dev.registry.compiler.validate_layout_authority_content import validate_layout_authority_content

from .....core.resources.bundled_data import bundled_path
from .....domain.calculations.registry.tests.registry_tree import bundled_registry_tree
from ..schema_references import SourceReference

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
    resolution and the sibling below asserts the emptiness. The public-validator
    fixture checks below cover the non-vacuous positive and negative content
    cases directly.
    """
    source = _bundled_sources()[_ANCHOR_SOURCE_ID]
    assert source.evidence_tier == "official_source_guidance", (
        "the last false layout-authority claim was retiered; if it is claiming "
        "layout authority again, the retier has been reverted"
    )
    assert source.corpus_path.startswith("corpus/normatives/")
    assert source.corpus_path.endswith(".html")


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


def test_boe_boilerplate_alone_does_not_satisfy_the_claim(tmp_path: Path) -> None:
    """ "DISPOSICIONES GENERALES" heads every BOE document and proves nothing.

    The public validator must reject the fixture rather than exposing its
    content predicate to this test package.
    """
    relative_path = "corpus/normatives/html/layout-boilerplate.html"
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True)
    path.write_text(_BOE_BOILERPLATE, encoding="utf-8")
    source = _bundled_sources()[_HONEST_SOURCE_ID].model_copy(update={"corpus_path": relative_path})
    assert validate_layout_authority_content({_HONEST_SOURCE_ID: source}, source_root=tmp_path)


def test_an_annex_heading_satisfies_the_claim_and_a_reference_to_one_does_not(tmp_path: Path) -> None:
    """Containing the annex is the claim; pointing at it is the defect."""
    positive_relative_path = "corpus/normatives/html/layout-annex.html"
    negative_relative_path = "corpus/normatives/html/layout-annex-reference.html"
    for relative_path, content in (
        (positive_relative_path, _ANNEX_HEADING_DOC),
        (negative_relative_path, _ANNEX_CROSS_REFERENCE_DOC),
    ):
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    anchor = _bundled_sources()[_HONEST_SOURCE_ID]
    positive = anchor.model_copy(update={"corpus_path": positive_relative_path})
    negative = anchor.model_copy(update={"corpus_path": negative_relative_path})
    assert validate_layout_authority_content({"positive": positive}, source_root=tmp_path) == []
    assert validate_layout_authority_content({"negative": negative}, source_root=tmp_path)


def test_the_gate_yields_nothing_without_a_source_root() -> None:
    """No reachable corpus means no claim can be checked, and none is invented."""
    assert validate_layout_authority_content(_norm_text_layout_claims(), source_root=None) == []
