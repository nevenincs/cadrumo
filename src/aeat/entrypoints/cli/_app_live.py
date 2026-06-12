"""Explicit read-only AEAT live observation CLI commands."""

from __future__ import annotations

import asyncio
import json
import os
import platform
import re
import shutil
import signal
import subprocess
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer

from ...application.live import (
    FiledDataCaptureFailureRow,
    FiledDataListingRow,
    IvaCompensationHistoryReport,
    IvaRemoteStateAcquisitionReport,
    IvaWalletCaptureReport,
    capture_filed_data,
    capture_filed_data_bulk,
    capture_source_filed_data,
    filed_data_capture_failure_row,
    list_filed_data,
)
from ...application.operator_surface import FilingStatus
from ...core import Period, PeriodError
from ...core.i18n import tr
from ._app_live_borrador_cli import borrador_100_app, borrador_app, register_borrador_commands
from ._app_live_expedientes_cli import expedientes_app, register_expedientes_commands
from ._app_live_justificante_cli import justificante_app, register_justificante_commands
from ._app_live_notifications_cli import notifications_app, register_notifications_commands
from ._app_live_portals_cli import portals_app, portals_list, portals_show, register_portals_commands
from ._app_live_verify_cli import register_verify_commands, verify_app
from ._common import _emit_envelope

if TYPE_CHECKING:
    from ...application.auth import LiveAuthPreflightReport
    from ...application.live import VerifyVerdict


def _verify_expected(value: str | None) -> VerifyVerdict | None:
    if value is None:
        return None
    if value == "valid":
        return "valid"
    if value == "invalid":
        return "invalid"
    if value == "unknown":
        return "unknown"
    raise typer.BadParameter(tr("cli.app.live.verify.expected_values_error"))


app = typer.Typer(
    name="live",
    help=tr("cli.app.live.app_help"),
    no_args_is_help=True,
    add_completion=False,
)
filed_app = typer.Typer(
    name=FilingStatus.FILED,
    help=tr("cli.app.live.filed_app_help"),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(filed_app, name=FilingStatus.FILED)

iva_wallet_app = typer.Typer(
    name="iva-wallet",
    help=tr(
        "cli.app.live.iva_wallet.app_help",
        default=(
            "AEAT IVA compensation wallet capture (read-only; allows only own-name representation and "
            "the guarded wallet read query)."
        ),
    ),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(iva_wallet_app, name="iva-wallet")


def _metric_line(key: str, value: object) -> str:
    return f"{key}={value}"


def _live_period_option(period: str | None, *, year: int) -> Period | None:
    if period is None:
        return None
    try:
        return Period.from_year_and_code(year, period)
    except PeriodError as exc:
        raise typer.BadParameter(f"invalid AEAT period {period!r} for year {year}") from exc


def _required_live_period_option(period: str, *, year: int) -> Period:
    parsed = _live_period_option(period, year=year)
    if parsed is None:
        raise typer.BadParameter("--period is required")
    return parsed


def _resolve_pull_year_range(
    *,
    year: int | None,
    year_from: int | None,
    year_to: int | None,
) -> tuple[int, int]:
    if year is not None and (year_from is not None or year_to is not None):
        raise typer.BadParameter("use --year for a single-year pull or --from-year/--to-year for a range, not both")
    if year is not None:
        return year, year
    if year_from is None and year_to is None:
        raise typer.BadParameter("either --year or both --from-year and --to-year are required")
    if year_from is None or year_to is None:
        raise typer.BadParameter("--from-year and --to-year must be supplied together")
    if year_from > year_to:
        raise typer.BadParameter("--from-year must be less than or equal to --to-year")
    return year_from, year_to


def _live_iva_outcome_label(value: object) -> str:
    token = getattr(value, "value", value)
    normalized = str(token or "unknown")
    if normalized == "aeat_403":
        return tr("cli.app.live.iva_wallet.acquisition.outcome.aeat_403", default="AEAT 403/auth gate")
    if normalized == "authenticated":
        return tr("cli.app.live.iva_wallet.acquisition.outcome.authenticated", default="authenticated")
    if normalized == "certificate_required":
        return tr(
            "cli.app.live.iva_wallet.acquisition.outcome.certificate_required",
            default="certificate required",
        )
    if normalized == "dom_drift":
        return tr("cli.app.live.iva_wallet.acquisition.outcome.dom_drift", default="AEAT page shape changed")
    if normalized == "live_navigation_failed":
        return tr(
            "cli.app.live.iva_wallet.acquisition.outcome.live_navigation_failed",
            default="live navigation failed",
        )
    if normalized == "no_clave_prompt":
        return tr("cli.app.live.iva_wallet.acquisition.outcome.no_clave_prompt", default="no Cl@ve prompt")
    if normalized == "operator_timeout":
        return tr(
            "cli.app.live.iva_wallet.acquisition.outcome.operator_timeout",
            default="operator approval timed out",
        )
    if normalized == "pending_clave_request":
        return tr(
            "cli.app.live.iva_wallet.acquisition.outcome.pending_clave_request",
            default="pending Cl@ve request",
        )
    if normalized == "qr_required":
        return tr("cli.app.live.iva_wallet.acquisition.outcome.qr_required", default="QR approval required")
    if normalized == "wrong_identity":
        return tr("cli.app.live.iva_wallet.acquisition.outcome.wrong_identity", default="wrong identity")
    return tr("cli.app.live.iva_wallet.acquisition.outcome.unknown", default=normalized.replace("_", " "))


def _emit_live_auth_preflight(provider: str | None = None) -> None:
    from ...application.auth import build_live_auth_preflight_report
    from ...core.redaction import redact_for_cli_output

    report = build_live_auth_preflight_report(provider)
    for line in _live_auth_preflight_lines(report):
        typer.echo(redact_for_cli_output(line), err=True)


def _live_auth_preflight_lines(report: LiveAuthPreflightReport) -> tuple[str, ...]:
    return (
        _metric_line("auth_preflight", "redacted"),
        _metric_line("auth_provider", report.provider),
        _metric_line("auth_configured", report.configured),
        _metric_line("auth_available", report.available),
        _metric_line("auth_active_profile", "<profile-id>" if report.active_profile else ""),
        _metric_line("auth_active_profile_status", report.active_profile_status),
        _metric_line("auth_active_profile_registered", report.active_profile_registered),
        _metric_line("auth_active_profile_record_present", report.active_profile_record_present),
        _metric_line("auth_profile_tax_id", "present" if report.profile_tax_id_present else "missing"),
        _metric_line("auth_provider_identity", "present" if report.provider_identity_present else "missing"),
        _metric_line("auth_identity_alignment", report.identity_alignment),
        _metric_line("auth_identity_kind", report.identity_kind),
        _metric_line("auth_mode", report.auth_mode),
        _metric_line("auth_prefer_non_qr", report.prefer_non_qr),
        _metric_line("auth_timeout_ms", report.timeout_ms),
        _metric_line("auth_dni_fecha", "present" if report.dni_fecha_configured else "missing"),
        _metric_line("auth_nie_soporte", "present" if report.nie_soporte_configured else "missing"),
        _metric_line("auth_certificate_path", "present" if report.certificate_path_configured else "missing"),
        _metric_line("auth_certificate_file", "present" if report.certificate_file_present else "missing"),
        _metric_line("auth_certificate_backend", report.certificate_backend),
        _metric_line("auth_persisted_session", "present" if report.persisted_session_present else "missing"),
        _metric_line("auth_persisted_session_expired", report.persisted_session_expired),
        _metric_line("auth_persisted_session_state", report.persisted_session_state),
        _metric_line("auth_probe_result", report.probe_result),
    )


_IVA_WALLET_LIVE_SAFETY_LINES = (
    _metric_line("safety_policy", "read_only_fail_closed"),
    _metric_line("representation_gate_policy", "own_name_only_no_represented_taxpayer_choice"),
    _metric_line(
        "aeat_form_submission_policy",
        "wallet_execute_read_query_only_no_filing_or_represented_taxpayer_data",
    ),
)


@iva_wallet_app.command(
    "pull",
    help=tr(
        "cli.app.live.iva_wallet.pull_help",
        default=(
            "Live-fetch and persist AEAT's IVA compensation wallet. The only AEAT form action allowed is "
            "the guarded wallet read query; representation gates only continue in own-name mode."
        ),
    ),
)
def iva_wallet_pull_cmd(
    ctx: typer.Context,
    year: Annotated[
        int,
        typer.Option("--year", min=2000, max=2099, help=tr("cli.app.live.year_help")),
    ],
    period: Annotated[str, typer.Option("--period", help=tr("cli.app.live.period_help"))],
    taxpayer_nif: Annotated[
        str | None,
        typer.Option(
            "--taxpayer-nif",
            help=tr(
                "cli.app.live.iva_wallet.taxpayer_nif_help",
                default="Taxpayer NIF; defaults to authenticated identity.",
            ),
        ),
    ] = None,
) -> None:
    """Pull the authenticated AEAT IVA compensation wallet.

    This is a live read. It can trigger the configured authentication
    provider, including Cl@ve Móvil manual approval. Under pytest, the
    shared live-read gate still requires the live-test opt-in.
    """
    from ...application.live import capture_iva_compensation_wallet

    _emit_live_auth_preflight()
    report = asyncio.run(
        capture_iva_compensation_wallet(
            target_year=year,
            target_period=_required_live_period_option(period, year=year),
            taxpayer_nif=taxpayer_nif,
        ),
    )
    from ._app_live_payloads import IvaWalletPullResult

    result = IvaWalletPullResult(
        taxpayer_ref=report.taxpayer_ref,
        target_year=report.target_year,
        target_period=report.target_period,
        observation_path=report.observation_path,
        decision_key=report.decision_key,
        row_count=report.row_count,
        total_pending=report.total_pending,
        selected_authority=report.selected_authority,
        selected_amount=report.selected_amount,
        local_recurrence_amount=report.local_recurrence_amount,
        divergence=report.divergence,
        blocked=report.blocked,
        captured_at=report.captured_at.isoformat(),
    )
    _emit_envelope(ctx, command="app.live.iva_wallet.pull", result=result, lines=_iva_wallet_pull_lines(report))


def _iva_wallet_pull_lines(report: IvaWalletCaptureReport) -> tuple[str, ...]:
    return (
        *_IVA_WALLET_LIVE_SAFETY_LINES,
        *(
            _metric_line("taxpayer_ref", report.taxpayer_ref),
            _metric_line("target_year", report.target_year),
            _metric_line("target_period", report.target_period),
            _metric_line("row_count", report.row_count),
            _metric_line("total_pending", report.total_pending),
            _metric_line("selected_authority", report.selected_authority),
            _metric_line("selected_amount", report.selected_amount),
            _metric_line("local_recurrence_amount", report.local_recurrence_amount),
            _metric_line("divergence", report.divergence),
            _metric_line("blocked", report.blocked),
            _metric_line("captured_at", report.captured_at.isoformat()),
            _metric_line("observation_path", report.observation_path),
        ),
    )


@iva_wallet_app.command(
    "history",
    help=tr(
        "cli.app.live.iva_wallet.history_help",
        default=(
            "List secure local IVA compensation history, carry-forward lots, and persisted wallet "
            "authority decisions derived from Modelo 303 captures."
        ),
    ),
)
def iva_wallet_history_cmd(
    ctx: typer.Context,
    as_of_year: Annotated[
        int | None,
        typer.Option("--as-of-year", min=2000, max=2099, help=tr("cli.app.live.iva_wallet.as_of_year_help")),
    ] = None,
) -> None:
    """List the profile-local IVA compensation history without contacting AEAT."""
    from ...application.live import list_iva_compensation_history

    report = list_iva_compensation_history(as_of_year=as_of_year)
    result = _iva_wallet_history_result(report)
    _emit_envelope(ctx, command="app.live.iva_wallet.history", result=result, lines=_iva_wallet_history_lines(report))


def _iva_wallet_history_result(report: IvaCompensationHistoryReport) -> Any:
    from ._app_live_payloads import (
        IvaCompensationCarryForwardLotPayload,
        IvaCompensationHistoryRowPayload,
        IvaWalletAuthorityDecisionPayload,
        IvaWalletHistoryResult,
    )

    return IvaWalletHistoryResult(
        row_count=report.row_count,
        as_of_year=report.as_of_year,
        carry_forward_lot_count=report.carry_forward_lot_count,
        unallocated_applied_amount=report.unallocated_applied_amount,
        authority_decision_count=report.authority_decision_count,
        rows=[
            IvaCompensationHistoryRowPayload(
                year=row.year,
                period=row.period,
                status=row.status,
                presented_at=row.presented_at.isoformat(),
                prior_pending_amount=row.prior_pending_amount,
                applied_amount=row.applied_amount,
                pending_for_later_amount=row.pending_for_later_amount,
                period_result_amount=row.period_result_amount,
                final_result_amount=row.final_result_amount,
                generated_amount=row.generated_amount,
                available_end_amount=row.available_end_amount,
            )
            for row in report.rows
        ],
        carry_forward_lots=[
            IvaCompensationCarryForwardLotPayload(
                taxpayer_ref=lot.taxpayer_ref,
                source_filing_year=lot.source_filing_year,
                source_period=lot.source_period,
                generated_amount=lot.generated_amount,
                applied_amount=lot.applied_amount,
                remaining_amount=lot.remaining_amount,
                age_years=lot.age_years,
                expiry_review_state=lot.expiry_review_state,
                source_observation_key=lot.source_observation_key,
            )
            for lot in report.carry_forward_lots
        ],
        authority_decisions=[
            IvaWalletAuthorityDecisionPayload(
                taxpayer_ref=decision.taxpayer_ref,
                target_year=decision.target_year,
                target_period=decision.target_period,
                selected_authority=decision.selected_authority,
                selected_amount=decision.selected_amount,
                wallet_amount=decision.wallet_amount,
                local_recurrence_amount=decision.local_recurrence_amount,
                override_amount=decision.override_amount,
                divergence=decision.divergence,
                blocked=decision.blocked,
                stale_wallet=decision.stale_wallet,
                authority_sources=list(decision.authority_sources),
            )
            for decision in report.authority_decisions
        ],
    )


def _iva_wallet_history_lines(report: IvaCompensationHistoryReport) -> tuple[str, ...]:
    lines = [
        _metric_line("row_count", report.row_count),
        _metric_line("as_of_year", report.as_of_year),
        _metric_line("carry_forward_lot_count", report.carry_forward_lot_count),
        _metric_line("unallocated_applied_amount", report.unallocated_applied_amount),
        _metric_line("authority_decision_count", report.authority_decision_count),
    ]
    for row in report.rows:
        lines.append(
            _metric_line(
                "row",
                "\t".join(
                    (
                        str(row.year),
                        row.period.registry_token,
                        row.status,
                        f"prior={row.prior_pending_amount}",
                        f"applied={row.applied_amount}",
                        f"pending_later={row.pending_for_later_amount}",
                        f"period_result={row.period_result_amount}",
                        f"final_result={row.final_result_amount}",
                        f"generated={row.generated_amount}",
                        f"available_end={row.available_end_amount}",
                    ),
                ),
            ),
        )
    for lot in report.carry_forward_lots:
        lines.append(
            _metric_line(
                "carry_forward_lot",
                "\t".join(
                    (
                        str(lot.source_filing_year),
                        lot.source_period.registry_token,
                        f"generated={lot.generated_amount}",
                        f"applied={lot.applied_amount}",
                        f"remaining={lot.remaining_amount}",
                        f"age_years={lot.age_years}",
                        f"expiry_review_state={lot.expiry_review_state}",
                        f"source={lot.source_observation_key}",
                        f"taxpayer_ref={lot.taxpayer_ref}",
                    ),
                ),
            ),
        )
    for decision in report.authority_decisions:
        lines.append(
            _metric_line(
                "authority_decision",
                "\t".join(
                    (
                        str(decision.target_year),
                        decision.target_period.registry_token,
                        f"selected_authority={decision.selected_authority}",
                        f"selected_amount={decision.selected_amount}",
                        f"wallet_amount={decision.wallet_amount}",
                        f"local_recurrence_amount={decision.local_recurrence_amount}",
                        f"override_amount={decision.override_amount}",
                        f"divergence={decision.divergence}",
                        f"blocked={decision.blocked}",
                        f"stale_wallet={decision.stale_wallet}",
                        f"taxpayer_ref={decision.taxpayer_ref}",
                    ),
                ),
            ),
        )
        for source in decision.authority_sources:
            lines.append(
                _metric_line(
                    "authority_source",
                    f"{decision.target_year}\t{decision.target_period.registry_token}\t{source}",
                ),
            )
    return tuple(lines)


@iva_wallet_app.command(
    "pull-history",
    help=tr(
        "cli.app.live.iva_wallet.pull_history_help",
        default=(
            "Pull filed Modelo 303 history and persist secure IVA compensation state. "
            "No AEAT filing or wallet form choices are submitted."
        ),
    ),
)
def iva_wallet_capture_history_cmd(
    ctx: typer.Context,
    year_from: Annotated[
        int,
        typer.Option("--from-year", min=2000, max=2099, help=tr("cli.app.live.from_year_help")),
    ],
    year_to: Annotated[
        int,
        typer.Option("--to-year", min=2000, max=2099, help=tr("cli.app.live.to_year_help")),
    ],
    output_root: Annotated[
        Path,
        typer.Option(
            "--output-root",
            file_okay=False,
            dir_okay=True,
            writable=True,
            help=tr("cli.app.live.output_root_help"),
        ),
    ] = Path("var/aeat/live/iva-compensation-history"),
) -> None:
    """Pull multi-year Modelo 303 filing history and verify secure reload."""
    from ...application.live import capture_iva_compensation_history

    _emit_live_auth_preflight()
    report = asyncio.run(
        capture_iva_compensation_history(
            year_from=year_from,
            year_to=year_to,
            output_root=output_root,
        ),
    )
    lines = (
        *_IVA_WALLET_LIVE_SAFETY_LINES,
        _metric_line("year_from", report.year_from),
        _metric_line("year_to", report.year_to),
        _metric_line("captured_count", report.captured_count),
        _metric_line("calculation_observation_count", report.calculation_observation_count),
        _metric_line("reloaded_history_count", report.reloaded_history_count),
        _metric_line("output_root", report.output_root),
    )
    from ._app_live_payloads import IvaWalletCaptureHistoryResult

    result = IvaWalletCaptureHistoryResult(
        output_root=report.output_root,
        year_from=report.year_from,
        year_to=report.year_to,
        captured_count=report.captured_count,
        calculation_observation_count=report.calculation_observation_count,
        reloaded_history_count=report.reloaded_history_count,
    )
    _emit_envelope(ctx, command="app.live.iva_wallet.pull_history", result=result, lines=lines)


@iva_wallet_app.command(
    "pull-remote-state",
    help=tr(
        "cli.app.live.iva_wallet.pull_remote_state_help",
        default=(
            "Pull filed Modelo 303 history and attempt the AEAT IVA wallet/cartera read as one "
            "typed read-only acquisition."
        ),
    ),
)
def iva_wallet_capture_remote_state_cmd(
    ctx: typer.Context,
    year_from: Annotated[
        int,
        typer.Option("--from-year", min=2000, max=2099, help=tr("cli.app.live.from_year_help")),
    ],
    year_to: Annotated[
        int,
        typer.Option("--to-year", min=2000, max=2099, help=tr("cli.app.live.to_year_help")),
    ],
    target_year: Annotated[
        int,
        typer.Option("--target-year", min=2000, max=2099, help=tr("cli.app.live.year_help")),
    ],
    target_period: Annotated[str, typer.Option("--target-period", help=tr("cli.app.live.period_help"))],
    taxpayer_nif: Annotated[
        str | None,
        typer.Option(
            "--taxpayer-nif",
            help=tr(
                "cli.app.live.iva_wallet.taxpayer_nif_help",
                default="Taxpayer NIF; defaults to authenticated identity.",
            ),
        ),
    ] = None,
    output_root: Annotated[
        Path,
        typer.Option(
            "--output-root",
            file_okay=False,
            dir_okay=True,
            writable=True,
            help=tr("cli.app.live.output_root_help"),
        ),
    ] = Path("var/aeat/live/iva-remote-state"),
) -> None:
    """Capture filed-history and wallet/cartera evidence as one read-only operation."""
    from ...application.live import capture_iva_remote_state

    _emit_live_auth_preflight()
    report = asyncio.run(
        _run_live_iva_remote_state_command(
            capture_iva_remote_state(
                year_from=year_from,
                year_to=year_to,
                target_year=target_year,
                target_period=target_period,
                taxpayer_nif=taxpayer_nif,
                output_root=output_root,
            ),
            timeout_ms=_live_iva_remote_state_command_timeout_ms(year_from=year_from, year_to=year_to),
        ),
    )
    from ._app_live_payloads import (
        IvaWalletCaptureRemoteStateResult,
        LiveIvaAuthOutcomePayload,
        LiveIvaSurfaceOutcomePayload,
    )

    result = IvaWalletCaptureRemoteStateResult(
        output_root=report.output_root,
        year_from=report.year_from,
        year_to=report.year_to,
        target_year=report.target_year,
        target_period=report.target_period,
        acquisition_manifest_id=report.acquisition_manifest_id or "",
        auth=LiveIvaAuthOutcomePayload(
            status=report.auth.status.value,
            outcome_mode=report.auth.outcome_mode.value,
            failure_mode=report.auth.failure_mode.value if report.auth.failure_mode else None,
            failure_type=report.auth.failure_type,
            provider_kind=report.auth.provider_kind,
            reused_persisted_session=report.auth.reused_persisted_session,
            fresh=report.auth.fresh,
        ),
        filed_history_succeeded=report.filed_history_succeeded,
        wallet_succeeded=report.wallet_succeeded,
        outcomes=[
            LiveIvaSurfaceOutcomePayload(
                surface=outcome.surface.value,
                status=outcome.status.value,
                outcome_mode=outcome.outcome_mode.value,
                failure_mode=outcome.failure_mode.value if outcome.failure_mode else None,
                failure_type=outcome.failure_type,
                failure_context=outcome.failure_context,
                captured_count=outcome.captured_count,
                calculation_observation_count=outcome.calculation_observation_count,
            )
            for outcome in report.outcomes
        ],
    )
    _emit_envelope(
        ctx,
        command="app.live.iva_wallet.pull_remote_state",
        result=result,
        lines=_iva_remote_state_capture_lines(report),
    )


def _iva_remote_state_capture_lines(report: IvaRemoteStateAcquisitionReport) -> tuple[str, ...]:
    lines = [
        *_IVA_WALLET_LIVE_SAFETY_LINES,
        _metric_line("year_from", report.year_from),
        _metric_line("year_to", report.year_to),
        _metric_line("target_year", report.target_year),
        _metric_line("target_period", report.target_period),
        _metric_line("acquisition_manifest_id", report.acquisition_manifest_id or ""),
        _metric_line("auth_status", report.auth.status.value),
        _metric_line("auth_outcome", report.auth.outcome_mode.value),
        _metric_line("auth_outcome_label", _live_iva_outcome_label(report.auth.outcome_mode)),
        _metric_line("auth_failure_mode", report.auth.failure_mode.value if report.auth.failure_mode else ""),
        _metric_line("auth_failure_type", report.auth.failure_type or ""),
        _metric_line("auth_provider_kind", report.auth.provider_kind or ""),
        _metric_line("auth_reused_persisted_session", report.auth.reused_persisted_session),
        _metric_line("auth_fresh", report.auth.fresh),
        _metric_line("filed_history_succeeded", report.filed_history_succeeded),
        _metric_line("wallet_succeeded", report.wallet_succeeded),
        _metric_line("output_root", report.output_root),
    ]
    for outcome in report.outcomes:
        calculation_count = (
            outcome.calculation_observation_count if outcome.calculation_observation_count is not None else ""
        )
        lines.append(
            _metric_line(
                "surface_outcome",
                "\t".join(
                    (
                        outcome.surface.value,
                        f"status={outcome.status.value}",
                        f"outcome={outcome.outcome_mode.value}",
                        f"outcome_label={_live_iva_outcome_label(outcome.outcome_mode)}",
                        f"failure_mode={outcome.failure_mode.value if outcome.failure_mode else ''}",
                        f"failure_type={outcome.failure_type or ''}",
                        f"failure_context={_compact_failure_context(outcome.failure_context)}",
                        f"captured_count={outcome.captured_count if outcome.captured_count is not None else ''}",
                        f"calculation_observation_count={calculation_count}",
                    ),
                ),
            ),
        )
    return tuple(lines)


async def _run_live_iva_remote_state_command[T](
    awaitable: Awaitable[T],
    *,
    timeout_ms: int | None = None,
) -> T:
    """Run the combined IVA remote-state read under a CLI-level watchdog."""
    from ...application.live import LiveIvaReadSurface, LiveIvaSurfaceTimeoutError
    from ...core.config import load_settings

    resolved_timeout_ms = (
        timeout_ms if timeout_ms is not None else load_settings().aeat_live_iva_cli_watchdog_timeout_ms
    )
    preexisting_profiles = _playwright_profile_tokens(_process_command_inventory())
    pre_timeout_auth_context = _live_iva_auth_watchdog_context(stage="before")
    try:
        return await asyncio.wait_for(awaitable, timeout=resolved_timeout_ms / 1000)
    except TimeoutError as exc:
        killed_processes = _reap_new_playwright_profile_processes(preexisting_profiles=preexisting_profiles)
        post_timeout_auth_context = _live_iva_auth_watchdog_context(stage="after")
        raise LiveIvaSurfaceTimeoutError(
            f"live IVA remote-state command did not complete within {resolved_timeout_ms} ms",
            surface="remote_state_command",
            timeout_ms=resolved_timeout_ms,
            progress_context={
                "stage": "cli_watchdog",
                "surface": LiveIvaReadSurface.FILED_HISTORY.value,
                "watchdog_reaped_process_count": killed_processes,
                **pre_timeout_auth_context,
                **post_timeout_auth_context,
            },
        ) from exc


def _live_iva_remote_state_command_timeout_ms(*, year_from: int, year_to: int) -> int:
    """Return the CLI watchdog budget for one combined IVA remote-state command."""
    from ...core.config import load_settings

    settings = load_settings()
    year_count = max(1, year_to - year_from + 1)
    filed_history_budget_ms = settings.aeat_live_iva_surface_timeout_ms * year_count
    wallet_budget_ms = settings.aeat_live_iva_surface_timeout_ms
    auth_budget_ms = settings.aeat_clave_movil_timeout_ms
    cleanup_budget_ms = settings.aeat_live_iva_cli_watchdog_timeout_ms
    return max(
        settings.aeat_live_iva_cli_watchdog_timeout_ms,
        auth_budget_ms + filed_history_budget_ms + wallet_budget_ms + cleanup_budget_ms,
    )


def _live_iva_auth_watchdog_context(*, stage: str) -> dict[str, object]:
    """Return redacted local auth-session state for live IVA watchdog diagnostics."""
    try:
        from ...application.auth import build_live_auth_preflight_report

        report = build_live_auth_preflight_report()
    except Exception:
        return {f"auth_watchdog_{stage}_probe": "unavailable"}
    return {
        f"auth_watchdog_{stage}_provider": report.provider,
        f"auth_watchdog_{stage}_profile_status": report.active_profile_status,
        f"auth_watchdog_{stage}_identity_alignment": report.identity_alignment,
        f"auth_watchdog_{stage}_persisted_session": "present" if report.persisted_session_present else "missing",
        f"auth_watchdog_{stage}_persisted_session_expired": report.persisted_session_expired,
    }


@dataclass(frozen=True, slots=True)
class _ProcessCommand:
    pid: int
    command_line: str


_PLAYWRIGHT_PROFILE_RE = re.compile(r"playwright_chromiumdev_profile-[A-Za-z0-9_-]+")
_PROCESS_INVENTORY_TIMEOUT_SECONDS = 2


def _process_command_inventory() -> tuple[_ProcessCommand, ...]:
    """Return local process command lines for watchdog cleanup."""
    try:
        if platform.system() == "Windows":
            powershell = shutil.which("powershell") or shutil.which("pwsh")
            if powershell is None:
                return ()
            script = "Get-CimInstance Win32_Process | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
            completed = subprocess.run(  # noqa: S603 - executable resolved with shutil.which; argv is fixed
                [powershell, "-NoProfile", "-Command", script],
                check=True,
                capture_output=True,
                text=True,
                timeout=_PROCESS_INVENTORY_TIMEOUT_SECONDS,
            )
            payload = completed.stdout.strip()
            if not payload:
                return ()
            # ANY-RETURN-RATIONALE-JSON-PROCESS-INVENTORY: json.loads returns Any;
            # payload is a Win32_Process PowerShell JSON array or single-object response.
            decoded: Any = json.loads(payload)
            win_rows: list[Any] = [decoded] if isinstance(decoded, dict) else decoded
            return tuple(
                _ProcessCommand(pid=int(row["ProcessId"]), command_line=str(row.get("CommandLine") or ""))
                for row in win_rows
            )

        ps = shutil.which("ps")
        if ps is None:
            return ()
        completed = subprocess.run(  # noqa: S603 - executable resolved with shutil.which; argv is fixed
            [ps, "-axo", "pid=,args="],
            check=True,
            capture_output=True,
            text=True,
            timeout=_PROCESS_INVENTORY_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return ()

    rows: list[_ProcessCommand] = []
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        pid, _, command_line = line.partition(" ")
        if pid.isdigit():
            rows.append(_ProcessCommand(pid=int(pid), command_line=command_line))
    return tuple(rows)


def _playwright_profile_tokens(processes: tuple[_ProcessCommand, ...]) -> frozenset[str]:
    """Return Playwright temp profile tokens visible in process command lines."""
    tokens: set[str] = set()
    for process in processes:
        tokens.update(_PLAYWRIGHT_PROFILE_RE.findall(process.command_line))
    return frozenset(tokens)


def _reap_new_playwright_profile_processes(*, preexisting_profiles: frozenset[str]) -> int:
    """Terminate processes tied to Playwright temp profiles created by this command."""
    processes = _process_command_inventory()
    new_profiles = _playwright_profile_tokens(processes) - preexisting_profiles
    if not new_profiles:
        return 0

    killed = 0
    current_pid = os.getpid()
    for process in processes:
        if process.pid == current_pid:
            continue
        if not any(profile in process.command_line for profile in new_profiles):
            continue
        try:
            os.kill(process.pid, signal.SIGTERM)
        except OSError:
            continue
        killed += 1
    return killed


def _compact_failure_context(context: dict[str, object] | None) -> str:
    if not context:
        return ""
    parts: list[str] = []
    for key in sorted(context):
        value = context[key]
        if isinstance(value, dict):
            nested = ",".join(f"{nested_key}:{nested_value}" for nested_key, nested_value in sorted(value.items()))
            parts.append(f"{key}={{" + nested + "}")
            continue
        parts.append(f"{key}={value}")
    return ";".join(parts)


@filed_app.command("list", help=tr("cli.app.live.filed.list_help"))
def filed_list_cmd(
    ctx: typer.Context,
    modelo: Annotated[str | None, typer.Option("--modelo", help=tr("cli.app.live.modelo_help"))] = None,
    year_from: Annotated[
        int | None,
        typer.Option("--from-year", min=2000, max=2099, help=tr("cli.app.live.from_year_help")),
    ] = None,
    year_to: Annotated[
        int | None,
        typer.Option("--to-year", min=2000, max=2099, help=tr("cli.app.live.to_year_help")),
    ] = None,
) -> None:
    """List filed-declaration rows without downloading justificantes or submitted files.

    All filters are optional refinements. When ``--modelo`` is omitted the
    listing iterates every modelo configured in the registry. When
    ``--from-year`` / ``--to-year`` are omitted they default to the current
    calendar year.
    """
    from datetime import date as _date

    from ...core.resources import resources

    resolved_from = year_from if year_from is not None else _date.today().year
    resolved_to = year_to if year_to is not None else _date.today().year
    modelos = tuple(str(m.id) for m in resources().modelos.all()) if modelo is None else (modelo,)
    all_rows: list[FiledDataListingRow] = []
    failures: list[FiledDataCaptureFailureRow] = []
    total_count = 0
    _emit_live_auth_preflight()
    for code in modelos:
        try:
            report = asyncio.run(
                list_filed_data(
                    modelo=code,
                    year_from=resolved_from,
                    year_to=resolved_to,
                ),
            )
        except Exception as exc:
            if modelo is not None:
                raise
            failures.append(filed_data_capture_failure_row(modelo=code, year=resolved_to, error=exc))
            continue
        total_count += report.row_count
        all_rows.extend(report.rows)
    result, lines = _filed_list_result_and_lines(
        modelo_filter=modelo,
        year_from=resolved_from,
        year_to=resolved_to,
        row_count=total_count,
        rows=all_rows,
        failures=failures,
    )
    _emit_envelope(ctx, command="app.live.filed.list", result=result, lines=lines)


def _filed_list_result_and_lines(
    *,
    modelo_filter: str | None,
    year_from: int,
    year_to: int,
    row_count: int,
    rows: Sequence[FiledDataListingRow],
    failures: Sequence[FiledDataCaptureFailureRow],
) -> tuple[Any, tuple[str, ...]]:
    from ._app_live_payloads import FiledCaptureFailurePayload, FiledListingRowPayload, FiledListResult

    lines = [_metric_line("row_count", row_count), _metric_line("failed_count", len(failures))]
    for row in rows:
        lines.append(
            _metric_line(
                "row",
                "\t".join(
                    (
                        row.modelo,
                        str(row.year),
                        row.period.registry_token,
                        row.expediente_id,
                        row.status,
                        row.presented_at.isoformat(),
                        f"submitted_file={row.has_submitted_file}",
                        f"declaration_copy={row.has_declaration_copy}",
                        f"justificante={row.has_justificante}",
                    ),
                ),
            ),
        )
    lines.extend(
        _metric_line(
            "failure",
            "\t".join(
                (
                    failure.modelo,
                    str(failure.year),
                    failure.period.registry_token if failure.period is not None else "",
                    failure.expediente_id or "",
                    failure.error_type,
                    failure.message,
                ),
            ),
        )
        for failure in failures
    )
    result = FiledListResult(
        modelo_filter=modelo_filter,
        year_from=year_from,
        year_to=year_to,
        row_count=row_count,
        failed_count=len(failures),
        rows=[
            FiledListingRowPayload(
                modelo=row.modelo,
                year=row.year,
                period=row.period.registry_token,
                expediente_id=row.expediente_id,
                status=row.status,
                presented_at=row.presented_at.isoformat(),
                has_submitted_file=row.has_submitted_file,
                has_declaration_copy=row.has_declaration_copy,
                has_justificante=row.has_justificante,
            )
            for row in rows
        ],
        failures=[
            FiledCaptureFailurePayload(
                modelo=failure.modelo,
                year=failure.year,
                period=failure.period.registry_token if failure.period is not None else None,
                expediente_id=failure.expediente_id,
                error_type=failure.error_type,
                message=failure.message,
            )
            for failure in failures
        ],
    )
    return result, tuple(lines)


@filed_app.command("pull", help=tr("cli.app.live.filed.pull_help"))
def filed_capture_cmd(
    ctx: typer.Context,
    modelos: Annotated[
        list[str] | None,
        typer.Option(
            "--modelo",
            help=tr(
                "cli.app.live.filed.pull_modelo_help",
                default="Modelo code to include. Repeat or omit with --from-year/--to-year for a bulk pull.",
            ),
        ),
    ] = None,
    year: Annotated[int | None, typer.Option("--year", min=2000, max=2099, help=tr("cli.app.live.year_help"))] = None,
    year_from: Annotated[
        int | None,
        typer.Option("--from-year", min=2000, max=2099, help=tr("cli.app.live.from_year_help")),
    ] = None,
    year_to: Annotated[
        int | None,
        typer.Option("--to-year", min=2000, max=2099, help=tr("cli.app.live.to_year_help")),
    ] = None,
    output_root: Annotated[
        Path,
        typer.Option(
            "--output-root",
            file_okay=False,
            dir_okay=True,
            writable=True,
            help=tr("cli.app.live.output_root_help"),
        ),
    ] = Path("var/aeat/filed-declarations"),
    period: Annotated[str | None, typer.Option("--period", help=tr("cli.app.live.period_help"))] = None,
    expediente_id: Annotated[str | None, typer.Option("--expediente", help=tr("cli.app.live.expediente_help"))] = None,
    limit: Annotated[int | None, typer.Option("--limit", min=1, help=tr("cli.app.live.limit_help"))] = None,
) -> None:
    """Capture filed-declaration data from the authenticated AEAT register."""
    from ._app_live_payloads import FiledCaptureFailurePayload, FiledCaptureResult

    _emit_live_auth_preflight()
    selected_modelos = tuple(modelos or ())
    single_mode = (
        len(selected_modelos) == 1
        and year is not None
        and year_from is None
        and year_to is None
    )
    if single_mode:
        resolved_period = _live_period_option(period, year=year)
        report = asyncio.run(
            capture_filed_data(
                modelo=selected_modelos[0],
                year=year,
                output_root=output_root,
                period=resolved_period,
                expediente_id=expediente_id,
                limit=limit,
            ),
        )
        lines = (
            _metric_line("captured_count", report.captured_count),
            _metric_line("casilla_count", report.casilla_count),
            _metric_line("calculation_observation_count", report.calculation_observation_count),
            _metric_line("calculation_observation_keys", ",".join(report.calculation_observation_keys)),
            _metric_line("observation_paths", ",".join(report.observation_paths)),
            _metric_line("artefact_refs", ",".join(report.artefact_refs)),
        )
        result = FiledCaptureResult(
            output_root=report.output_root,
            modelo=report.modelo,
            year=report.year,
            captured_count=report.captured_count,
            observation_paths=list(report.observation_paths),
            artefact_refs=list(report.artefact_refs),
            casilla_count=report.casilla_count,
            calculation_observation_count=report.calculation_observation_count,
            calculation_observation_keys=list(report.calculation_observation_keys),
        )
        _emit_envelope(ctx, command="app.live.filed.pull", result=result, lines=lines)
        return

    if period is not None or expediente_id is not None or limit is not None:
        raise typer.BadParameter("--period, --expediente, and --limit are only valid for one --modelo with --year")
    resolved_from, resolved_to = _resolve_pull_year_range(year=year, year_from=year_from, year_to=year_to)
    report = asyncio.run(
        capture_filed_data_bulk(
            year_from=resolved_from,
            year_to=resolved_to,
            output_root=output_root,
            modelos=selected_modelos or None,
        ),
    )
    lines = (
        _metric_line("modelo_count", len(report.modelos)),
        _metric_line("year_from", report.year_from),
        _metric_line("year_to", report.year_to),
        _metric_line("captured_count", report.captured_count),
        _metric_line("failed_count", report.failed_count),
        _metric_line("casilla_count", report.casilla_count),
        _metric_line("calculation_observation_count", report.calculation_observation_count),
        _metric_line("calculation_observation_keys", ",".join(report.calculation_observation_keys)),
        _metric_line("observation_paths", ",".join(report.observation_paths)),
        _metric_line("artefact_refs", ",".join(report.artefact_refs)),
        *(
            _metric_line(
                "failure",
                "\t".join(
                    (
                        failure.modelo,
                        str(failure.year),
                        failure.period.registry_token if failure.period is not None else "",
                        failure.expediente_id or "",
                        failure.error_type,
                        failure.message,
                    ),
                ),
            )
            for failure in report.failures
        ),
    )
    result = FiledCaptureResult(
        mode="bulk",
        output_root=report.output_root,
        modelos=list(report.modelos),
        year_from=report.year_from,
        year_to=report.year_to,
        captured_count=report.captured_count,
        failed_count=report.failed_count,
        observation_paths=list(report.observation_paths),
        artefact_refs=list(report.artefact_refs),
        casilla_count=report.casilla_count,
        calculation_observation_count=report.calculation_observation_count,
        calculation_observation_keys=list(report.calculation_observation_keys),
        failures=[
            FiledCaptureFailurePayload(
                modelo=failure.modelo,
                year=failure.year,
                period=failure.period.registry_token if failure.period is not None else None,
                expediente_id=failure.expediente_id,
                error_type=failure.error_type,
                message=failure.message,
            )
            for failure in report.failures
        ],
    )
    _emit_envelope(ctx, command="app.live.filed.pull", result=result, lines=lines)


@filed_app.command("pull-sources", help=tr("cli.app.live.filed.pull_sources_help"))
def filed_capture_sources_cmd(
    ctx: typer.Context,
    modelo: Annotated[str, typer.Option("--modelo", help=tr("cli.app.live.modelo_help"))],
    year: Annotated[int, typer.Option("--year", min=2000, max=2099, help=tr("cli.app.live.year_help"))],
    period: Annotated[str, typer.Option("--period", help=tr("cli.app.live.period_help"))],
    output_root: Annotated[
        Path,
        typer.Option(
            "--output-root",
            file_okay=False,
            dir_okay=True,
            writable=True,
            help=tr("cli.app.live.output_root_help"),
        ),
    ] = Path("var/aeat/filed-declarations"),
    registry_root: Annotated[
        Path | None,
        typer.Option(
            "--registry-root",
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.app.live.registry_root_help"),
        ),
    ] = None,
    source_root: Annotated[
        Path | None,
        typer.Option(
            "--source-root",
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.app.live.source_root_help"),
        ),
    ] = None,
) -> None:
    """Capture filed observations required by a target filing's dependencies."""
    from ._app_live_payloads import FiledCaptureSourcesResult

    _emit_live_auth_preflight()
    report = asyncio.run(
        capture_source_filed_data(
            modelo=modelo,
            year=year,
            period=_required_live_period_option(period, year=year),
            output_root=output_root,
            registry_root=registry_root,
            source_root=source_root,
        ),
    )
    lines = (
        _metric_line("captured_count", report.captured_count),
        _metric_line("casilla_count", report.casilla_count),
        _metric_line("calculation_observation_count", report.calculation_observation_count),
        _metric_line("calculation_observation_keys", ",".join(report.calculation_observation_keys)),
        _metric_line("observation_paths", ",".join(report.observation_paths)),
        _metric_line("artefact_refs", ",".join(report.artefact_refs)),
    )
    result = FiledCaptureSourcesResult(
        output_root=report.output_root,
        target_modelo=report.target_modelo,
        target_year=report.target_year,
        target_period=report.target_period,
        captured_count=report.captured_count,
        observation_paths=list(report.observation_paths),
        artefact_refs=list(report.artefact_refs),
        casilla_count=report.casilla_count,
        calculation_observation_count=report.calculation_observation_count,
        calculation_observation_keys=list(report.calculation_observation_keys),
    )
    _emit_envelope(ctx, command="app.live.filed.pull_sources", result=result, lines=lines)


def _active_bucket_id() -> str:
    from ...core import require_active_bucket_id

    try:
        return require_active_bucket_id()
    except Exception as exc:
        raise typer.BadParameter(tr("cli.config.errors.no_active_profile")) from exc


register_notifications_commands(app, active_bucket_id=_active_bucket_id, auth_preflight=_emit_live_auth_preflight)


# ─────────────────────────────────────────────────────────────────────────

register_portals_commands(app)


register_expedientes_commands(app, active_bucket_id=_active_bucket_id, auth_preflight=_emit_live_auth_preflight)


register_justificante_commands(app, active_bucket_id=_active_bucket_id, auth_preflight=_emit_live_auth_preflight)


register_verify_commands(app, active_bucket_id=_active_bucket_id, verify_expected=_verify_expected)


register_borrador_commands(app, active_bucket_id=_active_bucket_id)


__all__ = [
    "app",
    "borrador_100_app",
    "borrador_app",
    "expedientes_app",
    "filed_app",
    "filed_capture_cmd",
    "filed_capture_sources_cmd",
    "filed_list_cmd",
    "iva_wallet_app",
    "iva_wallet_capture_history_cmd",
    "iva_wallet_capture_remote_state_cmd",
    "iva_wallet_history_cmd",
    "iva_wallet_pull_cmd",
    "justificante_app",
    "notifications_app",
    "portals_app",
    "portals_list",
    "portals_show",
    "verify_app",
]
