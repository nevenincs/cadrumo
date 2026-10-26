"""Exact-session dispatch and receipt correlation for the installed register TUI doors."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.application.bienes_inversion.ports import BienesInversionIvaRegisterRepositoryFactory
from cadrumo.application.bienes_inversion.registered_contracts import (
    BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID,
)
from cadrumo.application.bienes_inversion.registered_operation import (
    build_bienes_inversion_declare_definition,
    build_bienes_inversion_declare_registration,
    build_bienes_inversion_list_definition,
    build_bienes_inversion_list_registration,
)
from cadrumo.application.bienes_inversion.registered_requests import (
    BienesInversionDeclareRequest,
    BienesInversionListRequest,
)
from cadrumo.application.bienes_inversion.registered_result_contracts import (
    BienesInversionDeclareProjection,
    BienesInversionListProjection,
    BienesInversionRefusalProjection,
)
from cadrumo.application.inventory.ports import InventoryServicePortsFactory
from cadrumo.application.inventory.registered_operation import (
    build_inventory_closing_authority_record_definition,
    build_inventory_closing_authority_record_registration,
    build_inventory_create_definition,
    build_inventory_create_registration,
    build_inventory_list_definition,
    build_inventory_list_registration,
    build_inventory_movement_add_definition,
    build_inventory_movement_add_registration,
    build_inventory_valuation_preview_definition,
    build_inventory_valuation_preview_registration,
)
from cadrumo.application.inventory.registered_projections import (
    InventoryClosingAuthorityOperationProjection,
    InventoryClosingAuthorityRecordProjection,
    InventoryCreateProjection,
    InventoryLedgerProjection,
    InventoryListProjection,
    InventoryMovementAddProjection,
    InventoryRefusalProjection,
    InventoryValuationOperationProjection,
    InventoryValuationPreviewProjection,
)
from cadrumo.application.inventory.registered_requests import (
    INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    INVENTORY_LIST_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
    INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
    InventoryAcquisitionCostRequest,
    InventoryClosingAuthorityRecordInput,
    InventoryClosingAuthorityRecordRequest,
    InventoryCreateRequest,
    InventoryListRequest,
    InventoryMovementAddRequest,
    InventoryValuationPreviewRequest,
)
from cadrumo.application.ledger.workspace import LedgerWorkspaceArea
from cadrumo.application.modelo.calculation_action_ports import CalculationActionPortsFactory
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1, OperationPublicEventPageV1
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.prorrata_register.operation_requests import (
    PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID,
    PRORRATA_LIST_OPERATION_DEFINITION_ID,
    PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID,
    ProrrataElectGeneralRequest,
    ProrrataListRequest,
    ProrrataSettleSectorRequest,
)
from cadrumo.application.prorrata_register.ports import ProrrataRegisterRepositoryFactory
from cadrumo.application.prorrata_register.projection_contracts import (
    ProrrataListProjection,
    ProrrataMutationProjection,
    ProrrataRefusalProjection,
)
from cadrumo.application.prorrata_register.registered_operations import (
    build_prorrata_declare_sector_definition,
    build_prorrata_elect_especial_definition,
    build_prorrata_elect_general_definition,
    build_prorrata_list_definition,
    build_prorrata_list_registration,
    build_prorrata_mutation_registration,
    build_prorrata_revoke_especial_definition,
    build_prorrata_seed_definition,
    build_prorrata_seed_sector_definition,
    build_prorrata_settle_sector_definition,
)
from cadrumo.core.i18n.render import tr
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.contribuyente.inventory.closing_authority_records import InventoryClosingAuthorityRecord
from cadrumo.domain.contribuyente.inventory.records import MovementKind, ValuationMethod
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.ledger.registers_capital_goods import CAPITAL_GOODS_TOOL_KEY, LedgerCapitalGoodsScreen
from cadrumo.entrypoints.tui.ledger.registers_inventory import INVENTORY_TOOL_KEY, LedgerInventoryScreen
from cadrumo.entrypoints.tui.ledger.registers_prorrata import PRORRATA_TOOL_KEY, LedgerProrrataRegisterScreen
from cadrumo.entrypoints.tui.ledger.tests.registers_fixtures import (
    synthetic_acquisition_cost,
    synthetic_capital_good,
    synthetic_closing_authority,
    synthetic_prorrata_entry,
)
from cadrumo.entrypoints.tui.ledger.tests.workspace_fixtures import ledger_controller, ledger_projection
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.operation_controller import OperationController

from ....frontend.tui.runtime_ledger_registers import (
    RuntimeCapitalGoodsTuiDoorV1,
    RuntimeInventoryTuiDoorV1,
    RuntimeProrrataRegisterTuiDoorV1,
    compose_registers_tools,
)
from .unsupported_result import raises_unsupported_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000d5")
_OTHER_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000d6")
_SESSION_ID = UUID("6bb00000-0000-4000-8000-0000000000d5")
_OPERATION_ID = "d" * 64
_NOW = datetime(2026, 10, 22, tzinfo=UTC)
_LABEL = "Fixture profile"


def _never[FactoryT](_kind: type[FactoryT]) -> FactoryT:
    """A repository factory the door tests never reach: no executor runs here."""
    return cast(FactoryT, cast(object, lambda **_kwargs: None))


def _registry() -> OperationRegistry:
    prorrata = _never(ProrrataRegisterRepositoryFactory)
    bienes = _never(BienesInversionIvaRegisterRepositoryFactory)
    inventory = _never(InventoryServicePortsFactory)
    prorrata_list = build_prorrata_list_definition(prorrata)
    mutations = (
        build_prorrata_declare_sector_definition(prorrata),
        build_prorrata_elect_general_definition(prorrata),
        build_prorrata_elect_especial_definition(prorrata),
        build_prorrata_revoke_especial_definition(prorrata),
        build_prorrata_seed_definition(prorrata, _never(CalculationActionPortsFactory)),
        build_prorrata_seed_sector_definition(prorrata),
        build_prorrata_settle_sector_definition(prorrata),
    )
    bienes_list = build_bienes_inversion_list_definition(bienes)
    bienes_declare = build_bienes_inversion_declare_definition(bienes)
    inventory_pairs = (
        (build_inventory_list_definition(inventory), build_inventory_list_registration),
        (build_inventory_create_definition(inventory), build_inventory_create_registration),
        (build_inventory_movement_add_definition(inventory), build_inventory_movement_add_registration),
        (build_inventory_valuation_preview_definition(inventory), build_inventory_valuation_preview_registration),
        (
            build_inventory_closing_authority_record_definition(inventory),
            build_inventory_closing_authority_record_registration,
        ),
    )
    definitions = (
        prorrata_list,
        *mutations,
        bienes_list,
        bienes_declare,
        *(definition for definition, _register in inventory_pairs),
    )
    registrations = (
        build_prorrata_list_registration(prorrata_list),
        *(build_prorrata_mutation_registration(definition) for definition in mutations),
        build_bienes_inversion_list_registration(bienes_list),
        build_bienes_inversion_declare_registration(bienes_declare),
        *(register(definition) for definition, register in inventory_pairs),
    )
    return OperationRegistry(
        definitions=definitions,
        public_registrations=tuple(sorted(registrations, key=lambda item: item.contract.definition_id)),
    )


_REGISTRY = _registry()


class _Client:
    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.profile_id = _PROFILE_ID
        self.session_id = _SESSION_ID
        self.session_read_threads: list[int] = []
        """The thread of each blocking session read: at composition, then around each operation."""


class _Controller:
    operation_id = _OPERATION_ID
    client: _Client

    def __init__(self, observation: OperationObservationSuccessV1, result: BaseModel | None) -> None:
        self.observation = observation
        self.result = result
        self.result_reads: list[tuple[type[BaseModel], bool]] = []
        self.detail_reads = 0

    async def start(self) -> str:
        return self.operation_id

    async def observe(self, after_cursor: int, *, page_limit: int) -> OperationObservationSuccessV1:
        assert after_cursor == 0
        assert page_limit == 1
        return self.observation

    async def read_settled_result(
        self,
        projection: OperationPublicProjectionV1,
        result_type: type[BaseModel],
        *,
        result_version: int,
        allow_refusal_detail: bool = False,
    ) -> BaseModel:
        assert projection.operation_id == self.operation_id
        assert result_version == 1
        self.result_reads.append((result_type, allow_refusal_detail))
        assert self.result is not None
        return self.result

    async def settled_error_detail(self, projection: OperationPublicProjectionV1) -> None:
        assert projection.operation_id == self.operation_id
        self.detail_reads += 1


def _observation(
    definition_id: str,
    *,
    condition: OperationTerminalCondition,
    effect: OperationEffect,
    refusal_ref: str | None,
) -> OperationObservationSuccessV1:
    contract = _REGISTRY.lookup_public_contract(definition_id)
    refused = condition is OperationTerminalCondition.REFUSED
    state = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE_ID)),
        revision=1,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=_REGISTRY.public_contract_set.contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=condition,
        effect=effect,
        phase_code=None,
        started_at=_NOW,
        updated_at=_NOW,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=False,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref=None if refused else "f" * 64,
        refusal_ref=refusal_ref,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    return OperationObservationSuccessV1(
        projection=state,
        event_page=OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=0,
            requested_cursor=0,
            status=OperationReplayStatus.CAUGHT_UP,
            events=(),
            next_cursor=0,
            restart_cursor=None,
        ),
    )


def _install(monkeypatch: pytest.MonkeyPatch, client: _Client, controller: _Controller) -> list[dict[str, object]]:
    from ....frontend.tui.operations import runtime_profile_session as bridge

    def read_session(_client: FrontendClient, *, profile_id: UUID, session_id: UUID, profile_label: str) -> object:
        assert profile_label == _LABEL
        client.session_read_threads.append(threading.get_ident())
        if client.profile_id != profile_id or client.session_id != session_id:
            raise AccountSessionExpiredError()
        return object()

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)
    submissions: list[dict[str, object]] = []

    async def submit(_type: type[OperationController], received: FrontendClient, **kwargs: object) -> _Controller:
        assert received is client
        submissions.append(kwargs)
        controller.client = client
        return controller

    monkeypatch.setattr(OperationController, "submit", classmethod(submit))
    return submissions


def _decimal(text: str) -> PublicDecimal:
    return PublicDecimal(decimal=text)


def _ledger(actividad_id: str = "act-01", year: int = 2026) -> InventoryLedgerProjection:
    return InventoryLedgerProjection(
        actividad_id=actividad_id,
        year=year,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=_decimal("0"),
        opening_layers=(),
        closing_authority_fingerprints=None,
        period_movements=(),
        schema_version="1",
        bucket_event_ids=("event-1",),
    )


type _Call = Callable[[Any], Coroutine[Any, Any, BaseModel]]


def _prorrata(client: _Client) -> RuntimeProrrataRegisterTuiDoorV1:
    return RuntimeProrrataRegisterTuiDoorV1(cast(FrontendClient, client), profile_label=_LABEL)


def _capital(client: _Client) -> RuntimeCapitalGoodsTuiDoorV1:
    return RuntimeCapitalGoodsTuiDoorV1(cast(FrontendClient, client), profile_label=_LABEL)


def _inventory(client: _Client) -> RuntimeInventoryTuiDoorV1:
    return RuntimeInventoryTuiDoorV1(cast(FrontendClient, client), profile_label=_LABEL)


_ELECT = ProrrataElectGeneralRequest(profile_id=_PROFILE_ID, ejercicio=2026, percentage=_decimal("82"))
_SETTLE = ProrrataSettleSectorRequest(
    profile_id=_PROFILE_ID,
    ejercicio=2026,
    sector_id="S1",
    con_derecho_volume=_decimal("7500"),
    sin_derecho_volume=_decimal("2500"),
)
_DECLARE = BienesInversionDeclareRequest(
    profile_id=_PROFILE_ID,
    identifier="BI-01",
    description="Synthetic good",
    acquisition_year=2024,
    acquisition_ledger_id="tx-BI-01",
    cuota_soportada=_decimal("2100.00"),
    prorrata_inicial_pct=_decimal("80"),
    kind="synthetic_kind",
)
_CREATE = InventoryCreateRequest(profile_id=_PROFILE_ID, actividad_id="act-01", year=2026, valuation_method="fifo")
_MOVEMENT = InventoryMovementAddRequest(
    profile_id=_PROFILE_ID,
    actividad_id="act-01",
    year=2026,
    movement_id="mv-01",
    movement_date=date(2026, 3, 1),
    kind=MovementKind.COUNT,
    quantity=_decimal("3"),
)
_PREVIEW = InventoryValuationPreviewRequest(profile_id=_PROFILE_ID, actividad_id="act-01", year=2026)
_CLOSING = InventoryClosingAuthorityRecordRequest(
    profile_id=_PROFILE_ID,
    actividad_id="act-01",
    year=2026,
    authority_record=InventoryClosingAuthorityRecordInput.from_domain(synthetic_closing_authority("act-01", 2026)),
)


def _preview(profile_id: UUID = _PROFILE_ID, year: int = 2026) -> InventoryValuationOperationProjection:
    return InventoryValuationOperationProjection(
        outcome="previewed",
        preview=InventoryValuationPreviewProjection(
            profile_id=profile_id,
            actividad_id="act-01",
            year=year,
            valuation_method=ValuationMethod.FIFO,
            derived_closing_value=_decimal("155.00"),
            cogs=_decimal("45.00"),
            bucket_event_ids=("event-2",),
        ),
    )


def _closing(*, changed: bool, profile_id: UUID = _PROFILE_ID) -> InventoryClosingAuthorityOperationProjection:
    return InventoryClosingAuthorityOperationProjection(
        outcome="recorded",
        record=InventoryClosingAuthorityRecordProjection(
            profile_id=profile_id,
            actividad_id="act-01",
            year=2026,
            authority_record_fingerprint="d" * 64,
            decision_fingerprint="e" * 64,
            physical_observation_fingerprint=None,
            prior_closing_link_fingerprint="f" * 64,
            changed=changed,
        ),
    )


def _movement_ledger(movement_id: str) -> InventoryLedgerProjection:
    from cadrumo.application.inventory.registered_projections import InventoryMovementProjection

    movement = InventoryMovementProjection(
        movement_id=movement_id,
        movement_date=date(2026, 3, 1),
        kind=MovementKind.COUNT,
        sku="default",
        quantity=_decimal("3"),
        unit_cost=None,
        taxable_base=None,
        iva_rate=_decimal("0"),
        iva_amount=None,
        deductible_iva_ratio=_decimal("1"),
        acquisition_cost=None,
        schema_version="1",
    )
    return _ledger().model_copy(update={"period_movements": (movement,)})


@dataclass(frozen=True, slots=True)
class _Case:
    """One door call, the receipt that truthfully settles it, and the result it must return."""

    name: str
    definition_id: str
    door: Callable[[_Client], object]
    call: _Call
    result: BaseModel
    effect: OperationEffect
    refusal_detail: bool


_SUCCESSES: tuple[_Case, ...] = (
    _Case(
        "prorrata list",
        PRORRATA_LIST_OPERATION_DEFINITION_ID,
        _prorrata,
        lambda door: door.read_register(ProrrataListRequest(profile_id=_PROFILE_ID)),
        ProrrataListProjection(profile_id=_PROFILE_ID, entries=(synthetic_prorrata_entry(2025),), sectors=(), count=1),
        OperationEffect.NONE,
        False,
    ),
    _Case(
        "prorrata election",
        PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID,
        _prorrata,
        lambda door: door.apply(_ELECT),
        ProrrataMutationProjection(
            operation_id="elect_general",
            profile_id=_PROFILE_ID,
            outcome="success",
            entry=synthetic_prorrata_entry(2026, provisional="82"),
            count=1,
        ),
        OperationEffect.UPDATED,
        True,
    ),
    _Case(
        "prorrata settlement",
        PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID,
        _prorrata,
        lambda door: door.apply(_SETTLE),
        ProrrataMutationProjection(
            operation_id="settle_sector",
            profile_id=_PROFILE_ID,
            outcome="success",
            entry=synthetic_prorrata_entry(2026, sector_id="S1", definitive="75"),
            count=1,
        ),
        OperationEffect.UPDATED,
        True,
    ),
    _Case(
        "capital goods list",
        BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID,
        _capital,
        lambda door: door.read_register(BienesInversionListRequest(profile_id=_PROFILE_ID)),
        BienesInversionListProjection(profile_id=_PROFILE_ID, rows=(synthetic_capital_good("BI-01"),)),
        OperationEffect.NONE,
        False,
    ),
    _Case(
        "capital goods declaration",
        BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
        _capital,
        lambda door: door.declare(_DECLARE),
        BienesInversionDeclareProjection(
            outcome="declared", profile_id=_PROFILE_ID, record=synthetic_capital_good("BI-01"), count=1
        ),
        OperationEffect.UPDATED,
        True,
    ),
    _Case(
        "inventory list",
        INVENTORY_LIST_OPERATION_DEFINITION_ID,
        _inventory,
        lambda door: door.read_register(InventoryListRequest(profile_id=_PROFILE_ID)),
        InventoryListProjection(profile_id=_PROFILE_ID, rows=()),
        OperationEffect.NONE,
        False,
    ),
    _Case(
        "inventory create",
        INVENTORY_CREATE_OPERATION_DEFINITION_ID,
        _inventory,
        lambda door: door.create(_CREATE),
        InventoryCreateProjection(
            outcome="created", profile_id=_PROFILE_ID, ledger=_ledger(), bucket_event_ids=("event-1",)
        ),
        OperationEffect.UPDATED,
        True,
    ),
    _Case(
        "inventory movement",
        INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
        _inventory,
        lambda door: door.add_movement(_MOVEMENT),
        InventoryMovementAddProjection(
            outcome="added", profile_id=_PROFILE_ID, ledger=_movement_ledger("mv-01"), bucket_event_ids=("event-1",)
        ),
        OperationEffect.UPDATED,
        True,
    ),
    _Case(
        "inventory valuation preview",
        INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
        _inventory,
        lambda door: door.preview_valuation(_PREVIEW),
        _preview(),
        OperationEffect.UPDATED,
        True,
    ),
    _Case(
        "inventory closing authority",
        INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
        _inventory,
        lambda door: door.record_closing_authority(_CLOSING),
        _closing(changed=True),
        OperationEffect.UPDATED,
        True,
    ),
    _Case(
        "inventory closing authority replay",
        INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
        _inventory,
        lambda door: door.record_closing_authority(_CLOSING),
        _closing(changed=False),
        OperationEffect.NONE,
        True,
    ),
)


def _run(
    monkeypatch: pytest.MonkeyPatch, case: _Case, *, result: BaseModel, **receipt: Any
) -> tuple[BaseModel, _Controller, list[dict[str, object]]]:
    client = _Client()
    settled = {
        "condition": OperationTerminalCondition.SUCCEEDED,
        "effect": case.effect,
        "refusal_ref": None,
        **receipt,
    }
    controller = _Controller(_observation(case.definition_id, **settled), result)
    submissions = _install(monkeypatch, client, controller)
    return asyncio.run(case.call(case.door(client))), controller, submissions


@pytest.mark.parametrize("case", _SUCCESSES, ids=[case.name for case in _SUCCESSES])
def test_each_door_submits_to_its_own_operation_and_returns_the_receipt_supported_result(
    monkeypatch: pytest.MonkeyPatch, case: _Case
) -> None:
    returned, controller, submissions = _run(monkeypatch, case, result=case.result)

    assert returned == case.result
    assert submissions[0]["definition_id"] == case.definition_id
    assert submissions[0]["expected_session_id"] == _SESSION_ID
    payload = submissions[0]["payload"]
    assert isinstance(payload, BaseModel)
    assert payload.model_dump()["profile_id"] == _PROFILE_ID
    assert controller.result_reads == [(type(case.result), case.refusal_detail)]


def _wrong_effect(effect: OperationEffect) -> OperationEffect:
    return OperationEffect.NONE if effect is OperationEffect.UPDATED else OperationEffect.UPDATED


@pytest.mark.parametrize("case", _SUCCESSES, ids=[case.name for case in _SUCCESSES])
def test_each_door_refuses_a_result_whose_receipt_reports_another_effect(
    monkeypatch: pytest.MonkeyPatch, case: _Case
) -> None:
    effect = _wrong_effect(case.effect)
    with raises_unsupported_result(effect, _REGISTRY.lookup_public_contract(case.definition_id)):
        _run(monkeypatch, case, result=case.result, effect=effect)


def _for_other_profile(result: BaseModel) -> BaseModel:
    if isinstance(result, InventoryValuationOperationProjection):
        return _preview(profile_id=_OTHER_PROFILE_ID)
    if isinstance(result, InventoryClosingAuthorityOperationProjection):
        record = result.record
        assert record is not None
        return _closing(changed=record.changed, profile_id=_OTHER_PROFILE_ID)
    return result.model_copy(update={"profile_id": _OTHER_PROFILE_ID})


@pytest.mark.parametrize("case", _SUCCESSES, ids=[case.name for case in _SUCCESSES])
def test_each_door_refuses_a_result_for_another_profile(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    with raises_unsupported_result(case.effect, _REGISTRY.lookup_public_contract(case.definition_id)):
        _run(monkeypatch, case, result=_for_other_profile(case.result))


@pytest.mark.parametrize("case", _SUCCESSES, ids=[case.name for case in _SUCCESSES])
def test_each_door_fails_closed_when_its_session_has_lapsed(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    client = _Client()
    controller = _Controller(
        _observation(
            case.definition_id, condition=OperationTerminalCondition.SUCCEEDED, effect=case.effect, refusal_ref=None
        ),
        case.result,
    )
    submissions = _install(monkeypatch, client, controller)
    door = case.door(client)
    client.session_id = UUID("7cc00000-0000-4000-8000-0000000000d5")

    with pytest.raises(AccountSessionExpiredError):
        asyncio.run(case.call(door))

    assert submissions == []


@pytest.mark.parametrize("case", _SUCCESSES, ids=[case.name for case in _SUCCESSES])
def test_each_door_reads_its_session_off_the_event_loop_thread(monkeypatch: pytest.MonkeyPatch, case: _Case) -> None:
    """The session read is a blocking IPC exchange; a door awaited on the loop never runs it there."""
    client = _Client()
    controller = _Controller(
        _observation(
            case.definition_id, condition=OperationTerminalCondition.SUCCEEDED, effect=case.effect, refusal_ref=None
        ),
        case.result,
    )
    _install(monkeypatch, client, controller)
    door = case.door(client)
    client.session_read_threads.clear()

    asyncio.run(case.call(door))

    assert client.session_read_threads, "a door reads its session around its operation"
    assert threading.get_ident() not in client.session_read_threads


_REFUSALS: tuple[tuple[_Case, BaseModel, str], ...] = (
    (
        _SUCCESSES[1],
        ProrrataMutationProjection(
            operation_id="elect_general",
            profile_id=_PROFILE_ID,
            outcome="refused",
            refusal=ProrrataRefusalProjection(
                code="REFUSED_PRORRATA_ELECTION", reason="provenance_required", detail="synthetic"
            ),
        ),
        "REFUSED_PRORRATA_ELECTION",
    ),
    (
        _SUCCESSES[4],
        BienesInversionDeclareProjection(
            outcome="refused",
            profile_id=_PROFILE_ID,
            refusal=BienesInversionRefusalProjection(
                code="REFUSED_PROFILE_BIENES_INVERSION_VALIDATION", reason="duplicate_identifier", identifier="BI-01"
            ),
        ),
        "REFUSED_PROFILE_BIENES_INVERSION_VALIDATION",
    ),
    (
        _SUCCESSES[7],
        InventoryMovementAddProjection(
            outcome="refused",
            profile_id=_PROFILE_ID,
            refusal=InventoryRefusalProjection(
                code="REFUSED_INVENTORY_ACTIVIDAD_NOT_FOUND", reason="activity_not_found", actividad_id="act-01"
            ),
        ),
        "REFUSED_INVENTORY_ACTIVIDAD_NOT_FOUND",
    ),
)


@pytest.mark.parametrize(("case", "refused", "code"), _REFUSALS, ids=[case.name for case, _r, _c in _REFUSALS])
def test_a_registered_refusal_is_returned_with_its_own_refused_receipt(
    monkeypatch: pytest.MonkeyPatch, case: _Case, refused: BaseModel, code: str
) -> None:
    returned, controller, _submissions = _run(
        monkeypatch,
        case,
        result=refused,
        condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        refusal_ref=code,
    )
    assert returned == refused
    assert controller.result_reads == [(type(refused), True)]


@pytest.mark.parametrize(("case", "refused", "code"), _REFUSALS, ids=[case.name for case, _r, _c in _REFUSALS])
def test_a_refusal_receipt_never_settles_a_successful_result_nor_a_refusal_settle_a_success(
    monkeypatch: pytest.MonkeyPatch, case: _Case, refused: BaseModel, code: str
) -> None:
    with pytest.raises(RefusalError) as success_under_refusal:
        _run(
            monkeypatch,
            case,
            result=case.result,
            condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
            refusal_ref=code,
        )
    assert success_under_refusal.value.reason is RefusalCode.INVALID_FRAME
    with raises_unsupported_result(case.effect, _REGISTRY.lookup_public_contract(case.definition_id)):
        _run(monkeypatch, case, result=refused)


def test_a_refused_register_read_is_raised_rather_than_read(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    controller = _Controller(
        _observation(
            PRORRATA_LIST_OPERATION_DEFINITION_ID,
            condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
            refusal_ref="REFUSED_PROFILE_PRORRATA_REGISTER_VALIDATION",
        ),
        None,
    )
    _install(monkeypatch, client, controller)

    with pytest.raises(FrontendRefusedError) as raised:
        asyncio.run(_prorrata(client).read_register(ProrrataListRequest(profile_id=_PROFILE_ID)))

    assert raised.value.reason == "REFUSED_PROFILE_PRORRATA_REGISTER_VALIDATION"
    assert controller.detail_reads == 1
    assert controller.result_reads == []


@pytest.mark.parametrize(
    ("case", "result"),
    [
        (
            _SUCCESSES[2],
            ProrrataMutationProjection(
                operation_id="settle_sector",
                profile_id=_PROFILE_ID,
                outcome="success",
                entry=synthetic_prorrata_entry(2026, sector_id="S2", definitive="75"),
                count=1,
            ),
        ),
        (
            _SUCCESSES[1],
            ProrrataMutationProjection(
                operation_id="elect_especial",
                profile_id=_PROFILE_ID,
                outcome="success",
                entry=synthetic_prorrata_entry(2026),
                count=1,
            ),
        ),
        (
            _SUCCESSES[4],
            BienesInversionDeclareProjection(
                outcome="declared", profile_id=_PROFILE_ID, record=synthetic_capital_good("BI-99"), count=1
            ),
        ),
        (
            _SUCCESSES[7],
            InventoryMovementAddProjection(
                outcome="added", profile_id=_PROFILE_ID, ledger=_movement_ledger("mv-99"), bucket_event_ids=("e",)
            ),
        ),
        (_SUCCESSES[8], _preview(year=2025)),
    ],
    ids=["other sector", "other operation", "other good", "other movement", "other year"],
)
def test_a_result_naming_another_record_than_its_request_is_refused(
    monkeypatch: pytest.MonkeyPatch, case: _Case, result: BaseModel
) -> None:
    with raises_unsupported_result(case.effect, _REGISTRY.lookup_public_contract(case.definition_id)):
        _run(monkeypatch, case, result=result)


def test_typed_source_files_are_read_and_validated_as_the_command_line_reads_them(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _Client()
    _install(
        monkeypatch,
        client,
        _Controller(
            _observation(
                INVENTORY_LIST_OPERATION_DEFINITION_ID,
                condition=OperationTerminalCondition.SUCCEEDED,
                effect=OperationEffect.NONE,
                refusal_ref=None,
            ),
            None,
        ),
    )
    door = _inventory(client)
    authority = tmp_path / "authority.json"
    authority.write_text(synthetic_closing_authority("act-01", 2026).model_dump_json(), encoding="utf-8")
    purchase = tmp_path / "purchase.json"
    purchase.write_text(synthetic_acquisition_cost().model_dump_json(), encoding="utf-8")
    broken = tmp_path / "broken.json"
    broken.write_text('{"decision": {}}', encoding="utf-8")

    assert asyncio.run(door.read_closing_authority(str(authority))) == InventoryClosingAuthorityRecordInput.from_domain(
        synthetic_closing_authority("act-01", 2026)
    )
    assert asyncio.run(door.read_acquisition_cost(str(purchase))) == InventoryAcquisitionCostRequest.from_domain(
        synthetic_acquisition_cost()
    )
    with pytest.raises(ValidationError) as invalid:
        InventoryClosingAuthorityRecord.model_validate_json(broken.read_text(encoding="utf-8"))
    with pytest.raises(ValueError) as refused:
        asyncio.run(door.read_closing_authority(str(broken)))
    assert str(refused.value) == tr(
        "tui.ledger.registers.inventory.source_invalid", path=str(broken), count=invalid.value.error_count()
    )
    absent = str(tmp_path / "absent.json")
    with pytest.raises(ValueError) as unreadable:
        asyncio.run(door.read_acquisition_cost(absent))
    assert str(unreadable.value) == tr("tui.ledger.registers.inventory.source_unreadable", path=absent)


def test_typed_source_files_are_read_off_the_event_loop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from ....frontend.tui import runtime_ledger_registers as module

    client = _Client()
    _install(
        monkeypatch,
        client,
        _Controller(
            _observation(
                INVENTORY_LIST_OPERATION_DEFINITION_ID,
                condition=OperationTerminalCondition.SUCCEEDED,
                effect=OperationEffect.NONE,
                refusal_ref=None,
            ),
            None,
        ),
    )
    on_loop: list[bool] = []
    real = module._read_typed_file

    def recording(path: str, model: type[BaseModel]) -> BaseModel:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            on_loop.append(False)
        else:
            on_loop.append(True)
        return real(path, model)

    monkeypatch.setattr(module, "_read_typed_file", recording)
    purchase = tmp_path / "purchase.json"
    purchase.write_text(synthetic_acquisition_cost().model_dump_json(), encoding="utf-8")
    asyncio.run(_inventory(client).read_acquisition_cost(str(purchase)))
    assert on_loop == [False]


def test_the_composer_offers_the_three_registers_on_the_overview(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    _install(
        monkeypatch,
        client,
        _Controller(
            _observation(
                PRORRATA_LIST_OPERATION_DEFINITION_ID,
                condition=OperationTerminalCondition.SUCCEEDED,
                effect=OperationEffect.NONE,
                refusal_ref=None,
            ),
            None,
        ),
    )

    tools = compose_registers_tools(cast(FrontendClient, client), _LABEL)

    assert [tool.key for tool in tools] == [PRORRATA_TOOL_KEY, CAPITAL_GOODS_TOOL_KEY, INVENTORY_TOOL_KEY]
    assert {tool.area for tool in tools} == {LedgerWorkspaceArea.OVERVIEW}
    controller = ledger_controller(ledger_projection())
    screens = [tool.build(controller) for tool in tools]
    assert [type(screen) for screen in screens] == [
        LedgerProrrataRegisterScreen,
        LedgerCapitalGoodsScreen,
        LedgerInventoryScreen,
    ]
    doors = [
        screen.door
        for screen in screens
        if isinstance(screen, LedgerProrrataRegisterScreen | LedgerCapitalGoodsScreen | LedgerInventoryScreen)
    ]
    assert [door.profile_id for door in doors] == [_PROFILE_ID] * 3


def test_the_composer_refuses_a_lapsed_session(monkeypatch: pytest.MonkeyPatch) -> None:
    from ....frontend.tui.operations import runtime_profile_session as bridge

    def lapsed(_client: FrontendClient, *, profile_id: UUID, session_id: UUID, profile_label: str) -> object:
        raise AccountSessionExpiredError()

    monkeypatch.setattr(bridge, "read_runtime_account_session", lapsed)
    with pytest.raises(AccountSessionExpiredError):
        compose_registers_tools(cast(FrontendClient, _Client()), _LABEL)
