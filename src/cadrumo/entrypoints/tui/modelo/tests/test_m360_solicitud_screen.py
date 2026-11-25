"""The Modelo 360 solicitud screen, driven by a real pilot over the operation's own action logic."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Select, Static

from .....application.filing.producer_snapshot_m360 import M360TitularEnCalidadDe
from .....application.ledger.workspace import LedgerWorkspaceArea
from .....application.modelo.m360_solicitud_operation import Modelo360SolicitudRequest
from .....core.config import override_settings
from .....core.external_constants import UTF_8_ENCODING
from .....core.i18n.render import tr
from ...ledger.controller import LedgerWorkspaceController
from ...ledger.tests.workspace_fixtures import (
    WorkspaceHostApp,
    ledger_context,
    ledger_projection,
    ledger_review_action,
)
from ...ledger.workspace_injection import LedgerWorkspaceInjection
from ...tests.settling import settle
from ..m360_solicitud import (
    SOLICITUD_360_TOOL_KEY,
    Modelo360SolicitudDoorV1,
    Modelo360SolicitudScreen,
    solicitud_360_tool,
)
from .solicitud_360_fixtures import (
    SOLICITUD_PROFILE_ID,
    SYNTHETIC_OWN_IBAN,
    SYNTHETIC_REPRESENTANTE_IBAN,
    MemorySolicitudDoor,
    synthetic_facts_json,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]


def _screen(door: MemorySolicitudDoor) -> Modelo360SolicitudScreen:
    controller = LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
    return Modelo360SolicitudScreen(controller, cast(Modelo360SolicitudDoorV1, door))


async def _press(pilot: Pilot[None], screen: Modelo360SolicitudScreen, button_id: str) -> None:
    screen.query_one(f"#{button_id}", Button).press()
    await settle(pilot)


async def _choose(pilot: Pilot[None], screen: Modelo360SolicitudScreen, select_id: str, value: str) -> None:
    cast("Select[str]", screen.query_one(f"#{select_id}", Select)).value = value
    await settle(pilot)


def _text(screen: Modelo360SolicitudScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


def _keys(screen: Modelo360SolicitudScreen) -> list[str]:
    return [str(row.key.value) for row in screen.query_one("#m360-solicitudes", DataTable).ordered_rows]


def _facts_file(directory: Path, holder: M360TitularEnCalidadDe) -> str:
    path = directory / "solicitud-facts.json"
    path.write_text(synthetic_facts_json(holder), encoding=UTF_8_ENCODING)
    return str(path)


def _type(screen: Modelo360SolicitudScreen, **values: str) -> None:
    for name, value in values.items():
        screen.query_one(f"#{name.replace('_', '-')}", Input).value = value


def _screen_text(screen: Modelo360SolicitudScreen) -> str:
    return " ".join(str(widget.render()) for widget in screen.query(Static))


@pytest.mark.asyncio
async def test_a_solicitante_declaration_with_an_own_account_lists_masked(tmp_path: Path) -> None:
    door = MemorySolicitudDoor()
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            assert door.requests == [Modelo360SolicitudRequest(profile_id=SOLICITUD_PROFILE_ID, action="list")]
            assert _text(screen, "#ledger-flow-status") == tr("tui.modelo.m360_solicitud.empty")

            facts = _facts_file(tmp_path, M360TitularEnCalidadDe.SOLICITANTE)
            _type(screen, m360_year="2025", m360_facts_path=facts, m360_own_account="acc-01")
            await _press(pilot, screen, "register-review")
            staged = screen.staged
            assert isinstance(staged, Modelo360SolicitudRequest), _text(screen, "#ledger-refusal")
            assert (staged.action, staged.filing_year, staged.own_account_id) == ("declare", 2025, "acc-01")
            assert staged.representante_account is None
            assert "acc-01" in _text(screen, "#register-staged")

            await _press(pilot, screen, "register-confirm")
            assert door.requests[1] == staged
            assert _keys(screen) == ["2025"]
            (entry,) = door.solicitudes.register.entries
            assert entry.period.filing_year == 2025
            row = screen.query_one("#m360-solicitudes", DataTable).get_row_at(0)
            assert row[1] == "FR"
            assert row[4] == "acc-01"
            assert _text(screen, "#register-result") == tr("tui.modelo.m360_solicitud.done_declare")
            assert SYNTHETIC_OWN_IBAN not in _screen_text(screen)


@pytest.mark.asyncio
async def test_a_representante_account_is_typed_as_a_secret_and_shown_only_by_its_mask(tmp_path: Path) -> None:
    door = MemorySolicitudDoor()
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, "m360-account-kind", "representante")
            assert not screen.query_one("#m360-own-account-field").display
            assert screen.query_one("#m360-iban-field").display
            assert screen.query_one("#m360-iban", Input).password
            assert screen.query_one("#m360-bic", Input).password

            facts = _facts_file(tmp_path, M360TitularEnCalidadDe.REPRESENTANTE)
            _type(
                screen,
                m360_year="2025",
                m360_facts_path=facts,
                m360_iban=SYNTHETIC_REPRESENTANTE_IBAN,
                m360_bic="COBADEFFXXX",
            )
            await _press(pilot, screen, "register-review")
            staged = screen.staged
            assert isinstance(staged, Modelo360SolicitudRequest), _text(screen, "#ledger-refusal")
            assert staged.own_account_id is None
            assert staged.representante_account is not None
            reviewed = _text(screen, "#register-staged")
            assert "DE ···· 3000" in reviewed
            assert SYNTHETIC_REPRESENTANTE_IBAN not in reviewed

            await _press(pilot, screen, "register-confirm")
            row = screen.query_one("#m360-solicitudes", DataTable).get_row_at(0)
            assert row[4] == "DE ···· 3000"
            assert SYNTHETIC_REPRESENTANTE_IBAN not in _screen_text(screen)


@pytest.mark.asyncio
async def test_an_own_account_without_a_bic_is_refused_by_the_operation_and_stays_staged(tmp_path: Path) -> None:
    door = MemorySolicitudDoor(own_account_bic="")
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            facts = _facts_file(tmp_path, M360TitularEnCalidadDe.SOLICITANTE)
            _type(screen, m360_year="2025", m360_facts_path=facts, m360_own_account="acc-01")
            await _press(pilot, screen, "register-review")
            await _press(pilot, screen, "register-confirm")
            assert _text(screen, "#ledger-refusal")
            assert isinstance(screen.staged, Modelo360SolicitudRequest)
            assert door.solicitudes.register.entries == ()


@pytest.mark.asyncio
async def test_removing_an_undeclared_year_is_refused_by_the_operation() -> None:
    door = MemorySolicitudDoor()
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _choose(pilot, screen, "m360-action", "remove")
            assert not screen.query_one("#m360-facts-path-field").display
            _type(screen, m360_year="2025")
            await _press(pilot, screen, "register-review")
            staged = screen.staged
            assert isinstance(staged, Modelo360SolicitudRequest)
            assert staged.action == "remove"
            await _press(pilot, screen, "register-confirm")
            assert _text(screen, "#ledger-refusal")
            assert door.solicitudes.register.entries == ()


@pytest.mark.asyncio
async def test_removing_a_declared_solicitud_empties_the_register(tmp_path: Path) -> None:
    door = MemorySolicitudDoor()
    screen = _screen(door)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            facts = _facts_file(tmp_path, M360TitularEnCalidadDe.SOLICITANTE)
            _type(screen, m360_year="2025", m360_facts_path=facts, m360_own_account="acc-01")
            await _press(pilot, screen, "register-review")
            await _press(pilot, screen, "register-confirm")
            assert _keys(screen) == ["2025"]

            await _choose(pilot, screen, "m360-action", "remove")
            await _press(pilot, screen, "register-review")
            await _press(pilot, screen, "register-confirm")
            assert _keys(screen) == []
            assert door.solicitudes.register.entries == ()
            assert _text(screen, "#register-result") == tr("tui.modelo.m360_solicitud.done_remove")


@pytest.mark.asyncio
async def test_an_unreadable_or_invalid_facts_file_is_refused_before_anything_is_sent(tmp_path: Path) -> None:
    door = MemorySolicitudDoor()
    screen = _screen(door)
    absent = str(tmp_path / "absent.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{}", encoding=UTF_8_ENCODING)
    with override_settings(cadrumo_output_language="en"):
        async with WorkspaceHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            _type(screen, m360_year="2025", m360_own_account="acc-01", m360_facts_path=absent)
            await _press(pilot, screen, "register-review")
            assert screen.staged is None
            assert _text(screen, "#ledger-refusal") == tr("tui.modelo.m360_solicitud.source_unreadable", path=absent)

            _type(screen, m360_facts_path=str(broken))
            await _press(pilot, screen, "register-review")
            assert screen.staged is None
            assert str(broken) in _text(screen, "#ledger-refusal")
            assert len(door.requests) == 1


def test_the_solicitud_tool_attaches_to_the_overview() -> None:
    tool = solicitud_360_tool(cast(Modelo360SolicitudDoorV1, MemorySolicitudDoor()))
    controller = LedgerWorkspaceController(
        ledger_context(),
        ledger_projection(),
        LedgerWorkspaceInjection(review_action=ledger_review_action(), tools=(tool,)),
    )
    assert tool.key == SOLICITUD_360_TOOL_KEY
    assert tool.area is LedgerWorkspaceArea.OVERVIEW
    assert isinstance(tool.build(controller), Modelo360SolicitudScreen)
