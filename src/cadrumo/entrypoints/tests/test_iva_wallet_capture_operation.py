"""Recorded exact-profile IVA wallet capture with synthetic provider state."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.auth.session_types import AeatSession
from cadrumo.application.live.filed_data_ports import FiledEffectGuard
from cadrumo.application.live.iva_remote_state_ports import IvaRemoteStatePort
from cadrumo.application.live.iva_wallet_capture_operation import (
    IVA_WALLET_CAPTURE_DEFINITION_ID,
    IvaWalletCapturePublicResultV1,
    IvaWalletCaptureRequest,
    build_iva_wallet_capture_definition,
    build_iva_wallet_capture_registration,
)
from cadrumo.application.live.remote_state_models import IvaWalletCaptureReport
from cadrumo.application.live.session import SessionWriteReporter
from cadrumo.application.operations.access_resolution import resolve_operation_access
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.core.config import Settings
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

_YEAR = filing_year_envelope().horizon

_NOW = datetime(_YEAR, 8, 24, 20, tzinfo=UTC)
_TARGET_PERIOD = Period.from_year_and_code(_YEAR, "3T")
_TAXPAYER_NIF = "12345678Z"
_REPORT = IvaWalletCaptureReport(
    taxpayer_ref="synthetic-taxpayer-ref",
    target_year=_YEAR,
    target_period=_TARGET_PERIOD,
    observation_path=f"encrypted-observations/iva-wallet/{_YEAR}-3T.json",
    decision_key="synthetic-wallet-decision",
    row_count=2,
    total_pending="120.00",
    selected_authority="aeat_wallet",
    selected_amount="120.00",
    local_recurrence_amount="120.00",
    divergence="none",
    blocked=False,
    captured_at=_NOW,
)


class _SyntheticIvaRemoteStatePort:
    """Model provider acquisition and guarded persistence without live access."""

    wallet_target_url = "https://test.invalid/iva-wallet"

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.session = cast(AeatSession, object())
        self.settings = cast(Settings, object())
        self.effect_guard: FiledEffectGuard | None = None
        self.authority_operation: PinnedAuthorityOperation | None = None
        self.local_persistence_guarded = False

    @contextmanager
    def active_storage_span(self) -> Generator[None]:
        self.events.append("storage-span")
        yield

    async def active_verified_session(
        self,
        *,
        operation: str,
        target_url: str | None,
        authority_operation: PinnedAuthorityOperation | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> tuple[AeatSession, Settings]:
        assert operation == "live-iva-wallet-read"
        assert effect_guard is not None and on_session_write is not None
        assert target_url == self.wallet_target_url
        assert authority_operation is not None
        self.authority_operation = authority_operation
        self.events.append("verified-session")
        return self.session, self.settings

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
        assert session is self.session
        assert settings is self.settings
        assert (target_year, target_period) == (_YEAR, _TARGET_PERIOD)
        assert taxpayer_nif == _TAXPAYER_NIF
        assert output_root == Path("synthetic-wallet-output")
        assert progress_context is None
        assert effect_guard is not None
        assert authority_operation is self.authority_operation
        self.effect_guard = effect_guard

        # This event stands for the provider read. Only the synthetic local
        # persistence below enters the supervisor's irreversible section.
        self.events.append("wallet-fetch")
        async with effect_guard():
            self.local_persistence_guarded = True
            self.events.append("wallet-persist")
        return _REPORT

    async def capture_history(self, *args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("wallet capture must not acquire IVA filing history")


@dataclass(frozen=True, slots=True)
class _Composition:
    output_root: Path
    iva_remote_state_port: IvaRemoteStatePort


def test_supervisor_admits_exact_profile_and_projects_guarded_wallet_capture(tmp_path: Path) -> None:
    """Record one synthetic wallet observation with profile-scoped authority."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        events: list[str] = []
        port = _SyntheticIvaRemoteStatePort(events)
        composition = _Composition(
            output_root=Path("synthetic-wallet-output"),
            iva_remote_state_port=cast(IvaRemoteStatePort, port),
        )
        resources = ProcessResourceScope()

        def provider_preflight(profile_id_arg: UUID, pinned_authority: PinnedAuthorityOperation) -> None:
            assert profile_id_arg == profile_id
            assert pinned_authority is authority
            events.append("provider-preflight")

        def composition_factory(*, operation: PinnedAuthorityOperation):
            events.append("composition")
            return composition

        def resources_factory() -> ProcessResourceScope:
            events.append("browser-resources")
            return resources

        definition = build_iva_wallet_capture_definition(
            composition_factory=composition_factory,
            browser_resources_factory=resources_factory,
            provider_preflight=provider_preflight,
        )
        registration = build_iva_wallet_capture_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        request = OperationRequest(
            definition_id=IVA_WALLET_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=IvaWalletCaptureRequest(
                profile_id=profile_id,
                target_year=_YEAR,
                target_period="3T",
                taxpayer_nif=_TAXPAYER_NIF,
            ),
        )
        access_context = operation_access_context(
            registration.contract, profile_id=profile_id, frontend=OperationFrontendProjection.EXTERNAL_CLIENT
        )

        admitted = resolve_operation_access(registry=registry, request=request, context=access_context)
        assert admitted.request.profile_id == profile_id
        assert admitted.request.periods == frozenset({_TARGET_PERIOD})
        assert AccessAction.COMMIT in admitted.policy.actions

        assert_foreign_profile_refused(registry=registry, request=request, context=access_context)

        _, _, _, supervisor, result_service = build_supervised_operation(
            tmp_path=tmp_path, objects=profile.repository, authority=authority, registry=registry, now=_NOW
        )

        terminal, projected = asyncio.run(
            settle_and_project(supervisor, result_service, registry, request, IvaWalletCapturePublicResultV1)
        )

    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.effect is OperationEffect.UPDATED
    assert isinstance(projected, OperationResultProjectionSuccessV1)
    assert isinstance(projected.projection, IvaWalletCapturePublicResultV1)
    result = projected.projection
    assert (result.target_year, result.target_period) == (_YEAR, "3T")
    assert result.taxpayer_ref == _REPORT.taxpayer_ref
    assert _TAXPAYER_NIF not in result.model_dump_json()
    assert not hasattr(result, "taxpayer_nif")
    assert result.observation_path == _REPORT.observation_path
    assert port.effect_guard is not None
    assert port.authority_operation is authority
    assert port.local_persistence_guarded
    assert events.index("provider-preflight") < events.index("wallet-fetch")
    assert events.index("wallet-fetch") < events.index("wallet-persist")
    assert resources.closed
    assert resources.close_calls == 1
