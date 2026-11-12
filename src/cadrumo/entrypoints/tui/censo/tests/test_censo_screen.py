"""The mounted census declarations destination over the real read projections and the real served record form.

The record opens the registered operation's own request form, built from the
request schema the registry publishes for it. The door holds the declarations in
memory: the screen under test only reads them, and records through the form.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from functools import lru_cache
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID

import pytest
from pydantic import BaseModel
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Static

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.transport.frontend_client import FrontendClient

from .....application.modelo.m036_operation import (
    M036DeclarationSnapshot,
    M036ReadProjection,
    M036RecordProjection,
    build_m036_operation_definitions,
    build_m036_operation_registrations,
)
from .....application.modelo.m036_operation_ports import M036OperationPortsFactory
from .....application.operations.registry import OperationRegistry
from .....application.user_profile.access_errors import ProfileAccessRefusedError
from .....core.config import override_settings
from .....core.errors.hierarchy import CadrumoError
from .....core.i18n.render import tr
from .....domain.calculations.registry.censo_modelos import CensoModeloEventKind
from ...account import AccountSessionExpiredError
from ...components.host import ScreenHostApp
from ...operations.catalogue import OperationCatalogueEntryV1, served_operation_entry
from ...operations.outcome import OperationOutcomeUnknownError
from ...operations.request_form import request_fields
from ...operations.run_screen import OperationRunScreen
from ...refusal.panel import RefusalSlot
from ...tests.settling import settle, settle_until
from ..screen import CensoScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_SESSION_ID = UUID("6bb00000-0000-4000-8000-0000000000bb")
_RECORD_DEFINITION_ID = "modelo.036.record"


@lru_cache(maxsize=1)
def _registry() -> OperationRegistry:
    factory = cast(M036OperationPortsFactory, cast(object, lambda **_kwargs: None))
    definitions = tuple(sorted(build_m036_operation_definitions(factory), key=lambda item: item.definition_id))
    return OperationRegistry(
        definitions=definitions, public_registrations=build_m036_operation_registrations(definitions)
    )


def _entry() -> OperationCatalogueEntryV1:
    registry = _registry()
    description = registry.describe_public_definition(_RECORD_DEFINITION_ID)
    contract = description.contract
    assert contract.result_schema is not None
    return served_operation_entry(
        contract,
        description.request_json_schema,
        request_type=registry.lookup(_RECORD_DEFINITION_ID).request_type,
        result_type=registry.lookup_public_schema_binding(contract.result_schema).model_type,
    )


def _declaration(
    kind: CensoModeloEventKind, declared_on: date, *, fill: str, justificante: str | None, note: str | None
) -> M036DeclarationSnapshot:
    return M036DeclarationSnapshot(
        declaration_id=fill * 64,
        bucket_id=str(_PROFILE_ID),
        profile_id=str(_PROFILE_ID),
        event_kind=kind,
        declared_on=declared_on,
        sede_justificante=justificante,
        note=note,
        recorded_at=datetime(2026, 10, 3, 9, 30, tzinfo=UTC),
    )


_ALTA = _declaration(
    CensoModeloEventKind.ALTA, date(2026, 9, 1), fill="a", justificante="SYNTHETIC-REF-1", note="Synthetic note"
)
_BAJA = _declaration(CensoModeloEventKind.BAJA, date(2026, 9, 20), fill="b", justificante=None, note=None)


class _SettledForm(OperationRunScreen):
    """A run screen that reports a settled result once dismissed, standing in for a submitted run."""

    def __init__(self, prefill: Mapping[str, object], result: BaseModel | None) -> None:
        client = cast(FrontendClient, SimpleNamespace(profile_id=_PROFILE_ID, session_id=_SESSION_ID))
        super().__init__(client, _entry(), initial=prefill)
        self._result = result

    @property
    @override
    def settled_result(self) -> BaseModel | None:
        return self._result


class _MemoryDoor:
    """Serve fixed declarations, open the real served form, and record every read and form opened."""

    def __init__(self, rows: tuple[M036DeclarationSnapshot, ...] = ()) -> None:
        self.rows = rows
        self.list_reads = 0
        self.viewed: list[str] = []
        self.forms: list[dict[str, object]] = []
        self.settled: BaseModel | None = None
        self.read_error: CadrumoError | None = None

    @property
    def profile_id(self) -> UUID:
        return _PROFILE_ID

    async def declarations(self) -> M036ReadProjection:
        self.list_reads += 1
        if self.read_error is not None:
            raise self.read_error
        return M036ReadProjection(profile_id=_PROFILE_ID, kind="list", declarations=self.rows)

    async def declaration(self, declaration_id: str) -> M036ReadProjection:
        self.viewed.append(declaration_id)
        found = tuple(row for row in self.rows if row.declaration_id == declaration_id)
        return M036ReadProjection(profile_id=_PROFILE_ID, kind="view", declarations=found)

    def record_form(self, prefill: Mapping[str, object]) -> OperationRunScreen:
        self.forms.append(dict(prefill))
        return _SettledForm(prefill, self.settled)


def _cells(table: DataTable[str]) -> list[list[str]]:
    return [[str(cell) for cell in table.get_row_at(row)] for row in range(table.row_count)]


def _headers(table: DataTable[str]) -> list[str]:
    return [str(column.label) for column in table.columns.values()]


def _text(screen: CensoScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


async def _press(pilot: Pilot[None], screen: CensoScreen, button_id: str) -> None:
    screen.query_one(f"#{button_id}", Button).press()
    await settle(pilot)


@pytest.mark.asyncio
async def test_the_destination_lists_each_declaration_as_read_and_says_it_is_a_local_record() -> None:
    door = _MemoryDoor((_ALTA, _BAJA))
    screen = CensoScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)

            assert door.list_reads == 1
            table = cast("DataTable[str]", screen.query_one("#censo-declarations", DataTable))
            assert _headers(table) == [
                tr("tui.censo.column.kind"),
                tr("tui.censo.column.declared_on"),
                tr("tui.censo.column.recorded_at"),
            ]
            assert _cells(table) == [["alta", "2026-09-01", "2026-10-03"], ["baja", "2026-09-20", "2026-10-03"]]
            assert _text(screen, "#censo-status") == ""
            assert screen.query_one("#censo-refusal", RefusalSlot).refusal is None
            # The page states beside the list that nothing recorded here was sent.
            assert any(str(widget.render()) == tr("tui.censo.local_note") for widget in screen.query(Static))


@pytest.mark.asyncio
async def test_choosing_a_row_reads_that_declaration_in_full_and_blanks_are_said_not_filled() -> None:
    door = _MemoryDoor((_ALTA, _BAJA))
    screen = CensoScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            table = cast("DataTable[str]", screen.query_one("#censo-declarations", DataTable))

            await _press(pilot, screen, "censo-show-detail")
            assert door.viewed == [_ALTA.declaration_id]
            detail = _text(screen, "#censo-detail")
            assert _ALTA.declaration_id in detail
            assert "SYNTHETIC-REF-1" in detail
            assert "Synthetic note" in detail
            assert tr("tui.censo.local_note") in detail

            table.move_cursor(row=1)
            await _press(pilot, screen, "censo-show-detail")
            detail = _text(screen, "#censo-detail")
            assert door.viewed[-1] == _BAJA.declaration_id
            assert f"{tr('tui.censo.detail.justificante')}: {tr('tui.censo.detail.none')}" in detail
            assert f"{tr('tui.censo.detail.note')}: {tr('tui.censo.detail.none')}" in detail


@pytest.mark.asyncio
async def test_no_declarations_say_so_and_detail_needs_a_chosen_row() -> None:
    door = _MemoryDoor()
    screen = CensoScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            table = cast("DataTable[str]", screen.query_one("#censo-declarations", DataTable))

            assert table.row_count == 0
            assert _text(screen, "#censo-status") == tr("tui.censo.status.empty")
            await _press(pilot, screen, "censo-show-detail")
            assert door.viewed == []
            assert _text(screen, "#censo-status") == tr("tui.censo.status.choose_declaration")


@pytest.mark.asyncio
async def test_record_opens_the_served_form_and_a_settled_record_is_said_local_then_listed() -> None:
    door = _MemoryDoor()
    screen = CensoScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(140, 80)) as pilot:
            await settle(pilot)
            # The stand-in form reports the result a submitted run would have settled.
            door.rows = (_ALTA,)
            door.settled = M036RecordProjection(profile_id=_PROFILE_ID, declaration=_ALTA)
            await _press(pilot, screen, "censo-record")
            form = pilot.app.screen
            assert isinstance(form, OperationRunScreen)
            assert door.forms == [{}]
            names = {field.name for field in request_fields(form.entry.input_json_schema, profile_id=_PROFILE_ID)}
            assert {"event_kind", "declared_on", "sede_justificante", "note"} <= names

            form.query_one("#operation-close", Button).press()
            await settle_until(pilot, lambda: pilot.app.screen is screen, "the form returned to the destination")
            await settle(pilot)

            assert door.list_reads == 2
            assert _text(screen, "#censo-status") == tr(
                "tui.censo.status.recorded", kind="alta", declared_on="2026-09-01"
            )
            table = cast("DataTable[str]", screen.query_one("#censo-declarations", DataTable))
            assert _cells(table) == [["alta", "2026-09-01", "2026-10-03"]]


@pytest.mark.asyncio
async def test_a_form_that_settled_nothing_is_never_claimed_as_recorded() -> None:
    door = _MemoryDoor()
    screen = CensoScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(140, 80)) as pilot:
            await settle(pilot)
            await _press(pilot, screen, "censo-record")
            form = pilot.app.screen
            assert isinstance(form, OperationRunScreen)
            form.query_one("#operation-close", Button).press()
            await settle_until(pilot, lambda: pilot.app.screen is screen, "the form returned to the destination")
            await settle(pilot)

            # The list is read again, and it is the list that says what is stored.
            assert door.list_reads == 2
            assert _text(screen, "#censo-status") == tr("tui.censo.status.unconfirmed")
            assert cast("DataTable[str]", screen.query_one("#censo-declarations", DataTable)).row_count == 0


@pytest.mark.asyncio
async def test_a_refused_read_shows_the_served_refusal_and_draws_no_list() -> None:
    door = _MemoryDoor((_ALTA,))
    door.read_error = ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    screen = CensoScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)

            assert _text(screen, "#censo-status") == tr("tui.censo.status.read_failed")
            slot = screen.query_one("#censo-refusal", RefusalSlot)
            assert slot.refusal is not None
            assert slot.refusal.sentence is not None
            assert slot.refusal.no_recovery_words is not None
            # The served sentences are drawn by the slot's panel, and no failure text stands beside them.
            panel_text = {str(widget.render()) for widget in slot.query(Static)}
            assert {slot.refusal.sentence, slot.refusal.no_recovery_words.words} <= panel_text
            assert _text(screen, "#censo-failure") == ""
            assert cast("DataTable[str]", screen.query_one("#censo-declarations", DataTable)).row_count == 0


@pytest.mark.asyncio
async def test_an_unknown_outcome_is_shown_as_unknown_and_keeps_the_list_last_read() -> None:
    door = _MemoryDoor((_ALTA,))
    screen = CensoScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            door.read_error = OperationOutcomeUnknownError(operation_id="a" * 64, effect=None)
            await _press(pilot, screen, "censo-read")

            assert _text(screen, "#censo-status") == tr("tui.censo.status.read_failed")
            refusal = screen.query_one("#censo-refusal", RefusalSlot).refusal
            assert refusal is not None
            # The served sentence names the operation and says its outcome is unknown.
            assert refusal.sentence is not None
            assert "a" * 64 in refusal.sentence
            assert "unknown" in refusal.sentence
            assert [row.declaration_id for row in screen.declarations] == [_ALTA.declaration_id]


@pytest.mark.asyncio
async def test_a_lapsed_session_drops_what_was_read_for_it() -> None:
    door = _MemoryDoor((_ALTA,))
    screen = CensoScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp(screen).run_test(size=(120, 60)) as pilot:
            await settle(pilot)
            await _press(pilot, screen, "censo-show-detail")
            assert _text(screen, "#censo-detail")
            door.read_error = AccountSessionExpiredError()
            await _press(pilot, screen, "censo-read")

            assert screen.declarations == ()
            assert screen.detail is None
            assert _text(screen, "#censo-detail") == ""
            assert cast("DataTable[str]", screen.query_one("#censo-declarations", DataTable)).row_count == 0
