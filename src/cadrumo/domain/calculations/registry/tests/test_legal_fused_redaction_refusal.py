"""Registry build must refuse a citation whose evidence fuses redactions.

BOE's open-data article endpoint concatenates every historical redaction of an
article into one response. That history is why the endpoint is worth reading,
but the bundled extractor folds the whole response into a single undelimited
unit with no ``fecha_vigencia`` attribution, so the text a ``required_text``
clause is checked against is several successive statements of the same
provision run together. A phrase surviving only in a redaction repealed decades
ago is then *present*, the presence check passes, and the entry reads as
grounded in current law while its evidence is a pile.

These tests drive that refusal against the REAL bundled corpus rather than a
synthetic fixture, because a detector that is correct on synthetic input and
never reaches the real site is the failure mode a synthetic proof cannot see.

The two directions of the name-independence claim are both driven:
``boe-a-1991-14392-a30-redacciones`` is refused and carries the convention in
its stem, ``rd-1065-2007-art-25`` is refused and does not, and a single-redaction
capture carrying the stem is accepted. So the stem neither convicts nor acquits.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final

import pytest

from .....core import corpus_redaction_marks, normalise_corpus_text, resolve_anchored_extracted_unit
from .....core.resources import bundled_path
from ..errors import RegistryValidationError
from .._legal import verify_legal_reference, verify_legal_reference_grounding
from .._schema import LegalReference
from ._catalogue_verification_support import _registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NORMATIVES: Final = "corpus/normatives/html"

#: A redaction-history capture whose stem announces itself. Measured: ten dated
#: redactions of Ley 19/1991 art. 30 collapsed into one 15,802-character unit.
_FUSED_BY_NAME: Final = f"{_NORMATIVES}/boe-a-1991-14392-a30-redacciones.html"

#: A redaction-history capture whose stem does NOT. This is the one the live
#: catalogue actually cited, which is why the detection cannot rest on the
#: naming convention: two dated redactions of RGAT art. 25 in one unit.
_FUSED_BY_SHAPE: Final = f"{_NORMATIVES}/rd-1065-2007-art-25.html"

#: The consolidated whole-document RGAT, serving art. 25 as it stands in force.
#: An independent bundled oracle for what the fused capture adds.
_CONSOLIDATED_RGAT: Final = f"{_NORMATIVES}/rd-1065-2007.html"

#: The heading of RGAT art. 25. A provision states its own heading once; a
#: document stating it twice is stating the provision twice.
_RGAT_ARTICLE_HEADING: Final = "Artículo 25. Especialidades del número de identificación fiscal"

#: The 1992 peseta tariff of Ley 19/1991 art. 30, repealed long ago.
_PATRIMONIO_REPEALED_TARIFF: Final = "1.275.000"

#: What the same article says today: the base is taxed at the scale the
#: autonomous community approved. It cannot be true at the same time as a
#: peseta tariff printed in the same article, which is what makes the pair a
#: proof of fusion rather than an argument about one.
_PATRIMONIO_CURRENT_DELEGATION: Final = "escala que haya sido aprobada por la Comunidad Autónoma"

#: A capture carrying the redaction-history stem whose article was never
#: amended, so it declares a single redaction and is legitimate evidence.
#: Art. 10 (Dividendos) of the Spain-Netherlands convention.
_SINGLE_REDACTION_BY_NAME: Final = f"{_NORMATIVES}/boe-a-1972-1469-a1-2-redacciones.html"

#: The deliberately year-vintaged excerpts, restated here rather than imported:
#: they legitimately contain text current law does not, so a refusal that caught
#: them would be wrong, and this module must fail if it starts catching them.
_DELIBERATELY_VINTAGED_EXCERPT_IDS: Final = (
    "ley-35-2006:art-23-2021",
    "ley-35-2006:art-52-2015",
    "ley-35-2006:art-52-2021",
    "ley-35-2006:art-66-2021",
    "ley-35-2006:art-68-2018",
)


def _redaction_count(document: Path) -> int:
    """Return how many dated redactions the bundled ``document`` declares."""
    return len(corpus_redaction_marks(document.read_text(encoding="utf-8", errors="replace")))


def _unit_text(document: Path, *, anchor: str) -> str:
    """Return the normalised unit a citation into ``document`` would be checked against."""
    sidecar = document.with_name(f"{document.name}.extracted.json")
    return normalise_corpus_text(resolve_anchored_extracted_unit(sidecar, anchor=anchor, include_title=True))


def _reference(corpus_ref: str, *, required_text: tuple[str, ...]) -> LegalReference:
    """Build a minimal filing-grade reference citing ``corpus_ref``."""
    return LegalReference(
        id="probe:art-1",
        evidence_tier="legal_authority",
        authority="boe",
        kind="real_decreto",
        corpus_ref=corpus_ref,
        document_id="BOE-A-2007-15984",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2007-15984",
        published_at=date(2007, 9, 5),
        effective_from=date(2008, 1, 1),
        review_status="operator_reviewed",
        reviewed_at=date(2026, 8, 13),
        reviewed_by="operator",
        notes="Probe reference driving the fused-redaction refusal.",
        required_text=required_text,
    )


@pytest.mark.parametrize(
    ("corpus_ref", "quoted_phrase"),
    [
        (f"{_FUSED_BY_NAME}#a30", _PATRIMONIO_REPEALED_TARIFF),
        (f"{_FUSED_BY_SHAPE}#a25", "al que se antepondrá el prefijo ES"),
    ],
)
def test_registry_build_refuses_a_citation_into_a_fused_redaction_history(
    corpus_ref: str,
    quoted_phrase: str,
) -> None:
    """The refusal fires against the real bundled artefacts, and says what to do.

    Each probe quotes a phrase the fused unit genuinely contains, so the entry
    would otherwise pass the presence check: what refuses it is the shape of its
    evidence, not a missing phrase. The redaction count is measured from the
    payload rather than pinned as a pass condition, so re-acquiring a document
    with further amendments does not turn this into a maintenance chore.
    """
    root = bundled_path()
    document = root / corpus_ref.partition("#")[0]
    redactions = _redaction_count(document)
    assert redactions > 1, f"{document} must still carry the fused shape this refusal exists for"
    assert normalise_corpus_text(quoted_phrase) in _unit_text(document, anchor=corpus_ref.partition("#")[2]), (
        "the probe must quote text the fused unit really carries, or the refusal is untested"
    )

    with pytest.raises(RegistryValidationError) as refusal:
        verify_legal_reference(_reference(corpus_ref, required_text=(quoted_phrase,)), source_root=root)

    message = str(refusal.value)
    assert "probe:art-1" in message, "the refusal must name the offending entry"
    assert corpus_ref.partition("#")[0] in message, "the refusal must name the file"
    assert f"{redactions} dated redactions" in message, "the refusal must quantify the fusion"
    assert "consolidated current-text document" in message, "the refusal must name the remedy"
    assert "redaction in force" in message, "the refusal must name the other remedy"


def test_a_fused_unit_states_one_provision_two_ways_that_cannot_both_be_law() -> None:
    """The hazard is real on the committed data, not an argued possibility.

    Ley 19/1991 art. 30 fixed a peseta tariff in 1992 and, since 2021, defers
    the scale to the autonomous community. Both statements sit in the single
    unit a citation into that capture would be checked against, and they cannot
    both be the law. Any ``required_text`` phrase drawn from either one is
    therefore *present*, so a presence check against this unit says nothing
    about which of them the entry is grounded in.
    """
    fused = _unit_text(bundled_path() / _FUSED_BY_NAME, anchor="a30")

    assert normalise_corpus_text(_PATRIMONIO_REPEALED_TARIFF) in fused, "the repealed peseta tariff must be present"
    assert normalise_corpus_text(_PATRIMONIO_CURRENT_DELEGATION) in fused, "the current delegation must be present too"


def test_a_fused_unit_states_its_own_provision_more_than_once() -> None:
    """The consolidated document is the oracle for what one provision looks like.

    RGAT art. 25 states its heading once in the consolidated whole-document
    text and more than once in the article-endpoint capture the live catalogue
    used to cite. The repetition is the fusion, measured against a bundled
    control rather than asserted, so the claim does not rest on this module's
    own reading of the capture.
    """
    root = bundled_path()
    heading = normalise_corpus_text(_RGAT_ARTICLE_HEADING)
    fused = _unit_text(root / _FUSED_BY_SHAPE, anchor="a25")
    in_force = _unit_text(root / _CONSOLIDATED_RGAT, anchor="a25")

    assert in_force.count(heading) == 1, "the consolidated article states its own heading exactly once"
    assert fused.count(heading) > 1, "the capture states the provision more than once, which is the fusion"
    assert len(fused) > len(in_force), "the fused capture is the larger document because it is several"


def test_a_single_redaction_capture_is_accepted_despite_the_redaction_history_stem() -> None:
    """The stem does not convict. Only the shape does.

    A ``-redacciones`` capture of an article BOE never amended declares one
    redaction, fuses nothing, and is ordinary evidence. A filename-driven
    refusal would reject it and would teach the next author to rename around
    the gate.
    """
    root = bundled_path()
    document = root / _SINGLE_REDACTION_BY_NAME
    assert _redaction_count(document) == 1, f"{document} must remain the single-redaction control"
    assert "redacciones" in document.name, "the control is only meaningful while it carries the stem"

    verify_legal_reference(
        _reference(f"{_SINGLE_REDACTION_BY_NAME}#a10", required_text=("Dividendos",)),
        source_root=root,
    )


def test_no_committed_legal_entry_cites_a_fused_redaction_history() -> None:
    """The control that decides closure: the legitimate population still loads.

    A refusal firing proves it CAN catch fused evidence and proves nothing about
    whether it over-reaches on the real catalogue. Every committed entry is
    validated here through the same path a registry build takes, and the
    deliberately year-vintaged excerpts are named because they legitimately
    contain text current law does not -- a refusal catching one of those would
    be wrong, and this control is what would say so.
    """
    _modelos, catalogues = _registry_tree()

    assert len(catalogues.legal) > 0, "the control is meaningless against an empty catalogue"
    for vintaged_id in _DELIBERATELY_VINTAGED_EXCERPT_IDS:
        assert vintaged_id in catalogues.legal, f"{vintaged_id!r} must remain in the committed legal catalogue"

    for reference in catalogues.legal.values():
        verify_legal_reference_grounding(reference, source_root=bundled_path())

    root = bundled_path()
    cited = {reference.corpus_ref.partition("#")[0] for reference in catalogues.legal.values()}
    absent = sorted(path_text for path_text in cited if not (root / path_text).is_file())
    assert absent == [], (
        "the refusal defers on a cited document that is not bundled, so a missing one would leave that "
        f"entry unexamined rather than refused: {absent}"
    )
    fused = sorted(path_text for path_text in cited if _redaction_count(root / path_text) > 1)
    assert fused == [], f"these cited documents fuse redactions and would refuse at registry build: {fused}"
