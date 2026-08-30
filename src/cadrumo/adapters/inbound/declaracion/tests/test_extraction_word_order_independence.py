"""Extraction depends on the SET of word matches, never on their order.

The real-render coverage gate cannot see this property, and that is why it is
pinned separately. ``_find_bbox_casilla_hits`` reports multiple matches as
ambiguous by COUNT, so the gate passing tells you the box-number matches still
resolve; it tells you nothing about whether a different word ordering would have
resolved them differently. Reading a green gate as clearing an ordering risk is
over-reading it.

The risk is not hypothetical. Requesting the font size on word extraction, which
is what stops a box number printed over an amount from merging into it, changes
the returned word lists: header and footer text reorganises on Modelo 390 and
duplicate-match ordering swaps on Modelo 111. Neither changed any extracted
value, but nothing was asserting that it could not.

The structural reason it holds is that every selection in the path is
order-free. Candidate value words are chosen by ``min``/``max`` over a bounded
set, column ranges by ``min``/``max`` over header matches, lines by sorting on
``(top, x0)`` before grouping and on ``x0`` within a line, and a target with more
than one hit is refused as ambiguous rather than resolved to whichever came
first.

**What this module does and does not cover, measured rather than assumed.** It
catches an order dependence in line assembly: removing both normalisations from
``_words_by_line`` fails it on Modelo 100 for all 21 targets and on Modelo 390
for two, under both permutations. Removing only one passes, because either sort
alone is sufficient -- so the redundancy is real and this module will not tell
you which of the two you deleted.

It does **not** currently cover the ``bbox_anchored`` candidate selections.
Replacing ``min(candidates, key=x0)`` with ``candidates[0]`` passes, and the
reason is a property of the corpus rather than of the assertion: instrumenting
``_resolve_value_word`` over the bundled specimens shows it is offered zero or
one candidate and never more, so the two expressions cannot differ. Those
selections are order-free by construction and unproven by measurement here. A
specimen that puts two words to the right of one box number on the same row
would close that gap; none is bundled.

Permuting the list is the whole method: if any outcome moves when the same words
arrive in a different order, something reads position in the list rather than
position on the page.

The permutations are fixed rather than random. Reversal is the strongest single
probe for an overlooked ``[0]``, because it puts the last candidate first, and a
deterministic case cannot pass on one CI run and fail on the next.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from .....domain.calculations.registry.authority import bundled_authority
from .....tests import FIXTURES_DIR
from .._parser import (
    _classify_target,
    _extract_pages_words,
    _numeric_casilla_anchors,
    _PdfWord,
    _printed_box_numbers,
    _select_extraction_profile,
    extract_pages_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _reversed(words: list[_PdfWord]) -> list[_PdfWord]:
    """Last candidate first: the strongest probe for an overlooked ``[0]``."""
    return list(reversed(words))


def _interleaved(words: list[_PdfWord]) -> list[_PdfWord]:
    """Even-indexed words then odd, so neighbours on the page stop being adjacent."""
    return words[::2] + words[1::2]


_PERMUTATIONS: tuple[tuple[str, Callable[[list[_PdfWord]], list[_PdfWord]]], ...] = (
    ("reversed", _reversed),
    ("interleaved", _interleaved),
)

# One specimen per extraction shape, because the shapes fail differently.
# Modelo 111 is entirely bbox_anchored and is where duplicate-match ordering was
# observed to swap; Modelo 100 is entirely named_label amount targets and reads
# lines assembled from words; Modelo 390 mixes both and is the render whose
# header and footer text reorganises.
_CASES: tuple[tuple[str, int, str, Path], ...] = (
    ("111", 2024, "1T", FIXTURES_DIR / "justificantes" / "111" / "2024-1T.pdf"),
    ("100", 2021, "0A", FIXTURES_DIR / "justificantes" / "100" / "2021-0A.pdf"),
    ("390", 2021, "0A", FIXTURES_DIR / "justificantes" / "390" / "2021-0A.pdf"),
)


def _classify_every_target(
    modelo: str,
    filing_year: int,
    period: str,
    pdf: Path,
    pages_words: tuple[list[_PdfWord], ...],
) -> dict[str, tuple[str, str | None, int | None]]:
    """Every target's full outcome, so a substitution cannot hide behind a count."""
    snapshot = bundled_authority().snapshot(modelo, filing_year=filing_year, period=period)
    revision = snapshot.revision
    profile = _select_extraction_profile(snapshot, extraction_profile_id=None)
    pages = extract_pages_text(pdf)
    printed = _printed_box_numbers(profile, revision)
    anchors = _numeric_casilla_anchors(profile, revision)

    outcomes: dict[str, tuple[str, str | None, int | None]] = {}
    for target in profile.target_casillas:
        result = _classify_target(
            target,
            pages=pages,
            pages_words=pages_words,
            numeric_anchors=anchors,
            printed_box_numbers=printed,
        )
        casilla_id = str(target.casilla_id)
        if result.value is not None:
            outcomes[casilla_id] = ("value", str(result.value.printed_value), result.value.source_page)
        elif result.malformed is not None:
            outcomes[casilla_id] = ("malformed", None, None)
        elif result.ambiguous is not None:
            outcomes[casilla_id] = ("ambiguous", None, None)
        else:
            outcomes[casilla_id] = ("missing", None, None)
    return outcomes


@pytest.mark.parametrize("modelo,filing_year,period,pdf", _CASES, ids=[f"{c[0]}-{c[3].stem}" for c in _CASES])
@pytest.mark.parametrize("permutation_name,permute", _PERMUTATIONS, ids=[p[0] for p in _PERMUTATIONS])
def test_permuting_the_word_list_changes_no_extraction_outcome(
    modelo: str,
    filing_year: int,
    period: str,
    pdf: Path,
    permutation_name: str,
    permute: Callable[[list[_PdfWord]], list[_PdfWord]],
) -> None:
    """The same words in a different order must yield the same extraction.

    Compared per target and including the failure category and source page, not
    only the value: a target moving between ``missing`` and ``ambiguous`` is an
    order dependence even though no amount changed, and a value read from a
    different page is one even though the amount happens to match.
    """
    assert pdf.is_file(), f"{pdf} is missing, so this specimen proves nothing"

    natural = _extract_pages_words(pdf)
    assert any(natural), f"{pdf.name}: no words extracted, so permuting proves nothing"

    baseline = _classify_every_target(modelo, filing_year, period, pdf, natural)

    permuted: tuple[list[_PdfWord], ...] = tuple(permute(list(page)) for page in natural)

    assert any(page != original for page, original in zip(permuted, natural, strict=True)), (
        f"{pdf.name}: the {permutation_name} permutation was a no-op, so this asserts nothing"
    )

    reordered = _classify_every_target(modelo, filing_year, period, pdf, permuted)

    drifted = {key: (baseline[key], reordered[key]) for key in baseline if baseline[key] != reordered[key]}

    assert not drifted, (
        f"M{modelo} {pdf.name}: extraction changed under the {permutation_name} permutation, so "
        f"something reads position in the list rather than position on the page: {drifted}"
    )
