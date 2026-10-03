"""Exact-profile registered LLM diagnostics and lossless public report."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from threading import get_ident
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.public_scalar import PublicDecimal
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import (
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
    OperationAccessRequest,
    OsLoginContext,
    ProfileAccessBinding,
    ProfileAccessState,
    SessionKind,
    SessionState,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ...user_profile.operation_access_policy import evaluate_operation_access
from ..llm_diagnostics import LlmConfidenceProviderMetrics, LlmDiagnosticsReport, LlmUsageCostProviderMetrics
from ..llm_diagnostics_operation import (
    LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID,
    LedgerLlmDiagnosticsExecutionResult,
    LedgerLlmDiagnosticsExecutor,
    LedgerLlmDiagnosticsOperationPorts,
    LedgerLlmDiagnosticsProjection,
    LedgerLlmDiagnosticsReportSnapshot,
    LedgerLlmDiagnosticsRequest,
    build_ledger_llm_diagnostics_definition,
    build_ledger_llm_diagnostics_registration,
    project_ledger_llm_diagnostics_result,
    resolve_ledger_llm_diagnostics_access,
)
from ..llm_diagnostics_ports import LlmDiagnosticsPorts, LlmUsageDiagnosticRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("3a3a3a3a-3a3a-4a3a-8a3a-3a3a3a3a3a3a")
_OTHER = UUID("4b4b4b4b-4b4b-4b4b-8b4b-4b4b4b4b4b4b")
_PIN = cast(PinnedAuthorityOperation, object())
_OPERATION_ID = LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID


class _UsageReader:
    def load_records(self, *, since: date | None, until: date | None) -> tuple[LlmUsageDiagnosticRecord, ...]:
        del since, until
        return (
            LlmUsageDiagnosticRecord(
                provider="local",
                input_tokens=3,
                output_tokens=7,
                cost_estimate_usd=Decimal("0.0001234500"),
                cache_hit=False,
            ),
            LlmUsageDiagnosticRecord(
                provider="local",
                input_tokens=2,
                output_tokens=4,
                cost_estimate_usd=None,
                cache_hit=True,
            ),
        )


class _TransactionReader:
    def load_transactions(self) -> tuple[()]:
        return ()


def _ports(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> LedgerLlmDiagnosticsOperationPorts:
    assert profile_id == _PROFILE and operation is _PIN
    return LedgerLlmDiagnosticsOperationPorts(
        profile_id=profile_id,
        operation=operation,
        diagnostics=LlmDiagnosticsPorts(usage_reader=_UsageReader(), transaction_reader=_TransactionReader()),
    )


def _registry() -> OperationRegistry:
    definition = build_ledger_llm_diagnostics_definition(_ports)
    registration = build_ledger_llm_diagnostics_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,))


def _request(payload: LedgerLlmDiagnosticsRequest | None = None) -> OperationRequest[LedgerLlmDiagnosticsRequest]:
    return OperationRequest(
        definition_id=_OPERATION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=payload or LedgerLlmDiagnosticsRequest(profile_id=_PROFILE),
    )


def _access_request() -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=_OPERATION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerLlmDiagnosticsRequest(profile_id=_PROFILE),
    )


def _report() -> LlmDiagnosticsReport:
    return LlmDiagnosticsReport(
        since=date(2026, 1, 31),
        until=date(2026, 1, 1),
        low_confidence_threshold=Decimal("0.5000"),
        usage_providers=(
            LlmUsageCostProviderMetrics(
                provider="alpha",
                calls=2,
                cache_hits=1,
                input_tokens=5,
                output_tokens=11,
                total_tokens=16,
                cost_estimate_usd=None,
                unpriced_calls=1,
            ),
            LlmUsageCostProviderMetrics(
                provider="zeta",
                calls=1,
                cache_hits=0,
                input_tokens=1,
                output_tokens=1,
                total_tokens=2,
                cost_estimate_usd=Decimal("0.0001234500"),
                unpriced_calls=0,
            ),
        ),
        total_calls=3,
        total_cache_hits=1,
        total_input_tokens=6,
        total_output_tokens=12,
        total_cost_estimate_usd=None,
        total_unpriced_calls=1,
        confidence_providers=(
            LlmConfidenceProviderMetrics(
                provider="alpha",
                classified_count=2,
                low_confidence_count=1,
                high_confidence_count=1,
                medium_confidence_count=0,
                min_confidence=Decimal("0.1234500"),
                max_confidence=Decimal("0.900000"),
                mean_confidence=Decimal("0.5117"),
            ),
        ),
        total_classified=2,
        total_low_confidence=1,
    )


def test_public_report_is_lossless_for_precision_null_costs_order_and_reversed_dates() -> None:
    """Wire conversion keeps all original canonical facts, including absence."""
    original = _report()
    snapshot = LedgerLlmDiagnosticsReportSnapshot.from_report(original)
    reloaded = LedgerLlmDiagnosticsReportSnapshot.model_validate_json(snapshot.model_dump_json(), strict=True)
    assert reloaded == snapshot
    assert reloaded.to_report() == original
    assert reloaded.usage_providers[0].cost_estimate_usd is None
    assert reloaded.usage_providers[1].cost_estimate_usd == PublicDecimal(decimal="0.0001234500")
    assert tuple(row.provider for row in reloaded.usage_providers) == ("alpha", "zeta")
    assert reloaded.since is not None and reloaded.until is not None and reloaded.since > reloaded.until


def test_real_registry_compiles_and_request_threshold_keeps_legacy_bounds() -> None:
    """The registered schema accepts the canonical default and unit endpoints."""
    registry = _registry()
    definition = registry.lookup(_OPERATION_ID)
    assert definition.permitted_frontends == frozenset(OperationFrontendProjection)
    assert (
        AccessAction.COMMIT
        not in resolve_ledger_llm_diagnostics_access(
            _access_request(),
            OperationAccessContext(
                profile_id=_PROFILE,
                destination_id=uuid4(),
                action=AccessAction.SUBMIT,
                frontend=OperationFrontendProjection.MCP,
                contract=registry.lookup_public_contract(_OPERATION_ID),
                published_authority=Availability.AVAILABLE,
                authority_operation=_PIN,
            ),
        ).policy.actions
    )
    assert _request().payload.low_confidence_threshold == PublicDecimal(decimal="0.5")
    for threshold in ("0", "1", "0.5000"):
        assert (
            LedgerLlmDiagnosticsRequest(
                profile_id=_PROFILE, low_confidence_threshold=PublicDecimal(decimal=threshold)
            ).low_confidence_threshold.decimal
            == threshold
        )
    for threshold in ("-0.1", "1.0001"):
        with pytest.raises(ValidationError):
            LedgerLlmDiagnosticsRequest(profile_id=_PROFILE, low_confidence_threshold=PublicDecimal(decimal=threshold))


def _submitted(
    *,
    profile_id: UUID = _PROFILE,
    definition_id: str = _OPERATION_ID,
    action: AccessAction = AccessAction.SUBMIT,
    periods: frozenset[Period] = frozenset(),
) -> OperationAccessRequest:
    return OperationAccessRequest(
        profile_id=profile_id,
        definition_id=definition_id,
        action=action,
        frontend=OperationFrontendProjection.MCP,
        periods=periods,
        period_independent=not periods,
        destination_id=uuid4(),
    )


def _llm_context(
    action: AccessAction, *, frontend: OperationFrontendProjection, admitted: OperationAccessRequest
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=action,
        frontend=frontend,
        contract=_registry().lookup_public_contract(_OPERATION_ID),
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
    )


@pytest.mark.parametrize("action", [AccessAction.OBSERVE, AccessAction.RESULT])
@pytest.mark.parametrize("frontend", [OperationFrontendProjection.MCP, OperationFrontendProjection.CLI])
def test_later_actions_replay_the_admission_from_a_fresh_session_and_any_frontend(
    action: AccessAction, frontend: OperationFrontendProjection
) -> None:
    """A later session has a new destination and may use another frontend; observation stays available."""
    fresh = _llm_context(action, frontend=frontend, admitted=_submitted())
    assert fresh.admitted_request is not None and fresh.admitted_request.destination_id != fresh.destination_id

    resolved = resolve_ledger_llm_diagnostics_access(_access_request(), fresh)

    assert resolved.request.frontend is frontend
    assert resolved.request.destination_id == fresh.destination_id
    assert resolved.policy.disclosures
    assert all(item.destination_id == fresh.destination_id for item in resolved.policy.disclosures)
    for foreign in (
        _submitted(profile_id=_OTHER),
        _submitted(definition_id="ledger.other"),
        _submitted(action=AccessAction.START),
        _submitted(periods=frozenset({Period.from_year_and_code(2026, "1T")})),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_ledger_llm_diagnostics_access(
                _access_request(), replace(fresh, admitted_request=foreign, authority_operation=_PIN)
            )
        assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


@pytest.mark.parametrize("action", [AccessAction.SUBMIT, AccessAction.START])
def test_entry_actions_need_held_authority_even_with_a_matching_admission(action: AccessAction) -> None:
    context = _llm_context(action, frontend=OperationFrontendProjection.MCP, admitted=_submitted())

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_ledger_llm_diagnostics_access(_access_request(), context)

    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    held = replace(context, authority_operation=_PIN)
    assert resolve_ledger_llm_diagnostics_access(_access_request(), held).request.action is action


def test_result_release_rejects_foreign_subject_and_terminal_effect() -> None:
    """A typed report alone cannot bypass receipt, profile, or effect binding."""
    report = _report()
    projection = LedgerLlmDiagnosticsProjection(
        profile_id=_PROFILE,
        operation_id=_OPERATION_ID,
        outcome="completed",
        effect=OperationEffect.NONE,
        since=report.since,
        until=report.until,
        low_confidence_threshold=PublicDecimal(decimal=str(report.low_confidence_threshold)),
        report=LedgerLlmDiagnosticsReportSnapshot.from_report(report),
    )
    private = LedgerLlmDiagnosticsExecutionResult(projection=projection)
    identity = OperationIdentity(
        operation_id="a" * 64,
        definition_id=_OPERATION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
    )
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=datetime(2026, 10, 1, tzinfo=UTC),
        result_ref="b" * 64,
    )
    assert project_ledger_llm_diagnostics_result(private, receipt) == projection
    with pytest.raises(ValueError):
        project_ledger_llm_diagnostics_result(
            private,
            receipt.model_copy(
                update={"identity": identity.model_copy(update={"subject_ref": profile_operation_subject(str(_OTHER))})}
            ),
        )
    with pytest.raises(ValueError):
        project_ledger_llm_diagnostics_result(private, receipt.model_copy(update={"effect": OperationEffect.UPDATED}))


@pytest.mark.asyncio
async def test_executor_reads_canonical_report_under_exact_profile_and_retained_pin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The owner stores only one complete NONE result and rejects a foreign pin."""
    from .. import llm_diagnostics_operation as module

    caller_thread = get_ident()
    bucket_reads: list[tuple[int, tuple[str, ...]]] = []
    values: list[BaseModel] = []
    effects: list[OperationEffect] = []

    class Operands:
        async def put(self, value: BaseModel, *, written_at: datetime) -> str:
            assert written_at.tzinfo is not None
            values.append(value)
            return "f" * 64

    class Events:
        def __init__(self) -> None:
            self.phases: list[str] = []

        async def phase(self, code: str) -> None:
            self.phases.append(code)

        async def effect(self, effect: OperationEffect) -> None:
            effects.append(effect)

    events = Events()

    def active_bucket_id() -> str:
        bucket_reads.append((get_ident(), tuple(events.phases)))
        return str(_PROFILE)

    monkeypatch.setattr(module, "require_active_bucket_id", active_bucket_id)

    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="e" * 64,
                definition_id=_OPERATION_ID,
                subject_ref=profile_operation_subject(str(_PROFILE)),
            ),
            authority_operation=_PIN,
            events=events,
            operands=Operands(),
        ),
    )
    assert await LedgerLlmDiagnosticsExecutor(_ports).execute(_request(), context) == "f" * 64
    assert events.phases == [_OPERATION_ID]
    assert len(bucket_reads) == 2
    assert bucket_reads[0][1] == ()
    assert bucket_reads[1][1] == (_OPERATION_ID,)
    assert all(thread_id != caller_thread for thread_id, _phases in bucket_reads)
    assert effects == [OperationEffect.NONE]
    assert len(values) == 1 and isinstance(values[0], LedgerLlmDiagnosticsExecutionResult)
    assert values[0].projection.report.total_calls == 2
    assert values[0].projection.report.total_cost_estimate_usd is None

    def wrong_pin(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> LedgerLlmDiagnosticsOperationPorts:
        ports = _ports(profile_id=profile_id, operation=operation)
        return LedgerLlmDiagnosticsOperationPorts(
            profile_id=profile_id, operation=cast(PinnedAuthorityOperation, object()), diagnostics=ports.diagnostics
        )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        await LedgerLlmDiagnosticsExecutor(wrong_pin).execute(_request(), context)
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


@pytest.mark.asyncio
async def test_executor_identity_mismatch_refuses_on_caller_thread_before_bucket_phase_or_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Identity refusal stays ahead of both threaded bucket checks and diagnostics composition."""
    from .. import llm_diagnostics_operation as module

    caller_thread = get_ident()
    identity_threads: list[int] = []
    bucket_reads: list[int] = []
    provider_calls: list[tuple[UUID, PinnedAuthorityOperation]] = []
    phases: list[str] = []
    require_identity = module.require_profile_operation_identity

    def record_identity_check(
        request: OperationRequest[LedgerLlmDiagnosticsRequest],
        context: OperationExecutorContext,
        profile_id: UUID,
        *,
        expected_subject_ref: str | None = None,
    ) -> None:
        identity_threads.append(get_ident())
        require_identity(request, context, profile_id, expected_subject_ref=expected_subject_ref)

    def active_bucket_id() -> str:
        bucket_reads.append(get_ident())
        return str(_PROFILE)

    def ports(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> LedgerLlmDiagnosticsOperationPorts:
        provider_calls.append((profile_id, operation))
        return _ports(profile_id=profile_id, operation=operation)

    class Events:
        async def phase(self, code: str) -> None:
            phases.append(code)

        async def effect(self, _effect: OperationEffect) -> None:
            return None

    monkeypatch.setattr(module, "require_profile_operation_identity", record_identity_check)
    monkeypatch.setattr(module, "require_active_bucket_id", active_bucket_id)
    request = _request()
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="e" * 64,
                definition_id=f"{_OPERATION_ID}.other",
                subject_ref=request.subject_ref,
            ),
            authority_operation=_PIN,
            events=Events(),
            operands=object(),
        ),
    )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        await LedgerLlmDiagnosticsExecutor(ports).execute(request, context)

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert identity_threads == [caller_thread]
    assert bucket_reads == []
    assert phases == []
    assert provider_calls == []


@pytest.mark.parametrize("missing", [DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES, None])
def test_mcp_result_requires_both_categories_destination_and_all_periods(
    missing: DisclosureCategory | None,
) -> None:
    """Actual access policy rejects a partial financial disclosure grant."""
    registry = _registry()
    contract = registry.lookup_public_contract(_OPERATION_ID)
    schema = contract.result_schema
    assert schema is not None
    destination = uuid4()
    resolved = resolve_ledger_llm_diagnostics_access(
        _access_request(),
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
    assert resolved.policy.requires_all_periods and resolved.request.period_independent
    permissions = frozenset(
        DisclosurePermission(destination_id=destination, projection_id=schema.schema_id, category=category)
        for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
    )
    complete = AccessScope(
        operations=frozenset({_OPERATION_ID}),
        actions=frozenset({AccessAction.RESULT}),
        disclosures=permissions,
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )
    granted = AccessScope(
        operations=complete.operations,
        actions=complete.actions,
        disclosures=frozenset(permission for permission in permissions if permission.category is not missing),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )
    instant = datetime(2026, 10, 1, 12, tzinfo=UTC)
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
        scope=granted,
        valid_from=instant - timedelta(days=1),
        expires_at=instant + timedelta(days=1),
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
        scope=granted,
        grant_id=grant.grant_id,
        grant_generation=grant.generation,
        key_id=key.key_id,
        key_generation=key.generation,
        issued_at=instant,
        expires_at=instant + timedelta(minutes=2),
        issued_monotonic=100.0,
    )
    decision = evaluate_operation_access(
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
            scope=complete,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.AVAILABLE,
        ),
        context=AccessEvaluationContext(
            now=instant,
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
    if missing is None:
        assert isinstance(decision, AccessAllowed)
    else:
        assert isinstance(decision, AccessDenied) and decision.code is AccessDenialCode.DISCLOSURE_DENIED
