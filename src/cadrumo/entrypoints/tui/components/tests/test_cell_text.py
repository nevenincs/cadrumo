"""Display-cell fitting treats wide and combining characters by the cells they occupy."""

import pytest
from rich.cells import cell_len

from ..cell_text import ELLIPSIS, ellipsize, longest_word, wrap_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WIDE = "漢字" * 8
_DECOMPOSED = "é" * 12


def test_text_that_already_fits_is_returned_unchanged() -> None:
    assert ellipsize("Declaración", 11) == "Declaración"
    assert ellipsize(_DECOMPOSED, 12) == _DECOMPOSED


@pytest.mark.parametrize("width", [2, 3, 5, 8, 15, 16])
def test_wide_text_is_cut_to_the_cells_it_may_occupy(width: int) -> None:
    fitted = ellipsize(_WIDE, width)

    assert cell_len(fitted) <= width
    assert fitted.endswith(ELLIPSIS)
    assert _WIDE.startswith(fitted.removesuffix(ELLIPSIS))


def test_combining_marks_cost_no_cells_so_a_cut_keeps_more_than_the_code_point_count() -> None:
    fitted = ellipsize(_DECOMPOSED, 8)

    assert cell_len(fitted) == 8
    assert fitted == "é" * 7 + ELLIPSIS


def test_a_cut_never_leaves_a_dangling_space_before_the_ellipsis() -> None:
    assert ellipsize("Base imponible", 6) == "Base" + ELLIPSIS


@pytest.mark.parametrize("width", [1, 2, 3, 7])
def test_wrapped_wide_lines_stay_within_the_width_and_lose_nothing(width: int) -> None:
    lines = wrap_words(_WIDE, width)

    assert "".join(lines) == _WIDE
    assert all(cell_len(line) <= max(width, 2) for line in lines)


def test_wrapping_breaks_at_spaces_but_not_at_no_break_spaces() -> None:
    assert wrap_words("art.\u00a071 de la ley", 10) == ("art.\u00a071 de", "la ley")


def test_wrapping_an_empty_text_yields_one_empty_line() -> None:
    assert wrap_words("   ", 5) == ("",)


def test_the_longest_word_is_measured_in_cells() -> None:
    assert longest_word("a 漢字漢 bb") == 6
    assert longest_word("") == 0
