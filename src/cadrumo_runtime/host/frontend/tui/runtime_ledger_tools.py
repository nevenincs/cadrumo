"""The Ledger tools the installed TUI offers, each bound to the retained runtime session.

Every domain that adds screens to the Ledger workspace contributes one composer
to ``LEDGER_TOOL_COMPOSERS``; the workbench hands the combined tuple to the
workspace unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from cadrumo.entrypoints.tui.ledger.tools import LedgerToolV1, require_unique_tool_keys
from cadrumo_client.transport.frontend_client import FrontendClient

from .runtime_ledger_categorisation import compose_categorisation_tools
from .runtime_ledger_entries import compose_entries_tools
from .runtime_ledger_evidence_files import compose_evidence_files_tools
from .runtime_ledger_invoices import compose_invoices_tools
from .runtime_ledger_registers import compose_registers_tools

type LedgerToolComposerV1 = Callable[[FrontendClient, str], tuple[LedgerToolV1, ...]]
"""Build one domain's tools from the workbench's client and profile label."""

LEDGER_TOOL_COMPOSERS: Final[tuple[LedgerToolComposerV1, ...]] = (
    compose_registers_tools,
    compose_invoices_tools,
    compose_evidence_files_tools,
    compose_entries_tools,
    compose_categorisation_tools,
)
"""One composer per domain, in the order their tools are listed within an area."""


def compose_runtime_ledger_tools(
    client: FrontendClient,
    *,
    profile_label: str,
    composers: tuple[LedgerToolComposerV1, ...] = LEDGER_TOOL_COMPOSERS,
) -> tuple[LedgerToolV1, ...]:
    """Return every domain's Ledger tools for the exact profile session the workbench holds."""
    tools = tuple(tool for compose in composers for tool in compose(client, profile_label))
    require_unique_tool_keys(tools)
    return tools


__all__ = ["LEDGER_TOOL_COMPOSERS", "LedgerToolComposerV1", "compose_runtime_ledger_tools"]
