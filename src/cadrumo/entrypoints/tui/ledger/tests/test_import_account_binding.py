"""The import flow binds a statement to an own account and applies exactly the bytes it previewed."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Input, OptionList, Select, Static

from .....application.ledger.own_account_operation import LedgerOwnAccountRequest
from .....core.config import override_settings
from .....core.i18n.render import tr
from .....domain.transactions.own_accounts import OwnAccountHolding
from ...components.host import ScreenHostApp
from ..controller import LedgerWorkspaceController
from ..import_flow import LedgerImportScreen
from ..models import (
    LedgerFlowState,
    LedgerImportOutcomeV1,
    LedgerImportRequestV1,
    LedgerImportSourceBindingV1,
)
from ..own_accounts import LedgerOwnAccountDoorV1
from ..workspace_injection import LedgerWorkspaceInjection
from .own_account_fixtures import (
    OWN_ACCOUNT_PROFILE_ID,
    SYNTHETIC_ES_IBAN,
    SYNTHETIC_ES_IBAN_2,
    MemoryOwnAccountDoor,
)
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_DIGEST = "e" * 64


class _BindingImportDoor:
    """Records requests and reports the digest of each file a preview read."""

    def __init__(self) -> None:
        self.previews: list[LedgerImportRequestV1] = []
        self.applied: list[LedgerImportRequestV1] = []

    async def preview(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        self.previews.append(request)
        return LedgerImportOutcomeV1(
            source_kind=request.source_kind,
            dry_run=True,
            files=1,
            rows=2,
            imported=2,
            skipped=0,
            sources=(LedgerImportSourceBindingV1(path=request.path, sha256=_DIGEST),),
        )

    async def apply(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        self.applied.append(request)
        return LedgerImportOutcomeV1(
            source_kind=request.source_kind, dry_run=False, files=1, rows=2, imported=2, skipped=0
        )


def _accounts() -> MemoryOwnAccountDoor:
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
    return door


def _screen(import_door: _BindingImportDoor, accounts: MemoryOwnAccountDoor | None) -> LedgerImportScreen:
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(
            review_action=ledger_review_action(),
            import_door=import_door,
            own_account_door=None if accounts is None else cast(LedgerOwnAccountDoorV1, accounts),
        ),
    )
    return LedgerImportScreen(controller)


async def _settle(pilot: Pilot[None]) -> None:
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


@pytest.mark.asyncio
async def test_import_binds_the_chosen_own_account_and_applies_the_previewed_digest(tmp_path: Path) -> None:
    import_door = _BindingImportDoor()
    screen = _screen(import_door, _accounts())
    statement = tmp_path / "statement.csv"
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(110, 50)) as pilot:
            await _settle(pilot)
            account = cast("Select[str]", screen.query_one("#ledger-import-account", Select))
            overlay = account.query_one(OptionList)
            labels = [str(overlay.get_option_at_index(index).prompt) for index in range(overlay.option_count)]
            assert labels[1:] == ["acc-01 · Cuenta nómina · ES ···· 1332", "acc-02 · Ahorro · ES ···· 6789"]
            account.value = "acc-02"
            screen.query_one("#ledger-import-path", Input).value = str(statement)
            statement.write_text("synthetic", encoding="utf-8")
            screen.query_one("#ledger-import-preview-button", Button).press()
            await _settle(pilot)

            assert import_door.previews[0].own_account_id == "acc-02"
            assert import_door.previews[0].previewed_sources is None
            preview = str(screen.query_one("#ledger-import-preview", Static).render())
            assert tr("tui.ledger.import.account_line", account="Ahorro · ES ···· 6789") in preview
            assert SYNTHETIC_ES_IBAN_2 not in preview
            assert screen.query_one("#ledger-import-account", Select).disabled

            screen.query_one("#ledger-import-confirm", Button).press()
            await _settle(pilot)

            assert screen.flow_state is LedgerFlowState.SUCCEEDED
            applied = import_door.applied[0]
            assert applied.own_account_id == "acc-02"
            assert applied.previewed_sources == (LedgerImportSourceBindingV1(path=statement, sha256=_DIGEST),)


@pytest.mark.asyncio
async def test_import_without_an_account_register_offers_only_statement_binding(tmp_path: Path) -> None:
    import_door = _BindingImportDoor()
    screen = _screen(import_door, None)
    statement = tmp_path / "statement.csv"
    statement.write_text("synthetic", encoding="utf-8")
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(110, 50)) as pilot:
            await _settle(pilot)
            account = cast("Select[str]", screen.query_one("#ledger-import-account", Select))
            assert account.query_one(OptionList).option_count == 1
            screen.query_one("#ledger-import-path", Input).value = str(statement)
            screen.query_one("#ledger-import-preview-button", Button).press()
            await _settle(pilot)
            assert import_door.previews[0].own_account_id is None
            preview = str(screen.query_one("#ledger-import-preview", Static).render())
            assert tr("tui.ledger.import.account_line_unbound") in preview
