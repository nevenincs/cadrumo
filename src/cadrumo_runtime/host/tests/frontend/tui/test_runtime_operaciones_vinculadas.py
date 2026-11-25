"""Admission, exact-session dispatch and receipt correlation for the installed related-party operations TUI door.

The runtime's descriptions are served from a real registry of the seven
Modelo 232 related-party operations, so admission is judged against the
contracts and request schemas the operations really publish.
"""

from __future__ import annotations

import asyncio
import threading
from functools import lru_cache
from typing import cast
from uuid import UUID

import pytest

from cadrumo.application.m232_related_party.contracts import M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID
from cadrumo.application.m232_related_party.ports import Modelo232RelatedPartyPortsFactory
from cadrumo.application.m232_related_party.registered_operation import (
    build_m232_related_party_definition,
    build_m232_related_party_list_registration,
    build_m232_related_party_registration,
)
from cadrumo.application.m232_related_party.requests import Modelo232RelatedPartyListRequest
from cadrumo.application.m232_related_party.results import (
    Modelo232RelatedPartyListProjection,
    Modelo232YearProjection,
)
from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1, OperationRegistry
from cadrumo.core.operations import OperationEffect, OperationFrontendProjection
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.operaciones_vinculadas.screen import OperacionesVinculadasMutation
from cadrumo.entrypoints.tui.operations.request_form import request_fields
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....frontend.tui.runtime_operaciones_vinculadas import (
    OPERACIONES_VINCULADAS_OPERATION_SHAPES,
    RuntimeOperacionesVinculadasTuiDoorV1,
    compose_runtime_operaciones_vinculadas_door,
)
from .door_session_support import (
    PROFILE_ID,
    SESSION_ID,
    ScriptedController,
    SessionClient,
    install_scripted_controller,
    terminal_observation,
)
from .unsupported_result import raises_unsupported_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon
_OTHER_SESSION_ID = UUID("7cc00000-0000-4000-8000-0000000000cc")


@lru_cache(maxsize=1)
def _registry() -> OperationRegistry:
    ports = cast(Modelo232RelatedPartyPortsFactory, cast(object, lambda **_kwargs: None))
    # The registry holds its definitions in identity order.
    definitions = tuple(
        build_m232_related_party_definition(definition_id, ports)
        for definition_id in sorted(OPERACIONES_VINCULADAS_OPERATION_SHAPES)
    )
    return OperationRegistry(
        definitions=definitions,
        public_registrations=tuple(
            build_m232_related_party_list_registration(item)
            if item.definition_id == M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID
            else build_m232_related_party_registration(item)
            for item in definitions
        ),
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
        served = (
            OperacionesVinculadasMutation.WITHDRAW_OPERATION.value
            if definition_id == self.misdescribed
            else definition_id
        )
        return _registry().describe_public_definition(served)


def _compose(client: _DescribingClient) -> RuntimeOperacionesVinculadasTuiDoorV1 | None:
    return compose_runtime_operaciones_vinculadas_door(cast(FrontendClient, client), profile_label="Fixture profile")


def _door(client: _DescribingClient) -> RuntimeOperacionesVinculadasTuiDoorV1:
    door = _compose(client)
    assert door is not None
    return door


def _listing(ejercicio: int = _YEAR) -> Modelo232RelatedPartyListProjection:
    return Modelo232RelatedPartyListProjection(
        profile_id=PROFILE_ID,
        ejercicio=ejercicio,
        year=Modelo232YearProjection(
            guard_revision_id="guard-1", operations=(), none_statements=(), turnover_statements=(), verdict=None
        ),
    )


def _install(
    monkeypatch: pytest.MonkeyPatch, client: _DescribingClient, result: Modelo232RelatedPartyListProjection | None
) -> list[dict[str, object]]:
    return install_scripted_controller(
        monkeypatch,
        client,
        ScriptedController(
            observation=terminal_observation(_registry(), M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID),
            result=result,
        ),
    )


def test_the_door_is_admitted_only_with_every_operation_described_and_builds_forms_from_the_served_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _DescribingClient()
    _install(monkeypatch, client, None)
    door = _door(client)

    assert door.profile_id == PROFILE_ID
    assert client.described == list(OPERACIONES_VINCULADAS_OPERATION_SHAPES)
    form = door.mutation_form(OperacionesVinculadasMutation.STATE_OPERATION, {"ejercicio": _YEAR})
    served = _registry().describe_public_definition(OperacionesVinculadasMutation.STATE_OPERATION.value)
    assert form.entry.contract == served.contract
    assert form.entry.input_json_schema == served.request_json_schema
    names = {field.name for field in request_fields(form.entry.input_json_schema, profile_id=PROFILE_ID)}
    assert {"counterparty_name", "counterparty_tax_id", "expected_guard_revision_id"} <= names


@pytest.mark.parametrize("definition_id", list(OPERACIONES_VINCULADAS_OPERATION_SHAPES))
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


@pytest.mark.parametrize(
    "definition_id",
    [
        item
        for item in OPERACIONES_VINCULADAS_OPERATION_SHAPES
        if item != OperacionesVinculadasMutation.WITHDRAW_OPERATION.value
    ],
)
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


def test_the_listing_read_submits_the_exact_request_and_returns_its_result(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DescribingClient()
    controller = ScriptedController(
        observation=terminal_observation(_registry(), M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID),
        result=_listing(),
    )
    submissions = install_scripted_controller(monkeypatch, client, controller)

    assert asyncio.run(_door(client).year(_YEAR)) == _listing()
    assert submissions[0]["definition_id"] == M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID
    assert submissions[0]["payload"] == Modelo232RelatedPartyListRequest(profile_id=PROFILE_ID, ejercicio=_YEAR)
    assert submissions[0]["expected_session_id"] == SESSION_ID
    assert controller.result_reads == [(Modelo232RelatedPartyListProjection, 1, False)]


@pytest.mark.parametrize(
    ("result", "effect"),
    [
        # A listing of another ejercicio than the one asked.
        (_listing(_YEAR - 1), OperationEffect.NONE),
        # A read whose receipt says something changed.
        (_listing(), OperationEffect.UPDATED),
    ],
)
def test_the_listing_read_refuses_a_result_its_receipt_does_not_support(
    monkeypatch: pytest.MonkeyPatch, result: Modelo232RelatedPartyListProjection, effect: OperationEffect
) -> None:
    client = _DescribingClient()
    receipt = terminal_observation(_registry(), M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID, effect=effect)
    install_scripted_controller(monkeypatch, client, ScriptedController(observation=receipt, result=result))
    door = _door(client)

    with raises_unsupported_result(effect, receipt.projection.definition_contract):
        asyncio.run(door.year(_YEAR))


def test_the_read_and_the_forms_fail_closed_when_the_session_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DescribingClient()
    submissions = _install(monkeypatch, client, _listing())
    door = _door(client)
    client.session_id = _OTHER_SESSION_ID

    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(door.year(_YEAR))
    with pytest.raises(AccountSessionExpiredError):
        door.mutation_form(OperacionesVinculadasMutation.WITHDRAW_NONE, {})

    assert submissions == []


def test_the_read_checks_its_session_off_the_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DescribingClient()
    _install(monkeypatch, client, _listing())
    door = _door(client)
    client.session_read_threads.clear()

    asyncio.run(door.year(_YEAR))

    assert client.session_read_threads, "a door reads its session around its operation"
    assert threading.get_ident() not in client.session_read_threads
