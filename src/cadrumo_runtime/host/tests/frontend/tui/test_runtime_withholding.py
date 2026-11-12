"""Admission, exact-session dispatch and receipt correlation for the installed withholding TUI door.

The runtime's descriptions are served from a real registry of the six
withholding operations, so admission is judged against the contracts and
request schemas the operations really publish.
"""

from __future__ import annotations

import asyncio
import threading
from functools import lru_cache
from typing import cast
from uuid import UUID

import pytest

from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1, OperationRegistry
from cadrumo.application.retencion_soportada_absence.contracts import (
    RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID,
)
from cadrumo.application.retencion_soportada_absence.ports import RetencionSoportadaAbsencePortsFactory
from cadrumo.application.retencion_soportada_absence.registered_operation import (
    build_retencion_soportada_absence_attest_definition,
    build_retencion_soportada_absence_list_definition,
    build_retencion_soportada_absence_list_registration,
    build_retencion_soportada_absence_registration,
    build_retencion_soportada_absence_withdraw_definition,
)
from cadrumo.application.retencion_soportada_absence.requests import RetencionSoportadaAbsenceListRequest
from cadrumo.application.retencion_soportada_absence.results import RetencionSoportadaAbsenceListProjection
from cadrumo.application.retencion_soportada_certificado.contracts import (
    RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID,
)
from cadrumo.application.retencion_soportada_certificado.ports import RetencionSoportadaCertificadoPortsFactory
from cadrumo.application.retencion_soportada_certificado.registered_operation import (
    build_retencion_soportada_list_definition,
    build_retencion_soportada_list_registration,
    build_retencion_soportada_mutation_registration,
    build_retencion_soportada_record_definition,
    build_retencion_soportada_remove_definition,
)
from cadrumo.application.retencion_soportada_certificado.requests import RetencionSoportadaListRequest
from cadrumo.application.retencion_soportada_certificado.results import RetencionSoportadaListProjection
from cadrumo.core.operations import OperationEffect, OperationFrontendProjection
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.operations.request_form import request_fields
from cadrumo.entrypoints.tui.withholding.screen import WithholdingMutation
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....frontend.tui.runtime_withholding import (
    WITHHOLDING_OPERATION_SHAPES,
    RuntimeWithholdingTuiDoorV1,
    compose_runtime_withholding_door,
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
    certificates = cast(RetencionSoportadaCertificadoPortsFactory, cast(object, lambda **_kwargs: None))
    absences = cast(RetencionSoportadaAbsencePortsFactory, cast(object, lambda **_kwargs: None))
    attest = build_retencion_soportada_absence_attest_definition(absences)
    records = build_retencion_soportada_list_definition(certificates)
    statements = build_retencion_soportada_absence_list_definition(absences)
    record = build_retencion_soportada_record_definition(certificates)
    remove = build_retencion_soportada_remove_definition(certificates)
    withdraw = build_retencion_soportada_absence_withdraw_definition(absences)
    # The registry holds its definitions in identity order.
    return OperationRegistry(
        definitions=(attest, records, statements, record, remove, withdraw),
        public_registrations=(
            build_retencion_soportada_absence_registration(attest),
            build_retencion_soportada_list_registration(records),
            build_retencion_soportada_absence_list_registration(statements),
            build_retencion_soportada_mutation_registration(record),
            build_retencion_soportada_mutation_registration(remove),
            build_retencion_soportada_absence_registration(withdraw),
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
        served = WithholdingMutation.REMOVE.value if definition_id == self.misdescribed else definition_id
        return _registry().describe_public_definition(served)


def _compose(client: _DescribingClient) -> RuntimeWithholdingTuiDoorV1 | None:
    return compose_runtime_withholding_door(cast(FrontendClient, client), profile_label="Fixture profile")


def _door(client: _DescribingClient) -> RuntimeWithholdingTuiDoorV1:
    door = _compose(client)
    assert door is not None
    return door


def _records(ejercicio: int = _YEAR) -> RetencionSoportadaListProjection:
    return RetencionSoportadaListProjection(profile_id=PROFILE_ID, ejercicio=ejercicio, rows=())


def test_the_door_is_admitted_only_with_every_operation_described_and_builds_forms_from_the_served_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _DescribingClient()
    install_scripted_controller(
        monkeypatch,
        client,
        ScriptedController(
            observation=terminal_observation(_registry(), RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID),
            result=None,
        ),
    )
    door = _door(client)

    assert door.profile_id == PROFILE_ID
    assert client.described == list(WITHHOLDING_OPERATION_SHAPES)
    form = door.mutation_form(WithholdingMutation.RECORD, {"ejercicio": _YEAR})
    served = _registry().describe_public_definition(WithholdingMutation.RECORD.value)
    assert form.entry.contract == served.contract
    assert form.entry.input_json_schema == served.request_json_schema
    names = {field.name for field in request_fields(form.entry.input_json_schema, profile_id=PROFILE_ID)}
    assert {"reducciones_aplicables", "gastos_deducibles"} <= names


@pytest.mark.parametrize("definition_id", list(WITHHOLDING_OPERATION_SHAPES))
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
    [item for item in WITHHOLDING_OPERATION_SHAPES if item != WithholdingMutation.REMOVE.value],
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


def test_the_records_read_submits_the_exact_request_and_returns_its_result(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DescribingClient()
    controller = ScriptedController(
        observation=terminal_observation(_registry(), RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID),
        result=_records(),
    )
    submissions = install_scripted_controller(monkeypatch, client, controller)

    assert asyncio.run(_door(client).records(_YEAR)) == _records()
    assert submissions[0]["definition_id"] == RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID
    assert submissions[0]["payload"] == RetencionSoportadaListRequest(profile_id=PROFILE_ID, ejercicio=_YEAR)
    assert submissions[0]["expected_session_id"] == SESSION_ID
    assert controller.result_reads == [(RetencionSoportadaListProjection, 1, False)]


def test_the_absences_read_submits_the_exact_request_and_returns_its_result(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DescribingClient()
    result = RetencionSoportadaAbsenceListProjection(profile_id=PROFILE_ID, ejercicio=_YEAR, attestations=())
    controller = ScriptedController(
        observation=terminal_observation(_registry(), RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID),
        result=result,
    )
    submissions = install_scripted_controller(monkeypatch, client, controller)

    assert asyncio.run(_door(client).absences(_YEAR)) == result
    assert submissions[0]["payload"] == RetencionSoportadaAbsenceListRequest(profile_id=PROFILE_ID, ejercicio=_YEAR)
    assert controller.result_reads == [(RetencionSoportadaAbsenceListProjection, 1, False)]


@pytest.mark.parametrize(
    ("result", "effect"),
    [
        # A list of another ejercicio than the one asked.
        (_records(_YEAR - 1), OperationEffect.NONE),
        # A read whose receipt says something changed.
        (_records(), OperationEffect.UPDATED),
    ],
)
def test_the_records_read_refuses_a_result_its_receipt_does_not_support(
    monkeypatch: pytest.MonkeyPatch, result: RetencionSoportadaListProjection, effect: OperationEffect
) -> None:
    client = _DescribingClient()
    receipt = terminal_observation(_registry(), RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID, effect=effect)
    install_scripted_controller(monkeypatch, client, ScriptedController(observation=receipt, result=result))
    door = _door(client)

    with raises_unsupported_result(effect, receipt.projection.definition_contract):
        asyncio.run(door.records(_YEAR))


def test_the_reads_fail_closed_when_the_session_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DescribingClient()
    submissions = install_scripted_controller(
        monkeypatch,
        client,
        ScriptedController(
            observation=terminal_observation(_registry(), RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID),
            result=_records(),
        ),
    )
    door = _door(client)
    client.session_id = _OTHER_SESSION_ID

    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(door.records(_YEAR))
    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(door.absences(_YEAR))

    assert submissions == []


def test_a_form_is_not_opened_once_the_session_changed(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DescribingClient()
    install_scripted_controller(
        monkeypatch,
        client,
        ScriptedController(
            observation=terminal_observation(_registry(), RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID),
            result=None,
        ),
    )
    door = _door(client)
    client.session_id = _OTHER_SESSION_ID

    with pytest.raises(AccountSessionExpiredError):
        door.mutation_form(WithholdingMutation.REMOVE, {})


def test_the_reads_check_their_session_off_the_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _DescribingClient()
    install_scripted_controller(
        monkeypatch,
        client,
        ScriptedController(
            observation=terminal_observation(_registry(), RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID),
            result=_records(),
        ),
    )
    door = _door(client)
    client.session_read_threads.clear()

    asyncio.run(door.records(_YEAR))

    assert client.session_read_threads, "a door reads its session around its operation"
    assert threading.get_ident() not in client.session_read_threads
