"""The export dialog offers the charge and refund own account, prefilled from the Ledger designations.

The own-account door applies each request through the application's own
own-account logic over an in-memory register; account numbers are synthetic.
"""

from __future__ import annotations

from typing import cast

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Input, OptionList, Select

from ......application.ledger.own_account_operation import LedgerOwnAccountRequest
from ......core.config import override_settings
from ......core.i18n.render import tr
from ......core.modelo_export_artefact import ModeloExportArtefact
from ......domain.transactions.own_accounts import OwnAccountHolding, OwnAccountRole
from ....components.host import ScreenHostApp
from ....ledger.own_accounts import LedgerOwnAccountDoorV1
from ....ledger.tests.own_account_fixtures import (
    OWN_ACCOUNT_PROFILE_ID,
    SYNTHETIC_ES_IBAN,
    SYNTHETIC_ES_IBAN_2,
    MemoryOwnAccountDoor,
)
from ..export import DESIGNATED_ACCOUNT, WorkbenchExportScreen
from ..ports import WorkbenchExportOffer, WorkbenchExportRequest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _register(*, refund_scope: str | None) -> MemoryOwnAccountDoor:
    door = MemoryOwnAccountDoor()
    for label, iban in (("Cuenta nómina", SYNTHETIC_ES_IBAN), ("Ahorro", SYNTHETIC_ES_IBAN_2)):
        door.apply(
            LedgerOwnAccountRequest(
                profile_id=OWN_ACCOUNT_PROFILE_ID,
                action="add",
                label=label,
                holding=OwnAccountHolding.TITULAR,
                iban=iban,
            )
        )
    for role, account, modelo in (
        (OwnAccountRole.CHARGE, "acc-01", None),
        (OwnAccountRole.REFUND, "acc-02", refund_scope),
    ):
        door.apply(
            LedgerOwnAccountRequest(
                profile_id=OWN_ACCOUNT_PROFILE_ID, action="designate", own_account_id=account, role=role, modelo=modelo
            )
        )
    return door


async def _open(
    pilot: Pilot[WorkbenchExportRequest | None],
) -> WorkbenchExportScreen:
    for _ in range(3):
        await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()
    screen = pilot.app.screen
    assert isinstance(screen, WorkbenchExportScreen)
    return screen


def _offer(door: MemoryOwnAccountDoor, modelo: str) -> WorkbenchExportOffer:
    return WorkbenchExportOffer(
        artefacts=(ModeloExportArtefact.FICHERO_BOE,),
        asks_elections=True,
        modelo=modelo,
        own_accounts=cast(LedgerOwnAccountDoorV1, door),
    )


@pytest.mark.asyncio
async def test_export_prefills_each_role_from_its_designation_and_submits_the_choice() -> None:
    door = _register(refund_scope="303")
    app = ScreenHostApp(WorkbenchExportScreen(_offer(door, "303")))
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(140, 60)) as pilot:
            screen = await _open(pilot)
            charge = cast("Select[str]", screen.query_one("#export-charge-account", Select))
            refund = cast("Select[str]", screen.query_one("#export-refund-account", Select))
            assert charge.value == "acc-01"
            assert refund.value == "acc-02"
            options = charge.query_one(OptionList)
            labels = [str(options.get_option_at_index(index).prompt) for index in range(options.option_count)]
            assert labels[0] == tr("tui.modelo.export.account.designated")
            assert (
                tr("tui.modelo.export.account.designated_option", account="acc-01 · Cuenta nómina · ES ···· 1332")
                in labels
            )
            assert all(SYNTHETIC_ES_IBAN not in label and SYNTHETIC_ES_IBAN_2 not in label for label in labels)
            refund.value = "acc-01"
            screen.query_one("#export-path", Input).value = "salida.txt"
            screen.query_one("#export-submit", Button).press()
            await pilot.pause()
    request = app.return_value
    assert isinstance(request, WorkbenchExportRequest)
    assert request.charge_account_id == "acc-01"
    assert request.refund_account_id == "acc-01"


@pytest.mark.asyncio
async def test_a_designation_scoped_to_another_modelo_leaves_the_role_to_the_designations() -> None:
    door = _register(refund_scope="111")
    app = ScreenHostApp(WorkbenchExportScreen(_offer(door, "303")))
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=(140, 60)) as pilot:
            screen = await _open(pilot)
            assert cast("Select[str]", screen.query_one("#export-refund-account", Select)).value == DESIGNATED_ACCOUNT
            screen.query_one("#export-path", Input).value = "salida.txt"
            screen.query_one("#export-submit", Button).press()
            await pilot.pause()
    request = app.return_value
    assert isinstance(request, WorkbenchExportRequest)
    assert request.charge_account_id == "acc-01"
    assert request.refund_account_id is None
