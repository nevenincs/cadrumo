"""The rules tool: list, add, and apply only after a previewed dry run."""

from __future__ import annotations

from typing import cast

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Static

from .....application.ledger.rule_contracts import (
    LedgerRuleAddProjection,
    LedgerRuleAddRequest,
    LedgerRuleApplyProjection,
    LedgerRuleApplyRequest,
    LedgerRuleListProjection,
    LedgerRuleListRequest,
)
from .....core.config import override_settings
from .....core.i18n.render import tr
from .....domain.transactions.classification_rule import LedgerClassificationRule
from .....domain.transactions.enums import BusinessClassification
from ...tests.settling import settle
from ..categorisation_doors import LedgerRuleAddDoorV1, LedgerRuleApplyDoorV1, LedgerRuleListDoorV1
from ..categorisation_rules import RULES_PAGE_SIZE, LedgerRulesScreen
from ..controller import LedgerWorkspaceController
from ..workspace_injection import LedgerWorkspaceInjection
from .categorisation_fixtures import CATEGORISATION_REFUSAL_KEY, MemoryDoor, MemoryRuleBook, synthetic_id
from .workspace_fixtures import WorkspaceHostApp, ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

type _Doors = tuple[
    MemoryDoor[LedgerRuleListRequest, LedgerRuleListProjection],
    MemoryDoor[LedgerRuleAddRequest, LedgerRuleAddProjection],
    MemoryDoor[LedgerRuleApplyRequest, LedgerRuleApplyProjection],
]


def _doors(book: MemoryRuleBook) -> _Doors:
    return MemoryDoor(book.list_rules), MemoryDoor(book.add_rule), MemoryDoor(book.apply_rules)


def _screen(doors: _Doors) -> LedgerRulesScreen:
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    list_door, add_door, apply_door = doors
    return LedgerRulesScreen(
        controller,
        list_door=cast(LedgerRuleListDoorV1, list_door),
        add_door=cast(LedgerRuleAddDoorV1, add_door),
        apply_door=cast(LedgerRuleApplyDoorV1, apply_door),
    )


async def _press(pilot: Pilot[None], screen: LedgerRulesScreen, button_id: str) -> None:
    screen.query_one(f"#{button_id}", Button).press()
    await settle(pilot)


def _text(screen: LedgerRulesScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


def _keys(screen: LedgerRulesScreen, selector: str) -> list[str]:
    table = cast("DataTable[str]", screen.query_one(selector, DataTable))
    return [str(row.key.value) for row in table.ordered_rows]


@pytest.mark.asyncio
async def test_rules_are_added_listed_and_applied_only_after_a_dry_run() -> None:
    book = MemoryRuleBook(
        entries={
            synthetic_id(1): ("Papelería Norte factura 12", BusinessClassification.NOT_YET_PROCESSED),
            synthetic_id(2): ("Supermercado barrio", BusinessClassification.NOT_YET_PROCESSED),
        }
    )
    doors = _doors(book)
    list_door, add_door, apply_door = doors
    screen = _screen(doors)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            assert _keys(screen, "#categorisation-rules") == []
            assert _text(screen, "#categorisation-outcome") == tr("tui.ledger.categorisation.rules.empty")

            screen.query_one("#categorisation-rule-pattern", Input).value = "papelería"
            await _press(pilot, screen, "categorisation-rule-review-add")
            assert add_door.requests == []
            assert _text(screen, "#categorisation-staged") == tr(
                "tui.ledger.categorisation.rules.stage_add",
                pattern="papelería",
                classification=tr("tui.ledger.categorisation.classification.business"),
                category="-",
                priority=100,
            )
            await _press(pilot, screen, "categorisation-confirm")
            assert add_door.requests[0].description_pattern == "papelería"
            assert add_door.requests[0].classification is BusinessClassification.BUSINESS
            assert _keys(screen, "#categorisation-rules") == [book.rules[0].rule_id]
            assert _text(screen, "#categorisation-staged") == ""

            await _press(pilot, screen, "categorisation-rule-preview")
            assert [request.dry_run for request in apply_door.requests] == [True]
            assert _keys(screen, "#categorisation-rule-matches") == [synthetic_id(1)]
            assert book.entries[synthetic_id(1)][1] is BusinessClassification.NOT_YET_PROCESSED
            assert tr("tui.ledger.categorisation.rules.stage_apply", count=1) == _text(screen, "#categorisation-staged")

            await _press(pilot, screen, "categorisation-confirm")
            assert [request.dry_run for request in apply_door.requests] == [True, False]
            assert book.entries[synthetic_id(1)][1] is BusinessClassification.BUSINESS
            assert book.entries[synthetic_id(2)][1] is BusinessClassification.NOT_YET_PROCESSED
            assert _text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.rules.applied", applied=1, skipped=0, unmatched=1
            )
            assert len(list_door.requests) == 2


@pytest.mark.asyncio
async def test_a_refused_rule_list_is_said_on_the_screen() -> None:
    doors = _doors(MemoryRuleBook())
    doors[0].refusing = True
    screen = _screen(doors)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            assert _text(screen, "#ledger-refusal") == tr(CATEGORISATION_REFUSAL_KEY)
            assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.failed")


@pytest.mark.asyncio
async def test_an_empty_pattern_is_refused_with_the_operations_own_finding() -> None:
    doors = _doors(MemoryRuleBook())
    screen = _screen(doors)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            screen.query_one("#categorisation-rule-pattern", Input).value = "   "
            await _press(pilot, screen, "categorisation-rule-review-add")
            await _press(pilot, screen, "categorisation-confirm")
            assert len(doors[1].requests) == 1
            assert _text(screen, "#categorisation-outcome") == tr(
                "tui.ledger.categorisation.rules.add_refused",
                messages="description pattern must not be empty or whitespace",
            )
            assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.not_done")
            assert _keys(screen, "#categorisation-rules") == []


@pytest.mark.asyncio
async def test_a_preview_with_no_match_stages_nothing() -> None:
    book = MemoryRuleBook(entries={synthetic_id(1): ("Supermercado", BusinessClassification.NOT_YET_PROCESSED)})
    doors = _doors(book)
    screen = _screen(doors)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _press(pilot, screen, "categorisation-rule-preview")
            assert screen.staged is None
            assert _text(screen, "#categorisation-outcome") == tr("tui.ledger.categorisation.rules.nothing_matches")
            assert [request.dry_run for request in doors[2].requests] == [True]


@pytest.mark.asyncio
async def test_a_thousand_rules_render_one_page_at_a_time() -> None:
    book = MemoryRuleBook(
        rules=[
            LedgerClassificationRule.create(
                description_pattern=f"proveedor {index:04d}",
                classification=BusinessClassification.BUSINESS,
                category_id=None,
                priority=index + 1,
                actor="operator",
            )
            for index in range(1000)
        ]
    )
    screen = _screen(_doors(book))
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            assert RULES_PAGE_SIZE <= 200
            assert len(_keys(screen, "#categorisation-rules")) == RULES_PAGE_SIZE
            assert _text(screen, "#categorisation-rules-page") == tr(
                "tui.ledger.categorisation.page.window", first=1, last=RULES_PAGE_SIZE, total=1000
            )
            await _press(pilot, screen, "categorisation-rules-previous")
            assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.page.none")
            for _ in range(4):
                await _press(pilot, screen, "categorisation-rules-next")
            assert len(_keys(screen, "#categorisation-rules")) == RULES_PAGE_SIZE
            assert _text(screen, "#categorisation-rules-page") == tr(
                "tui.ledger.categorisation.page.window", first=801, last=1000, total=1000
            )
            await _press(pilot, screen, "categorisation-rules-next")
            assert _text(screen, "#ledger-flow-status") == tr("tui.ledger.categorisation.page.none")
            await _press(pilot, screen, "categorisation-rules-previous")
            assert _keys(screen, "#categorisation-rules")[0] == book.rules[600].rule_id
