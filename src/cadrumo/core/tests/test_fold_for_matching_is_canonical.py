"""The matching fold has one definition, and the property that let it merge holds.

The terminology search and the AEAT response-marker matcher each spelled out
fold-diacritics, collapse-whitespace, trim, casefold. They ordered the casefold
differently -- one before the collapse, one after -- so the merge was only safe
because those two orders agree. This module pins that property, since it is the
reason the two call sites could converge at all.

It also guards the name that made the collision visible. `_WHITESPACE_RE` meant
a run-collapsing pattern in three modules and a single-character DELETING
pattern in the PDF label reader. Those are different operations, so the deleting
one was renamed for what it does rather than merged.
"""

from __future__ import annotations

import re
from typing import Final

import pytest

from ..text_fold import fold_diacritics, fold_for_matching

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_RUN: Final[re.Pattern[str]] = re.compile(r"\s+")

#: Inputs chosen for the ways casefold and whitespace handling can interact:
#: Turkish dotted capital I, sharp S, a digraph, non-breaking space, tabs and
#: newlines, and the empty and whitespace-only strings.
_SAMPLES: Final[tuple[str, ...]] = (
    "",
    "   ",
    "  Año  FISCAL\tÑ  ",
    "ÁRBOL   \n  ÍNDICE",
    "MiXeD\u00a0Case  Text",
    "İstanbul  ß  STRASSE",
    "Modelo 303  —  IVA",
)


@pytest.mark.parametrize("raw", _SAMPLES)
def test_casefolding_before_or_after_the_collapse_agrees(raw: str) -> None:
    """The property the merge rests on: neither step affects what the other does.

    If this ever fails, the two call sites that were merged were not equivalent
    after all, and one of them changed behaviour when it started delegating.
    """
    folded = fold_diacritics(raw)
    casefold_first = _RUN.sub(" ", folded.casefold()).strip()
    casefold_last = _RUN.sub(" ", folded).strip().casefold()

    assert casefold_first == casefold_last


@pytest.mark.parametrize("raw", _SAMPLES)
def test_the_canonical_fold_matches_the_pipeline_it_replaced(raw: str) -> None:
    """The shared function reproduces the transform both callers spelled out."""
    assert fold_for_matching(raw) == _RUN.sub(" ", fold_diacritics(raw)).strip().casefold()


def test_the_fold_collapses_runs_rather_than_deleting_whitespace() -> None:
    """Collapsing and deleting are different operations, and this one collapses.

    The PDF label reader deletes whitespace instead. If this function ever began
    deleting, every marker comparison built on it would start matching text that
    differs by word boundaries.
    """
    assert fold_for_matching("a  \t b") == "a b"
    assert fold_for_matching("a  \t b") != "ab"
