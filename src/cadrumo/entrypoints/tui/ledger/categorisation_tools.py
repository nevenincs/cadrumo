"""The categorisation tools, each built over its injected doors.

Tools that act on the whole ledger are listed by the Entries area, which always
opens. Tools that act on the selected entry are listed by the Classification
area, which opens once an entry is selected.
"""

from __future__ import annotations

from typing import Final

from ....application.ledger.workspace import LedgerWorkspaceArea
from .categorisation_allocate import LedgerAllocateScreen
from .categorisation_bulk import LedgerBulkClassifyScreen
from .categorisation_counterparties import LedgerCounterpartiesScreen
from .categorisation_diagnostics import LedgerDiagnosticsScreen
from .categorisation_doors import LedgerCategorisationDoorsV1
from .categorisation_iva import LedgerIvaDeriveScreen
from .categorisation_participation import LedgerParticipationScreen
from .categorisation_ratios import LedgerRatiosScreen
from .categorisation_review import LedgerSuggestionReviewScreen
from .categorisation_rules import LedgerRulesScreen
from .categorisation_split import LedgerSplitScreen
from .tools import LedgerToolV1

ENTRY_LIST_TOOL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "ledger.tool.categorisation.bulk",
        "ledger.tool.categorisation.rules",
        "ledger.tool.categorisation.counterparties",
        "ledger.tool.categorisation.ratios",
        "ledger.tool.categorisation.diagnostics",
    }
)
"""The tools that need no selected entry, listed by the Entries area."""


def categorisation_tools(doors: LedgerCategorisationDoorsV1) -> tuple[LedgerToolV1, ...]:
    """Build the categorisation tools over one profile's doors."""
    entry_list = LedgerWorkspaceArea.ENTRIES
    selected_entry = LedgerWorkspaceArea.CLASSIFICATION
    return (
        LedgerToolV1(
            key="ledger.tool.categorisation.bulk",
            label_key="tui.ledger.categorisation.tool.bulk",
            area=entry_list,
            build=lambda controller: LedgerBulkClassifyScreen(
                controller, selection_door=doors.selection, bulk_door=doors.bulk_classify
            ),
        ),
        LedgerToolV1(
            key="ledger.tool.categorisation.iva",
            label_key="tui.ledger.categorisation.tool.iva",
            area=selected_entry,
            build=lambda controller: LedgerIvaDeriveScreen(controller, door=doors.operator_iva),
        ),
        LedgerToolV1(
            key="ledger.tool.categorisation.review",
            label_key="tui.ledger.categorisation.tool.review",
            area=selected_entry,
            build=lambda controller: LedgerSuggestionReviewScreen(controller, door=doors.classify_review),
        ),
        LedgerToolV1(
            key="ledger.tool.categorisation.rules",
            label_key="tui.ledger.categorisation.tool.rules",
            area=entry_list,
            build=lambda controller: LedgerRulesScreen(
                controller, list_door=doors.rule_list, add_door=doors.rule_add, apply_door=doors.rule_apply
            ),
        ),
        LedgerToolV1(
            key="ledger.tool.categorisation.counterparties",
            label_key="tui.ledger.categorisation.tool.counterparties",
            area=entry_list,
            build=lambda controller: LedgerCounterpartiesScreen(controller, door=doors.counterparty),
        ),
        LedgerToolV1(
            key="ledger.tool.categorisation.split",
            label_key="tui.ledger.categorisation.tool.split",
            area=selected_entry,
            build=lambda controller: LedgerSplitScreen(
                controller, split_door=doors.split, review_door=doors.split_review
            ),
        ),
        LedgerToolV1(
            key="ledger.tool.categorisation.allocate",
            label_key="tui.ledger.categorisation.tool.allocate",
            area=selected_entry,
            build=lambda controller: LedgerAllocateScreen(controller, door=doors.allocate),
        ),
        LedgerToolV1(
            key="ledger.tool.categorisation.participation",
            label_key="tui.ledger.categorisation.tool.participation",
            area=selected_entry,
            build=lambda controller: LedgerParticipationScreen(
                controller, read_door=doors.participation, rebuild_door=doors.participation_rebuild
            ),
        ),
        LedgerToolV1(
            key="ledger.tool.categorisation.ratios",
            label_key="tui.ledger.categorisation.tool.ratios",
            area=entry_list,
            build=lambda controller: LedgerRatiosScreen(
                controller,
                list_door=doors.ratios_list,
                eligible_door=doors.ratios_eligible,
                validate_door=doors.ratios_validate,
                set_door=doors.ratios_set,
                unset_door=doors.ratios_unset,
            ),
        ),
        LedgerToolV1(
            key="ledger.tool.categorisation.diagnostics",
            label_key="tui.ledger.categorisation.tool.diagnostics",
            area=entry_list,
            build=lambda controller: LedgerDiagnosticsScreen(controller, door=doors.llm_diagnostics),
        ),
    )


__all__ = ["ENTRY_LIST_TOOL_KEYS", "categorisation_tools"]
