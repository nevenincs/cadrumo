"""The article acquirer refuses anything but the requested article in force.

Driven against real BOE bytes, for the same reason the whole-document sibling
is: the defect this path exists to prevent is selecting a repealed redaction,
and a hand-written fixture would encode the version shape its author imagined.
Both fixtures were captured from the live endpoint -- the good one by asking for
``application/xml``, the refusal one by asking for a mime type BOE does not
serve.

The article endpoint's version rule is the INVERSE of ``act.php``'s, which is
the whole reason it needs its own tests rather than a shared one. There,
versions are radios listed newest first and the served one is marked
``checked``. Here every redaction ships, oldest first, each wrapped in a
``<version fecha_vigencia=...>``. Nothing reads order: selection takes the
maximum ``fecha_vigencia``, so the two rules cannot be transposed by accident.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from dev.corpus.fetch_boe_normative import (
    NormativeAcquisitionError,
    article_redactions,
    assert_serves_the_article_in_force,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FIXTURES: Final[Path] = Path(__file__).resolve().parent / "fixtures"
_ARTICLE: Final[str] = "boe-api-ley-37-1992-a90.xml"
_REFUSED: Final[str] = "boe-api-envelope-400.xml"
_LIVA: Final[str] = "BOE-A-1992-28740"


def _payload(name: str) -> str:
    path = _FIXTURES / name
    if not path.is_file():
        pytest.fail(f"fixture {name} is missing; this module's ground truth has moved")
    return path.read_text(encoding="utf-8", errors="replace")


def test_the_fixture_carries_several_redactions_at_all() -> None:
    """Anti-vacuity: with nothing parsed, every assertion below agrees with everything.

    A single redaction would also make the max-vigencia selection untestable,
    since any selection rule returns the same answer over a one-element set.
    """
    redactions = article_redactions(_payload(_ARTICLE))

    assert len(redactions) > 1, f"art. 90 should carry several redactions, parsed {len(redactions)}"
    assert len({r.vigencia for r in redactions}) > 1, "distinct vigencias are what the selection discriminates on"


def test_the_redactions_name_their_amending_norms_not_the_norm_being_read() -> None:
    """``id_norma`` is the norm that produced the redaction, and mostly is not LIVA.

    Recorded as a test rather than a comment because the first draft of the
    acquirer got it backwards: it treated any norm id other than the requested
    one as a wrong-document payload, which refuses every much-amended article --
    that is, every article worth fetching. The art. 90 fixture caught it.

    This is also the field that makes the endpoint worth using at all. "Which
    norm fixed this value, and from when" is the pair (amending_norm, vigencia),
    available structurally instead of by parsing prose.
    """
    norms = {r.amending_norm for r in article_redactions(_payload(_ARTICLE))}

    assert _LIVA in norms, "the original enactment is one of the redactions"
    assert norms - {_LIVA}, "art. 90 has been amended, so other norms must appear"
    assert "BOE-A-2012-9364" in norms, "RDL 20/2012 produced the 21 % redaction"


def test_the_redaction_in_force_is_the_latest_vigencia_not_the_first_block() -> None:
    """Selection returns the newest redaction, and the payload really does hold an older one.

    The second assertion is the one that matters. Art. 90's earliest redaction
    sets the general rate at 15 % and the current one at 21 %; if the payload did
    not still contain the 15 %, a rule that picked the FIRST block would pass
    this test too, and the whole point is that it must not.
    """
    payload = _payload(_ARTICLE)
    redactions = article_redactions(payload)

    in_force = assert_serves_the_article_in_force(payload, document_id=_LIVA, block="a90")

    assert in_force.vigencia == max(r.vigencia for r in redactions)
    assert "15 por 100" in payload, "the superseded 1992 redaction must still be present for this to prove anything"
    assert "21 por ciento" in payload


def test_the_payload_carries_the_amending_norm_notes() -> None:
    """The reason this endpoint is used at all.

    The whole-document view carries none of these for a given article, which is
    what blocked grounding a rate on the provision that fixed it. Asserted on a
    specific known amendment rather than on a count, so the test still means
    something if BOE reformats the panel.
    """
    payload = _payload(_ARTICLE)

    assert "Real Decreto-ley 20/2012" in payload
    assert "BOE-A-2012-9364" in payload


def test_a_refused_mime_negotiation_is_rejected_on_the_envelope() -> None:
    """The API's result lives in the body, so the body is what is believed.

    Captured live by requesting a mime type BOE does not serve. That response
    also carries HTTP 400, so ``raise_for_status`` would stop it first -- this
    assertion is the backstop for the case where the two disagree, not the only
    guard. It is kept because the envelope is the documented result channel.
    """
    with pytest.raises(NormativeAcquisitionError, match=r"envelope reports code '400'"):
        assert_serves_the_article_in_force(_payload(_REFUSED), document_id=_LIVA, block="a90")


def test_a_payload_for_another_block_is_refused() -> None:
    """Asking for art. 91 and being handed art. 90 must not pass silently."""
    with pytest.raises(NormativeAcquisitionError, match=r"describes block 'a90', not the requested 'a91'"):
        assert_serves_the_article_in_force(_payload(_ARTICLE), document_id=_LIVA, block="a91")


def test_a_payload_is_not_refused_merely_for_naming_other_norms() -> None:
    """The complement of the block check, and the retraction of a wrong first draft.

    Requesting LIVA and receiving a payload whose redactions name Ley 41/1994,
    RDL 12/1995, Ley 26/2009 and RDL 20/2012 is the NORMAL case, not a
    mismatch. Asserted explicitly so the refusal cannot be reintroduced: it
    would reject every article that has ever been amended, while looking like a
    prudent identity check.
    """
    in_force = assert_serves_the_article_in_force(_payload(_ARTICLE), document_id=_LIVA, block="a90")

    assert in_force.amending_norm == "BOE-A-2012-9364", "the redaction in force is RDL 20/2012's"


def test_a_payload_with_no_version_element_is_refused() -> None:
    """No ``<version>`` means nothing establishes which redaction the bytes are.

    Built by stripping the version tags from the real payload rather than by
    inventing markup, so the refusal is proved against bytes that are otherwise
    exactly what BOE sends.
    """
    stripped = _payload(_ARTICLE).replace("<version", "<noversion")

    with pytest.raises(NormativeAcquisitionError, match=r"no <version> element"):
        assert_serves_the_article_in_force(stripped, document_id=_LIVA, block="a90")


def test_a_tie_on_the_latest_vigencia_is_refused_not_guessed() -> None:
    """Two redactions dated the same day is a real shape, and picking one can pick the older.

    Not hypothetical. LIVA art. 91 carries two redactions both stamped
    19950120: one reads "Dos. Se aplicara el tipo del 3 por 100" and the other
    "del 4 por 100", because Ley 41/1994 art. 78.2 raised it. An arbitrary pick
    between tied dates therefore has a real chance of returning the SUPERSEDED
    text, which is precisely the defect this module exists to prevent, so the
    tie refuses instead.

    Built by duplicating the latest redaction's opening tag in the real art. 90
    payload, so the tie is introduced into bytes that are otherwise exactly what
    BOE sends.
    """
    payload = _payload(_ARTICLE)
    latest = max(r.vigencia for r in article_redactions(payload))
    tag = f'<version id_norma="{_LIVA}" fecha_publicacion="19921229" fecha_vigencia="{latest}">'

    with pytest.raises(NormativeAcquisitionError, match=r"share the latest fecha_vigencia"):
        assert_serves_the_article_in_force(payload + tag, document_id=_LIVA, block="a90")
