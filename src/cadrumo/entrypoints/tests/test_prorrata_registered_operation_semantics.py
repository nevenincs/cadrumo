"""Focused registered-executor checks for prorrata seed lifecycle semantics."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Literal, cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from ...adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ...adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ...adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ...application.modelo.calculation_action_ports import CalculationActionPortsFactory
from ...application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...application.operations.owner import OperationExecutorContext
from ...application.operations.public_scalar import PublicDecimal
from ...application.operations.refusal_evidence import OperationRefusalEvidence
from ...application.prorrata_register.executor import ProrrataOperationExecutor
from ...application.prorrata_register.operation_requests import (
    PRORRATA_SEED_OPERATION_DEFINITION_ID,
    PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID,
    ProrrataSettleSectorRequest,
)
from ...application.prorrata_register.projection_contracts import ProrrataMutationProjection
from ...application.prorrata_register.result_contracts import ProrrataOperationExecutionResult
from ...application.prorrata_register.result_projections import project_prorrata_mutation_result
from ...application.prorrata_register.service import ProrrataRegisterService
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.prorrata_register_catalogue import prorrata_sector_letters
from ...domain.prorrata_register.register import SectorDefinition
from .prorrata_operation_test_support import (
    ProrrataWholeSeedRefusalCase,
    prepare_prorrata_operation_conformance_case,
    prepare_prorrata_whole_seed_refusal_case,
    read_prorrata_operation_conformance_register,
)

_PROFILE_ID = UUID("517e31f8-91b9-47b6-9ac1-3e12cc773c4f")
_runtime_profile = bucket_scoped_runtime_profile_fixture(str(_PROFILE_ID))

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


@dataclass
class _Events:
    effects: list[OperationEffect] = field(default_factory=list)

    async def phase(self, _phase_code: str) -> None:
        return None

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Cancellation:
    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        yield


@dataclass
class _Operands:
    value: BaseModel | None = None

    async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
        del written_at
        self.value = operand
        return "a" * 64


@dataclass
class _Context:
    identity: OperationIdentity
    authority_operation: PinnedAuthorityOperation
    cancellation: _Cancellation
    events: _Events
    operands: _Operands


class _SeedPortsFactory:
    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> object:
        del operation
        return SimpleNamespace(observation_repository=CalculationObservationRepository(bucket_id=bucket_id))


def _repository_factory(*, bucket_id: str) -> ProrrataRegisterRepository:
    return ProrrataRegisterRepository(bucket_id=bucket_id)


def _run_executor(
    payload: BaseModel,
    *,
    definition_id: str,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    operation_number: int,
) -> tuple[str | OperationRefusalEvidence, ProrrataOperationExecutionResult, _Events, OperationIdentity]:
    import cadrumo.application.prorrata_register.executor as executor_module

    monkeypatch.setattr(executor_module, "require_active_bucket_id", lambda: str(_PROFILE_ID))
    subject_ref = profile_operation_subject(str(_PROFILE_ID))
    identity = OperationIdentity(
        operation_id=f"{operation_number:064x}",
        definition_id=definition_id,
        subject_ref=subject_ref,
    )
    request = OperationRequest[BaseModel](
        definition_id=definition_id,
        subject_ref=subject_ref,
        payload=payload,
    )
    events = _Events()
    operands = _Operands()
    context = _Context(
        identity=identity,
        authority_operation=authority_operation,
        cancellation=_Cancellation(),
        events=events,
        operands=operands,
    )
    executor = ProrrataOperationExecutor(
        _repository_factory,
        definition_id=definition_id,
        calculation_action_ports_factory=(
            cast(CalculationActionPortsFactory, _SeedPortsFactory())
            if definition_id == PRORRATA_SEED_OPERATION_DEFINITION_ID
            else None
        ),
    )
    result = asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))
    if not isinstance(operands.value, ProrrataOperationExecutionResult):
        raise AssertionError("prorrata executor did not persist its typed private result")
    if not isinstance(result, (str, OperationRefusalEvidence)):
        raise AssertionError("prorrata executor returned an unsettled result")
    return result, operands.value, events, identity


def _receipt(
    identity: OperationIdentity,
    *,
    refused: bool,
    refusal_code: str | None = None,
) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=identity,
        revision=1,
        condition=OperationTerminalCondition.REFUSED if refused else OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE if refused else OperationEffect.UPDATED,
        settled_at=datetime.now(UTC),
        result_ref=None if refused else "result-reference",
        refusal_ref=refusal_code if refused else None,
        refusal_detail_ref="b" * 64 if refused else None,
    )


def _seed_refusal_case(
    authority_operation: PinnedAuthorityOperation,
    *,
    refusal_reason: Literal["regulated_override_standing", "seed_existing_blocked"],
) -> ProrrataWholeSeedRefusalCase:
    observations = CalculationObservationRepository(bucket_id=str(_PROFILE_ID))
    return prepare_prorrata_whole_seed_refusal_case(
        _PROFILE_ID,
        repository_factory=_repository_factory,
        operation=authority_operation,
        observation_repository=observations,
        refusal_reason=refusal_reason,
    )


def _assert_refusal_projection(
    execution: ProrrataOperationExecutionResult,
    identity: OperationIdentity,
) -> ProrrataMutationProjection:
    if execution.refusal is None:
        raise AssertionError("expected refusal result lacks typed refusal detail")
    return project_prorrata_mutation_result(
        execution,
        _receipt(identity, refused=True, refusal_code=execution.refusal.code),
    )


def test_standing_override_refusal_preserves_exact_provenance_and_writes_nothing(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _seed_refusal_case(authority_operation, refusal_reason="regulated_override_standing")
    before = read_prorrata_operation_conformance_register(
        _PROFILE_ID,
        repository_factory=_repository_factory,
        operation=authority_operation,
    )

    returned, execution, events, identity = _run_executor(
        case.request,
        definition_id=PRORRATA_SEED_OPERATION_DEFINITION_ID,
        authority_operation=authority_operation,
        monkeypatch=monkeypatch,
        operation_number=1,
    )

    projection = _assert_refusal_projection(execution, identity)
    assert isinstance(returned, OperationRefusalEvidence)
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert projection.refusal is not None
    assert projection.refusal.reason == "regulated_override_standing"
    assert projection.refusal.existing_provenance == case.expected_provenance
    assert projection.refusal.findings == case.expected_findings
    after = read_prorrata_operation_conformance_register(
        _PROFILE_ID,
        repository_factory=_repository_factory,
        operation=authority_operation,
    )
    assert after == before == case.expected_register


def test_carried_observation_contradiction_refuses_without_overwriting_register(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _seed_refusal_case(authority_operation, refusal_reason="seed_existing_blocked")
    before = read_prorrata_operation_conformance_register(
        _PROFILE_ID,
        repository_factory=_repository_factory,
        operation=authority_operation,
    )

    returned, execution, events, identity = _run_executor(
        case.request,
        definition_id=PRORRATA_SEED_OPERATION_DEFINITION_ID,
        authority_operation=authority_operation,
        monkeypatch=monkeypatch,
        operation_number=2,
    )

    projection = _assert_refusal_projection(execution, identity)
    assert isinstance(returned, OperationRefusalEvidence)
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert projection.refusal is not None
    assert projection.refusal.reason == "seed_existing_blocked"
    assert projection.refusal.findings == case.expected_findings
    assert any(finding.blocking for finding in projection.refusal.findings)
    after = read_prorrata_operation_conformance_register(
        _PROFILE_ID,
        repository_factory=_repository_factory,
        operation=authority_operation,
    )
    assert after == before == case.expected_register


def test_repeating_a_whole_seed_keeps_one_canonical_entry(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = prepare_prorrata_operation_conformance_case(
        PRORRATA_SEED_OPERATION_DEFINITION_ID,
        _PROFILE_ID,
        repository_factory=_repository_factory,
        operation=authority_operation,
        observation_repository=CalculationObservationRepository(bucket_id=str(_PROFILE_ID)),
    )

    first_return, first_execution, first_events, first_identity = _run_executor(
        case.request,
        definition_id=PRORRATA_SEED_OPERATION_DEFINITION_ID,
        authority_operation=authority_operation,
        monkeypatch=monkeypatch,
        operation_number=3,
    )
    first_projection = project_prorrata_mutation_result(first_execution, _receipt(first_identity, refused=False))
    after_first = read_prorrata_operation_conformance_register(
        _PROFILE_ID,
        repository_factory=_repository_factory,
        operation=authority_operation,
    )
    second_return, second_execution, second_events, second_identity = _run_executor(
        case.request,
        definition_id=PRORRATA_SEED_OPERATION_DEFINITION_ID,
        authority_operation=authority_operation,
        monkeypatch=monkeypatch,
        operation_number=4,
    )
    second_projection = project_prorrata_mutation_result(second_execution, _receipt(second_identity, refused=False))
    after_second = read_prorrata_operation_conformance_register(
        _PROFILE_ID,
        repository_factory=_repository_factory,
        operation=authority_operation,
    )

    assert isinstance(first_return, str) and isinstance(second_return, str)
    assert first_events.effects == second_events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert first_projection.entry == second_projection.entry
    assert first_projection.count == second_projection.count == 1
    assert after_first == after_second
    assert len(after_second.entries) == 1
    assert after_second.entry_for(2026) == case.expected_entry


def test_settle_sector_without_a_current_entry_refuses_without_writing(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sector_id = "missing-settlement-entry"
    with validating_governed_facts(authority_operation):
        letter = prorrata_sector_letters()[0]
        service = ProrrataRegisterService(
            repository=_repository_factory(bucket_id=str(_PROFILE_ID)),
            operation=authority_operation,
        )
        service.declare_sector(SectorDefinition(sector_id=sector_id, letra=letter, member_activity_codes=("4711",)))
        before = service.list_all()
    request = ProrrataSettleSectorRequest(
        profile_id=_PROFILE_ID,
        ejercicio=2026,
        sector_id=sector_id,
        con_derecho_volume=PublicDecimal(decimal="100"),
        sin_derecho_volume=PublicDecimal(decimal="0"),
    )

    returned, execution, events, identity = _run_executor(
        request,
        definition_id=PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID,
        authority_operation=authority_operation,
        monkeypatch=monkeypatch,
        operation_number=5,
    )

    projection = _assert_refusal_projection(execution, identity)
    assert isinstance(returned, OperationRefusalEvidence)
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert projection.refusal is not None
    assert projection.refusal.reason == "sector_settlement_entry_absent"
    assert projection.refusal.sector_id == sector_id
    with validating_governed_facts(authority_operation):
        after = ProrrataRegisterService(
            repository=_repository_factory(bucket_id=str(_PROFILE_ID)),
            operation=authority_operation,
        ).list_all()
    assert after == before
    assert after.entry_for(2026, sector_id=sector_id) is None
