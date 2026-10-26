"""Gate: no categorisation door is entered on the event loop, and every call comes from a worker.

Each guarded door stands where the installed door's transport crosses the
runtime connection: the runtime door awaits that transport off the loop, so
the guard enters the shared ``TransportBoundary`` from a worker thread the same
way. It also records whether the screen called the door from a Textual worker;
a door awaited inline in a message handler would hold the screen's message
pump for the whole request, and the gate refuses that too.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest
from pydantic import BaseModel
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import Button, Static
from textual.worker import NoActiveWorker, get_current_worker

from .....application.ledger.rule_contracts import LedgerRuleListRequest
from .....core.config import override_settings
from ...tests.settling import settle
from ...tests.test_doors_run_off_the_event_loop import TransportBoundary
from ..categorisation_doors import LedgerCategorisationDoorsV1
from ..categorisation_tools import ENTRY_LIST_TOOL_KEYS, categorisation_tools
from .categorisation_fixtures import MemoryDoor
from .categorisation_memory_doors import MemoryCategorisationProfile, categorisation_controller
from .categorisation_pilot import press, type_into
from .workspace_fixtures import LEDGER_TX_A, WorkspaceHostApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]


class _Guard[RequestT: BaseModel, ResultT: BaseModel]:
    """A door that crosses the boundary off the loop and notes whether a worker called it."""

    def __init__(self, name: str, door: MemoryDoor[RequestT, ResultT], boundary: TransportBoundary) -> None:
        self.name = name
        self.door = door
        self.boundary = boundary
        self.outside_worker: list[str] = []

    @property
    def profile_id(self) -> UUID:
        return self.door.profile_id

    async def __call__(self, request: RequestT, /) -> ResultT:
        try:
            get_current_worker()
        except NoActiveWorker:
            self.outside_worker.append(self.name)
        await asyncio.to_thread(self.boundary.enter, self.name)
        return await self.door(request)


class _GuardedDoors:
    """Every plain categorisation door of one in-memory profile, each behind a guard."""

    def __init__(self, profile: MemoryCategorisationProfile, boundary: TransportBoundary) -> None:
        memory = profile.doors()
        self.records: list[list[str]] = []

        def guard[RequestT: BaseModel, ResultT: BaseModel](
            name: str, door: MemoryDoor[RequestT, ResultT]
        ) -> _Guard[RequestT, ResultT]:
            guarded = _Guard(name, door, boundary)
            self.records.append(guarded.outside_worker)
            return guarded

        self.bundle = LedgerCategorisationDoorsV1(
            selection=guard("selection", memory.selection),
            bulk_classify=guard("bulk_classify", memory.bulk_classify),
            operator_iva=guard("operator_iva", memory.operator_iva),
            classify_review=memory.classify_review,
            split_review=memory.split_review,
            rule_list=guard("rule_list", memory.rule_list),
            rule_add=guard("rule_add", memory.rule_add),
            rule_apply=guard("rule_apply", memory.rule_apply),
            counterparty=guard("counterparty", memory.counterparty),
            split=guard("split", memory.split),
            allocate=guard("allocate", memory.allocate),
            participation=guard("participation", memory.participation),
            participation_rebuild=guard("participation_rebuild", memory.participation_rebuild),
            llm_diagnostics=guard("llm_diagnostics", memory.llm_diagnostics),
            ratios_list=guard("ratios_list", memory.ratios_list),
            ratios_eligible=guard("ratios_eligible", memory.ratios_eligible),
            ratios_validate=guard("ratios_validate", memory.ratios_validate),
            ratios_set=guard("ratios_set", memory.ratios_set),
            ratios_unset=guard("ratios_unset", memory.ratios_unset),
        )

    def outside_worker(self) -> list[str]:
        return [name for record in self.records for name in record]


async def _accept_dialog(pilot: Pilot[None]) -> None:
    pilot.app.screen.query_one("#btn-confirm-accept", Button).press()
    await settle(pilot)


async def _drive_rules(pilot: Pilot[None], screen: Screen[None]) -> None:
    type_into(screen, "#categorisation-rule-pattern", "papelería")
    await press(pilot, screen, "categorisation-rule-review-add")
    await press(pilot, screen, "categorisation-confirm")
    await press(pilot, screen, "categorisation-rule-preview")


async def _drive_bulk(pilot: Pilot[None], screen: Screen[None]) -> None:
    await press(pilot, screen, "categorisation-bulk-review")
    await press(pilot, screen, "categorisation-confirm")


async def _drive_iva(pilot: Pilot[None], screen: Screen[None]) -> None:
    type_into(screen, "#categorisation-iva-category", "GENERAL")
    await press(pilot, screen, "categorisation-iva-review")
    await press(pilot, screen, "categorisation-confirm")


async def _drive_counterparties(pilot: Pilot[None], screen: Screen[None]) -> None:
    type_into(screen, "#categorisation-counterparty-identifier", "B00000000")
    type_into(screen, "#categorisation-counterparty-scope", "TAI")
    type_into(screen, "#categorisation-counterparty-asserted", "Operator")
    await press(pilot, screen, "categorisation-counterparty-confirm")
    await press(pilot, screen, "categorisation-confirm")
    await press(pilot, screen, "categorisation-counterparty-view")
    await press(pilot, screen, "categorisation-counterparty-withdraw")
    await press(pilot, screen, "categorisation-confirm")
    await _accept_dialog(pilot)


async def _drive_split(pilot: Pilot[None], screen: Screen[None]) -> None:
    for amount, description in (("1000", "Ordenador"), ("250", "Monitor")):
        type_into(screen, "#categorisation-split-amount", amount)
        type_into(screen, "#categorisation-split-description", description)
        await press(pilot, screen, "categorisation-split-add")
    await press(pilot, screen, "categorisation-split-review")
    await press(pilot, screen, "categorisation-confirm")


async def _drive_allocate(pilot: Pilot[None], screen: Screen[None]) -> None:
    type_into(screen, "#categorisation-allocate-pct", "0.5")
    await press(pilot, screen, "categorisation-allocate-review")
    await press(pilot, screen, "categorisation-confirm")


async def _drive_participation(pilot: Pilot[None], screen: Screen[None]) -> None:
    await press(pilot, screen, "categorisation-participation-rebuild")
    await press(pilot, screen, "categorisation-confirm")
    await _accept_dialog(pilot)


async def _drive_ratios(pilot: Pilot[None], screen: Screen[None]) -> None:
    type_into(screen, "#categorisation-ratios-category", "vehiculo")
    type_into(screen, "#categorisation-ratios-ratio", "0.5")
    await press(pilot, screen, "categorisation-ratios-set")
    await press(pilot, screen, "categorisation-confirm")
    await press(pilot, screen, "categorisation-ratios-validate")
    await press(pilot, screen, "categorisation-ratios-unset")
    await press(pilot, screen, "categorisation-confirm")
    await _accept_dialog(pilot)


async def _drive_diagnostics(pilot: Pilot[None], screen: Screen[None]) -> None:
    await press(pilot, screen, "categorisation-diagnostics-read")


type _Drive = Callable[[Pilot[None], Screen[None]], Awaitable[None]]

_DRIVES: dict[str, tuple[_Drive, frozenset[str]]] = {
    "ledger.tool.categorisation.rules": (_drive_rules, frozenset({"rule_list", "rule_add", "rule_apply"})),
    "ledger.tool.categorisation.bulk": (_drive_bulk, frozenset({"selection", "bulk_classify"})),
    "ledger.tool.categorisation.iva": (_drive_iva, frozenset({"operator_iva"})),
    "ledger.tool.categorisation.counterparties": (_drive_counterparties, frozenset({"counterparty"})),
    "ledger.tool.categorisation.split": (_drive_split, frozenset({"split"})),
    "ledger.tool.categorisation.allocate": (_drive_allocate, frozenset({"allocate"})),
    "ledger.tool.categorisation.participation": (
        _drive_participation,
        frozenset({"participation", "participation_rebuild"}),
    ),
    "ledger.tool.categorisation.ratios": (
        _drive_ratios,
        frozenset({"ratios_list", "ratios_eligible", "ratios_validate", "ratios_set", "ratios_unset"}),
    ),
    "ledger.tool.categorisation.diagnostics": (_drive_diagnostics, frozenset({"llm_diagnostics"})),
}
"""Every tool with plain doors, the operator steps that reach all of them, and the doors those steps enter."""


@pytest.mark.asyncio
@pytest.mark.parametrize("key", sorted(_DRIVES))
async def test_each_tool_enters_its_doors_off_the_loop_and_from_a_worker(key: str) -> None:
    boundary = TransportBoundary()
    guarded = _GuardedDoors(MemoryCategorisationProfile(), boundary)
    tool = next(item for item in categorisation_tools(guarded.bundle) if item.key == key)
    screen = tool.build(categorisation_controller(selected=None if key in ENTRY_LIST_TOOL_KEYS else LEDGER_TX_A))
    drive, expected = _DRIVES[key]
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await drive(pilot, screen)
            await settle(pilot)
            refusal = str(screen.query_one("#ledger-refusal", Static).render())
            assert refusal == "", refusal

    assert boundary.names == expected
    assert boundary.on_loop == []
    assert guarded.outside_worker() == []


@pytest.mark.asyncio
async def test_the_gate_catches_a_door_awaited_outside_a_worker() -> None:
    """Detector teeth: the guard notes a door awaited straight from the test, outside any worker."""
    boundary = TransportBoundary()
    guarded = _GuardedDoors(MemoryCategorisationProfile(), boundary)
    rule_list = guarded.bundle.rule_list

    await rule_list(LedgerRuleListRequest(profile_id=rule_list.profile_id))

    assert guarded.outside_worker() == ["rule_list"]
    assert boundary.on_loop == []
