"""Recorded combined IVA remote-state acquisition with synthetic provider facts."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.auth.session_types import (
    AeatLoginAssertion,
    AeatSession,
    ClavePermanenteLoginAssertionDetail,
    ClavePermanenteSessionDetail,
)
from cadrumo.application.auth.sessions import AuthenticatedAeatSessionResult
from cadrumo.application.live.filed_data_ports import FiledEffectGuard
from cadrumo.application.live.filed_history_operation import FiledHistoryComposition
from cadrumo.application.live.iva_remote_state_capture_operation import (
    IVA_REMOTE_STATE_CAPTURE_DEFINITION_ID,
    IvaRemoteStateCapturePublicResultV1,
    IvaRemoteStateCaptureRequest,
    build_iva_remote_state_capture_definition,
    build_iva_remote_state_capture_registration,
)
from cadrumo.application.live.iva_remote_state_ports import IvaRemoteStatePort
from cadrumo.application.live.remote_state_models import (
    IvaCompensationHistoryCaptureReport,
    IvaCompensationHistoryRow,
    IvaRemoteStateAcquisitionManifest,
    IvaWalletCaptureReport,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
)
from cadrumo.application.live.session import SessionWriteReporter
from cadrumo.application.operations.access_resolution import resolve_operation_access
from cadrumo.application.operations.capabilities import OperationOwnedResource
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import Settings, load_settings
from cadrumo.core.iva_compensation_provenance import IvaCompensationStateProvenance
from cadrumo.core.operations import (
    OperationEffect,
    OperationFrontendProjection,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo_client.contracts.access_vocabulary import AccessAction

from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .supervised_operation_rig import (
    ProcessResourceScope,
    assert_foreign_profile_refused,
    build_supervised_operation,
    operation_access_context,
    settle_and_project,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PRIOR_YEAR, _YEAR = filing_year_envelope().years[-2:]

_NOW = datetime(_YEAR, 8, 24, 20, tzinfo=UTC)
_TARGET_PERIOD = Period.from_year_and_code(_YEAR, "1T")
_NIF = "12345678Z"
_PRIVATE_HISTORY_AMOUNT = "9876.54"
_PRIVATE_WALLET_AMOUNT = "7654.32"

_HISTORY_REPORT = IvaCompensationHistoryCaptureReport(
    output_root="synthetic-history-output",
    year_from=_PRIOR_YEAR,
    year_to=_YEAR,
    captured_count=1,
    observation_paths=("encrypted-history/manifest.json",),
    artefact_refs=("encrypted-history:artefact",),
    casilla_count=3,
    calculation_observation_count=1,
    calculation_observation_keys=(f"303:{_YEAR}:1T",),
    reloaded_history_count=1,
    reloaded_rows=(
        IvaCompensationHistoryRow(
            year=_YEAR,
            period=_TARGET_PERIOD,
            provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
            register_status="ALTA",
            presented_at=_NOW,
            prior_pending_amount=_PRIVATE_HISTORY_AMOUNT,
            applied_amount="0.00",
            pending_for_later_amount=_PRIVATE_HISTORY_AMOUNT,
            period_result_amount=_PRIVATE_HISTORY_AMOUNT,
            final_result_amount=_PRIVATE_HISTORY_AMOUNT,
            generated_amount=_PRIVATE_HISTORY_AMOUNT,
            available_end_amount=_PRIVATE_HISTORY_AMOUNT,
        ),
    ),
)
_WALLET_REPORT = IvaWalletCaptureReport(
    taxpayer_ref="private-synthetic-taxpayer-ref",
    target_year=_YEAR,
    target_period=_TARGET_PERIOD,
    observation_path="encrypted-wallet/manifest.json",
    decision_key="private-synthetic-decision-key",
    row_count=2,
    total_pending=_PRIVATE_WALLET_AMOUNT,
    selected_authority="synthetic-wallet-source",
    selected_amount=_PRIVATE_WALLET_AMOUNT,
    local_recurrence_amount="0.00",
    divergence="synthetic-private-divergence",
    blocked=False,
    captured_at=_NOW,
)


class _SyntheticIvaRemoteStatePort:
    """Produce two synthetic read surfaces and retain the redacted manifest."""

    def __init__(
        self,
        *,
        settings: Settings,
        expected_authority: PinnedAuthorityOperation,
        resource_is_active: Callable[[], bool],
        trace: list[str],
    ) -> None:
        self.settings = settings
        self.expected_authority = expected_authority
        self._resource_is_active = resource_is_active
        self._trace = trace
        self.session = AeatSession(
            authenticated_at=_NOW,
            idle_deadline=_NOW + timedelta(hours=1),
            storage_state_path=None,
            identity_nif=_NIF,
            provider_detail=ClavePermanenteSessionDetail(dni_nie=_NIF),
        )
        self.auth_result = AuthenticatedAeatSessionResult(
            provider_kind=AuthProviderKind.CLAVE_PERMANENTE,
            session=self.session,
            assertion=AeatLoginAssertion(
                target_url="https://fixture.invalid/iva-wallet",
                is_valid=True,
                identity_nif=_NIF,
                status_code=200,
                elapsed_ms=1,
                attempted_at=_NOW,
                assertion_detail=ClavePermanenteLoginAssertionDetail(session_cookie_present=True),
            ),
            reused_persisted_session=True,
            fresh=False,
        )
        self.storage_span_depth = 0
        self.storage_span_entries = 0
        self.storage_span_exits = 0
        self.authentication_requests: list[tuple[str, str | None, PinnedAuthorityOperation | None]] = []
        self.history_calls: list[tuple[int, int, Path, PinnedAuthorityOperation | None]] = []
        self.wallet_calls: list[tuple[int, Period, str | None, Path | None, PinnedAuthorityOperation | None]] = []
        self.surface_guards: list[str] = []
        self.guard_depth = 0
        self.local_effects: list[str] = []
        self.manifests: list[IvaRemoteStateAcquisitionManifest] = []

    @property
    def wallet_target_url(self) -> str:
        return "https://fixture.invalid/iva-wallet"

    @contextmanager
    def active_storage_span(self) -> Generator[None]:
        self.storage_span_entries += 1
        self.storage_span_depth += 1
        try:
            yield
        finally:
            self.storage_span_depth -= 1
            self.storage_span_exits += 1

    def list_history(self, *, as_of_year: int | None):
        del as_of_year
        raise AssertionError("combined capture must not read the existing wallet history projection")

    def persist_manifest(self, manifest: IvaRemoteStateAcquisitionManifest) -> None:
        assert self._resource_is_active()
        assert self.storage_span_depth == 1
        self._trace.append("manifest-persist")
        self.manifests.append(manifest)

    async def active_verified_session(
        self,
        *,
        operation: str,
        target_url: str | None,
        authority_operation: PinnedAuthorityOperation | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> tuple[AeatSession, Settings]:
        del authority_operation, effect_guard, on_session_write
        del operation, target_url
        raise AssertionError("combined capture must use the authenticated-session ensure port")

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
        assert self._resource_is_active()
        assert effect_guard is not None and on_session_write is not None
        assert self.storage_span_depth == 1
        assert settings == self.settings
        self._trace.append("authentication")
        self.authentication_requests.append((operation, target_url, authority_operation))
        return self.auth_result

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
        assert self._resource_is_active()
        assert self.storage_span_depth == 1
        assert session is self.session
        assert settings == self.settings
        assert progress_context is not None
        assert effect_guard is not None
        self._trace.append("history-capture")
        self.history_calls.append((year_from, year_to, output_root, authority_operation))
        await self._guard_local_effect(effect_guard, "history")
        return _HISTORY_REPORT.model_copy(update={"output_root": str(output_root)})

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
        assert self._resource_is_active()
        assert self.storage_span_depth == 1
        assert session is self.session
        assert settings == self.settings
        assert progress_context is not None
        assert effect_guard is not None
        self._trace.append("wallet-capture")
        self.wallet_calls.append((target_year, target_period, taxpayer_nif, output_root, authority_operation))
        await self._guard_local_effect(effect_guard, "wallet")
        return _WALLET_REPORT

    async def _guard_local_effect(self, effect_guard: FiledEffectGuard, surface: str) -> None:
        @asynccontextmanager
        async def tracked_guard() -> AsyncGenerator[None]:
            async with effect_guard():
                self.guard_depth += 1
                self.surface_guards.append(surface)
                try:
                    yield
                finally:
                    self.guard_depth -= 1

        async with tracked_guard():
            assert self.guard_depth == 1
            self.local_effects.append(surface)


@dataclass(frozen=True, slots=True)
class _Composition:
    iva_remote_state_port: IvaRemoteStatePort


def _assert_settled_updated(terminal: OperationPersistedSnapshot) -> None:
    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.effect is OperationEffect.UPDATED
    assert terminal.terminal_receipt is not None
    assert terminal.terminal_receipt.effect is OperationEffect.UPDATED


def _assert_public_result(
    result: IvaRemoteStateCapturePublicResultV1, port: _SyntheticIvaRemoteStatePort, output_root: Path
) -> None:
    assert result.model_dump() == {
        "acquisition_manifest_id": port.manifests[0].acquisition_id,
        "output_root": str(output_root),
        "year_from": _PRIOR_YEAR,
        "year_to": _YEAR,
        "target_year": _YEAR,
        "target_period": "1T",
        "auth": {
            "status": LiveIvaReadStatus.SUCCEEDED,
            "outcome_mode": "authenticated",
            "failure_mode": None,
            "failure_type": None,
            "diagnostic_ref": None,
            "provider_kind": "clave_permanente",
            "reused_persisted_session": True,
            "fresh": False,
        },
        "filed_history_succeeded": True,
        "wallet_succeeded": True,
        "outcomes": (
            {
                "surface": LiveIvaReadSurface.FILED_HISTORY,
                "status": LiveIvaReadStatus.SUCCEEDED,
                "outcome_mode": "authenticated",
                "failure_mode": None,
                "failure_type": None,
                "failure_context_json": None,
                "captured_count": 1,
                "calculation_observation_count": 1,
            },
            {
                "surface": LiveIvaReadSurface.WALLET_CARTERA,
                "status": LiveIvaReadStatus.SUCCEEDED,
                "outcome_mode": "authenticated",
                "failure_mode": None,
                "failure_type": None,
                "failure_context_json": None,
                "captured_count": None,
                "calculation_observation_count": None,
            },
        ),
    }
    public_json = json.dumps(result.model_dump(), default=str, sort_keys=True)
    assert "reloaded_rows" not in public_json
    assert "taxpayer_nif" not in public_json
    assert "taxpayer_ref" not in public_json
    assert _PRIVATE_HISTORY_AMOUNT not in public_json
    assert _PRIVATE_WALLET_AMOUNT not in public_json
    assert "private-synthetic-decision-key" not in public_json


def _assert_guarded_effects(
    port: _SyntheticIvaRemoteStatePort,
    trace: list[str],
    profile_id: UUID,
    authority: PinnedAuthorityOperation,
    output_root: Path,
    provider_preflights: list[tuple[UUID, PinnedAuthorityOperation]],
    composition_roots: list[Path],
) -> None:
    assert provider_preflights == [(profile_id, authority)]
    assert composition_roots == [output_root]
    assert trace == [
        "provider-preflight",
        "composition",
        "resources",
        "authentication",
        "history-capture",
        "wallet-capture",
        "manifest-persist",
    ]
    assert port.authentication_requests == [("live-iva-remote-state-read", port.wallet_target_url, authority)]
    assert port.history_calls == [
        (_PRIOR_YEAR, _YEAR, output_root / "filed-history", authority),
    ]
    assert port.wallet_calls == [
        (_YEAR, _TARGET_PERIOD, _NIF, output_root / "wallet", authority),
    ]
    assert port.surface_guards == ["history", "wallet"]
    assert port.guard_depth == 0
    assert port.local_effects == ["history", "wallet"]
    assert port.storage_span_entries == port.storage_span_exits == 1
    assert port.storage_span_depth == 0


def _assert_manifest_and_resources(
    port: _SyntheticIvaRemoteStatePort,
    result: IvaRemoteStateCapturePublicResultV1,
    resources: list[ProcessResourceScope],
) -> None:
    assert len(port.manifests) == 1
    manifest = port.manifests[0]
    assert manifest.acquisition_id == result.acquisition_manifest_id
    assert (manifest.year_from, manifest.year_to, manifest.target_year, manifest.target_period) == (
        _PRIOR_YEAR,
        _YEAR,
        _YEAR,
        _TARGET_PERIOD,
    )
    assert manifest.filed_history_succeeded and manifest.wallet_succeeded
    assert tuple(surface.surface for surface in manifest.surfaces) == (
        LiveIvaReadSurface.FILED_HISTORY,
        LiveIvaReadSurface.WALLET_CARTERA,
    )
    assert tuple(surface.status for surface in manifest.surfaces) == (
        LiveIvaReadStatus.SUCCEEDED,
        LiveIvaReadStatus.SUCCEEDED,
    )
    assert manifest.surfaces[0].reloaded_history_count == 1
    assert manifest.surfaces[1].wallet_row_count == 2
    assert len(resources) == 1
    assert resources[0].activation_entries == 1
    assert resources[0].closed and resources[0].close_calls == 1
    assert resources[0].activation_depth == 0


def test_supervisor_captures_iva_remote_state_for_exact_external_client_profile(tmp_path: Path) -> None:
    """Record both IVA evidence surfaces through pinned, guarded synthetic ports."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        trace: list[str] = []
        resources: list[ProcessResourceScope] = []

        def resource_is_active() -> bool:
            return any(resource.activation_depth == 1 for resource in resources)

        port = _SyntheticIvaRemoteStatePort(
            settings=load_settings(),
            expected_authority=authority,
            resource_is_active=resource_is_active,
            trace=trace,
        )
        composition = _Composition(iva_remote_state_port=port)
        provider_preflights: list[tuple[UUID, PinnedAuthorityOperation]] = []
        composition_roots: list[Path] = []

        def provider_preflight(profile_arg: UUID, pinned_authority: PinnedAuthorityOperation) -> None:
            provider_preflights.append((profile_arg, pinned_authority))
            trace.append("provider-preflight")

        def composition_factory(output_root: Path, *, operation: PinnedAuthorityOperation) -> FiledHistoryComposition:
            composition_roots.append(output_root)
            trace.append("composition")
            return cast(FiledHistoryComposition, composition)

        def browser_resources_factory() -> ProcessResourceScope:
            trace.append("resources")
            resource = ProcessResourceScope()
            resources.append(resource)
            return resource

        definition = build_iva_remote_state_capture_definition(
            composition_factory=composition_factory,
            browser_resources_factory=browser_resources_factory,
            provider_preflight=provider_preflight,
        )
        registration = build_iva_remote_state_capture_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        output_root = tmp_path / "iva-remote-state-output"
        request = OperationRequest(
            definition_id=IVA_REMOTE_STATE_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=IvaRemoteStateCaptureRequest(
                profile_id=profile_id,
                output_root=output_root,
                year_from=_PRIOR_YEAR,
                year_to=_YEAR,
                target_year=_YEAR,
                target_period="1T",
                taxpayer_nif=_NIF,
            ),
        )
        access_context = operation_access_context(
            registration.contract,
            profile_id=profile_id,
            frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
            authority_operation=authority,
        )
        admitted = resolve_operation_access(
            registry=registry, request=cast(OperationRequest[BaseModel], request), context=access_context
        )
        assert admitted.request.profile_id == profile_id
        assert admitted.request.period_independent
        assert admitted.request.periods == frozenset()
        assert admitted.policy.requires_all_periods
        assert AccessAction.COMMIT in admitted.policy.actions

        assert_foreign_profile_refused(registry=registry, request=request, context=access_context)
        assert definition.capabilities.owned_resources == frozenset({OperationOwnedResource.PROCESS})

        _, _, _, supervisor, result_service = build_supervised_operation(
            tmp_path=tmp_path, objects=profile.repository, authority=authority, registry=registry, now=_NOW
        )

        terminal, projected = asyncio.run(
            settle_and_project(
                supervisor,
                result_service,
                registry,
                request,
                IvaRemoteStateCapturePublicResultV1,
            )
        )

    _assert_settled_updated(terminal)
    assert isinstance(projected, OperationResultProjectionSuccessV1)
    assert isinstance(projected.projection, IvaRemoteStateCapturePublicResultV1)
    result = projected.projection
    _assert_public_result(result, port, output_root)
    _assert_guarded_effects(port, trace, profile_id, authority, output_root, provider_preflights, composition_roots)
    _assert_manifest_and_resources(port, result, resources)
