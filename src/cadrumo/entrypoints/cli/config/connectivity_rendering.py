"""CLI-owned human rendering for browser-connectivity status records."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core.i18n.render import tr

if TYPE_CHECKING:
    from ....adapters.outbound.aeat.browser.site_health_records import SiteHealthStatus


def render_browser_connectivity_text(status: SiteHealthStatus) -> str:
    """Render one site-health status as compact config-repair output."""
    markers = ", ".join(status.evidence.detected_markers) or tr("cli.diagnostics.browser.markers_none")
    lines = [
        f"{tr('cli.diagnostics.browser.target_label')}\t{tr('cli.diagnostics.browser.target_browser')}",
        f"{tr('cli.diagnostics.browser.state_label')}\t{status.state.value}",
        f"{tr('cli.diagnostics.browser.http_status_label')}\t{status.evidence.http_status}",
        f"{tr('cli.diagnostics.browser.markers_label')}\t{markers}",
        f"{tr('cli.diagnostics.browser.observed_at_label')}\t{status.observed_at.isoformat()}",
    ]
    if status.retry_after_seconds is not None:
        lines.append(f"{tr('cli.diagnostics.browser.retry_after_label')}\t{status.retry_after_seconds}")
    return "\n".join(lines) + "\n"


__all__ = ["render_browser_connectivity_text"]
