"""Admission, exact-session dispatch and receipt correlation for the installed census declarations TUI door.

The runtime's descriptions are served from a real registry of the census
operations, so admission is judged against the contracts and request schemas
the operations really publish.
"""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import cast
from uuid import UUID

import pytest

from cadrumo.application.modelo.m036_operation import (
    M036_QUERY_OPERATION_DEFINITION_ID,
    M036_READ_OPERATION_DEFINITION_ID,
    M036_RECORD_OPERATION_DEFINITION_ID,
    M036DeclarationSnapshot,
    M036ReadProjection,
    M036ReadRequest,
    build_m036_operation_definitions,
    build_m036_operation_registrations,
)
from cadrumo.application.modelo.m036_operation_ports import M036OperationPortsFactory
from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1, OperationRegistry
from cadrumo.core.operations import OperationEffect, OperationFrontendProjection
from cadrumo.domain.calculations.registry.censo_modelos import CensoModeloEventKind
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.operations.request_form import request_fields
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .....frontend.tui.modelo.runtime_censo import (
    CENSO_OPERATION_SHAPES,
    RuntimeCensoTuiDoorV1,
    compose_runtime_censo_door,
)
from ..door_session_support import (
    PROFILE_ID,
    SESSION_ID,
    ScriptedController,
    SessionClient,
    install_scripted_controller,
    terminal_observation,
)
from ..unsupported_result import raises_unsupported_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OTHER_SESSION_ID = UUID("7cc00000-0000-4000-8000-0000000000cc")
_OTHER_PROFILE_ID = UUID("6cc00000-0000-4000-8000-0000000000cc")


@lru_cache(maxsize=1)
def _registry() -> OperationRegistry:
    factory = cast(M036OperationPortsFactory, cast(object, lambda **_kwargs: None))
    definitions = tuple(sorted(build_m036_operation_definitions(factory), key=lambda item: item.definition_id))
    return OperationRegistry(
        definitions=definitions, public_registrations=build_m036_operation_registrations(definitions)
    )


class _DescribingClient(SessionClient):
    """Describe each operation as the runtime would, from the real registry, or refuse or misdescribe one."""

    def __init__(self, *, refused: str | None = None, misdescribed: str | None = None) -> None:
        super().__init__()
        self.refused = refused
        self.misdescribed = misdescribed
        self.described: list[str] = []

    def describe(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionDescriptionV1:
        assert deadline > 0
        self.described.append(definition_id)
        if definition_id == self.refused:
            raise FrontendRefusedError("operation_not_admitted")
        served = M036_QUERY_OPERATION_DEFINITION_ID if definition_id == self.misdescribed else definition_id
        return _registry().describe_public_definition(served)


def _compose(client: _DescribingClient) -> RuntimeCensoTuiDoorV1 | None:
    return compose_runtime_censo_door(cast(FrontendClient, client), profile_label="Fixture profile")


def _door(client: _DescribingClient) -> RuntimeCensoTuiDoorV1:
    door = _compose(client)
    assert door is not None
    return door


def _declaration(fill: str, profile_id: UUID = PROFILE_ID) -> M036DeclarationSnapshot:
    return M036DeclarationSnapshot(
        declaration_id=fill * 64,
        bucket_id=str(profile_id),
        profile_id=str(profile_id),
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 9, 1),
        sede_justificante=None,
        note=None,
        recorded_at=datetime(2026, 10, 3, tzinfo=UTC),
    )


def _listed(*rows: M036DeclarationSnapshot, profile_id: UUID = PROFILE_ID) -> M036ReadProjection:
    return M036ReadProjection(profile_id=profile_id, kind="list", declarations=rows)


def _viewed(row: M036DeclarationSnapshot, profile_id: UUID = PROFILE_ID) -> M036ReadProjection:
    return M036ReadProjection(profile_id=profile_id, kind="view", declarations=(row,))


def test_the_door_is_admitted_only_with_both_operations_described_and_builds_the_form_from_the_served_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _DescribingClient()
    install_scripted_controller(
        monkeypatch,
        client,
        ScriptedController(
            observation=terminal_observation(_registry(), M036_READ_OPERATION_DEFINITION_ID), result=None
        ),
    )
    door = _door(client)

    assert door.profile_id == PROFILE_ID
    assert client.described == list(CENSO_OPERATION_SHAPES)
    form = door.record_form({})
    served = _registry().describe_public_definition(M036_RECORD_OPERATION_DEFINITION_ID)
    assert form.entry.contract == served.contract
    assert form.entry.input_json_schema == served.request_json_schema
    names = {field.name for field in request_fields(form.entry.input_json_schema, profile_id=PROFILE_ID)}
    assert {"event_kind", "declared_on", "sede_justificante", "note"} <= names


@pytest.mark.parametrize("definition_id", list(CENSO_OPERATION_SHAPES))
def test_a_refused_description_leaves_the_destination_unavailable(
    monkeypatch: pytest.MonkeyPatch, definition_id: str
) -> None:
    client = _DescribingClient(refused=definition_id)
    install_scripted_controller(
        monkeypatch,
        client,
        ScriptedController(observation=terminal_observation(_registry(), definition_id), result=None),
    )

    assert _compose(client) is None
    assert client.described[-1] == definition_id


@pytest.mark.parametrize("definition_id", list(CENSO_OPERATION_SHAPES))
def test_a_description_of_another_operation_leaves_the_destination_unavailable(
    monkeypatch: pytest.MonkeyPatch, definition_id: str
) -> None:
    client = _DescribingClient(misdescribed=definition_id)
    install_scripted_controller(
        monkeypatch,
        client,
        ScriptedController(observation=terminal_observation(_registry(), definition_id), result=None),
    )

    assert _compose(client) is None


def test_another_frontend_is_never_admitted() -> None:
    client = _DescribingClient()
    client.frontend = OperationFrontendProjection.CLI

    assert _compose(client) is None
    assert client.described == []


def test_the_list_read_submits_the_exact_request_and_returns_its_result(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DescribingClient()
    controller = ScriptedController(
        observation=terminal_observation(_registry(), M036_READ_OPERATION_DEFINITION_ID),
        result=_listed(_declaration("a")),
    )
    submissions = install_scripted_controller(monkeypatch, client, controller)

    assert asyncio.run(_door(client).declarations()) == _listed(_declaration("a"))
    assert submissions[0]["definition_id"] == M036_READ_OPERATION_DEFINITION_ID
    assert submissions[0]["payload"] == M036ReadRequest(profile_id=PROFILE_ID, kind="list")
    assert submissions[0]["expected_session_id"] == SESSION_ID
    assert controller.result_reads == [(M036ReadProjection, 1, False)]


def test_the_view_read_submits_the_selector_and_returns_that_record(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DescribingClient()
    row = _declaration("b")
    controller = ScriptedController(
        observation=terminal_observation(_registry(), M036_READ_OPERATION_DEFINITION_ID), result=_viewed(row)
    )
    submissions = install_scripted_controller(monkeypatch, client, controller)

    assert asyncio.run(_door(client).declaration(row.declaration_id[:12])) == _viewed(row)
    assert submissions[0]["payload"] == M036ReadRequest(
        profile_id=PROFILE_ID, kind="view", declaration_id=row.declaration_id[:12]
    )


@pytest.mark.parametrize(
    ("viewed", "result", "effect"),
    [
        # A list of another profile than the one asked.
        (False, _listed(profile_id=_OTHER_PROFILE_ID), OperationEffect.NONE),
        # A list answered with a view.
        (False, _viewed(_declaration("a")), OperationEffect.NONE),
        # A view answered with a list.
        (True, _listed(_declaration("a")), OperationEffect.NONE),
        # Reads whose receipt says something changed.
        (False, _listed(_declaration("a")), OperationEffect.UPDATED),
        (True, _viewed(_declaration("a")), OperationEffect.UPDATED),
    ],
)
def test_a_read_refuses_a_result_its_receipt_does_not_support(
    monkeypatch: pytest.MonkeyPatch, viewed: bool, result: M036ReadProjection, effect: OperationEffect
) -> None:
    client = _DescribingClient()
    receipt = terminal_observation(_registry(), M036_READ_OPERATION_DEFINITION_ID, effect=effect)
    install_scripted_controller(monkeypatch, client, ScriptedController(observation=receipt, result=result))
    door = _door(client)
    read = door.declaration("a" * 12) if viewed else door.declarations()

    with raises_unsupported_result(effect, receipt.projection.definition_contract):
        asyncio.run(read)


def test_a_view_answered_with_another_record_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DescribingClient()
    receipt = terminal_observation(_registry(), M036_READ_OPERATION_DEFINITION_ID)
    install_scripted_controller(
        monkeypatch, client, ScriptedController(observation=receipt, result=_viewed(_declaration("c")))
    )
    door = _door(client)

    with raises_unsupported_result(OperationEffect.NONE, receipt.projection.definition_contract):
        asyncio.run(door.declaration("d" * 12))


def test_the_reads_fail_closed_when_the_session_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DescribingClient()
    submissions = install_scripted_controller(
        monkeypatch,
        client,
        ScriptedController(
            observation=terminal_observation(_registry(), M036_READ_OPERATION_DEFINITION_ID), result=_listed()
        ),
    )
    door = _door(client)
    client.session_id = _OTHER_SESSION_ID

    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(door.declarations())
    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(door.declaration("a" * 12))

    assert submissions == []


def test_a_form_is_not_opened_once_the_session_changed(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DescribingClient()
    install_scripted_controller(
        monkeypatch,
        client,
        ScriptedController(
            observation=terminal_observation(_registry(), M036_READ_OPERATION_DEFINITION_ID), result=None
        ),
    )
    door = _door(client)
    client.session_id = _OTHER_SESSION_ID

    with pytest.raises(AccountSessionExpiredError):
        door.record_form({})


def test_the_reads_check_their_session_off_the_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DescribingClient()
    install_scripted_controller(
        monkeypatch,
        client,
        ScriptedController(
            observation=terminal_observation(_registry(), M036_READ_OPERATION_DEFINITION_ID), result=_listed()
        ),
    )
    door = _door(client)
    client.session_read_threads.clear()

    asyncio.run(door.declarations())

    assert client.session_read_threads, "a door reads its session around its operation"
    assert threading.get_ident() not in client.session_read_threads
