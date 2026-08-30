"""A mention the issuer printed must match even when our reading drops its accent.

The match folds case, collapses whitespace and folds combining accents away.
The accent is the one that needed a ruling: the mentions are Spanish and every
one carries a diacritic, while a text layer or an OCR pass routinely returns
ASCII. Without folding, a document carrying the mandated wording derives
nothing, no contradiction can fire on it, and a reverse charge honoured wrongly
OVER-declares -- the direction nothing else in this apparatus watches.

**This is not the loosening the match refuses.** That refusal is about
PARAPHRASE: deriving a regime from words the issuer did not print. Here the
issuer printed the mandated wording and our own pipeline degraded it, which is
the opposite case. It is also not the printed-country exonym widening rejected
twice on this codebase, which proposed DIFFERENT words rather than the same
words spelled without their accents.

**Folding is only sound while no two mentions collide under it**, which is why
the index refuses the whole vocabulary rather than keeping whichever row came
first. Two mentions differing only by an accent would make declaration order
decide a taxpayer's regime, and there is no basis for preferring either row.
The refusal is exercised against a supplied vocabulary rather than only the
shipped one, because a check reachable only through the bundled table is a check
nothing proves.
"""

from __future__ import annotations

import pytest

from ....core.text_fold import fold_printed_phrase
from ..legend_derivation import (
    index_regime_legends,
    match_regime_legend,
)
from ..regime_legend import REGIME_LEGENDS, RegimeLegend

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The mandated reverse-charge mention as the regulation fixes it.
_ACCENTED = "Inversión del sujeto pasivo"
#: The same mention as a text layer that dropped the accent returns it.
_UNACCENTED = "Inversion del sujeto pasivo"


def test_the_shipped_vocabulary_folds_without_collision() -> None:
    """The blocking condition folding rests on, asserted against the real table.

    A collision would make declaration order decide which regime a mention
    declares. The count comparison is what makes this more than a smoke test:
    an index that silently dropped a colliding row would still be non-empty.
    """
    indexed = index_regime_legends(REGIME_LEGENDS)

    assert len(indexed) == len(REGIME_LEGENDS), (
        "two mentions share a normalised form, so the vocabulary lost a row to folding"
    )
    assert len(REGIME_LEGENDS) > 1, "a single-entry vocabulary cannot collide, so this proves nothing"


def test_a_vocabulary_that_collides_under_folding_is_refused_whole() -> None:
    """Supplied rather than shipped, so the refusal is reachable and proven."""
    colliding = (
        RegimeLegend(
            phrase="régimen especial del criterio de caja",
            provision="art-6.1.p",
            declares=None,
            expects_repercutido_line=True,
        ),
        RegimeLegend(
            phrase="regimen especial del criterio de caja",
            provision="art-6.1.z",
            declares=None,
            expects_repercutido_line=True,
        ),
    )

    with pytest.raises(ValueError) as caught:
        index_regime_legends(colliding)

    message = str(caught.value)
    # Both claimants must be named: a refusal saying only that something
    # collided leaves the author to find which two rows it meant.
    assert "art-6.1.p" in message
    assert "art-6.1.z" in message


def test_an_empty_vocabulary_is_refused() -> None:
    """An empty index matches nothing and would read as "no mention was printed"."""
    with pytest.raises(ValueError, match="empty"):
        index_regime_legends(())


def test_the_mandated_mention_matches_with_and_without_its_accent() -> None:
    """The ruling itself: the same printed wording, degraded by our own reading."""
    accented = match_regime_legend(_ACCENTED)
    unaccented = match_regime_legend(_UNACCENTED)

    assert accented is not None
    assert unaccented is not None
    assert accented.provision == unaccented.provision
    assert accented.declares is unaccented.declares


def test_a_mention_broken_across_a_line_still_matches() -> None:
    """Whitespace collapse: an invoice sets the mention as a line and it wraps."""
    assert match_regime_legend("Inversion  del\n  sujeto   pasivo") is not None


def test_every_mention_stays_a_multi_word_phrase_after_folding() -> None:
    """The second blocking condition: distinctiveness must survive folding.

    Matching a token would make "régimen" or "especial" declare a regime. Each
    mention is four words or more, and folding removes accents rather than
    words, so the phrase carries the distinctiveness both before and after.
    """
    for legend in REGIME_LEGENDS:
        assert len(fold_printed_phrase(legend.phrase).split()) >= 4, legend.provision


def test_no_single_token_of_a_mention_matches_on_its_own() -> None:
    """The behavioural half of the same condition, rather than a word count.

    A word count would pass against a matcher that had been loosened to compare
    tokens. This asks the matcher.
    """
    for legend in REGIME_LEGENDS:
        for token in fold_printed_phrase(legend.phrase).split():
            assert match_regime_legend(token) is None, f"the lone token {token!r} matched a mandated mention"


def test_no_folded_mention_is_contained_in_another() -> None:
    """Nesting would make iteration order, not the document, pick the regime.

    Not true by construction and not implied by the collision check: two
    distinct forms can still nest. Asserted separately because the matcher
    returns the FIRST containment hit.
    """
    folded = [fold_printed_phrase(legend.phrase) for legend in REGIME_LEGENDS]
    for outer in folded:
        for inner in folded:
            if inner != outer:
                assert inner not in outer, f"{inner!r} sits inside {outer!r}, so first-match order decides"


@pytest.mark.parametrize(
    "printed",
    [
        "Στο πλαίσιο",  # Greek: casefolds, and NFKD does not transliterate it
        "Инверсия",  # Cyrillic: likewise
        "ＩＶＡ ２１％",  # fullwidth compatibility forms NFKD does rewrite
        "inﬁrma",  # an fi ligature NFKD decomposes
        "①②③",  # circled digits NFKD rewrites
        "Factura simplificada",  # a real Spanish phrase that is not a mandated mention
    ],
)
def test_folding_manufactures_no_match_it_did_not_have(printed: str) -> None:
    """The cost side of the ruling, measured rather than assumed.

    Folding is NFKD-based, so it rewrites more than accents: ligatures,
    fullwidth forms and circled digits all change. None of that can assemble a
    mandated Spanish mention, and this asserts it on the shapes that change most
    under the transform rather than on Latin text alone.
    """
    assert match_regime_legend(printed) is None
