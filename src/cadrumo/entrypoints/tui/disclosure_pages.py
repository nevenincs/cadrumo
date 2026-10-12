"""The session's disclosures in the terminal interface: counted by category, read a page at a time.

The status reply counts the disclosures and the runtime serves the full list by
page, as it does for the command line and MCP. This module walks those pages
and words them; it decides nothing about what a session may disclose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...application.user_profile.access_contracts import (
    DisclosurePage,
    DisclosurePageRequest,
    EffectiveScopeSummary,
)
from ...core.i18n.render import tr
from ...core.identity.digest import ContentDigest


class DisclosurePageReader(Protocol):
    """The runtime client's page read of its own session's disclosures."""

    def disclosure_page(self, request: DisclosurePageRequest, *, timeout: float = 5) -> DisclosurePage:
        """Read one page of the disclosures this session's status counts."""
        ...


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


@dataclass
class DisclosurePager:
    """Walk one counted list from its start, page after page, and begin again after its last page.

    Every read is pinned to the digest of the list the status counted, so a
    list that changed is refused rather than read across two lists. A new
    digest starts the walk over.
    """

    reader: DisclosurePageReader
    digest: ContentDigest | None = None
    next_offset: int = 0

    def next_page(self, digest: ContentDigest) -> DisclosurePage:
        """Read the page after the last one read of the list ``digest`` names."""
        if digest != self.digest:
            self.digest, self.next_offset = digest, 0
        page = self.reader.disclosure_page(DisclosurePageRequest(offset=self.next_offset, expected_digest=digest))
        self.next_offset = page.next_offset or 0
        return page


__all__ = ["DisclosurePageReader", "DisclosurePager", "disclosure_page_text", "disclosure_summary_text"]
