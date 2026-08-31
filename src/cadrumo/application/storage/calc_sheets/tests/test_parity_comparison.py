"""The parity comparison must be usable without the write path that acquires its inputs.

`verify_modelo_parity` acquires its spreadsheet side by creating or updating the
workbook, seeding operator inputs and reading cells back. The export preview must
answer the same question — which cells would change — while writing nothing, so
the comparison has to be reachable without that path. These tests pin both the
decoupling and the comparison rules it carries.
"""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest

from .....domain.calculations.registry.authority import bundled_authority
from .....domain.calculations.registry.schema_input_kind import InputKind
from .....domain.calculations.registry.schema_surfaces import CasillaDefinition
from .. import _parity_comparison
from .._parity_comparison import CasillaParity, collect_parity_rows, resolve_parity_verdict

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _computed_casillas() -> tuple[CasillaDefinition, ...]:
    """Return the real bundled Modelo 130 computed casillas used as the subject."""
    modelo = next(definition for definition in bundled_authority().modelos if definition.id == "130")
    revision = modelo.revisions["2019-y-siguientes"]
    computed = tuple(casilla for casilla in revision.casillas if casilla.input_kind == InputKind.COMPUTED)
    assert computed, "subject revision declares no computed casilla; the tests would be vacuous"
    return computed


def test_the_comparison_reaches_neither_the_harness_nor_google() -> None:
    """Decoupling is the point of the extraction, so it is asserted rather than assumed."""
    source = inspect.getsource(_parity_comparison)

    assert "_parity_harness" not in source
    assert "google" not in source.lower()


def test_agreeing_surfaces_produce_no_divergence() -> None:
    """Three surfaces holding the same figure must not be reported as disagreeing."""
    casillas = _computed_casillas()
    values = {casilla.id: Decimal("100.00") for casilla in casillas}

    rows, divergences = collect_parity_rows(
        casillas=casillas,
        local_values=values,
        sheets_values=values,
        aeat_values=values,
        inputs_by_id={},
    )

    assert len(rows) == len(casillas)
    assert divergences == ()
    assert all(row.sheets_vs_local and row.local_vs_aeat and row.sheets_vs_aeat for row in rows)


def test_a_disagreeing_surface_is_reported_against_the_casilla_that_disagrees() -> None:
    """One divergent cell must surface as one divergent row, not as a whole-report verdict."""
    casillas = _computed_casillas()
    subject = casillas[0]
    local = {casilla.id: Decimal("100.00") for casilla in casillas}
    sheets = dict(local)
    sheets[subject.id] = Decimal("250.00")

    rows, divergences = collect_parity_rows(
        casillas=casillas,
        local_values=local,
        sheets_values=sheets,
        aeat_values={},
        inputs_by_id={},
    )

    assert [row.casilla_id for row in divergences] == [subject.id]
    # The divergent list is a sublist, never a re-derivation.
    assert all(row in rows for row in divergences)


def test_a_blank_sheets_cell_for_a_computed_casilla_is_a_divergence() -> None:
    """A formula that produced nothing is a failure the operator must see, not a silent skip."""
    casillas = _computed_casillas()
    subject = casillas[0]
    local = {casilla.id: Decimal("100.00") for casilla in casillas}
    sheets = {casilla.id: Decimal("100.00") for casilla in casillas if casilla.id != subject.id}

    _rows, divergences = collect_parity_rows(
        casillas=casillas,
        local_values=local,
        sheets_values=sheets,
        aeat_values={},
        inputs_by_id={},
    )

    assert [row.casilla_id for row in divergences] == [subject.id]


def test_an_absent_oracle_leaves_the_aeat_flags_unset_rather_than_false() -> None:
    """Not compared must stay distinguishable from compared and disagreed."""
    casillas = _computed_casillas()
    values = {casilla.id: Decimal("100.00") for casilla in casillas}

    rows, divergences = collect_parity_rows(
        casillas=casillas,
        local_values=values,
        sheets_values=values,
        aeat_values={},
        inputs_by_id={},
    )

    assert divergences == ()
    assert all(row.local_vs_aeat is None and row.sheets_vs_aeat is None for row in rows)


def test_the_preview_use_reads_divergences_as_the_cells_that_would_change() -> None:
    """The export preview's question is this comparison with the plan on the local side."""
    casillas = _computed_casillas()
    would_write = {casilla.id: Decimal("100.00") for casilla in casillas}
    currently_holds = dict(would_write)
    changing = casillas[0]
    currently_holds[changing.id] = Decimal("42.00")

    _rows, divergences = collect_parity_rows(
        casillas=casillas,
        local_values=would_write,
        sheets_values=currently_holds,
        aeat_values={},
        inputs_by_id={},
    )

    assert [row.casilla_id for row in divergences] == [changing.id]
    assert isinstance(divergences[0], CasillaParity)


def test_no_oracle_is_inconclusive_and_never_all_match() -> None:
    """Two local surfaces agreeing says nothing about whether either matches AEAT."""
    assert resolve_parity_verdict(divergences=(), aeat_present=False) == "inconclusive"
    assert resolve_parity_verdict(divergences=(), aeat_present=True) == "all_match"


def test_any_divergence_outranks_the_oracle_question() -> None:
    """A divergence is a divergence whether or not an oracle was supplied."""
    casillas = _computed_casillas()
    row = CasillaParity(casilla_id=casillas[0].id, display_number="1", label="x")

    assert resolve_parity_verdict(divergences=(row,), aeat_present=False) == "divergence"
    assert resolve_parity_verdict(divergences=(row,), aeat_present=True) == "divergence"
