"""A let property's row figures fill the persona table's casillas only where the public scalar is zero or absent."""

from __future__ import annotations

import pytest

from ..row_figures import merge_row_figures, single_row_figures

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FED = {"binding-ingresos": "0102", "binding-gastos": "0109"}


def test_one_row_gives_its_figure_by_the_target_casilla() -> None:
    assert single_row_figures({"binding-ingresos": {"1": "11400"}}, _FED) == {"0102": "11400"}


def test_two_rows_give_no_figure_so_a_stated_value_stays_unmet() -> None:
    figures = single_row_figures({"binding-ingresos": {"1": "11400", "2": "9000"}}, _FED)

    assert figures == {}
    merged, conflicts = merge_row_figures({"0102": "0"}, figures)
    assert merged["0102"] == "0"
    assert conflicts == []


def test_a_binding_no_column_feeds_is_ignored() -> None:
    assert single_row_figures({"binding-other": {"1": "5"}}, _FED) == {}


def test_a_row_figure_fills_a_zero_or_absent_scalar() -> None:
    merged, conflicts = merge_row_figures(
        {"0102": "0", "0109": "0.00"}, {"0102": "11400", "0109": "540", "0114": "186"}
    )

    assert (merged["0102"], merged["0109"], merged["0114"]) == ("11400", "540", "186")
    assert conflicts == []


def test_a_nonzero_scalar_that_differs_from_the_row_figure_is_a_conflict_naming_both_and_is_not_overridden() -> None:
    merged, conflicts = merge_row_figures({"0102": "9000"}, {"0102": "11400"})

    assert merged["0102"] == "9000"
    assert conflicts == ["casilla 0102 scalar 9000 differs from its row figure 11400"]


def test_a_nonzero_scalar_equal_to_the_row_figure_is_no_conflict() -> None:
    assert merge_row_figures({"0102": "11400.00"}, {"0102": "11400"})[1] == []
