"""Application orchestration for read-only live IVA remote state."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from ...application.auth.sessions import AuthenticatedAeatSessionResult as _AuthenticatedAeatSessionResult
from ...core.access_gate.gate import AeatAccessGate as _AeatAccessGate
from ...core.config import Settings as _Settings
from ...core.config import load_settings as _load_settings
from ...core.errors.hierarchy import CadrumoError as _CadrumoError
from ...core.hashing import sha256_hex as _sha256_hex
from ...core.modelo import Modelo
from ...core.period import Period
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_location as _storage_location
from ...core.time.clock import now
from .errors import LiveApplicationInputError, LiveIvaSurfaceTimeoutError
from .iva_remote_state_ports import IvaRemoteStatePort
from .remote_state_models import (
    IvaCompensationHistoryCaptureReport,
    IvaCompensationHistoryReport,
    IvaRemoteStateAcquisitionManifest,
    IvaRemoteStateAcquisitionReport,
    IvaRemoteStateAcquisitionSurfaceManifest,
    IvaWalletCaptureReport,
    LiveIvaReadOutcome,
    LiveIvaReadSurface,
)
from .remote_state_outcomes import auth_outcome as _auth_outcome
from .remote_state_outcomes import evidence_ref as _evidence_ref
from .remote_state_outcomes import surface_outcome as _surface_outcome

_LIVE_STATE_IVA_REMOTE_STATE_DIRNAME = Path(_storage_location(StorageCategory.LIVE_STATE_IVA_REMOTE_STATE).subpath).name
_IVA_REMOTE_STATE_FILED_HISTORY_DIRNAME = Path(
    _storage_location(StorageCategory.LIVE_STATE_IVA_REMOTE_STATE_FILED_HISTORY).subpath
).name
_IVA_REMOTE_STATE_WALLET_DIRNAME = Path(
    _storage_location(StorageCategory.LIVE_STATE_IVA_REMOTE_STATE_WALLET).subpath
).name


def list_iva_compensation_history(
    *, ports: IvaRemoteStatePort, as_of_year: int | None = None
) -> IvaCompensationHistoryReport:
    """List profile-local IVA history through the entrypoint-composed port."""
    with ports.active_storage_span():
        return ports.list_history(as_of_year=as_of_year)


async def capture_iva_compensation_history(
    *,
    ports: IvaRemoteStatePort,
    year_from: int,
    year_to: int,
    output_root: Path,
) -> IvaCompensationHistoryCaptureReport:
    """Capture filed Modelo 303 history using the composed remote-state port."""
    if year_from > year_to:
        raise LiveApplicationInputError(translated_message="live.errors.year_range_invalid")
    with ports.active_storage_span():
        session, settings = await ports.active_verified_session(operation="live-filed-read", target_url=None)
        return await ports.capture_history(
            session,
            settings=settings,
            year_from=year_from,
            year_to=year_to,
            output_root=output_root,
            progress_context=None,
        )


def _assert_target_period_year(*, target_year: int, target_period: Period) -> None:
    if target_period.filing_year != target_year:
        raise LiveApplicationInputError(
            translated_message="live.errors.target_period_year_mismatch",
            context={"target_year": str(target_year), "target_period_year": str(target_period.filing_year)},
        )


async def capture_iva_compensation_wallet(
    *,
    ports: IvaRemoteStatePort,
    target_year: int,
    target_period: Period,
    taxpayer_nif: str | None = None,
    output_root: Path | None = None,
) -> IvaWalletCaptureReport:
    """Live-fetch AEAT's IVA wallet using the entrypoint-composed port."""
    _assert_target_period_year(target_year=target_year, target_period=target_period)
    with ports.active_storage_span():
        session, settings = await ports.active_verified_session(
            operation="live-iva-wallet-read",
            target_url=ports.wallet_target_url,
        )
        return await ports.capture_wallet(
            session,
            settings=settings,
            target_year=target_year,
            target_period=target_period,
            taxpayer_nif=taxpayer_nif,
            output_root=output_root,
            progress_context=None,
        )


async def capture_iva_remote_state(
    *,
    ports: IvaRemoteStatePort,
    year_from: int,
    year_to: int,
    target_year: int,
    target_period: Period,
    taxpayer_nif: str | None = None,
    output_root: Path | None = None,
) -> IvaRemoteStateAcquisitionReport:
    """Acquire filed-history and wallet state, retaining independent outcomes."""
    _assert_target_period_year(target_year=target_year, target_period=target_period)
    with ports.active_storage_span():
        return await _capture_iva_remote_state_for_active_storage(
            ports=ports,
            year_from=year_from,
            year_to=year_to,
            target_year=target_year,
            target_period=target_period,
            taxpayer_nif=taxpayer_nif,
            output_root=output_root,
        )


async def _capture_iva_remote_state_for_active_storage(
    *,
    ports: IvaRemoteStatePort,
    year_from: int,
    year_to: int,
    target_year: int,
    target_period: Period,
    taxpayer_nif: str | None,
    output_root: Path | None,
) -> IvaRemoteStateAcquisitionReport:
    settings = _load_settings()
    async with suppress_live_iva_playwright_cancellation_noise(
        drain_ms=settings.cadrumo_live_iva_cancellation_drain_ms,
        restore_on_exit=False,
    ):
        if year_from > year_to:
            raise LiveApplicationInputError(translated_message="live.errors.year_range_invalid")
        _AeatAccessGate(settings).require_live_read()
        store_root = output_root or settings.cadrumo_live_state_dir / _LIVE_STATE_IVA_REMOTE_STATE_DIRNAME
        auth_result: _AuthenticatedAeatSessionResult | None = None
        auth_error: BaseException | None = None
        try:
            auth_result = await ports.ensure_authenticated_session(
                settings,
                operation="live-iva-remote-state-read",
                target_url=ports.wallet_target_url,
            )
        except (TimeoutError, _CadrumoError, OSError) as exc:
            auth_error = exc
        if auth_result is None:
            return _persist_report(
                build_iva_remote_state_acquisition_report(
                    output_root=store_root,
                    year_from=year_from,
                    year_to=year_to,
                    target_year=target_year,
                    target_period=target_period,
                    auth_error=auth_error,
                ),
                ports=ports,
            )
        filed_history: IvaCompensationHistoryCaptureReport | None = None
        wallet: IvaWalletCaptureReport | None = None
        filed_error: BaseException | None = None
        wallet_error: BaseException | None = None
        filed_progress: dict[str, object] = {
            "stage": "not_started",
            "modelo": Modelo.M303.value,
            "year_from": year_from,
            "year_to": year_to,
        }
        try:
            filed_history = await await_live_iva_surface(
                ports.capture_history(
                    auth_result.session,
                    settings=settings,
                    year_from=year_from,
                    year_to=year_to,
                    output_root=store_root / _IVA_REMOTE_STATE_FILED_HISTORY_DIRNAME,
                    progress_context=filed_progress,
                ),
                surface=LiveIvaReadSurface.FILED_HISTORY,
                timeout_ms=filed_history_surface_timeout_ms(settings, year_from=year_from, year_to=year_to),
                progress_context=filed_progress,
            )
        except (TimeoutError, _CadrumoError, OSError) as exc:
            filed_error = exc
        wallet_progress: dict[str, object] = {
            "stage": "not_started",
            "target_year": target_year,
            "target_period": target_period.registry_token,
        }
        try:
            wallet = await await_live_iva_surface(
                ports.capture_wallet(
                    auth_result.session,
                    settings=settings,
                    target_year=target_year,
                    target_period=target_period,
                    taxpayer_nif=taxpayer_nif,
                    output_root=store_root / _IVA_REMOTE_STATE_WALLET_DIRNAME,
                    progress_context=wallet_progress,
                ),
                surface=LiveIvaReadSurface.WALLET_CARTERA,
                timeout_ms=settings.cadrumo_live_iva_surface_timeout_ms,
                progress_context=wallet_progress,
            )
        except (TimeoutError, _CadrumoError, OSError) as exc:
            wallet_error = exc
        return _persist_report(
            build_iva_remote_state_acquisition_report(
                output_root=store_root,
                year_from=year_from,
                year_to=year_to,
                target_year=target_year,
                target_period=target_period,
                auth_result=auth_result,
                filed_history=filed_history,
                wallet=wallet,
                filed_history_error=filed_error,
                wallet_error=wallet_error,
            ),
            ports=ports,
        )


def _persist_report(
    report: IvaRemoteStateAcquisitionReport, *, ports: IvaRemoteStatePort
) -> IvaRemoteStateAcquisitionReport:
    manifest = persist_iva_remote_state_acquisition_report(report, ports=ports)
    return report.model_copy(update={"acquisition_manifest_id": manifest.acquisition_id})


def filed_history_surface_timeout_ms(settings: _Settings, *, year_from: int, year_to: int) -> int:
    return settings.cadrumo_live_iva_surface_timeout_ms * max(1, year_to - year_from + 1)


async def await_live_iva_surface[T](
    awaitable: Awaitable[T],
    *,
    surface: LiveIvaReadSurface,
    timeout_ms: int,
    progress_context: Mapping[str, object] | None = None,
) -> T:
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout_ms / 1000)
    except TimeoutError as exc:
        raise LiveIvaSurfaceTimeoutError(
            f"live IVA {surface.value} read did not complete within {timeout_ms} ms",
            surface=surface.value,
            timeout_ms=timeout_ms,
            progress_context=progress_context,
        ) from exc


@asynccontextmanager
async def suppress_live_iva_playwright_cancellation_noise(*, drain_ms: int = 0, restore_on_exit: bool = True):
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()

    def handler(loop: asyncio.AbstractEventLoop, context: dict[str, object]) -> None:
        if _is_playwright_target_closed_context(context):
            return
        if previous_handler is not None:
            previous_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(handler)
    try:
        yield
    finally:
        if drain_ms:
            await asyncio.sleep(drain_ms / 1000)
        if restore_on_exit:
            loop.set_exception_handler(previous_handler)


def _is_playwright_target_closed_context(context: dict[str, object]) -> bool:
    exception = context.get("exception")
    if exception is None:
        return False
    name, message = type(exception).__name__, str(exception)
    return (name == "TargetClosedError" and "Target page, context or browser has been closed" in message) or (
        name == "Error" and "net::ERR_ABORTED" in message and "frame was detached" in message
    )


def build_iva_remote_state_acquisition_report(
    *,
    output_root: Path,
    year_from: int,
    year_to: int,
    target_year: int,
    target_period: Period,
    acquisition_manifest_id: str | None = None,
    auth_result: _AuthenticatedAeatSessionResult | None = None,
    auth_error: BaseException | None = None,
    filed_history: IvaCompensationHistoryCaptureReport | None = None,
    wallet: IvaWalletCaptureReport | None = None,
    filed_history_error: BaseException | None = None,
    wallet_error: BaseException | None = None,
) -> IvaRemoteStateAcquisitionReport:
    auth = _auth_outcome(auth_result=auth_result, error=auth_error)
    outcomes = (
        _surface_outcome(LiveIvaReadSurface.FILED_HISTORY, report=filed_history, error=filed_history_error, auth=auth),
        _surface_outcome(LiveIvaReadSurface.WALLET_CARTERA, report=wallet, error=wallet_error, auth=auth),
    )
    return IvaRemoteStateAcquisitionReport(
        acquisition_manifest_id=acquisition_manifest_id,
        output_root=str(output_root),
        year_from=year_from,
        year_to=year_to,
        target_year=target_year,
        target_period=target_period,
        auth=auth,
        filed_history=filed_history,
        wallet=wallet,
        outcomes=outcomes,
    )


def persist_iva_remote_state_acquisition_report(
    report: IvaRemoteStateAcquisitionReport,
    *,
    ports: IvaRemoteStatePort,
    captured_at: datetime | None = None,
) -> IvaRemoteStateAcquisitionManifest:
    manifest = _iva_remote_state_acquisition_manifest(report, captured_at=captured_at or now())
    ports.persist_manifest(manifest)
    return manifest


def _iva_remote_state_acquisition_manifest(
    report: IvaRemoteStateAcquisitionReport, *, captured_at: datetime
) -> IvaRemoteStateAcquisitionManifest:
    surfaces = tuple(_iva_remote_state_surface_manifest(report, outcome) for outcome in report.outcomes)
    seed = "|".join(
        (
            str(report.year_from),
            str(report.year_to),
            str(report.target_year),
            report.target_period.registry_token,
            captured_at.isoformat(),
            report.auth.model_dump_json(),
            *(surface.model_dump_json() for surface in surfaces),
        )
    )
    digest = _sha256_hex(seed.encode("utf-8"))
    timestamp = captured_at.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return IvaRemoteStateAcquisitionManifest(
        acquisition_id=f"live-iva-acquisition:{report.target_year}:{report.target_period.registry_token}:{timestamp}:{digest}",
        captured_at=captured_at,
        year_from=report.year_from,
        year_to=report.year_to,
        target_year=report.target_year,
        target_period=report.target_period,
        auth=report.auth,
        filed_history_succeeded=report.filed_history_succeeded,
        wallet_succeeded=report.wallet_succeeded,
        surfaces=surfaces,
    )


def _iva_remote_state_surface_manifest(
    report: IvaRemoteStateAcquisitionReport, outcome: LiveIvaReadOutcome
) -> IvaRemoteStateAcquisitionSurfaceManifest:
    if outcome.surface is LiveIvaReadSurface.FILED_HISTORY:
        filed = report.filed_history
        return IvaRemoteStateAcquisitionSurfaceManifest(
            surface=outcome.surface,
            status=outcome.status,
            outcome_mode=outcome.outcome_mode,
            failure_mode=outcome.failure_mode,
            failure_type=outcome.failure_type,
            failure_context=outcome.failure_context,
            captured_count=outcome.captured_count,
            calculation_observation_count=outcome.calculation_observation_count,
            reloaded_history_count=filed.reloaded_history_count if filed is not None else None,
        )
    wallet = report.wallet
    return IvaRemoteStateAcquisitionSurfaceManifest(
        surface=outcome.surface,
        status=outcome.status,
        outcome_mode=outcome.outcome_mode,
        failure_mode=outcome.failure_mode,
        failure_type=outcome.failure_type,
        failure_context=outcome.failure_context,
        captured_count=outcome.captured_count,
        calculation_observation_count=outcome.calculation_observation_count,
        wallet_row_count=wallet.row_count if wallet is not None else None,
        decision_ref=_evidence_ref(wallet.decision_key) if wallet is not None else None,
        selected_authority=wallet.selected_authority if wallet is not None else None,
        divergence=wallet.divergence if wallet is not None else None,
        blocked=wallet.blocked if wallet is not None else None,
    )


__all__ = [
    "build_iva_remote_state_acquisition_report",
    "await_live_iva_surface",
    "capture_iva_compensation_history",
    "capture_iva_compensation_wallet",
    "capture_iva_remote_state",
    "filed_history_surface_timeout_ms",
    "list_iva_compensation_history",
    "persist_iva_remote_state_acquisition_report",
    "suppress_live_iva_playwright_cancellation_noise",
]
