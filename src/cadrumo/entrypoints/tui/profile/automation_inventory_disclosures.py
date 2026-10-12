"""Read the selected grant's or request's disclosures a page at a time.

The inventory counts each scope's disclosures by category; the full list of
one is read through the same inventory operation, by page, as the command line
reads it. The walk over the pages is the application's pager.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from textual.widgets import Button, Static

from ....adapters.local_runtime.automation_inventory import read_automation_inventory
from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.user_profile.access_contracts import DisclosurePage, DisclosurePageRequest
from ....application.user_profile.disclosure_paging import DisclosurePager
from ....core.async_cleanup import await_cancellation_complete
from ....core.i18n.render import tr
from ..disclosure_pages import disclosure_page_text

if TYPE_CHECKING:
    from .automation_inventory import RuntimeAutomationInventoryScreen


@dataclass(frozen=True)
class InventoryDisclosureReader:
    """Read pages of one grant's or pending request's disclosures from the inventory."""

    client: RuntimeFrontendClient
    target_id: UUID

    def disclosure_page(self, request: DisclosurePageRequest, *, timeout: float = 60) -> DisclosurePage:
        """Read one page through a fresh inventory read that names the target."""
        completed = read_automation_inventory(
            self.client, timeout=timeout, disclosures_of=self.target_id, disclosure_page=request
        )
        page = completed.projection.disclosure_page
        if page is None:
            raise LookupError("the inventory returned no disclosure page")
        return page


class AutomationInventoryDisclosureMixin:
    """Page the selected scope's disclosures beneath its details."""

    def _select_disclosures(self: RuntimeAutomationInventoryScreen, target_id: UUID | None, digest: str | None) -> None:
        self._disclosure_target = target_id
        self._disclosure_digest = digest
        self._disclosure_pager = (
            None if target_id is None else DisclosurePager(InventoryDisclosureReader(self._client, target_id))
        )
        for button in self.query("#automation-inventory-disclosures"):
            button.disabled = target_id is None or not digest

    def _start_disclosure_page(self: RuntimeAutomationInventoryScreen) -> None:
        if self._busy or self._access_lost or self._disclosure_pager is None or self._disclosure_digest is None:
            return
        self._worker = self.run_worker(self._read_disclosure_page(), group="automation-inventory", exclusive=True)

    async def _read_disclosure_page(self: RuntimeAutomationInventoryScreen) -> None:
        pager, digest = self._disclosure_pager, self._disclosure_digest
        if pager is None or digest is None:
            return
        self._busy = True
        self.query_one("#automation-inventory-disclosures", Button).disabled = True
        try:
            page = await await_cancellation_complete(
                asyncio.to_thread(pager.next_page, digest), task_name="tui-automation-disclosure-page"
            )
            if self._live and self.is_mounted:
                self.query_one("#automation-inventory-status", Static).update(disclosure_page_text(page))
        except Exception:
            if self._live and self.is_mounted:
                self.query_one("#automation-inventory-status", Static).update(
                    tr("tui.restricted.disclosure_page_stale")
                )
        finally:
            self._busy = False
            if self._live and self.is_mounted and not self._access_lost:
                self.query_one("#automation-inventory-disclosures", Button).disabled = False


__all__ = ["AutomationInventoryDisclosureMixin", "InventoryDisclosureReader"]
