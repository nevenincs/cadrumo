"""Adversarial proofs for the canonical safe error presentation component."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from .....core.prose_elision import PROSE_ELISION_MARKER
from ..errors import (
    MAX_ERROR_MESSAGE_CHARACTERS,
    ErrorPanel,
    SafeErrorRecord,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _record(message: str = "The operation could not continue.") -> SafeErrorRecord:
    return SafeErrorRecord(
        code="profile_refused",
        category="REFUSED",
        message=message,
    )


def test_error_record_uses_only_safe_envelope_facts_and_visibly_bounds_message() -> None:
    record = _record(("safe " * 100).strip())

    assert record.code == "profile_refused"
    assert record.category == "REFUSED"
    assert len(record.message) <= MAX_ERROR_MESSAGE_CHARACTERS
    assert record.message.endswith(PROSE_ELISION_MARKER)


@pytest.mark.asyncio
async def test_error_panel_never_mounts_envelope_context_or_trace_identifiers() -> None:
    class _Harness(App[None]):
        def compose(self) -> ComposeResult:
            yield ErrorPanel(_record(), id="error")

    app = _Harness()
    async with app.run_test() as pilot:
        await pilot.pause()
        rendered = "\n".join(str(widget.content) for widget in app.query(Static))

    assert "profile_refused" in rendered
    assert "The operation could not continue." in rendered


@pytest.mark.parametrize(
    "unsafe_message",
    [
        "Traceback (most recent call last): hidden frame",
        r"Could not read C:\\private\\profile.json",
        "See https://sede.example.test/private/session",
        "Bearer synthetic-secret-token-value-1234567890",
    ],
)
def test_error_record_refuses_unredacted_diagnostic_material(unsafe_message: str) -> None:
    with pytest.raises(ValueError, match="safe for public TUI presentation"):
        _record(unsafe_message)
