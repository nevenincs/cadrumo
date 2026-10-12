"""The session's disclosures in the terminal interface: counted by category, read a page at a time.

The status reply counts the disclosures and the runtime serves the full list by
page, as it does for the command line and MCP. The walk over those pages is the
application's pager; this module only words what it reads.
"""

from __future__ import annotations

from ...application.user_profile.access_contracts import DisclosurePage, EffectiveScopeSummary
from ...core.i18n.render import tr


def disclosure_summary_text(scope: EffectiveScopeSummary, empty: str) -> str:
    """Word the count and the per-category counts a status carries."""
    if not scope.disclosure_count:
        return empty
    categories = ", ".join(f"{item.category.value} {item.count}" for item in scope.disclosure_summary)
    return f"{scope.disclosure_count} ({categories})"


def disclosure_page_text(page: DisclosurePage) -> str:
    """Word one page: which entries of how many, then one line per entry."""
    if not page.entries:
        return tr("tui.restricted.disclosure_page_empty")
    heading = tr(
        "tui.restricted.disclosure_page",
        first=page.offset + 1,
        last=page.offset + len(page.entries),
        total=page.total,
    )
    lines = (f"{item.category.value}  {item.projection_id}  {item.destination_id}" for item in page.entries)
    return "\n".join((heading, *lines))


__all__ = ["disclosure_page_text", "disclosure_summary_text"]
