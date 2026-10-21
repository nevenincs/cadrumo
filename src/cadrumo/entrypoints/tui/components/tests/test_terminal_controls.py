"""Imported text shown in a Cadrumo frame reaches the terminal without live controls.

The assertions read the exact terminal sequence Textual's compositor produces
for the screen, which is what the driver writes, so they cover the real render
pipeline rather than a widget's stored value.
"""

from __future__ import annotations

from typing import override

import pytest
from rich.cells import cell_len
from rich.segment import Segment
from textual._compositor import CompositorUpdate
from textual.app import App, ComposeResult
from textual.color import Color
from textual.widgets import DataTable, Static

from ..quiet_app import QuietApp
from ..terminal_controls import TerminalControlFilter

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ESC = chr(0x1B)
_C1_CSI = chr(0x9B)
_RLO = chr(0x202E)
_OSC52 = f"{_ESC}]52;c;eA=={chr(0x07)}"
_CLEAR = f"{_ESC}[2J"
_HOSTILE = f"Cafe{_OSC52}|{_C1_CSI}31m|{_RLO}gnp.exe|{_CLEAR}"


class _LedgerHarness(QuietApp[None]):
    @override
    def compose(self) -> ComposeResult:
        yield Static(_HOSTILE, markup=False)
        table: DataTable[str] = DataTable()
        table.add_columns("description")
        table.add_row(_HOSTILE)
        yield table


class _PlainHarness(App[None]):
    @override
    def compose(self) -> ComposeResult:
        yield Static(_HOSTILE, markup=False)


async def _terminal_sequence(app: App[None]) -> str:
    async with app.run_test(size=(80, 10)) as pilot:
        await pilot.pause()
        update = app.screen._compositor.render_update(full=True)
        assert isinstance(update, CompositorUpdate)
        return update.render_segments(app.console)


def _payload_controls(sequence: str) -> list[str]:
    return [
        name
        for name, needle in (("osc52", f"{_ESC}]52"), ("clear", _CLEAR), ("c1", _C1_CSI), ("bidi", _RLO))
        if needle in sequence
    ]


@pytest.mark.asyncio
async def test_plain_textual_frame_carries_the_imported_controls() -> None:
    """Precondition: without the filter Textual writes the payload's controls to the terminal."""
    sequence = await _terminal_sequence(_PlainHarness())

    assert _payload_controls(sequence) == ["osc52", "clear", "c1", "bidi"]


@pytest.mark.asyncio
async def test_cadrumo_frame_renders_imported_controls_inert_and_keeps_the_text() -> None:
    sequence = await _terminal_sequence(_LedgerHarness())

    assert _payload_controls(sequence) == []
    assert sequence.count("Cafe]52;c;eA==|31m|gnp.exe|[2J") == 2
    # Textual's own styling still reaches the terminal.
    assert f"{_ESC}[" in sequence


def test_filter_keeps_cell_width_and_control_segments() -> None:
    control = Segment(f"{_ESC}[1;1H", None, [])
    segments = [Segment(_HOSTILE), control, Segment("plain")]

    filtered = TerminalControlFilter().apply(segments, Color(0, 0, 0))

    assert filtered[1] is control
    assert filtered[2] is segments[2]
    assert cell_len(filtered[0].text) == cell_len(_HOSTILE)
    assert filtered[0].text == "Cafe]52;c;eA==|31m|gnp.exe|[2J"


def test_filter_returns_clean_lines_unchanged() -> None:
    segments = [Segment("Cafeteria Ñandú € — 12345678Z")]

    assert TerminalControlFilter().apply(segments, Color(0, 0, 0)) is segments
