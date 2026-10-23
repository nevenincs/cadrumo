"""Categorisation tool states for reviewing the shipped Ledger Entries and Classification tools.

Each tool is built by the production tool list over in-memory doors that answer
with the operations' own public result models. A tool that acts on one entry
opens with the first synthetic entry selected; a whole-ledger tool opens with
none, as it does from Entries. Each is driven through its own controls to the
declared state. Values are synthetic; nothing is written to storage.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import override

from textual.events import Mount
from textual.widgets import Input

from cadrumo.domain.transactions.classification_rule import LedgerClassificationRule
from cadrumo.domain.transactions.enums import BusinessClassification
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.ledger.categorisation_common import CategorisationScreen
from cadrumo.entrypoints.tui.ledger.categorisation_tools import ENTRY_LIST_TOOL_KEYS, categorisation_tools
from cadrumo.entrypoints.tui.ledger.tests.categorisation_entry_fixtures import synthetic_participation
from cadrumo.entrypoints.tui.ledger.tests.categorisation_memory_doors import (
    MemoryCategorisationProfile,
    categorisation_controller,
)
from cadrumo.entrypoints.tui.ledger.tests.workspace_fixtures import LEDGER_TX_A

from .settling import press_when_enabled, settle

_INTERFACES = {
    "ledger.tool.categorisation.bulk": "cadrumo.entrypoints.tui.ledger.categorisation_bulk.LedgerBulkClassifyScreen",
    "ledger.tool.categorisation.iva": "cadrumo.entrypoints.tui.ledger.categorisation_iva.LedgerIvaDeriveScreen",
    "ledger.tool.categorisation.review": (
        "cadrumo.entrypoints.tui.ledger.categorisation_review.LedgerSuggestionReviewScreen"
    ),
    "ledger.tool.categorisation.rules": "cadrumo.entrypoints.tui.ledger.categorisation_rules.LedgerRulesScreen",
    "ledger.tool.categorisation.counterparties": (
        "cadrumo.entrypoints.tui.ledger.categorisation_counterparties.LedgerCounterpartiesScreen"
    ),
    "ledger.tool.categorisation.split": "cadrumo.entrypoints.tui.ledger.categorisation_split.LedgerSplitScreen",
    "ledger.tool.categorisation.allocate": (
        "cadrumo.entrypoints.tui.ledger.categorisation_allocate.LedgerAllocateScreen"
    ),
    "ledger.tool.categorisation.participation": (
        "cadrumo.entrypoints.tui.ledger.categorisation_participation.LedgerParticipationScreen"
    ),
    "ledger.tool.categorisation.ratios": "cadrumo.entrypoints.tui.ledger.categorisation_ratios.LedgerRatiosScreen",
    "ledger.tool.categorisation.diagnostics": (
        "cadrumo.entrypoints.tui.ledger.categorisation_diagnostics.LedgerDiagnosticsScreen"
    ),
}


class CategorisationFixtureState(StrEnum):
    """The reviewable states of the categorisation tools."""

    BULK_REVIEWED = "bulk-reviewed"
    IVA_STAGED = "iva-staged"
    REVIEW_OPTIONS = "review-options"
    RULES_PREVIEWED = "rules-previewed"
    COUNTERPARTY_VIEWED = "counterparty-viewed"
    SPLIT_UNBALANCED = "split-unbalanced"
    ALLOCATE_STAGED = "allocate-staged"
    PARTICIPATION_LISTED = "participation-listed"
    RATIOS_LISTED = "ratios-listed"
    DIAGNOSTICS_READ = "diagnostics-read"
    ENTRY_REQUIRED = "entry-required"


_TOOL_BY_STATE = {
    CategorisationFixtureState.BULK_REVIEWED: "ledger.tool.categorisation.bulk",
    CategorisationFixtureState.IVA_STAGED: "ledger.tool.categorisation.iva",
    CategorisationFixtureState.REVIEW_OPTIONS: "ledger.tool.categorisation.review",
    CategorisationFixtureState.RULES_PREVIEWED: "ledger.tool.categorisation.rules",
    CategorisationFixtureState.COUNTERPARTY_VIEWED: "ledger.tool.categorisation.counterparties",
    CategorisationFixtureState.SPLIT_UNBALANCED: "ledger.tool.categorisation.split",
    CategorisationFixtureState.ALLOCATE_STAGED: "ledger.tool.categorisation.allocate",
    CategorisationFixtureState.PARTICIPATION_LISTED: "ledger.tool.categorisation.participation",
    CategorisationFixtureState.RATIOS_LISTED: "ledger.tool.categorisation.ratios",
    CategorisationFixtureState.DIAGNOSTICS_READ: "ledger.tool.categorisation.diagnostics",
    CategorisationFixtureState.ENTRY_REQUIRED: "ledger.tool.categorisation.allocate",
}


def _seeded_profile() -> MemoryCategorisationProfile:
    """Two rules, an entry in one finalised declaration and one usage ratio override."""
    profile = MemoryCategorisationProfile()
    profile.rules.rules.extend(
        LedgerClassificationRule.create(
            description_pattern=pattern,
            classification=classification,
            category_id=None,
            priority=priority,
            actor="operator",
        )
        for pattern, classification, priority in (
            ("material de oficina", BusinessClassification.BUSINESS, 10),
            ("supermercado", BusinessClassification.PERSONAL, 20),
        )
    )
    profile.rules.entries[LEDGER_TX_A] = ("Material de oficina", BusinessClassification.NOT_YET_PROCESSED)
    profile.ledger.participations = (synthetic_participation(1),)
    profile.ratios.overrides["vehiculo"] = "0.5"
    return profile


class CategorisationCaptureHost(ScreenHostApp[None]):
    """Drive one production categorisation tool to one declared, settled review state."""

    def __init__(self, screen: CategorisationScreen, state: CategorisationFixtureState) -> None:
        """Bind the production tool screen and the state the capture must reach."""
        super().__init__(screen)
        self.tool_screen = screen
        self.fixture_state = state

    @override
    async def on_mount(self, event: Mount | None = None) -> None:
        # Mounted explicitly before driving, so Textual must not dispatch the inherited handler again.
        if event is not None:
            event.prevent_default()
        await super().on_mount()
        await self._settle()
        drive = _DRIVES.get(self.fixture_state)
        if drive is not None:
            await drive(self)

    async def _settle(self) -> None:
        await settle(self)

    async def press(self, button_id: str) -> None:
        """Press one of the tool's buttons once it is enabled, and wait for what it started."""
        await press_when_enabled(self, button_id, within=self.tool_screen)

    def type(self, selector: str, value: str) -> None:
        """Type one value into one of the tool's inputs."""
        self.tool_screen.query_one(selector, Input).value = value

    def show(self, selector: str) -> None:
        """Scroll the page so the frame opens on ``selector``."""
        self.tool_screen.query_one(selector).scroll_visible(top=True, animate=False, immediate=True)


async def _bulk(host: CategorisationCaptureHost) -> None:
    await host.press("categorisation-bulk-review")
    host.show("#categorisation-staged")


async def _iva(host: CategorisationCaptureHost) -> None:
    host.type("#categorisation-iva-category", "GENERAL")
    await host.press("categorisation-iva-review")


async def _rules(host: CategorisationCaptureHost) -> None:
    await host.press("categorisation-rule-preview")
    host.show("#categorisation-staged")


async def _counterparty(host: CategorisationCaptureHost) -> None:
    host.type("#categorisation-counterparty-identifier", "B00000000")
    await host.press("categorisation-counterparty-view")


async def _split(host: CategorisationCaptureHost) -> None:
    for amount, description in (("1000", "Ordenador portátil"), ("200", "Monitor")):
        host.type("#categorisation-split-amount", amount)
        host.type("#categorisation-split-description", description)
        await host.press("categorisation-split-add")
    await host.press("categorisation-split-review")
    host.show("#ledger-refusal")


async def _allocate(host: CategorisationCaptureHost) -> None:
    host.type("#categorisation-allocate-pct", "0.6")
    host.type("#categorisation-allocate-category", "vehiculo")
    await host.press("categorisation-allocate-review")


async def _ratios(host: CategorisationCaptureHost) -> None:
    await host.press("categorisation-ratios-validate")


_DRIVES: dict[CategorisationFixtureState, Callable[[CategorisationCaptureHost], Awaitable[None]]] = {
    CategorisationFixtureState.BULK_REVIEWED: _bulk,
    CategorisationFixtureState.IVA_STAGED: _iva,
    CategorisationFixtureState.RULES_PREVIEWED: _rules,
    CategorisationFixtureState.COUNTERPARTY_VIEWED: _counterparty,
    CategorisationFixtureState.SPLIT_UNBALANCED: _split,
    CategorisationFixtureState.ALLOCATE_STAGED: _allocate,
    CategorisationFixtureState.RATIOS_LISTED: _ratios,
}


def build_categorisation_fixture(state: CategorisationFixtureState) -> CategorisationCaptureHost:
    """Open one categorisation tool over a synthetic in-memory profile."""
    key = _TOOL_BY_STATE[state]
    tool = next(item for item in categorisation_tools(_seeded_profile().doors().bundle()) if item.key == key)
    # Whole-ledger tools open from Entries with nothing selected; the entry-required state shows the guidance.
    no_selection = state is CategorisationFixtureState.ENTRY_REQUIRED or key in ENTRY_LIST_TOOL_KEYS
    controller = categorisation_controller(selected=None) if no_selection else categorisation_controller()
    screen = tool.build(controller)
    if not isinstance(screen, CategorisationScreen):
        raise TypeError(f"{key} did not build a categorisation tool")
    return CategorisationCaptureHost(screen, state)


def categorisation_fixture_interfaces(state: CategorisationFixtureState) -> tuple[str, ...]:
    """The tool screen each state paints."""
    return (_INTERFACES[_TOOL_BY_STATE[state]],)


__all__ = [
    "CategorisationCaptureHost",
    "CategorisationFixtureState",
    "build_categorisation_fixture",
    "categorisation_fixture_interfaces",
]
