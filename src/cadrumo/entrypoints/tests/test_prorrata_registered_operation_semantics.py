"""Focused registered-executor checks for prorrata seed lifecycle semantics."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
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
    PRORRATA_DECLARE_GROSS_OPERATION_DEFINITION_ID,
    PRORRATA_REMOVE_GROSS_OPERATION_DEFINITION_ID,
    PRORRATA_SEED_OPERATION_DEFINITION_ID,
    PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID,
    ProrrataDeclareGrossRequest,
    ProrrataRemoveGrossRequest,
    ProrrataSettleSectorRequest,
)
from ...application.prorrata_register.projection_contracts import ProrrataMutationProjection
from ...application.prorrata_register.refusal_words import served_refusal_words
from ...application.prorrata_register.result_contracts import ProrrataOperationExecutionResult
from ...application.prorrata_register.result_projections import project_prorrata_mutation_result
from ...application.prorrata_register.service import ProrrataRegisterService
from ...core.i18n.render import tr
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.prorrata_register_catalogue import prorrata_sector_letters
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...domain.prorrata_register.register import ProrrataRegister, SectorDefinition
from .prorrata_operation_test_support import (
    ProrrataWholeSeedRefusalCase,
    prepare_prorrata_operation_conformance_case,
    prepare_prorrata_whole_seed_refusal_case,
    read_prorrata_operation_conformance_register,
)

_PROFILE_ID = UUID("517e31f8-91b9-47b6-9ac1-3e12cc773c4f")
_runtime_profile = bucket_scoped_runtime_profile_fixture(str(_PROFILE_ID))

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon


@dataclass
class _Events:
    effects: list[OperationEffect] = field(default_factory=list)

    async def phase(self, _phase_code: str) -> None:
        return None

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Cancellation:
    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
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
    projection = project_prorrata_mutation_result(
        execution,
        _receipt(identity, refused=True, refusal_code=execution.refusal.code),
    )
    served = projection.refusal
    assert served is not None
    expected, language = served_refusal_words(served.reason, error_code=served.code)
    assert (served.refusal_words, served.refusal_words_language) == (expected, language)
    return projection


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
    assert after_second.entry_for(_YEAR) == case.expected_entry


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
        ejercicio=_YEAR,
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
    assert projection.refusal.refusal_words == tr("application.prorrata_register.served.sector_settlement_entry_absent")
    assert projection.refusal.sector_id == sector_id
    with validating_governed_facts(authority_operation):
        after = ProrrataRegisterService(
            repository=_repository_factory(bucket_id=str(_PROFILE_ID)),
            operation=authority_operation,
        ).list_all()
    assert after == before
    assert after.entry_for(_YEAR, sector_id=sector_id) is None


def _declare_gross(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    *,
    operation_number: int,
    period: str = "1T",
    amount: str = "400.00",
    evidence: str = f"operator-evidence:303-{_YEAR}-1T",
    sector_id: str | None = None,
    replace: bool = False,
) -> tuple[str | OperationRefusalEvidence, ProrrataMutationProjection, _Events]:
    request = ProrrataDeclareGrossRequest(
        profile_id=_PROFILE_ID,
        ejercicio=_YEAR,
        period=period,
        sector_id=sector_id,
        gross_cuota=PublicDecimal(decimal=amount),
        evidence_reference=evidence,
        replace=replace,
    )
    returned, execution, events, identity = _run_executor(
        request,
        definition_id=PRORRATA_DECLARE_GROSS_OPERATION_DEFINITION_ID,
        authority_operation=authority_operation,
        monkeypatch=monkeypatch,
        operation_number=operation_number,
    )
    refused = isinstance(returned, OperationRefusalEvidence)
    refusal_code = execution.refusal.code if execution.refusal is not None else None
    projection = project_prorrata_mutation_result(
        execution, _receipt(identity, refused=refused, refusal_code=refusal_code)
    )
    return returned, projection, events


def _register(authority_operation: PinnedAuthorityOperation) -> ProrrataRegister:
    return read_prorrata_operation_conformance_register(
        _PROFILE_ID,
        repository_factory=_repository_factory,
        operation=authority_operation,
    )


def _q(code: str) -> Period:
    return Period.from_year_and_code(_YEAR, code)


def test_declare_gross_persists_an_operator_declared_period_base(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = datetime.now(UTC)

    returned, projection, events = _declare_gross(authority_operation, monkeypatch, operation_number=11)

    assert isinstance(returned, str)
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert projection.outcome == "success"
    assert projection.count == 1
    assert projection.gross_declaration is not None
    assert projection.gross_declaration.period == "1T"
    assert projection.gross_declaration.gross_cuota.decimal == "400.00"
    assert projection.gross_declaration.provenance == "operator_declared"
    stored = _register(authority_operation).gross_declaration_for(_q("1T"), sector_id=None)
    assert stored is not None
    assert stored.gross_cuota == Decimal("400.00")
    assert stored.evidence_reference == f"operator-evidence:303-{_YEAR}-1T"
    assert started <= stored.declared_at <= datetime.now(UTC)
    assert projection.gross_declaration.declared_at == stored.declared_at


def test_declare_gross_refuses_a_duplicate_unless_replacing(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _declare_gross(authority_operation, monkeypatch, operation_number=12)
    before = _register(authority_operation)

    returned, refused, events = _declare_gross(authority_operation, monkeypatch, operation_number=13, amount="410.00")

    assert isinstance(returned, OperationRefusalEvidence)
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert refused.refusal is not None
    assert refused.refusal.reason == "gross_declaration_duplicate"
    assert refused.refusal.ejercicio == _YEAR
    assert _register(authority_operation) == before

    returned, replaced, _ = _declare_gross(
        authority_operation, monkeypatch, operation_number=14, amount="410.00", replace=True
    )

    assert isinstance(returned, str)
    assert replaced.count == 1
    after = _register(authority_operation)
    assert len(after.gross_declarations) == 1
    stored = after.gross_declaration_for(_q("1T"), sector_id=None)
    assert stored is not None
    assert stored.gross_cuota == Decimal("410.00")


@pytest.mark.parametrize(
    ("period", "amount", "evidence", "fragment"),
    [
        ("1T", "-0.01", "operator-evidence", "greater than or equal to 0"),
        ("1T", "400.00", "", "evidence_reference"),
        ("1T", "400.00", "   ", "must not be blank"),
        ("4T", "400.00", "operator-evidence", "settlement liquidation"),
        ("13", "400.00", "operator-evidence", "not a Modelo 303 liquidation period"),
    ],
)
def test_declare_gross_refuses_invalid_input_without_writing(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    period: str,
    amount: str,
    evidence: str,
    fragment: str,
) -> None:
    before = _register(authority_operation)

    returned, refused, events = _declare_gross(
        authority_operation, monkeypatch, operation_number=15, period=period, amount=amount, evidence=evidence
    )

    assert isinstance(returned, OperationRefusalEvidence)
    assert events.effects == [OperationEffect.NONE]
    assert refused.refusal is not None
    assert refused.refusal.reason == "validation"
    assert fragment in refused.refusal.detail
    assert _register(authority_operation) == before


def test_declare_gross_refuses_an_undeclared_sector(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _register(authority_operation)

    returned, refused, _ = _declare_gross(
        authority_operation, monkeypatch, operation_number=16, sector_id="sector-never-declared"
    )

    assert isinstance(returned, OperationRefusalEvidence)
    assert refused.refusal is not None
    assert refused.refusal.reason == "gross_declaration_sector_unknown"
    assert refused.refusal.sector_id == "sector-never-declared"
    assert _register(authority_operation) == before


def test_declare_gross_binds_a_declared_sector_apart_from_the_whole_entity(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with validating_governed_facts(authority_operation):
        ProrrataRegisterService(
            repository=_repository_factory(bucket_id=str(_PROFILE_ID)),
            operation=authority_operation,
        ).declare_sector(
            SectorDefinition(
                sector_id="arrendamiento", letra=prorrata_sector_letters()[0], member_activity_codes=("6820",)
            )
        )
    _declare_gross(authority_operation, monkeypatch, operation_number=17)

    returned, projection, _ = _declare_gross(
        authority_operation, monkeypatch, operation_number=18, amount="12.34", sector_id="arrendamiento"
    )

    assert isinstance(returned, str)
    assert projection.count == 2
    after = _register(authority_operation)
    whole = after.gross_declaration_for(_q("1T"), sector_id=None)
    sector = after.gross_declaration_for(_q("1T"), sector_id="arrendamiento")
    assert whole is not None and whole.gross_cuota == Decimal("400.00")
    assert sector is not None and sector.gross_cuota == Decimal("12.34")


def test_remove_gross_deletes_only_the_named_declaration_and_refuses_an_absent_one(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _declare_gross(authority_operation, monkeypatch, operation_number=19)
    _declare_gross(
        authority_operation, monkeypatch, operation_number=20, period="2T", amount="420.00", evidence="evidence-2T"
    )

    def remove(period: str, operation_number: int) -> tuple[str | OperationRefusalEvidence, ProrrataMutationProjection]:
        returned, execution, _, identity = _run_executor(
            ProrrataRemoveGrossRequest(profile_id=_PROFILE_ID, ejercicio=_YEAR, period=period),
            definition_id=PRORRATA_REMOVE_GROSS_OPERATION_DEFINITION_ID,
            authority_operation=authority_operation,
            monkeypatch=monkeypatch,
            operation_number=operation_number,
        )
        refused = isinstance(returned, OperationRefusalEvidence)
        code = execution.refusal.code if execution.refusal is not None else None
        return returned, project_prorrata_mutation_result(
            execution, _receipt(identity, refused=refused, refusal_code=code)
        )

    returned, removed = remove("2T", 21)

    assert isinstance(returned, str)
    assert removed.count == 1
    assert removed.gross_declaration is not None
    assert removed.gross_declaration.period == "2T"
    assert removed.gross_declaration.gross_cuota.decimal == "420.00"
    after = _register(authority_operation)
    assert after.gross_declaration_for(_q("2T"), sector_id=None) is None
    assert after.gross_declaration_for(_q("1T"), sector_id=None) is not None

    returned, absent = remove("2T", 22)

    assert isinstance(returned, OperationRefusalEvidence)
    assert absent.refusal is not None
    assert absent.refusal.reason == "gross_declaration_absent"
    assert _register(authority_operation) == after
