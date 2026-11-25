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

_ONE_PROPERTY = "record\tinmuebles\t1\t0063\t12000.00\nrecord\tinmuebles\t1\t0065\t3500\n"
_TWO_PROPERTIES = _ONE_PROPERTY + "record\tinmuebles\t2\t0063\t800\nrecord\tinmuebles\t2\t0067\t40\n"


def test_tab_lines_are_read_as_record_block_row_casilla_and_value() -> None:
    assert parse_form_lines(_ONE_PROPERTY) == (
        FormValue("record", "inmuebles", 1, "0063", "12000.00"),
        FormValue("record", "inmuebles", 1, "0065", "3500"),
    )


@pytest.mark.parametrize(
    "text",
    [
        "record\tinmuebles\t1\t0063\n",
        "record\tinmuebles\t1\t0063\t5\textra\n",
        "record\tinmuebles\tone\t0063\t5\n",
        "record\tinmuebles\t0\t0063\t5\n",
        "record\tinmuebles\t1\t\t5\n",
        "record\tblock\trow\tcasilla\tvalue\n",
        _ONE_PROPERTY + "a broken line\n",
    ],
)
def test_one_unreadable_line_gives_no_value_at_all(text: str) -> None:
    assert parse_form_lines(text) == ()


def test_blank_lines_and_no_output_give_no_value() -> None:
    assert parse_form_lines("") == parse_form_lines("\n\n") == ()


def _json_block(*cells: object, known: bool = True) -> dict[str, object]:
    records = [{"index": 1, "values": list(cells)}] if cells else []
    return {"block_id": "inmueble-rows", "rows_known": known, "records": records if known else []}


def test_the_json_form_is_read_whole_or_not_at_all() -> None:
    cell = {"column_key": "a", "casilla_id": "0063", "kind": "decimal", "value": "12000.00", "value_text": None}
    block = _json_block(cell)

    assert parse_form_result({"blocks": [block]}) == (FormValue("record", "inmueble-rows", 1, "0063", "12000.00"),)
    assert parse_form_result({"blocks": [block, _json_block({**cell, "value": None})]}) == ()
    assert parse_form_result({"blocks": [block, _json_block({"casilla_id": "0065"})]}) == ()
    assert parse_form_result({"blocks": [block, {**block, "records": [{"index": 0, "values": [cell]}]}]}) == ()
    assert parse_form_result({"blocks": [block, {"block_id": "x"}]}) == ()
    assert parse_form_result({"blocks": "text"}) == ()
    assert parse_form_result({}) == ()


def test_an_unknown_block_adds_no_value_and_a_cell_no_casilla_owns_is_skipped() -> None:
    cell = {"casilla_id": "0063", "value": "5"}
    other = {"casilla_id": None, "value": "text"}

    assert parse_form_result({"blocks": [_json_block(known=False), _json_block(cell, other)]}) == (
        FormValue("record", "inmueble-rows", 1, "0063", "5"),
    )
    assert parse_form_result({"blocks": [{**_json_block(known=False), "records": [{"index": 1, "values": []}]}]}) == ()


def test_the_text_form_skips_header_block_and_column_lines() -> None:
    text = (
        (
            "operation@modelo.work.form!work_unit_id@w!block@inmueble-rows@known@1!"
            "record_column@inmueble-rows@1@notas@hola!record@inmueble-rows@1@0063@5!block@hijo-rows@unknown@words!"
        )
        .replace("@", "\t")
        .replace("!", "\n")
    )

    assert parse_form_lines(text) == (FormValue("record", "inmueble-rows", 1, "0063", "5"),)


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
    values = parse_form_lines("r\tb\t1\t0063\t5\nrecord\tb\t2\t0063\t0\n")

    assert form_row_figures(values) == {}


def test_a_casilla_in_two_blocks_is_two_rows_and_a_repeated_line_is_not_collapsed() -> None:
    assert form_row_figures(parse_form_lines("r\ta\t1\t0063\t5\nrecord\tb\t1\t0063\t5\n")) == {}
    assert form_row_figures(parse_form_lines("r\ta\t1\t0063\t5\nrecord\ta\t1\t0063\t5\n")) == {}


def test_a_text_value_of_one_row_is_kept_as_printed_and_a_text_casilla_in_several_rows_has_no_figure() -> None:
    values = parse_form_lines(
        "record\tb\t1\t0066\t0000002VK0000N0001LH\nrecord\tb\t1\t0093\tref-b\n"
        "record\tb\t1\t0063\t5\nrecord\tb\t2\t0063\tn/a\n"
        "record\tb\t1\t0120\tref-c\nrecord\tb\t2\t0120\tref-d\n"
    )

    assert form_row_figures(values) == {"0066": "0000002VK0000N0001LH", "0093": "ref-b"}


def test_a_text_row_figure_fills_an_absent_scalar_and_a_differing_printed_text_is_a_conflict() -> None:
    merged, conflicts = merge_form_figures((("0100", "1"),), {"0093": "ref-b"})

    assert merged == (("0093", "ref-b"), ("0100", "1"))
    assert conflicts == []
    _, conflicts = merge_form_figures((("0093", "ref-a"),), {"0093": "ref-b"})
    assert conflicts == ["casilla 0093 scalar ref-a differs from its row figure ref-b"]


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


_REDACTED = "sha256:0123abcd"


def test_a_redacted_value_of_one_row_is_kept_as_printed_and_numeric_rules_stay() -> None:
    values = parse_form_lines(
        f"record\tb\t1\t0091\t{_REDACTED}\nrecord\tb\t1\t0063\t12000.00\nrecord\tb\t1\t0001\tcalle mayor 1\n"
    )

    assert form_row_figures(values) == {"0091": _REDACTED, "0063": "12000", "0001": "calle mayor 1"}


def test_a_redacted_value_in_several_rows_or_mixed_with_a_number_has_no_figure() -> None:
    assert (
        form_row_figures(parse_form_lines(f"record\tb\t1\t0091\t{_REDACTED}\nrecord\tb\t2\t0091\t{_REDACTED}\n")) == {}
    )
    assert form_row_figures(parse_form_lines(f"record\tb\t1\t0091\t{_REDACTED}\nrecord\tb\t2\t0091\t5\n")) == {}
    assert form_row_figures(parse_form_lines("r\tb\t1\t0091\tsha256:0123ABCD\n")) == {}


def test_a_redacted_row_figure_is_added_and_named_while_numeric_conflicts_stay_numeric() -> None:
    rows = {"0091": _REDACTED, "0067": "40"}

    merged, notes = merge_form_figures((("0067", "41"),), rows)

    assert dict(merged) == {"0067": "41", "0091": _REDACTED}
    assert notes == ["casilla 0067 scalar 41 differs from its row figure 40", "redacted: 0091"]


def test_a_redacted_row_figure_fills_only_an_absent_or_zero_figure_and_a_different_one_conflicts() -> None:
    assert merge_form_figures((("0091", "0"),), {"0091": _REDACTED}) == ((("0091", _REDACTED),), ["redacted: 0091"])
    same = merge_form_figures((("0091", _REDACTED),), {"0091": _REDACTED})
    assert same == ((("0091", _REDACTED),), ["redacted: 0091"])
    other, notes = merge_form_figures((("0091", "sha256:ffffffff"),), {"0091": _REDACTED})
    assert dict(other) == {"0091": "sha256:ffffffff"}
    assert notes == [f"casilla 0091 scalar sha256:ffffffff differs from its row figure {_REDACTED}", "redacted: 0091"]


def test_no_redacted_figure_adds_no_note() -> None:
    assert merge_form_figures((("0100", "1"),), {"0063": "2"})[1] == []
