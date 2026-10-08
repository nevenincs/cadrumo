"""Supervised, exact-profile contracts for live verification capture."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.live import verify as verify_module
from ...application.live import verify_capture_operation as capture_module
from ...application.live.verify import VerifyObservation, VerifySurface
from ...application.live.verify_capture_operation import (
    VERIFY_NIF_IVA_CAPTURE_DEFINITION_ID,
    VERIFY_TGVI_CAPTURE_DEFINITION_ID,
    VerifyCapturePublicResultV1,
    VerifyCaptureRequest,
    VerifyLiveObservation,
    build_verify_capture_definition,
    build_verify_capture_registration,
    resolve_verify_capture_access,
)
from ...application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationRequest
from ...application.operations.persistence.journal import OperationPersistedSnapshot
from ...application.operations.projection_services import OperationResultProjectionService
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.operations.supervisor import OperationSupervisor
from ...application.user_profile.access_contracts import AccessAction, Availability
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.identity_check_verdict import IdentityCheckVerdict
from ...core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)
_PROFILE_ID = UUID("11111111-1111-4111-8111-111111111111")
_FOREIGN_PROFILE_ID = UUID("22222222-2222-4222-8222-222222222222")
_NIF = "B12345674"
_RAW_EVIDENCE_LOCATOR = "private://synthetic-verify-evidence"


class _ExecutionAuthority:
    """Supervisor authority port that records each fresh commit fence."""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.guard_calls = 0
        self.guard_depth = 0

    async def require(self, *, identity: object, request: object, action: AccessAction) -> None:
        assert identity is not None and request is not None
        self.events.append(f"require:{action.value}")

    @asynccontextmanager
    async def commit_guard(self, identity: object) -> AsyncIterator[None]:
        assert identity is not None
        self.guard_calls += 1
        guard_number = self.guard_calls
        self.guard_depth += 1
        self.events.append(f"commit-guard-enter:{guard_number}")
        try:
            yield
        finally:
            self.guard_depth -= 1
            self.events.append(f"commit-guard-exit:{guard_number}")


class _Resources:
    """Synthetic browser owner with observable activation and cleanup."""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.active = False
        self.closed = False
        self.close_calls = 0

    @contextmanager
    def activate(self):
        assert not self.active
        self.active = True
        self.events.append("browser-activate")
        try:
            yield
        finally:
            self.active = False
            self.events.append("browser-deactivate")

    async def close(self) -> None:
        assert not self.active
        self.closed = True
        self.close_calls += 1
        self.events.append("browser-close")


class _VerifyPersistence:
    """In-memory application port whose write requires an active supervisor guard."""

    def __init__(self, *, bucket_id: str, events: list[str], authority: _ExecutionAuthority) -> None:
        self.bucket_id = bucket_id
        self.events = events
        self.authority = authority
        self.rows: dict[str, VerifyObservation] = {}

    def load(self, *, bucket_id: str, observation_id: str) -> VerifyObservation | None:
        assert bucket_id == self.bucket_id
        self.events.append("observation-load")
        return self.rows.get(observation_id)

    def list_observations(self, *, bucket_id: str) -> tuple[VerifyObservation, ...]:
        assert bucket_id == self.bucket_id
        return tuple(self.rows.values())

    def save(self, observation: VerifyObservation) -> None:
        assert self.authority.guard_depth == 1
        assert observation.bucket_id == self.bucket_id
        self.events.append("observation-save")
        self.rows[str(observation.observation_id)] = observation


async def _run_to_terminal(supervisor: OperationSupervisor, operation_id: str) -> OperationPersistedSnapshot:
    await supervisor.start(operation_id)
    return await supervisor.settled(operation_id)


def _supervisor(
    *,
    tmp_path: Path,
    registry: OperationRegistry,
    profile_repository: Any,
    authority: PinnedAuthorityOperation,
    execution_authority: _ExecutionAuthority,
) -> tuple[OperationSupervisor, OperationJournalRepository, Any]:
    durable_root = tmp_path / "operations"
    journal = OperationJournalRepository(storage_root=durable_root)
    operands = operation_secure_reference_repository(objects=profile_repository)
    supervisor = OperationSupervisor(
        authority_operation=authority,
        registry=registry,
        journal=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=durable_root),
        operands=operands,
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: _NOW,
        lease_duration=timedelta(minutes=5),
        execution_authority=execution_authority,
    )
    return supervisor, journal, operands


def test_real_supervisor_captures_exact_profile_under_commit_guard_and_reports_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settle two synthetic checks through the real supervisor and encrypted result store."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        assert profile_id == _PROFILE_ID
        events: list[str] = []
        execution_authority = _ExecutionAuthority(events)
        persistence = _VerifyPersistence(bucket_id=profile.bucket_id, events=events, authority=execution_authority)
        resources: list[_Resources] = []
        acquisitions: list[tuple[VerifySurface, str, object | None]] = []

        monkeypatch.setattr(capture_module, "require_active_bucket_id", lambda: profile.bucket_id)
        monkeypatch.setattr(capture_module, "now", lambda: _NOW)
        monkeypatch.setattr(verify_module, "now", lambda: _NOW)

        def provider_preflight(profile_arg: UUID, pinned_authority: PinnedAuthorityOperation) -> None:
            assert profile_arg == profile_id
            assert pinned_authority is authority
            events.append("provider-preflight")

        def resources_factory() -> _Resources:
            resource = _Resources(events)
            resources.append(resource)
            return resource

        async def acquire(
            surface: VerifySurface,
            nif: str,
            expected: object | None,
            pinned_authority: PinnedAuthorityOperation,
        ) -> VerifyLiveObservation:
            assert pinned_authority is authority
            assert resources[-1].active
            acquisitions.append((surface, nif, expected))
            events.append("remote-acquire")
            return VerifyLiveObservation(
                nif=nif,
                verdict=IdentityCheckVerdict.VALID,
                raw_evidence_locator=_RAW_EVIDENCE_LOCATOR,
            )

        definition = build_verify_capture_definition(
            VerifySurface.TGVI,
            persistence_factory=lambda bucket_id: (
                persistence if bucket_id == profile.bucket_id else pytest.fail("wrong profile persistence scope")
            ),
            acquire=acquire,
            browser_resources_factory=resources_factory,
            provider_preflight=provider_preflight,
        )
        registration = build_verify_capture_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        request = OperationRequest(
            definition_id=VERIFY_TGVI_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=VerifyCaptureRequest(
                profile_id=profile_id,
                nif=_NIF,
                expected=IdentityCheckVerdict.VALID,
            ),
        )
        admitted = resolve_operation_access(
            registry=registry,
            request=request,
            context=OperationAccessContext(
                profile_id=profile_id,
                destination_id=uuid4(),
                action=AccessAction.SUBMIT,
                frontend=OperationFrontendProjection.CLI,
                contract=registration.contract,
                published_authority=Availability.AVAILABLE,
                authority_operation=authority,
            ),
        )
        assert admitted.request.profile_id == profile_id
        assert admitted.policy.requires_all_periods
        assert AccessAction.COMMIT in admitted.policy.actions

        supervisor, journal, operands = _supervisor(
            tmp_path=tmp_path,
            registry=registry,
            profile_repository=profile.repository,
            authority=authority,
            execution_authority=execution_authority,
        )
        result_service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)

        async def run(operation_id: str) -> tuple[OperationPersistedSnapshot, BaseModel]:
            submitted_id = await supervisor.submit(request, operation_id=operation_id)
            terminal = await _run_to_terminal(supervisor, submitted_id)
            contract = registry.lookup_public_contract(VERIFY_TGVI_CAPTURE_DEFINITION_ID)
            assert contract.result_schema is not None
            result = await result_service.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=submitted_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                VerifyCapturePublicResultV1,
            )
            return terminal, result

        async def run_successes() -> tuple[tuple[OperationPersistedSnapshot, BaseModel], ...]:
            return await run("3" * 64), await run("4" * 64)

        (first_terminal, first_frame), (second_terminal, second_frame) = asyncio.run(run_successes())

        monkeypatch.setattr(capture_module, "require_active_bucket_id", lambda: str(_FOREIGN_PROFILE_ID))
        wrong_scope_id = asyncio.run(supervisor.submit(request, operation_id="5" * 64))
        wrong_scope_terminal = asyncio.run(_run_to_terminal(supervisor, wrong_scope_id))

    assert first_terminal.lifecycle is second_terminal.lifecycle is OperationLifecycle.TERMINAL
    assert (
        first_terminal.terminal_condition is second_terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    )
    assert first_terminal.effect is OperationEffect.UPDATED
    assert second_terminal.effect is OperationEffect.NONE
    assert first_terminal.terminal_receipt is not None
    assert first_terminal.terminal_receipt.effect is OperationEffect.UPDATED
    assert second_terminal.terminal_receipt is not None
    assert second_terminal.terminal_receipt.effect is OperationEffect.NONE
    assert isinstance(first_frame, OperationResultProjectionSuccessV1)
    assert isinstance(second_frame, OperationResultProjectionSuccessV1)
    first_result = first_frame.projection
    second_result = second_frame.projection
    assert isinstance(first_result, VerifyCapturePublicResultV1)
    assert isinstance(second_result, VerifyCapturePublicResultV1)
    assert first_result.bucket_id == second_result.bucket_id == profile.bucket_id
    assert first_result.observation_id == second_result.observation_id
    assert first_result.surface is second_result.surface is VerifySurface.TGVI
    assert first_result.nif == _NIF
    assert first_result.expected is IdentityCheckVerdict.VALID
    assert first_result.matched_expectation is True
    assert "raw_evidence_locator" not in first_result.model_dump()
    assert _RAW_EVIDENCE_LOCATOR not in first_result.model_dump_json()

    assert acquisitions == [
        (VerifySurface.TGVI, _NIF, IdentityCheckVerdict.VALID),
        (VerifySurface.TGVI, _NIF, IdentityCheckVerdict.VALID),
    ]
    assert events.count("observation-save") == 1
    assert events.count("remote-acquire") == 2
    assert events.index("remote-acquire") < events.index("browser-deactivate") < events.index("commit-guard-enter:1")
    assert events.index("commit-guard-enter:1") < events.index("observation-save")
    assert execution_authority.guard_calls == 4  # observation + result operand for each successful operation
    assert len(resources) == 2
    assert all(resource.closed and resource.close_calls == 1 for resource in resources)

    assert wrong_scope_terminal.lifecycle is OperationLifecycle.TERMINAL
    assert wrong_scope_terminal.terminal_condition is OperationTerminalCondition.REFUSED
    assert wrong_scope_terminal.effect is OperationEffect.NONE
    assert wrong_scope_terminal.terminal_receipt is not None
    assert wrong_scope_terminal.terminal_receipt.refusal_ref is not None
    assert events.count("remote-acquire") == 2
    assert events.count("observation-save") == 1


def test_nif_iva_check_refuses_before_any_browser_or_provider_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AEAT's lookup is certificate-only, so the check settles refused with its registered code."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        events: list[str] = []
        monkeypatch.setattr(capture_module, "require_active_bucket_id", lambda: profile.bucket_id)
        definition = build_verify_capture_definition(
            VerifySurface.NIF_IVA,
            persistence_factory=lambda _bucket_id: pytest.fail("a refused check must not persist"),
            acquire=lambda _surface, _nif, _expected, _authority: pytest.fail("a refused check must not acquire"),
            browser_resources_factory=lambda: pytest.fail("a refused check must not own a browser"),
            provider_preflight=lambda _profile_id, _authority: events.append("provider-preflight"),
        )
        registry = OperationRegistry(
            definitions=(definition,), public_registrations=(build_verify_capture_registration(definition),)
        )
        supervisor, _journal, _operands = _supervisor(
            tmp_path=tmp_path,
            registry=registry,
            profile_repository=profile.repository,
            authority=authority,
            execution_authority=_ExecutionAuthority(events),
        )
        request = OperationRequest(
            definition_id=VERIFY_NIF_IVA_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=VerifyCaptureRequest(profile_id=UUID(profile.bucket_id), nif=_NIF),
        )

        async def run() -> OperationPersistedSnapshot:
            return await _run_to_terminal(supervisor, await supervisor.submit(request, operation_id="6" * 64))

        terminal = asyncio.run(run())

    assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
    assert terminal.effect is OperationEffect.NONE
    assert terminal.terminal_receipt is not None
    assert terminal.terminal_receipt.refusal_ref == "REFUSED_APPLICATION_LIVE_NIF_IVA_CERTIFICATE_REQUIRED"
    assert "provider-preflight" not in events


def test_capture_access_refuses_a_foreign_profile_subject() -> None:
    definition = build_verify_capture_definition(
        VerifySurface.TGVI,
        persistence_factory=lambda _bucket_id: cast(Any, object()),
        acquire=lambda _surface, _nif, _expected, _authority: pytest.fail("unavailable capture must not execute"),
        browser_resources_factory=lambda: cast(Any, object()),
        provider_preflight=lambda _profile_id, _authority: None,
    )
    registration = build_verify_capture_registration(definition)
    request = OperationRequest(
        definition_id=definition.definition_id,
        subject_ref=profile_operation_subject(str(_FOREIGN_PROFILE_ID)),
        payload=VerifyCaptureRequest(profile_id=_PROFILE_ID, nif=_NIF),
    )

    with pytest.raises(ProfileAccessRefusedError):
        resolve_verify_capture_access(
            request,
            OperationAccessContext(
                profile_id=_PROFILE_ID,
                destination_id=uuid4(),
                action=AccessAction.SUBMIT,
                frontend=OperationFrontendProjection.CLI,
                contract=registration.contract,
                published_authority=Availability.AVAILABLE,
            ),
        )
