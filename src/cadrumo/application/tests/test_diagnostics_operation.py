"""Exact-profile diagnostics reads and their real schema and access policy.

Application port fixtures exercise the canonical report services. No test
claims native acceptance.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..diagnostics_operation import (
    DIAGNOSTICS_READ_OPERATION_DEFINITION_ID,
    DiagnosticsReadExecutor,
    build_diagnostics_read_definition,
    build_diagnostics_read_registration,
    project_diagnostics_read_result,
    resolve_diagnostics_read_access,
)
from ..diagnostics_operation_ports import DiagnosticsReadPorts
from ..diagnostics_read_contracts import (
    DiagnosticsReadExecutionResult,
    DiagnosticsReadKind,
    DiagnosticsReadProjection,
    DiagnosticsReadRequest,
)
from ..diagnostics_run_health import (
    build_error_breakdown,
    build_latency_report,
    build_llm_usage_report,
    build_run_health_report,
    list_recent_runs,
)
from ..diagnostics_run_health_ports import DiagnosticAuthProbeResult, DiagnosticRunRecord
from ..operations import profile_guard
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationFrontendProjection, OperationRegistry
from ..user_profile.access_contracts import (
    AccessAction,
    AccessAllowed,
    AccessDenialCode,
    AccessDenied,
    AccessEvaluationContext,
    AccessScope,
    AccessSession,
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
    ProfileAccessBinding,
    ProfileAccessState,
    SessionKind,
    SessionState,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from ..user_profile.operation_access_policy import evaluate_operation_access

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("3a3a3a3a-3a3a-4a3a-8a3a-3a3a3a3a3a3a")
_OTHER = UUID("4b4b4b4b-4b4b-4b4b-8b4b-4b4b4b4b4b4b")
_PIN = cast(PinnedAuthorityOperation, object())
_NOW = datetime(2026, 10, 1, 12, tzinfo=UTC)


class _Runs:
    def __init__(self) -> None:
        self.windows: list[tuple[date | None, date | None]] = []
        self.records = tuple(
            DiagnosticRunRecord(
                run_id=run_id,
                caller="ledger.classify",
                provider=provider,
                model=model,
                duration_ms=duration,
                succeeded=succeeded,
                error_kind="timeout" if not succeeded else "",
                started_at=datetime(2026, 4, day, tzinfo=UTC),
            )
            for run_id, provider, model, duration, succeeded, day in (
                ("a", "claude", "model-a", 100, True, 1),
                ("b", "claude", "model-b", 333, False, 2),
                ("c", "other", "model-c", 900, False, 2),
                ("d", "claude", "model-b", 700, True, 3),
            )
        )

    def load_records(self, *, since: date | None, until: date | None) -> tuple[DiagnosticRunRecord, ...]:
        self.windows.append((since, until))
        return tuple(
            row
            for row in self.records
            if (since is None or row.started_at.date() >= since) and (until is None or row.started_at.date() <= until)
        )


class _Probe:
    def __init__(self) -> None:
        self.calls = 0

    def probe(self) -> DiagnosticAuthProbeResult:
        self.calls += 1
        return DiagnosticAuthProbeResult(
            provider="certificate",
            configured=True,
            persisted_session_present=True,
            persisted_session_expired=True,
            persisted_session_state="expired",
            probe_summary="idle deadline",
        )


class _Commit:
    def __init__(self) -> None:
        self.active = False
        self.entries = 0
        self.refuse = False

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        if self.refuse:
            raise ProfileAccessRefusedError(AccessDenialCode.GRANT_INACTIVE)
        assert not self.active
        self.active = True
        self.entries += 1
        try:
            yield
        finally:
            self.active = False


class _Operands:
    def __init__(self) -> None:
        self.values: list[BaseModel] = []

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        self.values.append(value)
        return "f" * 64


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []
        self.phases: list[str] = []

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)

    async def phase(self, code: str) -> None:
        self.phases.append(code)


class _Invocation:
    def __init__(self, definition_id: str) -> None:
        self.identity = OperationIdentity(
            operation_id="e" * 64,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        )
        self.events = _Events()
        self.operands = _Operands()
        self.commit = _Commit()
        self.context = cast(
            OperationExecutorContext,
            SimpleNamespace(
                identity=self.identity,
                authority_operation=_PIN,
                cancellation=self.commit,
                events=self.events,
                operands=self.operands,
            ),
        )

    def receipt(self, effect: OperationEffect) -> OperationTerminalReceipt:
        return OperationTerminalReceipt(
            identity=self.identity,
            revision=2,
            condition=OperationTerminalCondition.SUCCEEDED,
            effect=effect,
            settled_at=_NOW,
            result_ref="f" * 64,
        )


def _read_factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> DiagnosticsReadPorts:
    raise AssertionError("schema compilation must not compose persistence")


def _registry() -> OperationRegistry:
    read = build_diagnostics_read_definition(_read_factory)
    return OperationRegistry(
        definitions=(read,),
        public_registrations=(build_diagnostics_read_registration(read),),
    )


def test_real_registration_compiles_closed_nested_schemas() -> None:
    registry = _registry()
    read = registry.lookup_public_contract(DIAGNOSTICS_READ_OPERATION_DEFINITION_ID)
    assert read.permitted_frontends == frozenset(OperationFrontendProjection)
    assert read.result_schema is not None
    assert read.request_schema.schema_version == read.result_schema.schema_version == 1


@pytest.mark.parametrize("kind", ["run_health", "runs", "latency", "errors", "llm_usage"])
@pytest.mark.asyncio
async def test_read_preserves_complete_canonical_report_and_filters(
    kind: DiagnosticsReadKind, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    runs, probe = _Runs(), _Probe()

    def factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> DiagnosticsReadPorts:
        assert profile_id == _PROFILE and operation is _PIN
        return DiagnosticsReadPorts(profile_id, operation, runs, probe)

    request = OperationRequest[DiagnosticsReadRequest](
        definition_id=DIAGNOSTICS_READ_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=DiagnosticsReadRequest(
            profile_id=_PROFILE,
            kind=kind,
            since=date(2026, 4, 1),
            until=date(2026, 4, 2),
            provider="claude",
            limit=1 if kind == "runs" else None,
        ),
    )
    invocation = _Invocation(request.definition_id)
    assert await DiagnosticsReadExecutor(factory).execute(request, invocation.context) == "f" * 64
    result = invocation.operands.values[0]
    assert isinstance(result, DiagnosticsReadExecutionResult)
    projection = result.projection
    assert runs.windows == [(request.payload.since, request.payload.until)]
    assert probe.calls == (1 if kind == "run_health" else 0)
    assert invocation.events.effects == [OperationEffect.NONE]
    assert invocation.commit.entries == 0
    assert project_diagnostics_read_result(result, invocation.receipt(OperationEffect.NONE)) == projection
    canonical_runs, canonical_probe = _Runs(), _Probe()
    if kind == "run_health":
        assert projection.run_health is not None
        assert projection.run_health.to_report() == build_run_health_report(
            since=request.payload.since,
            until=request.payload.until,
            provider=request.payload.provider,
            run_telemetry_port=canonical_runs,
            auth_probe_port=canonical_probe,
        )
        assert projection.run_health.to_report().session_stale
    elif kind == "runs":
        assert projection.runs is not None
        canonical = list_recent_runs(
            since=request.payload.since,
            until=request.payload.until,
            provider=request.payload.provider,
            limit=1,
            run_telemetry_port=canonical_runs,
        )
        assert tuple(row.model_dump() for row in projection.runs) == tuple(row.model_dump() for row in canonical)
        assert projection.runs[0].run_id == "b"
    elif kind == "latency":
        assert projection.latency is not None
        assert projection.latency.to_report() == build_latency_report(
            since=request.payload.since,
            until=request.payload.until,
            provider=request.payload.provider,
            run_telemetry_port=canonical_runs,
        )
    elif kind == "errors":
        assert projection.errors is not None
        assert (
            projection.errors.model_dump()
            == build_error_breakdown(
                since=request.payload.since,
                until=request.payload.until,
                provider=request.payload.provider,
                run_telemetry_port=canonical_runs,
            ).model_dump()
        )
    else:
        assert projection.llm_usage is not None
        assert projection.llm_usage.to_report() == build_llm_usage_report(
            since=request.payload.since,
            until=request.payload.until,
            provider=request.payload.provider,
            run_telemetry_port=canonical_runs,
        )
    with pytest.raises(ValueError):
        project_diagnostics_read_result(result, invocation.receipt(OperationEffect.UNKNOWN))


@pytest.mark.asyncio
async def test_wrong_worker_profile_refuses_before_composition(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_OTHER))
    request = OperationRequest[DiagnosticsReadRequest](
        definition_id=DIAGNOSTICS_READ_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=DiagnosticsReadRequest(profile_id=_PROFILE, kind="runs"),
    )
    with pytest.raises(ProfileAccessRefusedError) as refused:
        await DiagnosticsReadExecutor(_read_factory).execute(request, _Invocation(request.definition_id).context)
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


@pytest.mark.asyncio
async def test_factory_cannot_substitute_another_profile_before_private_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    runs, probe = _Runs(), _Probe()

    def wrong(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> DiagnosticsReadPorts:
        return DiagnosticsReadPorts(_OTHER, operation, runs, probe)

    request = OperationRequest[DiagnosticsReadRequest](
        definition_id=DIAGNOSTICS_READ_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=DiagnosticsReadRequest(profile_id=_PROFILE, kind="run_health"),
    )
    with pytest.raises(ProfileAccessRefusedError) as refused:
        await DiagnosticsReadExecutor(wrong).execute(request, _Invocation(request.definition_id).context)
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert not runs.windows and not probe.calls


def test_strict_read_filters_and_selected_report_refuse_invalid_shapes() -> None:
    with pytest.raises(ValidationError):
        DiagnosticsReadRequest(profile_id=_PROFILE, kind="latency", limit=1)
    with pytest.raises(ValidationError):
        DiagnosticsReadRequest(profile_id=_PROFILE, kind="runs", since=date(2026, 4, 2), until=date(2026, 4, 1))
    with pytest.raises(ValidationError):
        DiagnosticsReadProjection(profile_id=_PROFILE, kind="runs")
    empty = DiagnosticsReadProjection(profile_id=_PROFILE, kind="runs", runs=())
    assert DiagnosticsReadProjection.model_validate_json(empty.model_dump_json()) == empty
    with pytest.raises(ValidationError):
        DiagnosticsReadProjection.model_validate({**empty.model_dump(), "unreviewed": "data"})


def _policy_decision(
    resolved: ResolvedOperationAccess,
    registry: OperationRegistry,
    *,
    disclosures: frozenset[DisclosurePermission],
    all_periods: bool,
) -> AccessAllowed | AccessDenied:
    scope = AccessScope(
        operations=frozenset({resolved.request.definition_id}),
        actions=frozenset({resolved.request.action}),
        disclosures=disclosures,
        periods=None if all_periods else frozenset(),
        allow_period_independent=True,
        allow_delegation=False,
    )
    binding = ProfileAccessBinding(
        profile_id=_PROFILE,
        installation_id=uuid4(),
        os_owner_id="synthetic-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    )
    grant = AutomationGrant(
        grant_id=uuid4(),
        binding=binding,
        client_id=uuid4(),
        generation=1,
        profile_lock_generation=0,
        state=AuthorityState.ACTIVE,
        scope=scope,
        valid_from=_NOW - timedelta(days=1),
        expires_at=_NOW + timedelta(days=1),
        unattended=True,
        allow_os_lock=False,
    )
    key = ApiKeyRecord(
        key_id=uuid4(),
        grant_id=grant.grant_id,
        binding=binding,
        generation=1,
        state=AuthorityState.ACTIVE,
        valid_from=grant.valid_from,
        expires_at=grant.expires_at,
    )
    session = AccessSession(
        session_id=uuid4(),
        binding=binding,
        profile_lock_generation=0,
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        client_id=grant.client_id,
        kind=SessionKind.API_KEY,
        state=SessionState.ACTIVE,
        scope=scope,
        grant_id=grant.grant_id,
        grant_generation=grant.generation,
        key_id=key.key_id,
        key_generation=key.generation,
        issued_at=_NOW,
        expires_at=_NOW + timedelta(minutes=2),
        issued_monotonic=100.0,
    )
    return evaluate_operation_access(
        request=resolved.request,
        policy=resolved.policy,
        registry=registry,
        session=session,
        ancestors=(),
        grant=grant,
        key=key,
        profile=ProfileAccessState(
            binding=binding,
            lock_generation=0,
            globally_locked=False,
            automation_enabled=True,
            scope=scope,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.AVAILABLE,
        ),
        context=AccessEvaluationContext(
            now=_NOW,
            monotonic_now=100.0,
            clock_rollback_detected=False,
            runtime_boot_id=session.runtime_boot_id,
            connection_id=session.connection_id,
            authenticated_client_id=grant.client_id,
            login_contexts=(
                OsLoginContext(
                    login_id="synthetic-login",
                    os_owner_id=binding.os_owner_id,
                    active=True,
                    lock_state=OsLockState.UNLOCKED,
                    unattended=LoginEligibility.ELIGIBLE,
                    credential_facilities=Availability.AVAILABLE,
                ),
            ),
            private_work_available=True,
        ),
    )


@pytest.mark.parametrize("consent", ["exact", "missing", "wrong_destination", "restricted_periods"])
def test_mcp_report_result_uses_actual_disclosure_and_all_period_policy(consent: str) -> None:
    registry = _registry()
    destination = uuid4()
    contract = registry.lookup_public_contract(DIAGNOSTICS_READ_OPERATION_DEFINITION_ID)
    assert contract.result_schema is not None
    request = OperationRequest[BaseModel](
        definition_id=DIAGNOSTICS_READ_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=DiagnosticsReadRequest(profile_id=_PROFILE, kind="run_health"),
    )
    resolved = resolve_diagnostics_read_access(
        request,
        OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=destination,
            action=AccessAction.RESULT,
            frontend=OperationFrontendProjection.MCP,
            contract=contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=_PIN,
        ),
    )
    assert resolved.policy.requires_all_periods and AccessAction.COMMIT not in resolved.policy.actions
    observation = resolve_diagnostics_read_access(
        request,
        OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=destination,
            action=AccessAction.OBSERVE,
            frontend=OperationFrontendProjection.MCP,
            contract=contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=_PIN,
        ),
    )
    assert {permission.category for permission in observation.policy.disclosures} == {
        DisclosureCategory.OPERATION_METADATA
    }
    permissions = frozenset(
        (
            DisclosurePermission(
                destination_id=uuid4() if consent == "wrong_destination" else destination,
                projection_id=contract.result_schema.schema_id,
                category=DisclosureCategory.PROFILE_VALUES,
            ),
        )
    )
    decision = _policy_decision(
        resolved,
        registry,
        disclosures=frozenset[DisclosurePermission]() if consent == "missing" else permissions,
        all_periods=consent != "restricted_periods",
    )
    if consent == "exact":
        assert isinstance(decision, AccessAllowed)
    else:
        assert isinstance(decision, AccessDenied)
        assert decision.code is (
            AccessDenialCode.PERIOD_DENIED if consent == "restricted_periods" else AccessDenialCode.DISCLOSURE_DENIED
        )
