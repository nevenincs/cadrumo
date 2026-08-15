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

import pytest

from .....core.resources import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from .._schema_references import SourceReference
from .._validate_layout_authority_content import (
    _carries_layout_content,
    validate_layout_authority_content,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: One member of the cohort this gate was built for, used as a fixture anchor.
#: The companion test re-derives that it still carries the properties it is
#: named for, so a retier or a replaced file makes the anchor fail loudly
#: instead of making every assertion below pass vacuously.
_ANCHOR_SOURCE_ID = "enrolled-modelo-233-layout"

#: A source whose file is a genuine consolidated orden carrying its annex.
_HONEST_SOURCE_ID = "boe-modelo-714-layout"

_BOE_BOILERPLATE = "<html><body><p>I. DISPOSICIONES GENERALES MINISTERIO DE HACIENDA</p></body></html>"
_ANNEX_HEADING = "<html><body><h5 class='anexo'>ANEXO I</h5><p>Contenido.</p></body></html>"
_ANNEX_CROSS_REFERENCE = "<html><body><p>Se aprueba el modelo, que figura en el anexo de esta orden.</p></body></html>"


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


def test_the_anchor_source_still_carries_the_properties_it_is_named_for() -> None:
    """The named cohort member is still a norm-text HTML layout-authority claim.

    Without this, retiering the anchor would silently turn the cohort
    assertions below into statements about an empty set.
    """
    source = _bundled_sources()[_ANCHOR_SOURCE_ID]
    assert source.evidence_tier == "layout_authority"
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
    """The anchor is named, with a cause that says what to do about it."""
    claims = _norm_text_layout_claims()
    failures = validate_layout_authority_content(claims, source_root=bundled_path())
    matching = [failure for failure in failures if _ANCHOR_SOURCE_ID in failure]
    assert matching, f"{_ANCHOR_SOURCE_ID} declares layout authority over an excerpt and must be reported"
    assert "carries no annex section" in matching[0]
    assert "retier this source" in matching[0]


def test_an_honest_layout_authority_is_not_reported() -> None:
    """A consolidated orden carrying its annex satisfies the claim it makes."""
    claims = _norm_text_layout_claims()
    source = claims[_HONEST_SOURCE_ID]
    assert validate_layout_authority_content({_HONEST_SOURCE_ID: source}, source_root=bundled_path()) == []


def test_boe_boilerplate_alone_does_not_satisfy_the_claim() -> None:
    """ "DISPOSICIONES GENERALES" heads every BOE document and proves nothing.

    This is the anti-vacuity proof: drop the negative lookbehind and the
    predicate accepts the header every stub in the corpus already carries.
    """
    assert _carries_layout_content(_BOE_BOILERPLATE) is False


def test_an_annex_heading_satisfies_the_claim_and_a_reference_to_one_does_not() -> None:
    """Containing the annex is the claim; pointing at it is the defect."""
    assert _carries_layout_content(_ANNEX_HEADING) is True
    assert _carries_layout_content(_ANNEX_CROSS_REFERENCE) is False


def test_the_gate_yields_nothing_without_a_source_root() -> None:
    """No reachable corpus means no claim can be checked, and none is invented."""
    assert validate_layout_authority_content(_norm_text_layout_claims(), source_root=None) == []
