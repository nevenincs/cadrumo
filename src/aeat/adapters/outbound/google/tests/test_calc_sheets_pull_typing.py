"""Real-behavior tests for the calc-sheets pull adapter type refinements.

Exercises the helpers whose ``-> Any`` annotations were narrowed to
typed aliases (``_ValueRange``, ``_GoogleResource`` via Protocol) to
confirm the structural contracts hold at runtime — no mocks, no patches.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._calc_sheets_pull import (
    _batch_get_values,
    _decode_binding_edits,
    _decode_operator_edits,
    _decode_relation_edits,
    _raw_cell_value,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# ---------------------------------------------------------------------------
# _ValueRange structural shape preserved through helpers
# ---------------------------------------------------------------------------


def _value_range(range_: str, values: list[list[object]]) -> dict[str, object]:
    return {"range": range_, "values": values}


def test_raw_cell_value_returns_first_cell_from_value_range() -> None:
    vr = _value_range("Entradas!B2", [[42]])
    result = _raw_cell_value([vr], 0)
    assert result == 42


def test_raw_cell_value_returns_none_for_empty_rows() -> None:
    vr = _value_range("Entradas!B2", [])
    assert _raw_cell_value([vr], 0) is None


def test_raw_cell_value_returns_none_for_cursor_beyond_list() -> None:
    assert _raw_cell_value([], 5) is None


def test_raw_cell_value_returns_none_for_empty_inner_row() -> None:
    vr = _value_range("Entradas!B2", [[]])
    assert _raw_cell_value([vr], 0) is None


# ---------------------------------------------------------------------------
# _batch_get_values short-circuits on empty ranges without an API call
# ---------------------------------------------------------------------------


def test_batch_get_values_returns_empty_list_for_empty_ranges() -> None:
    """No API call must be issued when ranges is empty.

    ``_batch_get_values`` is the primary entry point narrowed from
    ``list[Any]`` to ``list[_ValueRange]``.  Passing empty ranges is the
    only branch exercisable without live credentials; a real list is
    returned and its type is correct (empty list of dicts).
    """

    # A sentinel object with no .spreadsheets() attribute so any call
    # beyond the empty-list guard would raise AttributeError.
    class _NeverCalledSheets:
        def spreadsheets(self) -> object:
            raise AssertionError("spreadsheets() must not be called for empty ranges")

    result = _batch_get_values(_NeverCalledSheets(), "some-id", [])  # type: ignore[arg-type]
    assert result == []
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# _decode_operator_edits over typed _ValueRange list
# ---------------------------------------------------------------------------


def test_decode_operator_edits_returns_empty_for_no_ids() -> None:
    edits, cursor, count = _decode_operator_edits([], 0, [], {})
    assert edits == ()
    assert cursor == 0
    assert count == 0


def test_decode_operator_edits_reads_decimal_from_value_range() -> None:
    """Use a real casilla pulled from the live registry to exercise the helper."""

    from .....core.resources import bundled_path
    from .....domain.calculations.registry import ValidatedRegistryAuthority
    from .....domain.calculations.registry._schema import InputKind

    authority = ValidatedRegistryAuthority.load(bundled_path("registry", "aeat"), source_root=bundled_path())
    snapshot = authority.snapshot("130", filing_year=2024, period="2T")
    manual_casillas = [c for c in snapshot.revision.casillas if c.input_kind == InputKind.MANUAL]
    assert manual_casillas, "bundled 130/2T-2024 snapshot must contain at least one MANUAL casilla"

    casilla = manual_casillas[0]
    casilla_id = casilla.id
    casilla_by_id = {casilla_id: casilla}
    vr = _value_range("Entradas!B2", [[1234]])
    edits, cursor, count = _decode_operator_edits([vr], 0, [casilla_id], casilla_by_id)
    assert len(edits) == 1
    assert edits[0].casilla_id == casilla_id
    assert edits[0].value == Decimal("1234")
    assert cursor == 1
    assert count == 1


# ---------------------------------------------------------------------------
# _decode_binding_edits over typed _ValueRange list
# ---------------------------------------------------------------------------


def test_decode_binding_edits_returns_empty_for_no_ids() -> None:
    edits, cursor, count = _decode_binding_edits([], 0, [])
    assert edits == ()
    assert cursor == 0
    assert count == 0


def test_decode_binding_edits_reads_string_from_value_range() -> None:
    binding_id: str = "ccaa"
    vr = _value_range("Bindings!C3", [["madrid"]])
    edits, cursor, count = _decode_binding_edits([vr], 0, [binding_id])  # type: ignore[arg-type]
    assert len(edits) == 1
    assert edits[0].binding == binding_id
    assert edits[0].value == "madrid"
    assert cursor == 1
    assert count == 1


# ---------------------------------------------------------------------------
# _decode_relation_edits over typed _ValueRange list
# ---------------------------------------------------------------------------


def test_decode_relation_edits_returns_empty_for_no_ids() -> None:
    edits, cursor, count = _decode_relation_edits([], 0, [], {})
    assert edits == ()
    assert cursor == 0
    assert count == 0


def test_decode_relation_edits_reads_decimal_from_value_range() -> None:
    relation_id: str = "r001"
    vr = _value_range("Tarifas!D4", [[99.5]])
    edits, cursor, count = _decode_relation_edits([vr], 0, [relation_id], {})  # type: ignore[arg-type]
    assert len(edits) == 1
    assert edits[0].relation == relation_id
    assert edits[0].value == Decimal("99.5")
    assert cursor == 1
    assert count == 1
