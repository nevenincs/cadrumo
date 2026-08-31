"""The apply cycle never leaves the operator's workbook empty.

The adapter used to clear every managed tab and then write, as two
unprotected Sheets calls. Sheets offers no transaction spanning
``values.batchClear`` and ``values.batchUpdate``, so an interruption between
them emptied the operator's workbook outright: the mirror holds no system
data, but the artefact the operator works in was destroyed and nothing
warned. The fix is ordering — write first, then clear only what the write
did not replace — so a run interrupted at any point leaves either the old
content or the new, never nothing.

These are offline request-pipeline tests, matching the sibling integration
module: write-shaped online tests against a real account are
project-forbidden, so what is gated here is that the assembled request set
carries the property, driven off a REAL modelo plan rather than a
hand-built fixture.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....application.storage.calc_sheets.engine import build_export_plan
from .....application.storage.calc_sheets.records import SheetCellAddress, TabName
from .....domain.calculations.registry.authority import bundled_authority
from .._calc_sheets_apply_values import (
    _build_evidence_value_data,
    _build_formula_data,
    _build_guide_value_data,
    _build_row_set_header_data,
    _build_value_data,
    payload_written_addresses,
    stale_addresses,
)
from ..calc_sheets_apply import _occupied_address_ranges, _occupied_addresses_from_response

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _m130_plan():
    snapshot = bundled_authority().snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))
    return build_export_plan(snapshot)


def _payload(plan) -> list[dict[str, object]]:
    """The exact payload the adapter hands to ``values.batchUpdate``."""
    raw_payload = (
        _build_value_data(plan.value_cells)
        + _build_guide_value_data(plan)
        + _build_row_set_header_data(plan.row_sets)
        + _build_evidence_value_data(plan)
        + _build_formula_data(plan.formula_cells)
    )
    payload: list[dict[str, object]] = []
    for item in raw_payload:
        assert isinstance(item, dict)
        normalized: dict[str, object] = {}
        for key, value in item.items():
            assert isinstance(key, str)
            normalized[key] = value
        payload.append(normalized)
    return payload


def test_occupied_ranges_keep_only_sorted_managed_positive_grids() -> None:
    """Operator tabs and zero-sized grids never enter the stale-clear read set."""
    second_tab = next(tab for tab in TabName if tab is not TabName.EVIDENCIA)

    ranges = _occupied_address_ranges(
        {
            "operator-notes": (99, 99),
            TabName.EVIDENCIA.value: (3, 2),
            second_tab.value: (0, 8),
        },
    )

    assert len(ranges) == 1
    assert ranges[0].tab is TabName.EVIDENCIA
    assert ranges[0].address == "'Evidencia'!A1:B3"


def test_occupied_response_preserves_zero_false_and_truncates_unaligned_blocks() -> None:
    """Only empty-string/None cells are vacant; missing or extra blocks cannot misalign tabs."""
    second_tab = next(tab for tab in TabName if tab is not TabName.EVIDENCIA)
    ranges = _occupied_address_ranges(
        {
            TabName.EVIDENCIA.value: (2, 3),
            second_tab.value: (2, 2),
        },
    )
    evidence_range = next(item for item in ranges if item.tab is TabName.EVIDENCIA)

    occupied = _occupied_addresses_from_response(
        ranges,
        {
            "valueRanges": [
                (
                    {"values": [["", None, 0], [False, "occupied"]]}
                    if address_range.tab is TabName.EVIDENCIA
                    else {"values": [["second-tab"]]}
                )
                for address_range in ranges
            ]
            + [
                {"values": [["must-not-map-to-any-tab"]]},
            ],
        },
    )

    assert occupied == {
        SheetCellAddress.at(evidence_range.tab, 1, 3).qualified(),
        SheetCellAddress.at(evidence_range.tab, 2, 1).qualified(),
        SheetCellAddress.at(evidence_range.tab, 2, 2).qualified(),
        SheetCellAddress.at(second_tab, 1, 1).qualified(),
    }
    missing_second = _occupied_addresses_from_response(ranges, {"valueRanges": [{"values": [["first"]]}]})
    assert missing_second == {SheetCellAddress.at(ranges[0].tab, 1, 1).qualified()}


class TestWrittenAddressesCoverThePayload:
    """The written set is the payload's real extent, not an approximation."""

    def test_a_real_modelo_payload_expands_to_every_cell_it_writes(self) -> None:
        payload = _payload(_m130_plan())
        assert payload, "the plan produced no value payload -- the gate below would be vacuous"
        written = payload_written_addresses(payload)
        # Every anchor is itself written, and multi-cell rows contribute
        # more addresses than there are entries. Both directions matter: the
        # first proves nothing was dropped, the second proves the row shape
        # is actually expanded rather than the anchor counted alone.
        anchors = {str(entry["range"]) for entry in payload}
        assert anchors <= written
        assert len(written) > len(anchors)

    def test_a_multi_cell_row_expands_across_its_columns(self) -> None:
        """A two-value row must yield both cells, not just the anchor."""
        entry = {"range": "'Evidencia'!B4", "values": [["left", "right"]]}
        written = payload_written_addresses([entry])
        assert written == {
            SheetCellAddress.at(TabName.EVIDENCIA, 4, 2).qualified(),
            SheetCellAddress.at(TabName.EVIDENCIA, 4, 3).qualified(),
        }

    def test_a_multi_row_block_expands_down_its_rows(self) -> None:
        entry = {"range": "'Evidencia'!A1", "values": [["a"], ["b"], ["c"]]}
        written = payload_written_addresses([entry])
        assert written == {SheetCellAddress.at(TabName.EVIDENCIA, row, 1).qualified() for row in (1, 2, 3)}

    def test_a_range_that_is_not_an_anchor_refuses_rather_than_under_reporting(self) -> None:
        """Silently skipping an unparsed entry is the data-destroying direction.

        An entry this function cannot expand would shrink the written set,
        which grows the stale set, which clears cells the write just filled.
        So it refuses loudly instead.
        """
        with pytest.raises(ValueError, match="single-cell anchor"):
            payload_written_addresses([{"range": "'Evidencia'!A1:C9", "values": [["x"]]}])


class TestStaleSetNeverNamesALiveCell:
    """The clear can only ever name cells the write did not fill."""

    def test_re_applying_the_same_plan_clears_nothing(self) -> None:
        """The common case must make no destructive call at all.

        A re-apply writes exactly what was there, so the stale set is empty
        and the adapter skips the batchClear entirely -- the destructive call
        is not merely reordered, it stops happening on the hot path.
        """
        written = payload_written_addresses(_payload(_m130_plan()))
        assert stale_addresses(occupied=written, written=written) == ()

    def test_a_cell_the_write_covers_is_never_stale(self) -> None:
        payload = _payload(_m130_plan())
        written = payload_written_addresses(payload)
        # Occupied is everything the write covers PLUS leftovers from a
        # longer previous run.
        leftovers = frozenset(SheetCellAddress.at(TabName.EVIDENCIA, row, 1).qualified() for row in range(9000, 9005))
        stale = stale_addresses(occupied=written | leftovers, written=written)
        assert set(stale) == set(leftovers)
        assert not (set(stale) & written)

    def test_a_shrinking_plan_clears_exactly_the_dropped_cells(self) -> None:
        """Positive control: the stale set is non-empty when it must be.

        Without this the suite could pass with a stale computation that
        always returns nothing -- which would silently restore the
        contamination the clear step exists to prevent.
        """
        previous = payload_written_addresses(
            [{"range": "'Evidencia'!A1", "values": [["a"], ["b"], ["c"], ["d"]]}],
        )
        current = payload_written_addresses(
            [{"range": "'Evidencia'!A1", "values": [["a"], ["b"]]}],
        )
        stale = stale_addresses(occupied=previous, written=current)
        assert set(stale) == {
            SheetCellAddress.at(TabName.EVIDENCIA, 3, 1).qualified(),
            SheetCellAddress.at(TabName.EVIDENCIA, 4, 1).qualified(),
        }

    def test_an_empty_workbook_yields_no_clear(self) -> None:
        """A first-ever apply has nothing to clear, so it makes one call."""
        written = payload_written_addresses(_payload(_m130_plan()))
        assert stale_addresses(occupied=frozenset(), written=written) == ()


class TestOrderingIsStructural:
    """The clear cannot precede the write, by construction rather than by care."""

    def test_the_clear_consumes_what_the_write_returns(self) -> None:
        """The stale computation's input does not exist until the write returns.

        ``_write_plan_values`` returns the addresses it wrote and
        ``_clear_stale_addresses`` requires them as a keyword argument, so
        the destructive call cannot be hoisted above the write without
        fabricating its input. Asserted on the signatures because that is
        where the guarantee lives -- a comment saying "write first" is a
        convention, a data dependency is not.
        """
        import inspect

        from ..calc_sheets_apply import _clear_stale_addresses, _write_plan_values

        assert inspect.signature(_write_plan_values).return_annotation == "frozenset[str]"
        clear_params = inspect.signature(_clear_stale_addresses).parameters
        assert "written" in clear_params
        assert "occupied" in clear_params

    def test_the_adapter_no_longer_clears_every_tab_wholesale(self) -> None:
        """The whole-tab clear is gone, not merely moved later.

        A reordered whole-tab clear would still empty the workbook for the
        duration of the write. What must be true is that no code path clears
        a bare tab range at all.
        """
        from pathlib import Path

        source = Path(_calc_sheets_apply_source()).read_text(encoding="utf-8")
        assert "clear_ranges = [f\"'{tab}'\" for tab in tab_titles]" not in source
        assert "_clear_and_write_plan_values" not in source


def _calc_sheets_apply_source() -> str:
    from .. import calc_sheets_apply

    assert calc_sheets_apply.__file__ is not None
    return calc_sheets_apply.__file__
