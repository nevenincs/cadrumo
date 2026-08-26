"""Real behavioral proofs that operation-feedback components stay render-only.

Status, error, and log presentation consume only already-classified, already
redacted public facts (`aeat-interface` D8): a spinner reflects a caller's
closed tone rather than any operation lifecycle, a safe error record renders
only the typed action/retry/runbook facts it was handed, and a bounded log
panel presents its own empty state and stays keyboard-focusable. None of
these assertions can be satisfied by a presence check alone -- a spinner
that never becomes visible, or a focus ring that a screen reader could not
reach, looks identical to a working one until driven at a real geometry.
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import LoadingIndicator, Static

from ..errors import ErrorPanel, SafeErrorRecord
from ..logs import BoundedLogPanel, LogSeverity, SafeLogRecord
from ..status import PinnedStatusBar

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _StatusHarness(App[None]):
    def compose(self) -> ComposeResult:
        yield PinnedStatusBar(summary="Sync", id="status")


@pytest.mark.asyncio
async def test_status_bar_spinner_is_visible_only_while_the_tone_is_progress() -> None:
    """The spinner reflects the caller's closed tone, never an operation state it reads itself."""
    app = _StatusHarness()
    async with app.run_test(size=(80, 24)) as pilot:
        bar = app.query_one("#status", PinnedStatusBar)
        spinner = bar.query_one(LoadingIndicator)

        assert not spinner.display, "an idle bar must not show a spinner"

        bar.show_progress("Working")
        await pilot.pause()
        assert spinner.display, "the progress tone must reveal the spinner"

        bar.show_success("Done")
        await pilot.pause()
        assert not spinner.display, "a final outcome tone must hide the spinner"

        bar.show_warning("Careful")
        await pilot.pause()
        assert not spinner.display

        bar.show_error("Failed")
        await pilot.pause()
        assert not spinner.display


def _record(**overrides: object) -> SafeErrorRecord:
    fields = {"code": "profile_refused", "category": "REFUSED", "message": "The operation could not continue."}
    fields.update(overrides)
    return SafeErrorRecord(**fields)  # type: ignore[arg-type]


class _ErrorHarness(App[None]):
    def __init__(self, record: SafeErrorRecord) -> None:
        super().__init__()
        self._record = record

    def compose(self) -> ComposeResult:
        yield ErrorPanel(self._record, id="error")


@pytest.mark.asyncio
async def test_error_panel_renders_action_retry_and_runbook_only_when_supplied() -> None:
    bare = _record()
    app = _ErrorHarness(bare)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        error = app.query_one("#error", ErrorPanel)
        assert len(error.query("#cadrumo-error-action")) == 0
        assert len(error.query("#cadrumo-error-runbook")) == 0
        retry = str(error.query_one("#cadrumo-error-retry", Static).render())
        assert retry.startswith("✕"), "a non-retryable record must not carry the retry glyph"


@pytest.mark.asyncio
async def test_error_panel_renders_every_typed_safe_extension_field_when_supplied() -> None:
    full = _record(action_label="Reconnect and try again", retryable=True, runbook_id="rb-profile-refused")
    app = _ErrorHarness(full)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        error = app.query_one("#error", ErrorPanel)
        action = str(error.query_one("#cadrumo-error-action", Static).render())
        retry = str(error.query_one("#cadrumo-error-retry", Static).render())
        runbook = str(error.query_one("#cadrumo-error-runbook", Static).render())

    assert "Reconnect and try again" in action
    assert retry.startswith("↻")
    assert "rb-profile-refused" in runbook


def test_safe_error_record_never_accepts_context_or_trace_fields() -> None:
    """`ErrorEnvelope.context`/`.trace_id` stay operator-support-only, never a public TUI field."""
    with pytest.raises(TypeError):
        SafeErrorRecord(  # type: ignore[call-arg]
            code="profile_refused",
            category="REFUSED",
            message="The operation could not continue.",
            context={"k": "v"},
        )
    with pytest.raises(TypeError):
        SafeErrorRecord(  # type: ignore[call-arg]
            code="profile_refused",
            category="REFUSED",
            message="The operation could not continue.",
            trace_id="trace-1",
        )


class _EmptyLogHarness(App[None]):
    def compose(self) -> ComposeResult:
        yield BoundedLogPanel((), id="logs")


@pytest.mark.asyncio
async def test_bounded_log_panel_renders_a_real_empty_state_and_is_keyboard_focusable() -> None:
    app = _EmptyLogHarness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        panel = app.query_one("#logs", BoundedLogPanel)
        empty = str(panel.query_one("#cadrumo-log-empty", Static).render())
        assert empty.strip(), "an empty log window must still render a visible state"

        await pilot.press("tab")
        await pilot.pause()
        assert app.focused is panel, "the log panel must be reachable by keyboard, not only visible"


class _PopulatedLogHarness(App[None]):
    def compose(self) -> ComposeResult:
        yield BoundedLogPanel(
            (SafeLogRecord(LogSeverity.INFO, "first record"), SafeLogRecord(LogSeverity.ERROR, "second record")),
            id="logs",
        )


@pytest.mark.asyncio
async def test_bounded_log_panel_with_records_carries_no_empty_state_marker() -> None:
    app = _PopulatedLogHarness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        panel = app.query_one("#logs", BoundedLogPanel)
        assert len(panel.query("#cadrumo-log-empty")) == 0
