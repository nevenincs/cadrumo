"""Walk a session's disclosures a page at a time, as a frontend that holds one session reads them.

The runtime serves the list by page; this walks those pages from the start,
pinned to the digest the status counted, and begins again after the last one.
It decides nothing about what a session may disclose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...core.identity.digest import ContentDigest
from .access_contracts import DisclosurePage, DisclosurePageRequest


class DisclosurePageReader(Protocol):
    """The runtime client's page read of its own session's disclosures."""

    def disclosure_page(self, request: DisclosurePageRequest, *, timeout: float = 5) -> DisclosurePage:
        """Read one page of the disclosures this session's status counts."""
        ...


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
