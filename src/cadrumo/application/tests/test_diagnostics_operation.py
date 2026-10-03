"""Exact-profile diagnostics, real schema/policy and bounded dispatch decisions.

Application port fixtures exercise the canonical report, consent and emit
services. No test invokes a network telemetry sink or claims native acceptance.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from threading import Event
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ...core.config import Settings
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.telemetry.emit import TelemetrySink
from ...core.telemetry.schema import TelemetryEventPayload
from ...core.telemetry.tier import TelemetryTier
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..diagnostics_operation import (
    DIAGNOSTICS_READ_OPERATION_DEFINITION_ID,
    DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID,
    DiagnosticsReadExecutionResult,
    DiagnosticsReadExecutor,
    DiagnosticsReadKind,
    DiagnosticsReadProjection,
    DiagnosticsReadRequest,
    DiagnosticsTelemetryFlushExecutionResult,
    DiagnosticsTelemetryFlushExecutor,
    DiagnosticsTelemetryFlushRequest,
    build_diagnostics_read_definition,
    build_diagnostics_read_registration,
    build_diagnostics_telemetry_flush_definition,
    build_diagnostics_telemetry_flush_registration,
    project_diagnostics_read_result,
    project_diagnostics_telemetry_flush_result,
    resolve_diagnostics_read_access,
    resolve_diagnostics_telemetry_flush_access,
)
from ..diagnostics_operation_ports import DiagnosticsReadPorts, DiagnosticsTelemetryFlushPorts
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


def _flush_factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> DiagnosticsTelemetryFlushPorts:
    raise AssertionError("schema compilation must not construct a telemetry sink")


def _registry() -> OperationRegistry:
    read = build_diagnostics_read_definition(_read_factory)
    flush = build_diagnostics_telemetry_flush_definition(_flush_factory)
    return OperationRegistry(
        definitions=(read, flush),
        public_registrations=(
            build_diagnostics_read_registration(read),
            build_diagnostics_telemetry_flush_registration(flush),
        ),
    )


def test_both_real_registrations_compile_closed_nested_schemas() -> None:
    registry = _registry()
    read = registry.lookup_public_contract(DIAGNOSTICS_READ_OPERATION_DEFINITION_ID)
    flush = registry.lookup_public_contract(DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID)
    assert read.permitted_frontends == frozenset(OperationFrontendProjection)
    assert flush.permitted_frontends == frozenset({OperationFrontendProjection.CLI})
    assert read.result_schema is not None and flush.result_schema is not None
    assert read.request_schema.schema_version == read.result_schema.schema_version == 1
    assert flush.request_schema.schema_version == flush.result_schema.schema_version == 1


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
                    locked=False,
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


def test_flush_commit_is_cli_only_and_absent_for_dry_run() -> None:
    registry = _registry()
    contract = registry.lookup_public_contract(DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID)
    for dry_run in (True, False):
        request = OperationRequest[BaseModel](
            definition_id=contract.definition_id,
            subject_ref=profile_operation_subject(str(_PROFILE)),
            payload=DiagnosticsTelemetryFlushRequest(profile_id=_PROFILE, dry_run=dry_run),
        )
        context = OperationAccessContext(
            profile_id=_PROFILE,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.CLI,
            contract=contract,
            published_authority=Availability.AVAILABLE,
            authority_operation=_PIN,
        )
        resolved = resolve_diagnostics_telemetry_flush_access(request, context)
        assert (AccessAction.COMMIT in resolved.policy.actions) is (not dry_run)
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_diagnostics_telemetry_flush_access(
                request, replace(context, frontend=OperationFrontendProjection.MCP)
            )
        assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED


def _enabled_settings() -> Settings:
    return Settings(
        cadrumo_telemetry_opt_in=True,
        cadrumo_telemetry_tier=TelemetryTier.FULL,
        cadrumo_telemetry_endpoint="https://telemetry.invalid/collect",
    )


class _FlushHarness:
    def __init__(self, *, settings: Settings | None = None) -> None:
        self.invocation = _Invocation(DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID)
        self.runs, self.probe = _Runs(), _Probe()
        self.settings = settings if settings is not None else _enabled_settings()
        self.current_settings = self.settings
        self.settings_reads = 0
        self.sink_settings: list[Settings] = []
        self.sent: list[TelemetryEventPayload] = []
        self.sink_error = False
        self.factory_error = False
        self.send_entered = Event()
        self.send_release: Event | None = None

    def load_settings(self) -> Settings:
        self.settings_reads += 1
        return self.settings if self.settings_reads == 1 else self.current_settings

    def sink_factory(self, settings: Settings) -> TelemetrySink:
        assert not self.invocation.commit.active
        self.sink_settings.append(settings)
        if self.factory_error:
            raise RuntimeError("synthetic pre-dispatch factory failure")
        owner = self

        class Sink:
            def send(self, payload: TelemetryEventPayload) -> None:
                assert not owner.invocation.commit.active
                owner.sent.append(payload)
                owner.send_entered.set()
                if owner.send_release is not None:
                    assert owner.send_release.wait(timeout=5)
                if owner.sink_error:
                    raise RuntimeError("synthetic sink failure after invocation")

        return Sink()

    def factory(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> DiagnosticsTelemetryFlushPorts:
        assert profile_id == _PROFILE and operation is _PIN
        return DiagnosticsTelemetryFlushPorts(
            profile_id,
            operation,
            self.runs,
            self.probe,
            self.load_settings,
            self.sink_factory,
        )

    async def execute(self, **fields: object) -> str:
        request = OperationRequest[DiagnosticsTelemetryFlushRequest](
            definition_id=DIAGNOSTICS_TELEMETRY_FLUSH_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
            payload=DiagnosticsTelemetryFlushRequest.model_validate({"profile_id": _PROFILE, **fields}),
        )
        return await DiagnosticsTelemetryFlushExecutor(self.factory).execute(request, self.invocation.context)

    def result(self) -> DiagnosticsTelemetryFlushExecutionResult:
        result = self.invocation.operands.values[0]
        assert isinstance(result, DiagnosticsTelemetryFlushExecutionResult)
        return result


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.asyncio
async def test_flush_dry_and_current_consent_noop_have_none_effect(
    dry_run: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    harness = _FlushHarness()
    harness.current_settings = Settings(cadrumo_telemetry_endpoint="https://telemetry.invalid/collect")
    assert await harness.execute(dry_run=dry_run, acknowledged=True) == "f" * 64
    result = harness.result()
    projection = result.projection
    assert not projection.sent and not harness.sent and not harness.sink_settings
    assert projection.preview.would_send is dry_run
    assert len(harness.runs.windows) == harness.probe.calls == 1
    assert harness.invocation.events.effects == [OperationEffect.NONE]
    assert harness.invocation.commit.entries == (0 if dry_run else 1)
    restored = projection.preview.to_preview()
    assert restored.payload.counters == {"runs": 4, "succeeded": 2, "failed": 2}
    assert restored.payload.timings_ms == {}
    assert (
        project_diagnostics_telemetry_flush_result(result, harness.invocation.receipt(OperationEffect.NONE))
        == projection
    )


@pytest.mark.asyncio
async def test_explicit_overrides_cross_worker_and_sink_attempt_is_unknown_outside_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    harness = _FlushHarness(settings=Settings())
    assert (
        await harness.execute(
            dry_run=False,
            acknowledged=True,
            opt_in=True,
            tier=TelemetryTier.FULL,
            endpoint="https://override.invalid/collect",
        )
        == "f" * 64
    )
    result = harness.result()
    assert result.projection.sent and result.projection.preview.would_send
    assert harness.settings_reads == 2 and harness.invocation.commit.entries == 1
    assert len(harness.sent) == len(harness.sink_settings) == 1
    assert harness.sink_settings[0].cadrumo_telemetry_endpoint == "https://override.invalid/collect"
    assert harness.sent[0] == result.projection.preview.to_preview().payload
    assert harness.invocation.events.effects == [OperationEffect.UNKNOWN, OperationEffect.UNKNOWN]
    assert (
        project_diagnostics_telemetry_flush_result(result, harness.invocation.receipt(OperationEffect.UNKNOWN))
        == result.projection
    )
    with pytest.raises(ValueError):
        project_diagnostics_telemetry_flush_result(result, harness.invocation.receipt(OperationEffect.NONE))


@pytest.mark.asyncio
async def test_authority_revocation_at_dispatch_refuses_without_sink_or_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    harness = _FlushHarness()
    harness.invocation.commit.refuse = True
    with pytest.raises(ProfileAccessRefusedError) as refused:
        await harness.execute(dry_run=False, acknowledged=True)
    assert refused.value.reason is AccessDenialCode.GRANT_INACTIVE
    assert not harness.sent and not harness.sink_settings and not harness.invocation.operands.values
    assert OperationEffect.UNKNOWN not in harness.invocation.events.effects


@pytest.mark.parametrize("failure", ["factory", "sink"])
@pytest.mark.asyncio
async def test_pre_dispatch_failure_and_uncertain_sink_failure_keep_truthful_effects(
    failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    harness = _FlushHarness()
    harness.factory_error = failure == "factory"
    harness.sink_error = failure == "sink"
    with pytest.raises(RuntimeError):
        await harness.execute(dry_run=False, acknowledged=True)
    assert not harness.invocation.operands.values
    assert bool(harness.sent) is (failure == "sink")
    assert harness.invocation.events.effects[-1] is (
        OperationEffect.NONE if failure == "factory" else OperationEffect.UNKNOWN
    )
    assert not harness.invocation.commit.active


@pytest.mark.asyncio
async def test_cancellation_joins_owned_dispatch_before_unknown_settlement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    harness = _FlushHarness()
    release = Event()
    harness.send_release = release
    task = asyncio.create_task(harness.execute(dry_run=False, acknowledged=True))
    try:
        assert await asyncio.to_thread(harness.send_entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(harness.sent) == 1 and harness.result().projection.sent
    assert harness.invocation.events.effects[-1] is OperationEffect.UNKNOWN
    assert not harness.invocation.commit.active


def test_flush_projection_refuses_undeclared_payload_metric() -> None:
    from ..diagnostics_operation import DiagnosticsTelemetryPreviewSnapshot
    from ..diagnostics_telemetry import build_telemetry_flush_preview

    preview = build_telemetry_flush_preview(
        settings=_enabled_settings(), acknowledged=True, run_telemetry_port=_Runs(), auth_probe_port=_Probe()
    )
    values = preview.model_dump()
    values["payload"]["counters"]["unreviewed"] = 1
    with pytest.raises(ValidationError):
        DiagnosticsTelemetryPreviewSnapshot.model_validate(values)
