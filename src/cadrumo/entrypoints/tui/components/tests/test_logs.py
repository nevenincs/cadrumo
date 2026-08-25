"""Adversarial proofs for bounded safe log presentation."""

from __future__ import annotations

import logging

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from cadrumo.core.prose_elision import PROSE_ELISION_MARKER
from cadrumo.entrypoints.tui.components.logs import (
    MAX_LOG_MESSAGE_CHARACTERS,
    BoundedLogPanel,
    LogSeverity,
    SafeLogRecord,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_safe_log_record_visibly_bounds_pre_redacted_prose() -> None:
    record = SafeLogRecord(LogSeverity.INFO, ("safe " * 100).strip())

    assert len(record.message) <= MAX_LOG_MESSAGE_CHARACTERS
    assert record.message.endswith(PROSE_ELISION_MARKER)


@pytest.mark.asyncio
async def test_bounded_log_panel_retains_only_the_requested_safe_tail() -> None:
    records = (
        SafeLogRecord(LogSeverity.INFO, "first safe record"),
        SafeLogRecord(LogSeverity.WARNING, "second safe record"),
        SafeLogRecord(LogSeverity.ERROR, "third safe record"),
    )

    class _Harness(App[None]):
        def compose(self) -> ComposeResult:
            yield BoundedLogPanel(records, maximum_entries=2, id="logs")

    app = _Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = app.query_one("#logs", BoundedLogPanel)
        rendered = "\n".join(str(widget.content) for widget in panel.query(Static))

    assert tuple(record.message for record in panel.records) == ("second safe record", "third safe record")
    assert "first safe record" not in rendered
    assert "WARNING: second safe record" in rendered
    assert "ERROR: third safe record" in rendered


@pytest.mark.parametrize(
    "unsafe_message",
    [
        "Traceback (most recent call last): hidden frame",
        r"Could not read C:\\private\\profile.json",
        "See https://sede.example.test/private/session",
        "password=synthetic-secret",
        "The taxpayer NIF is 12345678Z",
    ],
)
def test_safe_log_record_refuses_unredacted_diagnostic_material(unsafe_message: str) -> None:
    with pytest.raises(ValueError, match="safe for public TUI presentation"):
        SafeLogRecord(LogSeverity.ERROR, unsafe_message)


def test_bounded_log_panel_refuses_stdlib_logging_records() -> None:
    raw_record = logging.LogRecord("test", logging.ERROR, "unsafe.py", 1, "unsafe", (), None)

    with pytest.raises(TypeError, match="SafeLogRecord values only"):
        BoundedLogPanel((raw_record,))  # type: ignore[arg-type]
