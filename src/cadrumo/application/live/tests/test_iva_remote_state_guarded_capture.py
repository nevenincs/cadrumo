"""Guard each IVA remote-state local write after its remote capture completes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from cadrumo.application.auth.session_types import AeatLoginAssertion, AeatSession
from cadrumo.application.auth.sessions import AuthenticatedAeatSessionResult
from cadrumo.application.live import iva_remote_state
from cadrumo.application.live.filed_data_ports import FiledEffectGuard
from cadrumo.application.live.iva_remote_state_ports import IvaRemoteStatePort
from cadrumo.application.live.remote_state_models import (
    IvaCompensationHistoryCaptureReport,
    IvaRemoteStateAcquisitionManifest,
    IvaWalletCaptureReport,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
)
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import Settings
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 9, 29, 10, tzinfo=UTC)
_YEAR = 2025
_PERIOD = Period.from_year_and_code(_YEAR, "2T")


class _GuardProbe:
    """Record separate non-nested write fences and their enclosed callbacks."""

    def __init__(self, trace: list[str]) -> None:
        self.trace = trace
        self.depth = 0
        self.entries = 0
        self.maximum_depth = 0

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[None]:
        assert self.depth == 0, "local writes must use fresh sequential guard scopes"
        self.entries += 1
        entry = self.entries
        self.depth += 1
        self.maximum_depth = max(self.maximum_depth, self.depth)
        self.trace.append(f"guard-{entry}-enter")
        try:
            yield
        finally:
            self.depth -= 1
            self.trace.append(f"guard-{entry}-exit")


class _SyntheticIvaRemoteStatePort:
    """Return synthetic surface reports while checking the write-fence boundary."""

    wallet_target_url = "https://test.invalid/iva-wallet"

    def __init__(
        self,
        *,
        settings: Settings,
        session: AeatSession,
        auth_result: AuthenticatedAeatSessionResult,
        authority_operation: PinnedAuthorityOperation,
        guard: _GuardProbe,
        trace: list[str],
        failure: str | None = None,
    ) -> None:
        self.settings = settings
        self.session = session
        self.auth_result = auth_result
        self.authority_operation = authority_operation
        self.guard = guard
        self.trace = trace
        self.failure = failure
        self.manifests: list[IvaRemoteStateAcquisitionManifest] = []
        self.history_calls = 0
        self.wallet_calls = 0
        self.storage_span_entries = 0
        self.storage_span_exits = 0

    @contextmanager
    def active_storage_span(self) -> Iterator[None]:
        self.storage_span_entries += 1
        self.trace.append("storage-enter")
        try:
            yield
        finally:
            self.storage_span_exits += 1
            self.trace.append("storage-exit")

    async def ensure_authenticated_session(
        self,
        settings: Settings,
        *,
        operation: str,
        target_url: str | None,
        authority_operation: PinnedAuthorityOperation | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: object = None,
    ) -> AuthenticatedAeatSessionResult:
        assert settings is self.settings
        assert operation == "live-iva-remote-state-read"
        assert target_url == self.wallet_target_url
        assert authority_operation is self.authority_operation
        assert self.guard.depth == 0
        assert effect_guard is self.guard
        assert on_session_write is None
        self.trace.append("auth-remote")
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
        assert session is self.session
        assert settings is self.settings
        assert (year_from, year_to) == (_YEAR, _YEAR)
        assert output_root.name == "filed-history"
        assert progress_context is not None
        assert effect_guard is not None
        assert authority_operation is self.authority_operation
        assert self.guard.depth == 0, "filed-history remote acquisition ran inside a local write fence"
        self.history_calls += 1
        self.trace.append("filed-history-remote")
        if self.failure == "filed-history-remote":
            self.trace.append("filed-history-remote-failed")
            raise OSError("synthetic filed-history remote failure")
        async with effect_guard():
            assert self.guard.depth == 1
            self.trace.append("filed-history-persist")
            if self.failure == "filed-history-local":
                raise OSError("synthetic filed-history local persistence failure")
        return IvaCompensationHistoryCaptureReport.model_construct(
            output_root=str(output_root),
            year_from=year_from,
            year_to=year_to,
            captured_count=1,
            observation_paths=("encrypted/history/2025.json",),
            artefact_refs=("encrypted/history/artifact-1",),
            casilla_count=1,
            calculation_observation_count=1,
            calculation_observation_keys=("303:2025:2T",),
            reloaded_history_count=0,
            reloaded_rows=(),
            failed_declaration_count=0,
            failed_declarations=(),
        )

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
        assert (target_year, target_period) == (_YEAR, _PERIOD)
        assert taxpayer_nif is None
        assert output_root is not None and output_root.name == "wallet"
        assert progress_context is not None
        assert effect_guard is not None
        assert authority_operation is self.authority_operation
        assert self.guard.depth == 0, "wallet remote acquisition ran inside a local write fence"
        self.wallet_calls += 1
        self.trace.append("wallet-remote")
        async with effect_guard():
            assert self.guard.depth == 1
            self.trace.append("wallet-persist")
        return IvaWalletCaptureReport.model_construct(
            taxpayer_ref="synthetic-taxpayer-ref",
            target_year=target_year,
            target_period=target_period,
            observation_path="encrypted/wallet/2025-2T.json",
            decision_key="synthetic-decision-key",
            row_count=1,
            total_pending="100.00",
            selected_authority="aeat_wallet",
            selected_amount="100.00",
            local_recurrence_amount="100.00",
            divergence="none",
            blocked=False,
            captured_at=_NOW,
        )

    def persist_manifest(self, manifest: IvaRemoteStateAcquisitionManifest) -> None:
        assert self.guard.depth == 1, "final acquisition manifest escaped its write fence"
        self.trace.append("manifest-persist")
        self.manifests.append(manifest)


def _offline_service_setup(
    monkeypatch: pytest.MonkeyPatch,
    *,
    authority_operation: PinnedAuthorityOperation,
    failure: str | None = None,
) -> tuple[_SyntheticIvaRemoteStatePort, _GuardProbe, list[str]]:
    settings = Settings.model_construct(
        cadrumo_live_iva_cancellation_drain_ms=0,
        cadrumo_live_iva_surface_timeout_ms=10_000,
    )
    session = cast(AeatSession, object())
    auth_result = AuthenticatedAeatSessionResult.model_construct(
        provider_kind=AuthProviderKind.CERTIFICATE,
        session=session,
        assertion=cast(AeatLoginAssertion, object()),
        reused_persisted_session=True,
        fresh=False,
    )

    class _AllowedLiveRead:
        def __init__(self, received_settings: Settings) -> None:
            assert received_settings is settings

        def require_live_read(self) -> None:
            return None

    monkeypatch.setattr(iva_remote_state, "_load_settings", lambda: settings)
    monkeypatch.setattr(iva_remote_state, "_AeatAccessGate", _AllowedLiveRead)
    trace: list[str] = []
    guard = _GuardProbe(trace)
    port = _SyntheticIvaRemoteStatePort(
        settings=settings,
        session=session,
        auth_result=auth_result,
        authority_operation=authority_operation,
        guard=guard,
        trace=trace,
        failure=failure,
    )
    return port, guard, trace


async def _capture(
    port: _SyntheticIvaRemoteStatePort,
    *,
    output_root: Path,
    effect_guard: FiledEffectGuard,
    authority_operation: PinnedAuthorityOperation,
):
    return await iva_remote_state.capture_iva_remote_state(
        ports=cast(IvaRemoteStatePort, port),
        year_from=_YEAR,
        year_to=_YEAR,
        target_year=_YEAR,
        target_period=_PERIOD,
        output_root=output_root,
        effect_guard=effect_guard,
        authority_operation=authority_operation,
    )


def test_successful_surfaces_and_manifest_use_three_fresh_write_guards(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with bundled_indexed_authority().operation() as authority_operation:
        port, guard, trace = _offline_service_setup(
            monkeypatch,
            authority_operation=authority_operation,
        )
        report = asyncio.run(
            _capture(
                port,
                output_root=tmp_path / "iva-remote-state",
                effect_guard=guard,
                authority_operation=authority_operation,
            )
        )

    assert report.filed_history is not None
    assert report.wallet is not None
    assert report.filed_history_succeeded
    assert report.wallet_succeeded
    assert report.acquisition_manifest_id == port.manifests[0].acquisition_id
    assert port.manifests[0].filed_history_succeeded
    assert port.manifests[0].wallet_succeeded
    assert guard.entries == 3
    assert guard.maximum_depth == 1
    assert trace == [
        "storage-enter",
        "auth-remote",
        "filed-history-remote",
        "guard-1-enter",
        "filed-history-persist",
        "guard-1-exit",
        "wallet-remote",
        "guard-2-enter",
        "wallet-persist",
        "guard-2-exit",
        "guard-3-enter",
        "manifest-persist",
        "guard-3-exit",
        "storage-exit",
    ]
    assert (port.storage_span_entries, port.storage_span_exits) == (1, 1)


def test_local_persistence_failure_propagates_and_stops_before_wallet(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with bundled_indexed_authority().operation() as authority_operation:
        port, guard, trace = _offline_service_setup(
            monkeypatch,
            authority_operation=authority_operation,
            failure="filed-history-local",
        )
        with pytest.raises(OSError, match="synthetic filed-history local persistence failure"):
            asyncio.run(
                _capture(
                    port,
                    output_root=tmp_path / "iva-remote-state",
                    effect_guard=guard,
                    authority_operation=authority_operation,
                )
            )

    assert port.history_calls == 1
    assert port.wallet_calls == 0
    assert port.manifests == []
    assert guard.entries == 1
    assert trace == [
        "storage-enter",
        "auth-remote",
        "filed-history-remote",
        "guard-1-enter",
        "filed-history-persist",
        "guard-1-exit",
        "storage-exit",
    ]


def test_remote_surface_failure_still_captures_wallet_and_guards_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    with bundled_indexed_authority().operation() as authority_operation:
        port, guard, trace = _offline_service_setup(
            monkeypatch,
            authority_operation=authority_operation,
            failure="filed-history-remote",
        )
        report = asyncio.run(
            _capture(
                port,
                output_root=tmp_path / "iva-remote-state",
                effect_guard=guard,
                authority_operation=authority_operation,
            )
        )

    filed_outcome = next(outcome for outcome in report.outcomes if outcome.surface is LiveIvaReadSurface.FILED_HISTORY)
    wallet_outcome = next(
        outcome for outcome in report.outcomes if outcome.surface is LiveIvaReadSurface.WALLET_CARTERA
    )
    assert report.filed_history is None
    assert report.wallet is not None
    assert filed_outcome.status is LiveIvaReadStatus.FAILED
    assert wallet_outcome.status is LiveIvaReadStatus.SUCCEEDED
    assert port.wallet_calls == 1
    assert len(port.manifests) == 1
    assert not port.manifests[0].filed_history_succeeded
    assert port.manifests[0].wallet_succeeded
    assert guard.entries == 2
    assert guard.maximum_depth == 1
    assert trace == [
        "storage-enter",
        "auth-remote",
        "filed-history-remote",
        "filed-history-remote-failed",
        "wallet-remote",
        "guard-1-enter",
        "wallet-persist",
        "guard-1-exit",
        "guard-2-enter",
        "manifest-persist",
        "guard-2-exit",
        "storage-exit",
    ]
