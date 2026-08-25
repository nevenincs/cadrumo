"""Adversarial proofs for the canonical safe error presentation component."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from cadrumo.core.errors import ErrorEnvelope
from cadrumo.core.prose_elision import PROSE_ELISION_MARKER
from cadrumo.entrypoints.tui.components.errors import (
    MAX_ERROR_MESSAGE_CHARACTERS,
    ErrorPanel,
    safe_error_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _envelope(message: str = "The operation could not continue.") -> ErrorEnvelope:
    return ErrorEnvelope(
        code="profile_refused",
        category="REFUSED",
        message=message,
        action=None,
        retryable=False,
        runbook_id=None,
        context={"unrendered": "safe internal context"},
        trace_id="trace-123",
    )


def test_error_record_uses_only_safe_envelope_facts_and_visibly_bounds_message() -> None:
    record = safe_error_record(_envelope(("safe " * 100).strip()))

    assert record.code == "profile_refused"
    assert record.category == "REFUSED"
    assert len(record.message) <= MAX_ERROR_MESSAGE_CHARACTERS
    assert record.message.endswith(PROSE_ELISION_MARKER)


@pytest.mark.asyncio
async def test_error_panel_never_mounts_envelope_context_or_trace_identifiers() -> None:
    class _Harness(App[None]):
        def compose(self) -> ComposeResult:
            yield ErrorPanel(_envelope(), id="error")

    app = _Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        rendered = "\n".join(str(widget.content) for widget in app.query(Static))

    assert "profile_refused" in rendered
    assert "The operation could not continue." in rendered
    assert "safe internal context" not in rendered
    assert "trace-123" not in rendered


@pytest.mark.parametrize(
    "unsafe_message",
    [
        "Traceback (most recent call last): hidden frame",
        r"Could not read C:\\private\\profile.json",
        "See https://sede.example.test/private/session",
        "Bearer synthetic-secret-token-value-1234567890",
        "The taxpayer NIF is 12345678Z",
    ],
)
def test_error_record_refuses_unredacted_diagnostic_material(unsafe_message: str) -> None:
    with pytest.raises(ValueError, match="safe for public TUI presentation"):
        safe_error_record(_envelope(unsafe_message))


def test_error_panel_refuses_a_raw_exception() -> None:
    with pytest.raises(TypeError, match="never a raw exception"):
        ErrorPanel(RuntimeError("untrusted"))  # type: ignore[arg-type]
