"""Pure payload address coverage for fresh review publication.

Fresh publication and preservation of external edits are exercised through the
receipt-bound HTTP integration tests in test_review_publication.py. These local
tests do not establish real Google acceptance.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....application.storage.calc_sheets.engine import build_export_plan
from .....application.storage.calc_sheets.records import SheetCellAddress, TabName
from .....domain.calculations.registry.tests.published_authority import published_snapshot
from .._calc_sheets_apply_values import (
    build_evidence_value_data,
    build_formula_data,
    build_guide_value_data,
    build_row_set_header_data,
    build_value_data,
    written_cell_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _m130_plan():
    snapshot = published_snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))
    return build_export_plan(snapshot)


def _payload(plan) -> list[dict[str, object]]:
    """The exact payload the adapter hands to ``values.batchUpdate``."""
    raw_payload = (
        build_value_data(plan.value_cells)
        + build_guide_value_data(plan)
        + build_row_set_header_data(plan.row_sets)
        + build_evidence_value_data(plan)
        + build_formula_data(plan.formula_cells)
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


class TestWrittenAddressesCoverThePayload:
    """The written set is the payload's real extent, not an approximation."""

    def test_a_real_modelo_payload_expands_to_every_cell_it_writes(self) -> None:
        payload = _payload(_m130_plan())
        assert payload, "the plan produced no value payload -- the gate below would be vacuous"
        written = frozenset(written_cell_values(payload))
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
        written = frozenset(written_cell_values([entry]))
        assert written == {
            SheetCellAddress.at(TabName.EVIDENCIA, 4, 2).qualified(),
            SheetCellAddress.at(TabName.EVIDENCIA, 4, 3).qualified(),
        }

    def test_a_multi_row_block_expands_down_its_rows(self) -> None:
        entry = {"range": "'Evidencia'!A1", "values": [["a"], ["b"], ["c"]]}
        written = frozenset(written_cell_values([entry]))
        assert written == {SheetCellAddress.at(TabName.EVIDENCIA, row, 1).qualified() for row in (1, 2, 3)}

    def test_a_range_that_is_not_an_anchor_refuses_rather_than_under_reporting(self) -> None:
        """Silently skipping an unparsed entry is the data-destroying direction.

        An entry this function cannot expand would shrink the written set,
        which grows the stale set, which clears cells the write just filled.
        So it refuses loudly instead.
        """
        with pytest.raises(ValueError, match="single-cell anchor"):
            written_cell_values([{"range": "'Evidencia'!A1:C9", "values": [["x"]]}])


class TestOrderingIsStructural:
    """The clear cannot precede the write, by construction rather than by care."""

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
