"""Recorded exact-profile IVA history capture with synthetic provider state."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.auth.session_types import (
    AeatSession,
    ClavePermanenteSessionDetail,
)
from cadrumo.application.auth.sessions import AuthenticatedAeatSessionResult
from cadrumo.application.live.filed_data_ports import FiledEffectGuard
from cadrumo.application.live.filed_history_operation import FiledHistoryComposition
from cadrumo.application.live.iva_remote_state_ports import IvaRemoteStatePort
from cadrumo.application.live.iva_wallet_history_capture_operation import (
    IVA_WALLET_HISTORY_CAPTURE_DEFINITION_ID,
    IvaWalletHistoryCapturePublicResultV1,
    IvaWalletHistoryCaptureRequest,
    build_iva_wallet_history_capture_definition,
    build_iva_wallet_history_capture_registration,
)
from cadrumo.application.live.remote_state_models import (
    IvaCompensationHistoryCaptureReport,
    IvaCompensationHistoryReport,
    IvaCompensationHistoryRow,
    IvaRemoteStateAcquisitionManifest,
    IvaWalletCaptureReport,
)
from cadrumo.application.live.session import SessionWriteReporter
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.projection_services import OperationResultProjectionService
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.config import Settings, load_settings
from cadrumo.core.iva_compensation_provenance import IvaCompensationStateProvenance
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 24, 20, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "1T")
_RELOADED_ROW = IvaCompensationHistoryRow(
    year=2025,
    period=_PERIOD,
    provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
    register_status="ALTA",
    presented_at=_NOW,
    prior_pending_amount="10.00",
    applied_amount="0.00",
    pending_for_later_amount="10.00",
    period_result_amount="10.00",
    final_result_amount="10.00",
    generated_amount="10.00",
    available_end_amount="20.00",
)
_CAPTURE_REPORT = IvaCompensationHistoryCaptureReport(
    output_root="synthetic-iva-history-output",
    year_from=2025,
    year_to=2026,
    captured_count=2,
    observation_paths=("encrypted-observations/2025.json", "encrypted-observations/2026.json"),
    artefact_refs=("encrypted-artefact:2025", "encrypted-artefact:2026"),
    casilla_count=7,
    calculation_observation_count=2,
    calculation_observation_keys=("303:2025:1T", "303:2026:1T"),
    reloaded_history_count=1,
    reloaded_rows=(_RELOADED_ROW,),
    failed_declaration_count=1,
    failed_declarations=("303:2026:2T:synthetic capture failure",),
)


class _SyntheticIvaRemoteStatePort:
    """Provide synthetic capture results and prove local effects cross the guard."""

    def __init__(
        self,
        settings: Settings,
        *,
        resource_is_active: Callable[[], bool],
        trace: list[str],
    ) -> None:
        self.settings = settings
        self._resource_is_active = resource_is_active
        self._trace = trace
        self.session = AeatSession(
            authenticated_at=_NOW,
            idle_deadline=_NOW + timedelta(hours=1),
            storage_state_path=None,
            identity_nif="12345678Z",
            provider_detail=ClavePermanenteSessionDetail(dni_nie="12345678Z"),
        )
        self.storage_span_depth = 0
        self.storage_span_entries = 0
        self.storage_span_exits = 0
        self.session_requests: list[tuple[str, str | None]] = []
        self.capture_calls: list[tuple[int, int, Path]] = []
        self.authority_operation: PinnedAuthorityOperation | None = None
        self.guard_depth = 0
        self.guard_entries = 0
        self.local_effects = 0

    @property
    def wallet_target_url(self) -> str:
        raise AssertionError("history capture must not request the wallet endpoint")

    @contextmanager
    def active_storage_span(self) -> Iterator[None]:
        self.storage_span_entries += 1
        self.storage_span_depth += 1
        try:
            yield
        finally:
            self.storage_span_depth -= 1
            self.storage_span_exits += 1

    async def active_verified_session(
        self,
        *,
        operation: str,
        target_url: str | None,
        authority_operation: PinnedAuthorityOperation | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> tuple[AeatSession, Settings]:
        assert self.storage_span_depth == 1
        assert self._resource_is_active()
        assert effect_guard is not None and on_session_write is not None
        assert authority_operation is not None
        self.authority_operation = authority_operation
        self.session_requests.append((operation, target_url))
        return self.session, self.settings

    async def capture_history(
        self,
        session: AeatSession,
        *,
        settings: Settings,
        year_from: int,
        year_to: int,
        output_root: Path,
        progress_context: dict[str, object] | None,
        effect_guard: FiledEffectGuard | None = None,
        authority_operation: PinnedAuthorityOperation | None = None,
    ) -> IvaCompensationHistoryCaptureReport:
        assert self.storage_span_depth == 1
        assert self._resource_is_active()
        assert session is self.session
        assert settings is self.settings
        assert progress_context is None
        assert authority_operation is self.authority_operation
        assert effect_guard is not None
        self.capture_calls.append((year_from, year_to, output_root))
        self._trace.append("capture")

        @asynccontextmanager
        async def tracked_guard() -> AsyncIterator[None]:
            async with effect_guard():
                self.guard_entries += 1
                self.guard_depth += 1
                try:
                    yield
                finally:
                    self.guard_depth -= 1

        async with tracked_guard():
            assert self.guard_depth == 1
            self.local_effects += 1
        return _CAPTURE_REPORT.model_copy(update={"output_root": str(output_root)})

    def list_history(self, *, as_of_year: int | None) -> IvaCompensationHistoryReport:
        del as_of_year
        raise AssertionError("history capture must not read the existing history projection")

    def persist_manifest(self, manifest: IvaRemoteStateAcquisitionManifest) -> None:
        del manifest
        raise AssertionError("history capture must not create the combined remote-state manifest")

    async def ensure_authenticated_session(
        self,
        settings: Settings,
        *,
        operation: str,
        target_url: str | None,
        authority_operation: PinnedAuthorityOperation | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> AuthenticatedAeatSessionResult:
        del settings, operation, target_url, authority_operation, effect_guard, on_session_write
        raise AssertionError("history capture uses the verified session port directly")

    async def capture_wallet(
        self,
        session: AeatSession,
        *,
        settings: Settings,
        target_year: int,
        target_period: Period,
        taxpayer_nif: str | None,
        output_root: Path | None,
        progress_context: dict[str, object] | None,
        effect_guard: FiledEffectGuard | None = None,
        authority_operation: PinnedAuthorityOperation | None = None,
    ) -> IvaWalletCaptureReport:
        del session, settings, target_year, target_period, taxpayer_nif, output_root, progress_context
        del effect_guard, authority_operation
        raise AssertionError("history capture must not acquire wallet state")


@dataclass(frozen=True, slots=True)
class _Composition:
    iva_remote_state_port: IvaRemoteStatePort


class _ResourceScope:
    """Track the operation-owned process resource lifecycle without launching one."""

    def __init__(self) -> None:
        self.activation_depth = 0
        self.activation_entries = 0
        self.closed = False
        self.close_calls = 0

    @contextmanager
    def activate(self) -> Iterator[None]:
        self.activation_entries += 1
        self.activation_depth += 1
        try:
            yield
        finally:
            self.activation_depth -= 1

    async def close(self) -> None:
        assert self.activation_depth == 0
        self.close_calls += 1
        self.closed = True


async def _run_to_terminal(supervisor: OperationSupervisor, operation_id: str) -> OperationPersistedSnapshot:
    await supervisor.start(operation_id)
    return await supervisor.settled(operation_id)


def test_supervisor_admits_exact_mcp_profile_and_projects_guarded_iva_history_capture(tmp_path: Path) -> None:
    """Record a synthetic IVA history capture under exact-profile MCP authority."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        trace: list[str] = []
        resources = _ResourceScope()
        port = _SyntheticIvaRemoteStatePort(
            load_settings(),
            resource_is_active=lambda: resources.activation_depth == 1,
            trace=trace,
        )
        composition = _Composition(iva_remote_state_port=port)
        preflight_calls: list[tuple[UUID, PinnedAuthorityOperation]] = []
        composition_calls: list[Path] = []

        def provider_preflight(profile_id_arg: UUID, pinned_authority: PinnedAuthorityOperation) -> None:
            preflight_calls.append((profile_id_arg, pinned_authority))
            trace.append("provider_preflight")

        def composition_factory(output_root: Path, *, operation: PinnedAuthorityOperation) -> FiledHistoryComposition:
            composition_calls.append(output_root)
            trace.append("composition")
            return cast(FiledHistoryComposition, composition)

        def browser_resources_factory() -> _ResourceScope:
            trace.append("resources")
            return resources

        definition = build_iva_wallet_history_capture_definition(
            composition_factory=composition_factory,
            browser_resources_factory=browser_resources_factory,
            provider_preflight=provider_preflight,
        )
        registration = build_iva_wallet_history_capture_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        output_root = tmp_path / "iva-history-output"
        request = OperationRequest(
            definition_id=IVA_WALLET_HISTORY_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=IvaWalletHistoryCaptureRequest(
                profile_id=profile_id,
                output_root=output_root,
                year_from=2025,
                year_to=2026,
            ),
        )
        access_context = OperationAccessContext(
            profile_id=profile_id,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.MCP,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
        )
        admitted = resolve_operation_access(registry=registry, request=request, context=access_context)
        assert admitted.request.profile_id == profile_id
        assert admitted.request.period_independent
        assert admitted.request.periods == frozenset()
        assert admitted.policy.requires_all_periods
        assert AccessAction.COMMIT in admitted.policy.actions

        foreign_profile_id = uuid4()
        assert foreign_profile_id != profile_id
        foreign_request = request.model_copy(
            update={
                "subject_ref": profile_operation_subject(str(foreign_profile_id)),
                "payload": request.payload.model_copy(update={"profile_id": foreign_profile_id}),
            }
        )
        with pytest.raises(ProfileAccessRefusedError) as refusal:
            resolve_operation_access(registry=registry, request=foreign_request, context=access_context)
        assert refusal.value.reason is AccessDenialCode.PROFILE_MISMATCH

        durable_root = tmp_path / "operations"
        journal = OperationJournalRepository(storage_root=durable_root)
        leases = OperationLeaseFilesystemRepository(storage_root=durable_root)
        operands = operation_secure_reference_repository(objects=profile.repository)
        supervisor = OperationSupervisor(
            authority_operation=authority,
            registry=registry,
            journal=journal,
            event_stream=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )
        result_service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)

        async def run():
            operation_id = await supervisor.submit(request, operation_id="3" * 64)
            terminal = await _run_to_terminal(supervisor, operation_id)
            contract = registry.lookup_public_contract(definition.definition_id)
            assert contract.result_schema is not None
            projected = await result_service.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                IvaWalletHistoryCapturePublicResultV1,
            )
            return terminal, projected

        terminal, projected = asyncio.run(run())

    assert definition.definition_id == "live.iva-wallet.history-capture"
    assert OperationFrontendProjection.MCP in definition.permitted_frontends
    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.effect is OperationEffect.UPDATED
    assert terminal.terminal_receipt is not None
    assert terminal.terminal_receipt.effect is OperationEffect.UPDATED
    assert isinstance(projected, OperationResultProjectionSuccessV1)
    assert isinstance(projected.projection, IvaWalletHistoryCapturePublicResultV1)
    result = projected.projection
    assert result.model_dump() == {
        "output_root": str(output_root),
        "year_from": 2025,
        "year_to": 2026,
        "captured_count": 2,
        "observation_paths": ("encrypted-observations/2025.json", "encrypted-observations/2026.json"),
        "artefact_refs": ("encrypted-artefact:2025", "encrypted-artefact:2026"),
        "casilla_count": 7,
        "calculation_observation_count": 2,
        "calculation_observation_keys": ("303:2025:1T", "303:2026:1T"),
        "reloaded_history_count": 1,
        "failed_declaration_count": 1,
        "failed_declarations": ("303:2026:2T:synthetic capture failure",),
    }
    assert not hasattr(result, "reloaded_rows")
    assert preflight_calls == [(profile_id, authority)]
    assert composition_calls == [output_root]
    assert trace == ["provider_preflight", "composition", "resources", "capture"]
    assert resources.activation_entries == 1
    assert resources.closed
    assert resources.close_calls == 1
    assert port.session_requests == [("live-filed-read", None)]
    assert port.authority_operation is authority
    assert port.capture_calls == [(2025, 2026, output_root)]
    assert port.storage_span_entries == port.storage_span_exits == 1
    assert port.storage_span_depth == 0
    assert port.guard_entries == 1
    assert port.guard_depth == 0
    assert port.local_effects == 1
