"""A let property's row figures fill the persona table's casillas only where the public scalar is zero or absent."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema_form_layouts import FormPlacementKind

from ..row_figures import merge_row_figures, on_form_casillas, single_row_figures, split_figures

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


PRINTED_BOX = "SEXO_C"
WORKING_FIGURE = "PH18"
_CALCULATED = (("0003", "36000"), ("PH18", "1"), ("RESINGDEV", "-2158.99"), ("0670", "-2158.99"))


def test_figures_split_into_the_casillas_on_the_form_and_the_ones_it_does_not_place() -> None:
    shown, internal = split_figures(_CALCULATED, frozenset({"0003", "0670"}))

    assert shown == (("0003", "36000"), ("0670", "-2158.99"))
    assert internal == (("PH18", "1"), ("RESINGDEV", "-2158.99"))


def test_a_revision_without_a_form_layout_keeps_every_figure_on_the_form() -> None:
    assert split_figures(_CALCULATED, None) == (_CALCULATED, ())


def test_a_form_that_places_none_of_the_figures_leaves_them_all_internal() -> None:
    assert split_figures(_CALCULATED, frozenset()) == ((), _CALCULATED)


def test_a_working_figure_is_not_on_the_form_while_a_printed_casilla_is() -> None:
    seen: list[tuple[bool, bool]] = []
    named: set[str] = set()
    with bundled_indexed_authority().operation() as operation:
        for modelo, revision_id in operation.revision_ids():
            layout = operation.form_layout(modelo, revision_id)
            if layout is None:
                assert on_form_casillas(operation, modelo, revision_id) is None
                continue
            placed = {str(placement.casilla_id): placement.kind for placement in layout.placements}
            on_form = on_form_casillas(operation, modelo, revision_id)
            assert on_form is not None
            for casilla in (PRINTED_BOX, WORKING_FIGURE):
                if (
                    modelo == "100"
                    and placed.get(casilla) is not None
                    and (casilla in on_form) is (placed[casilla] is FormPlacementKind.ON_FORM)
                ):
                    named.add(casilla)
            seen.extend(
                (kind is FormPlacementKind.ON_FORM, casilla in on_form)
                for casilla, kind in placed.items()
                if modelo == "100"
            )
    assert PRINTED_BOX in named and WORKING_FIGURE in named
    assert (True, True) in seen
    assert (False, False) in seen
    assert (True, False) not in seen
    assert (False, True) not in seen
