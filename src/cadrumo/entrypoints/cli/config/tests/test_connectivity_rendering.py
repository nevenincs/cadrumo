"""CLI-owned rendering checks for browser-connectivity status records."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import AnyHttpUrl

from .....adapters.outbound.aeat.browser.site_health_records import SiteHealthEvidence, SiteHealthStatus
from .....core.errors.hierarchy import SiteHealthState
from ..connectivity_rendering import render_browser_connectivity_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_render_browser_connectivity_text_resolves_row_label_keys() -> None:
    """``config repair connectivity`` row keys must resolve, not leak ``.label``.

    Before fix: the browser diagnostics locale keys were unfilled, so
    ``tr('cli.diagnostics.browser.target_label')`` fell back to the
    humanised last segment and rendered ``Target label`` — the i18n
    ``.label`` key suffix bled into the operator-facing string.
    After fix: each key resolves to a real translated label.
    """
    status = SiteHealthStatus(
        state=SiteHealthState.OK,
        evidence=SiteHealthEvidence(
            url=AnyHttpUrl("https://example.org/"),
            http_status=200,
            html_fragment="<html></html>",
            detected_markers=("healthy",),
        ),
        observed_at=datetime(2026, 5, 21, 12, 0, 0, tzinfo=UTC),
        retry_after_seconds=None,
    )

    rendered = render_browser_connectivity_text(status)

    assert "label" not in rendered.lower()
    assert "cli.diagnostics" not in rendered
    first_keys = {line.split("\t", 1)[0] for line in rendered.splitlines()}
    assert all(key for key in first_keys)
