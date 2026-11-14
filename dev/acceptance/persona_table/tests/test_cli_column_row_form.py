"""The saved rows the ``work form`` command prints give a return's row figures by the table's own one-row rule.

The parser reads the TAB lines and the JSON form whole or not at all; the mapper hands the one-row rule and the
conflict rule to :mod:`..row_figures`, so these tests compare with what that module answers for the same rows.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from typer.core import TyperCommand, TyperGroup

from ..cli_column.row_form import (
    FormValue,
    form_leaf_present,
    form_row_figures,
    merge_form_figures,
    parse_form_lines,
    parse_form_result,
)
from ..row_figures import merge_row_figures, single_row_figures

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ONE_PROPERTY = "renta_inmueble\tinmuebles\t1\t0063\t12000.00\nrenta_inmueble\tinmuebles\t1\t0065\t3500\n"
_TWO_PROPERTIES = _ONE_PROPERTY + "renta_inmueble\tinmuebles\t2\t0063\t800\nrenta_inmueble\tinmuebles\t2\t0067\t40\n"


def test_tab_lines_are_read_as_record_block_row_casilla_and_value() -> None:
    assert parse_form_lines(_ONE_PROPERTY) == (
        FormValue("renta_inmueble", "inmuebles", 1, "0063", "12000.00"),
        FormValue("renta_inmueble", "inmuebles", 1, "0065", "3500"),
    )


@pytest.mark.parametrize(
    "text",
    [
        "renta_inmueble\tinmuebles\t1\t0063\n",
        "renta_inmueble\tinmuebles\t1\t0063\t5\textra\n",
        "renta_inmueble\tinmuebles\tone\t0063\t5\n",
        "renta_inmueble\tinmuebles\t0\t0063\t5\n",
        "renta_inmueble\tinmuebles\t1\t\t5\n",
        "record\tblock\trow\tcasilla\tvalue\n",
        _ONE_PROPERTY + "a broken line\n",
    ],
)
def test_one_unreadable_line_gives_no_value_at_all(text: str) -> None:
    assert parse_form_lines(text) == ()


def test_blank_lines_and_no_output_give_no_value() -> None:
    assert parse_form_lines("") == parse_form_lines("\n\n") == ()


def test_the_json_form_is_read_whole_or_not_at_all() -> None:
    entry = {"record": "renta_inmueble", "block": "inmuebles", "row": 1, "casilla_id": "0063", "value": "12000.00"}

    assert parse_form_result({"values": [entry]}) == (FormValue("renta_inmueble", "inmuebles", 1, "0063", "12000.00"),)
    assert parse_form_result({"values": [entry, {**entry, "row": "x"}]}) == ()
    assert parse_form_result({"values": [entry, {"record": "renta_inmueble"}]}) == ()
    assert parse_form_result({"values": [{**entry, "value": None}]}) == ()
    assert parse_form_result({"values": "text"}) == ()
    assert parse_form_result({}) == ()


def test_the_one_row_a_casilla_is_held_by_gives_its_figure_as_the_table_gives_it() -> None:
    figures = form_row_figures(parse_form_lines(_ONE_PROPERTY))

    assert figures == {"0063": "12000", "0065": "3500"}
    held = {"0063": {"1": "12000.00"}, "0065": {"1": "3500"}}
    tabled = single_row_figures(held, {"0063": "0063", "0065": "0065"})
    assert {casilla: Decimal(text) for casilla, text in figures.items()} == {
        casilla: Decimal(text) for casilla, text in tabled.items()
    }


def test_a_casilla_in_several_rows_has_no_figure_and_the_others_keep_theirs() -> None:
    figures = form_row_figures(parse_form_lines(_TWO_PROPERTIES))

    assert figures == {"0065": "3500", "0067": "40"}


def test_a_zero_row_still_counts_as_a_row() -> None:
    values = parse_form_lines("r\tb\t1\t0063\t5\nr\tb\t2\t0063\t0\n")

    assert form_row_figures(values) == {}


def test_a_casilla_in_two_blocks_is_two_rows_and_a_repeated_line_is_not_collapsed() -> None:
    assert form_row_figures(parse_form_lines("r\ta\t1\t0063\t5\nr\tb\t1\t0063\t5\n")) == {}
    assert form_row_figures(parse_form_lines("r\ta\t1\t0063\t5\nr\ta\t1\t0063\t5\n")) == {}


def test_a_casilla_with_any_text_value_is_left_out() -> None:
    values = parse_form_lines(
        "r\tb\t1\t0001\tcalle mayor 1\nr\tb\t1\t0063\t5\nr\tb\t2\t0063\tn/a\nr\tb\t1\t0064\tNaN\n"
    )

    assert form_row_figures(values) == {}


def test_a_row_figure_fills_an_absent_or_zero_scalar_and_a_differing_nonzero_scalar_is_a_conflict() -> None:
    rows = {"0063": "12000", "0065": "3500", "0067": "40"}
    printed = (("0065", "3500.00"), ("0067", "41"))

    merged, conflicts = merge_form_figures(printed, rows)

    assert dict(merged) == {"0063": "12000", "0065": "3500.00", "0067": "41"}
    assert conflicts == ["casilla 0067 scalar 41 differs from its row figure 40"]
    assert conflicts == merge_row_figures(dict(printed), rows)[1]


def test_merged_figures_stay_sorted_by_casilla_id() -> None:
    merged, conflicts = merge_form_figures((("0100", "1"),), {"0063": "2"})

    assert merged == (("0063", "2"), ("0100", "1"))
    assert conflicts == []


def _tree(*, leaf: bool, group: bool = False) -> TyperGroup:
    work = TyperGroup(name="work", commands={"calculate": TyperCommand("calculate")})
    if leaf:
        work.add_command(TyperGroup(name="form") if group else TyperCommand("form"))
    modelo = TyperGroup(name="modelo", commands={"work": work})
    return TyperGroup(name="aeat", commands={"app": TyperGroup(name="app", commands={"modelo": modelo})})


def test_the_form_leaf_is_found_only_when_the_live_tree_has_it_as_a_command() -> None:
    assert form_leaf_present(_tree(leaf=True)) is True
    assert form_leaf_present(_tree(leaf=False)) is False
    assert form_leaf_present(_tree(leaf=True, group=True)) is False
    assert form_leaf_present(TyperCommand("aeat")) is False
