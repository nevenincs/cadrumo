"""Saved filing navigation renders application projections without reopening work."""

from __future__ import annotations

import asyncio

import pytest
from textual.widgets import DataTable, Select, Static

from .....application.modelo.filing_record_view_operation import ModeloFilingRecordViewRequest, capture
from .....application.modelo.tests.test_filing_record_view_operation import PROFILE, filing_record_view_operation_bundle
from .....application.modelo.tests.test_related_filing_projection import _chain
from .....core.external_constants import OutputLanguage
from ...components.host import ScreenHostApp
from ...tests.frame import geometry_band
from ...tests.settling import settle
from ..saved_filing import SavedFilingScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _views():
    unit, records, catalogue = _chain(branched=False)
    bundle = filing_record_view_operation_bundle(unit=unit, filing_catalogue=catalogue)
    views = {
        record.filing_record_id: capture(
            ModeloFilingRecordViewRequest(
                profile_id=PROFILE, filing_record_id=record.filing_record_id, output_language=OutputLanguage.EN
            ),
            bundle,
        )
        for record in records
    }
    return records, views


@pytest.mark.asyncio
async def test_picker_and_links_keep_exact_original_and_corrective_ids() -> None:
    records, views = _views()
    original, first, latest = records
    reads = []

    async def read(filing_id):
        reads.append(filing_id)
        return views[filing_id]

    screen = SavedFilingScreen(original.filing_record_id, read)
    async with ScreenHostApp[None](screen).run_test(size=(80, 30)) as pilot:
        await settle(pilot)
        picker = screen.query_one("#saved-filing-select", Select)
        assert picker.value == original.filing_record_id
        links = screen.query_one("#saved-filing-links", DataTable)
        assert [row.key.value for row in links.ordered_rows] == [first.filing_record_id]
        picker.value = latest.filing_record_id
        await settle(pilot)
        assert [row.key.value for row in links.ordered_rows] == [first.filing_record_id]
        links.focus()
        await pilot.press("enter")
        await settle(pilot)
        assert picker.value == first.filing_record_id
        assert {row.key.value for row in links.ordered_rows} == {original.filing_record_id, latest.filing_record_id}
        assert screen.query_one("#saved-filing-values", DataTable).row_count == 0
        assert str(screen.query_one("#saved-filing-notice", Static).render())
        assert geometry_band(screen.app, 80) == []
    assert reads == [original.filing_record_id, latest.filing_record_id, first.filing_record_id]


@pytest.mark.asyncio
async def test_late_saved_read_cannot_replace_newer_selection() -> None:
    records, views = _views()
    original, _first, latest = records
    gate = asyncio.Event()
    started = asyncio.Event()
    selected = asyncio.Event()

    async def read(filing_id):
        if filing_id == original.filing_record_id:
            started.set()
            await gate.wait()
        else:
            selected.set()
        return views[filing_id]

    screen = SavedFilingScreen(original.filing_record_id, read)
    async with ScreenHostApp[None](screen).run_test(size=(100, 40)) as pilot:
        await asyncio.wait_for(started.wait(), timeout=5)
        screen._load(latest.filing_record_id)
        await asyncio.wait_for(selected.wait(), timeout=5)
        gate.set()
        await settle(pilot)
        assert screen.query_one("#saved-filing-select", Select).value == latest.filing_record_id
        links = screen.query_one("#saved-filing-links", DataTable)
        assert [row.key.value for row in links.ordered_rows] == [records[1].filing_record_id]
