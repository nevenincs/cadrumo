"""Every Records body that shows the area navigation opens the area the operator chooses there.

The shell answers the navigation table itself, so no body can show the table
and ignore a choice. This walks every concrete Records body, found by
subclass discovery rather than listed by hand, opens it idle, chooses an area
on its navigation table, and proves the chosen area replaced it. A body that
gains no builder here fails the completeness check, so a new body cannot skip
the walk. Refusal of the same choice while a write is out is proved per write
flow by the workspace-hold tests.
"""

from __future__ import annotations

import pkgutil
import sys
from collections.abc import Callable, Iterator
from typing import Final, cast

import pytest
from textual.pilot import Pilot
from textual.widgets import DataTable

from .....application.ledger.workspace import LedgerWorkspaceArea
from .....core.config import override_settings
from ... import ledger as ledger_package
from ...tests.settling import settle
from ..actividad_asset import ActivityAssetScreen
from ..categorisation_common import CategorisationScreen
from ..categorisation_review import ReviewingCategorisationScreen
from ..categorisation_tools import ENTRY_LIST_TOOL_KEYS, categorisation_tools
from ..classification import LedgerClassificationScreen
from ..controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from ..entries import LedgerEntriesScreen
from ..entries_add import LedgerEntryAddScreen
from ..entries_browse import LedgerEntriesBrowseScreen
from ..entries_export import LedgerEntriesExportScreen
from ..entries_health import LedgerHealthScreen
from ..entries_reset import LedgerResetScreen
from ..entries_trace import LedgerEntryTraceScreen
from ..evidence import LedgerEvidenceScreen
from ..evidence_files_common import EvidenceFilesToolScreen
from ..evidence_files_tools import evidence_files_tools
from ..evidence_files_write import EvidenceFilesOutcomeV1, EvidenceFilesWordingV1, LedgerEvidenceFilesWriteScreen
from ..evidence_records import LedgerEvidenceRecordActions
from ..import_flow import LedgerImportScreen
from ..invoice_entry import LedgerInvoiceEntryScreen
from ..invoices_import import LedgerInvoiceImportScreen
from ..invoices_wizard import LedgerInvoiceWizardScreen
from ..models import LedgerRecordDoorsV1
from ..overview import LedgerOverviewScreen
from ..own_accounts import LedgerOwnAccountDoorV1, LedgerOwnAccountsScreen
from ..reconciliation import LedgerReconciliationScreen
from ..record_views import LedgerInvoiceCatalogueScreen, LedgerInvoiceDetailScreen
from ..registers_capital_goods import LedgerCapitalGoodsDoorV1, LedgerCapitalGoodsScreen
from ..registers_inventory import LedgerInventoryDoorV1, LedgerInventoryScreen
from ..registers_presentation import LedgerRegisterScreen
from ..registers_prorrata import LedgerProrrataRegisterDoorV1, LedgerProrrataRegisterScreen
from ..review import LedgerReviewScreen
from ..routes import LedgerUnavailableScreen, resolve_ledger_screen
from ..transaction_views import LedgerTransactionDetailScreen
from ..workspace_injection import LedgerWorkspaceInjection
from ..workspace_presentation import LedgerConfirmationFlowScreen
from .categorisation_memory_doors import MemoryCategorisationProfile, categorisation_controller
from .entries_door_fixtures import MemoryEntriesLedger, entries_controller, entry_id
from .evidence_files_fixtures import MemoryEvidenceFilesStore
from .invoices_fixtures import (
    MemoryInvoiceImportDoor,
    MemoryInvoiceWizardDoor,
    MemoryRecordDoors,
    ReplacingHostApp,
    invoice_snapshot,
)
from .invoices_fixtures import transaction_projection as synthetic_transaction
from .own_account_fixtures import MemoryOwnAccountDoor
from .registers_fixtures import MemoryCapitalGoodsDoor, MemoryInventoryDoor, MemoryProrrataRegisterDoor
from .review_door_fixtures import MemoryEvidenceReviewListDoor
from .test_ledger_flows import _ImportDoor
from .test_ledger_ingestion_surfaces import _InvoiceDoor
from .workspace_fixtures import (
    LEDGER_TX_A,
    ClassificationDoor,
    ledger_classify_action,
    ledger_controller,
    ledger_evidence_action,
    ledger_focused_context,
    ledger_projection,
    ledger_review_action,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_SHARED_BASES: Final = frozenset(
    {
        LedgerConfirmationFlowScreen,
        CategorisationScreen,
        ReviewingCategorisationScreen,
        EvidenceFilesToolScreen,
        LedgerEvidenceRecordActions,
        LedgerRegisterScreen,
    }
)
"""Shells other bodies extend; none is opened on its own."""
_WITHOUT_AREA_NAVIGATION: Final = frozenset({ActivityAssetScreen})
"""Bodies that show no area navigation: the asset screen is pushed over the overview."""

type _Build = Callable[[], LedgerWorkspaceScreen]


def _concrete_bodies() -> set[type[LedgerWorkspaceScreen]]:
    # Subclass discovery sees only loaded modules. Recursive, so a module in a future subpackage is
    # required too; only the tests package is left out. This file's imports load every module.
    tests_package = f"{ledger_package.__name__}.tests"
    unloaded = sorted(
        module.name
        for module in pkgutil.walk_packages(ledger_package.__path__, prefix=f"{ledger_package.__name__}.")
        if module.name != tests_package
        and not module.name.startswith(f"{tests_package}.")
        and module.name not in sys.modules
    )
    assert not unloaded, f"Records modules this walk never loads, so their bodies escape discovery: {unloaded}"

    def walk(cls: type[LedgerWorkspaceScreen]) -> Iterator[type[LedgerWorkspaceScreen]]:
        for subclass in cls.__subclasses__():
            yield subclass
            yield from walk(subclass)

    return {
        body
        for body in walk(LedgerWorkspaceScreen)
        if body.__module__.startswith(ledger_package.__name__ + ".")
        and ".tests." not in body.__module__
        and body not in _SHARED_BASES | _WITHOUT_AREA_NAVIGATION
    }


def _area_controller(injection: LedgerWorkspaceInjection | None = None) -> LedgerWorkspaceController:
    """A workspace with the first entry chosen, given ``injection`` or only the review action."""
    return LedgerWorkspaceController(
        ledger_focused_context(LEDGER_TX_A),
        ledger_projection(),
        injection or LedgerWorkspaceInjection(review_action=ledger_review_action()),
    )


def _unavailable() -> LedgerWorkspaceScreen:
    controller = ledger_controller(ledger_projection())
    screen = resolve_ledger_screen(controller, controller.route_target(LedgerWorkspaceArea.IMPORT))
    assert isinstance(screen, LedgerUnavailableScreen)
    return screen


def _entry_doors() -> MemoryEntriesLedger:
    return MemoryEntriesLedger.with_entries(4)


def _trace() -> LedgerWorkspaceScreen:
    doors = _entry_doors().doors()
    return LedgerEntryTraceScreen(
        entries_controller(),
        doors,
        transaction_id=entry_id(0),
        label="Synthetic entry",
        back_to=lambda controller: LedgerEntriesBrowseScreen(controller, doors),
    )


def _evidence_write() -> LedgerWorkspaceScreen:
    async def submit() -> EvidenceFilesWordingV1:
        return lambda: EvidenceFilesOutcomeV1(lines=("Synthetic outcome",))

    return LedgerEvidenceFilesWriteScreen(
        ledger_controller(ledger_projection()),
        title=lambda: "Synthetic change",
        review=lambda: ("Synthetic staged change",),
        destructive=False,
        submit=submit,
        origin=LedgerOverviewScreen,
        origin_area=LedgerWorkspaceArea.EVIDENCE,
    )


def _records() -> MemoryRecordDoors:
    return MemoryRecordDoors(invoices=(invoice_snapshot(0),), transactions=(synthetic_transaction(LEDGER_TX_A),))


def _record_controller(doors: MemoryRecordDoors) -> LedgerWorkspaceController:
    return _area_controller(LedgerWorkspaceInjection(review_action=ledger_review_action(), record_doors=doors))


def _tool_builders() -> dict[type[LedgerWorkspaceScreen], _Build]:
    """Each categorisation and evidence tool, opened through its own tool entry."""
    builders: dict[type[LedgerWorkspaceScreen], _Build] = {}
    for tool in categorisation_tools(MemoryCategorisationProfile().doors().bundle()):
        selected = None if tool.key in ENTRY_LIST_TOOL_KEYS else LEDGER_TX_A
        built = tool.build(categorisation_controller(selected=selected))
        builders[type(built)] = lambda tool=tool, selected=selected: tool.build(
            categorisation_controller(selected=selected)
        )
    store = MemoryEvidenceFilesStore()
    store.seed_records(2)
    for tool in evidence_files_tools(store.doors()):
        built = tool.build(_area_controller())
        builders[type(built)] = lambda tool=tool: tool.build(_area_controller())
    return builders


def _builders() -> dict[type[LedgerWorkspaceScreen], _Build]:
    records = _records()
    builders: dict[type[LedgerWorkspaceScreen], _Build] = {
        LedgerOverviewScreen: lambda: LedgerOverviewScreen(ledger_controller(ledger_projection())),
        LedgerEntriesScreen: lambda: LedgerEntriesScreen(ledger_controller(ledger_projection())),
        LedgerReviewScreen: lambda: LedgerReviewScreen(ledger_controller(ledger_projection())),
        LedgerReconciliationScreen: lambda: LedgerReconciliationScreen(ledger_controller(ledger_projection())),
        LedgerUnavailableScreen: _unavailable,
        LedgerImportScreen: lambda: LedgerImportScreen(
            _area_controller(LedgerWorkspaceInjection(review_action=ledger_review_action(), import_door=_ImportDoor()))
        ),
        LedgerClassificationScreen: lambda: LedgerClassificationScreen(
            _area_controller(
                LedgerWorkspaceInjection(
                    review_action=ledger_review_action(),
                    classify_action=ledger_classify_action(),
                    classification_submitter=ClassificationDoor(),
                )
            )
        ),
        LedgerEvidenceScreen: lambda: LedgerEvidenceScreen(
            _area_controller(
                LedgerWorkspaceInjection(
                    review_action=ledger_review_action(),
                    evidence_action=ledger_evidence_action(),
                    evidence_items=(),
                    evidence_review_door=MemoryEvidenceReviewListDoor(()),
                )
            )
        ),
        LedgerInvoiceEntryScreen: lambda: LedgerInvoiceEntryScreen(
            _area_controller(
                LedgerWorkspaceInjection(review_action=ledger_review_action(), invoice_add_door=_InvoiceDoor())
            )
        ),
        LedgerEntryAddScreen: lambda: LedgerEntryAddScreen(entries_controller(), _entry_doors().doors()),
        LedgerEntriesExportScreen: lambda: LedgerEntriesExportScreen(entries_controller(), _entry_doors().doors()),
        LedgerResetScreen: lambda: LedgerResetScreen(entries_controller(), _entry_doors().doors()),
        LedgerEntriesBrowseScreen: lambda: LedgerEntriesBrowseScreen(entries_controller(), _entry_doors().doors()),
        LedgerHealthScreen: lambda: LedgerHealthScreen(entries_controller(), _entry_doors().doors()),
        LedgerEntryTraceScreen: _trace,
        LedgerEvidenceFilesWriteScreen: _evidence_write,
        LedgerInvoiceImportScreen: lambda: LedgerInvoiceImportScreen(_area_controller(), MemoryInvoiceImportDoor()),
        LedgerInvoiceWizardScreen: lambda: LedgerInvoiceWizardScreen(_area_controller(), MemoryInvoiceWizardDoor()),
        LedgerOwnAccountsScreen: lambda: LedgerOwnAccountsScreen(
            _area_controller(), cast(LedgerOwnAccountDoorV1, MemoryOwnAccountDoor())
        ),
        LedgerInvoiceCatalogueScreen: lambda: LedgerInvoiceCatalogueScreen(
            _record_controller(records), cast(LedgerRecordDoorsV1, records)
        ),
        LedgerInvoiceDetailScreen: lambda: LedgerInvoiceDetailScreen(
            _record_controller(records), cast(LedgerRecordDoorsV1, records), invoice_snapshot(0).invoice_id
        ),
        LedgerTransactionDetailScreen: lambda: LedgerTransactionDetailScreen(
            _record_controller(records), cast(LedgerRecordDoorsV1, records), LEDGER_TX_A
        ),
        LedgerCapitalGoodsScreen: lambda: LedgerCapitalGoodsScreen(
            _area_controller(), cast(LedgerCapitalGoodsDoorV1, MemoryCapitalGoodsDoor())
        ),
        LedgerInventoryScreen: lambda: LedgerInventoryScreen(
            _area_controller(), cast(LedgerInventoryDoorV1, MemoryInventoryDoor())
        ),
        LedgerProrrataRegisterScreen: lambda: LedgerProrrataRegisterScreen(
            _area_controller(), cast(LedgerProrrataRegisterDoorV1, MemoryProrrataRegisterDoor())
        ),
    }
    builders.update(_tool_builders())
    return builders


_BUILDERS: Final = _builders()


def test_every_records_body_is_walked() -> None:
    """Completeness: a body with no builder here would skip the walk below."""
    discovered = _concrete_bodies()
    assert len(discovered) >= 40, f"discovery found only {len(discovered)} bodies; the walk would be inert"
    missing = sorted(body.__qualname__ for body in discovered - set(_BUILDERS))
    assert not missing, f"Records bodies with no builder in this walk: {missing}"


async def _choose(pilot: Pilot[None], body: LedgerWorkspaceScreen, area: LedgerWorkspaceArea) -> None:
    navigation = cast("DataTable[str]", body.query_one("#ledger-navigation", DataTable))
    navigation.focus()
    navigation.move_cursor(row=tuple(LedgerWorkspaceArea).index(area))
    await pilot.press("enter")
    await settle(pilot)


@pytest.mark.asyncio
@pytest.mark.parametrize("body_type", sorted(_BUILDERS, key=lambda body: body.__qualname__), ids=lambda b: b.__name__)
async def test_an_idle_area_choice_opens_that_area(body_type: type[LedgerWorkspaceScreen]) -> None:
    body = _BUILDERS[body_type]()
    assert type(body) is body_type
    # Overview is open to every workspace here; from the overview itself, choose Entries.
    area = LedgerWorkspaceArea.ENTRIES if body_type is LedgerOverviewScreen else LedgerWorkspaceArea.OVERVIEW
    expected = LedgerEntriesScreen if area is LedgerWorkspaceArea.ENTRIES else LedgerOverviewScreen
    with override_settings(cadrumo_output_language="en"):
        async with ReplacingHostApp(body).run_test(size=(120, 50)) as pilot:
            await settle(pilot)
            assert pilot.app.screen is body
            assert not body.in_flight
            assert body.controller.refusal_for(area) is None
            await _choose(pilot, body, area)
            assert body.requested_target is not None
            assert body.requested_target.area is area
            shown = pilot.app.screen
            assert shown is not body
            assert type(shown) is expected
