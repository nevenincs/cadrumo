"""Explicit read-only AEAT live observation CLI commands.

This module wires filed-declaration commands through :func:`list_filed_data`,
:func:`list_filed_data_bulk`, :func:`capture_filed_data`,
:func:`capture_filed_data_bulk`, and :func:`capture_source_filed_data`; it also
delegates IVA-wallet and subgroup command families to live application services.
It emits graph-declared payload schemas such as :class:`FiledListResult`,
:class:`FiledCaptureResult`, and :class:`FiledCaptureSourcesResult` through
:func:`_emit_envelope`. The commands collect or render local evidence only; live
submission, payment, acknowledgement, and representative write actions remain
outside this CLI surface.

The filed-declaration commands resolve the operator's :class:`TaxpayerProfile`
and pass it to the application layer, because which modelos a filer is even
asked about is a property of their declared profile rather than of the command.
"""

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
from typing import TYPE_CHECKING, Any, Final

import typer

from ...adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from ...application.live import (
    BulkFiledDataCaptureReport,
    FiledCasillaSkipRow,
    FiledDataCaptureFailureRow,
    FiledDataCaptureReport,
    FiledDataListingRow,
    FiledHistoryDiscoveryReport,
    FiledHistoryOnboardingRun,
    IvaCompensationHistoryReport,
    IvaRemoteStateAcquisitionReport,
    IvaWalletCaptureReport,
    SourceFiledDataCaptureReport,
    capture_filed_data,
    capture_filed_data_bulk,
    capture_source_filed_data,
    discover_filed_history,
    expected_but_not_found_notice,
    found_more_than_expected_notices,
    list_filed_data,
    list_filed_data_bulk,
    pull_filed_history,
)
from ...core import Period, PeriodError
from ...core.errors import CadrumoError
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.iva_compensation import IvaCompensationDecisionReason
from ._app_live_auth_preflight import _emit_live_auth_preflight
from ._app_live_rendering import _filed_capture_lines, _metric_line, _source_filed_capture_lines
from ._common import (
    _emit_envelope,
    notice_lines,
    resolve_optional_root,
    resolve_pull_year_range,
)

if TYPE_CHECKING:
    from ...application.live import VerifyVerdict
    from ...domain.deadlines import TaxpayerProfile


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


_IVA_WALLET_LIVE_SAFETY_LINES = (
    _metric_line("safety_policy", "read_only_fail_closed"),
    _metric_line("representation_gate_policy", "own_name_only_no_represented_taxpayer_choice"),
    _metric_line(
        "aeat_form_submission_policy",
        "wallet_execute_read_query_only_no_filing_or_represented_taxpayer_data",
    ),
)


def iva_wallet_pull_cmd(
    ctx: typer.Context,
    year: int,
    period: str,
    taxpayer_nif: str | None = None,
) -> None:
    """Pull the authenticated AEAT IVA wallet into an :class:`IvaWalletCaptureReport`.

    Delegates to :func:`capture_iva_compensation_wallet` and emits
    :class:`IvaWalletPullResult`. The command can trigger the configured
    authentication provider, including Cl@ve Móvil manual approval, but the only
    remote action is the guarded wallet read query; reconciliation and blocking
    decisions are profile-local evidence.
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


def iva_wallet_history_cmd(
    ctx: typer.Context,
    as_of_year: int | None = None,
) -> None:
    """List stored :class:`IvaCompensationHistoryReport` evidence.

    Delegates to :func:`list_iva_compensation_history` and emits
    :class:`IvaWalletHistoryResult`. This local-only read reloads compensation
    history, carry-forward lots, and wallet authority decisions from secure
    profile storage without contacting AEAT.
    """
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
                provenance=row.provenance,
                register_status=row.register_status,
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
                reason_identity=decision.reason_identity.value,
                reason=_iva_wallet_decision_reason_text(decision.reason_identity),
                operator_explanation=decision.operator_explanation,
                wallet_captured_at=decision.wallet_captured_at,
                decided_at=decision.decided_at,
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
                        f"provenance={row.provenance.value}",
                        f"register_status={row.register_status or ''}",
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
        wallet_captured_at = decision.wallet_captured_at.isoformat() if decision.wallet_captured_at else None
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
                        f"reason_identity={decision.reason_identity.value}",
                        f"reason={_iva_wallet_decision_reason_text(decision.reason_identity)}",
                        f"operator_explanation={decision.operator_explanation}",
                        f"wallet_captured_at={wallet_captured_at}",
                        f"decided_at={decision.decided_at.isoformat()}",
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


_IVA_WALLET_DECISION_REASON_LOCALE_KEYS: Final[dict[IvaCompensationDecisionReason, str]] = {
    IvaCompensationDecisionReason.TAXPAYER_OVERRIDE: "application.iva_wallet.decision_reason.taxpayer_override",
    IvaCompensationDecisionReason.FIRST_PERIOD_ZERO_AEAT_WALLET: (
        "application.iva_wallet.decision_reason.first_period_zero_aeat_wallet"
    ),
    IvaCompensationDecisionReason.FIRST_PERIOD_ZERO_ACTIVITY_START_UNCONTRASTED: (
        "application.iva_wallet.decision_reason.first_period_zero_activity_start_uncontrasted"
    ),
    IvaCompensationDecisionReason.FIRST_PERIOD_ZERO_LOCAL_RECURRENCE: (
        "application.iva_wallet.decision_reason.first_period_zero_local_recurrence"
    ),
    IvaCompensationDecisionReason.LOCAL_EVIDENCE_UNREADABLE: (
        "application.iva_wallet.decision_reason.local_evidence_unreadable"
    ),
    IvaCompensationDecisionReason.NO_USABLE_AUTHORITY: "application.iva_wallet.decision_reason.no_usable_authority",
    IvaCompensationDecisionReason.FILED_HISTORY_ZERO: "application.iva_wallet.decision_reason.filed_history_zero",
    IvaCompensationDecisionReason.FILED_HISTORY_REQUIRES_OVERRIDE: (
        "application.iva_wallet.decision_reason.filed_history_requires_override"
    ),
    IvaCompensationDecisionReason.LOCAL_RECURRENCE_ZERO: "application.iva_wallet.decision_reason.local_recurrence_zero",
    IvaCompensationDecisionReason.LOCAL_RECURRENCE_REQUIRES_OVERRIDE: (
        "application.iva_wallet.decision_reason.local_recurrence_requires_override"
    ),
    IvaCompensationDecisionReason.STALE_WALLET_NO_LOCAL_RECURRENCE: (
        "application.iva_wallet.decision_reason.stale_wallet_no_local_recurrence"
    ),
    IvaCompensationDecisionReason.STALE_WALLET_LOCAL_RECURRENCE_REQUIRES_OVERRIDE: (
        "application.iva_wallet.decision_reason.stale_wallet_local_recurrence_requires_override"
    ),
    IvaCompensationDecisionReason.WALLET_LOCAL_RECURRENCE_DIVERGENCE: (
        "application.iva_wallet.decision_reason.wallet_local_recurrence_divergence"
    ),
    IvaCompensationDecisionReason.AEAT_WALLET_VALIDATED: "application.iva_wallet.decision_reason.aeat_wallet_validated",
    IvaCompensationDecisionReason.AEAT_WALLET_UNCROSSCHECKED: (
        "application.iva_wallet.decision_reason.aeat_wallet_uncrosschecked"
    ),
    IvaCompensationDecisionReason.CALLER_ZERO_MATCHES_LOCAL_AUTHORITY: (
        "application.iva_wallet.decision_reason.caller_zero_matches_local_authority"
    ),
}


def _iva_wallet_decision_reason_text(reason: IvaCompensationDecisionReason) -> str:
    """Localize one closed decision-reason identity for operator output."""
    try:
        translation_key = _IVA_WALLET_DECISION_REASON_LOCALE_KEYS[reason]
    except KeyError as exc:
        raise AssertionError(f"unhandled IVA wallet decision reason {reason!r}") from exc
    return tr(translation_key)


def iva_wallet_pull_history_cmd(
    ctx: typer.Context,
    year_from: int,
    year_to: int,
    output_root: Path | None = None,
) -> None:
    """Pull Modelo 303 filed history into an :class:`IvaCompensationHistoryCaptureReport`.

    Delegates to :func:`capture_iva_compensation_history` and emits
    :class:`IvaWalletCaptureHistoryResult`. The live read captures filed-history
    evidence, promotes calculation observations, then verifies the secure
    profile-local reload count. It does not query the wallet/cartera surface or
    submit AEAT form choices.
    """
    from ...application.live import capture_iva_compensation_history
    from ...core.config import load_settings

    _emit_live_auth_preflight()
    report = asyncio.run(
        capture_iva_compensation_history(
            year_from=year_from,
            year_to=year_to,
            output_root=resolve_optional_root(
                output_root,
                lambda: load_settings().cadrumo_iva_compensation_history_dir,
            ),
        ),
    )
    lines = (
        *_IVA_WALLET_LIVE_SAFETY_LINES,
        _metric_line("year_from", report.year_from),
        _metric_line("year_to", report.year_to),
        _metric_line("captured_count", report.captured_count),
        _metric_line("calculation_observation_count", report.calculation_observation_count),
        _metric_line("reloaded_history_count", report.reloaded_history_count),
        _metric_line("failed_declaration_count", report.failed_declaration_count),
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
        casilla_count=report.casilla_count,
        observation_paths=list(report.observation_paths),
        artefact_refs=list(report.artefact_refs),
        calculation_observation_keys=list(report.calculation_observation_keys),
        failed_declaration_count=report.failed_declaration_count,
        failed_declarations=list(report.failed_declarations),
    )
    _emit_envelope(ctx, command="app.live.iva_wallet.pull_history", result=result, lines=lines)


def iva_wallet_pull_evidence_cmd(
    ctx: typer.Context,
    year_from: int,
    year_to: int,
    target_year: int,
    target_period: str,
    taxpayer_nif: str | None = None,
    output_root: Path | None = None,
) -> None:
    """Capture filed-history and wallet/cartera evidence as an IVA remote-state report.

    Delegates to :func:`capture_iva_remote_state`, emits
    :class:`IvaWalletPullEvidenceResult`, returns a redacted
    :class:`IvaRemoteStateAcquisitionReport`, persists a
    :class:`IvaRemoteStateAcquisitionManifest`, and keeps
    :class:`LiveIvaReadOutcome` rows separate per surface. Filed-history evidence
    can therefore survive a wallet/cartera failure and vice versa. The command
    never performs AEAT filing, payment, or representative submission actions.
    """
    from ...application.live import capture_iva_remote_state
    from ...core.config import load_settings

    resolved_target_period = _required_live_period_option(target_period, year=target_year)
    _emit_live_auth_preflight()
    report = asyncio.run(
        _run_live_iva_evidence_pull_command(
            capture_iva_remote_state(
                year_from=year_from,
                year_to=year_to,
                target_year=target_year,
                target_period=resolved_target_period,
                taxpayer_nif=taxpayer_nif,
                output_root=resolve_optional_root(output_root, lambda: load_settings().cadrumo_iva_read_evidence_dir),
            ),
            timeout_ms=_live_iva_evidence_pull_command_timeout_ms(year_from=year_from, year_to=year_to),
        ),
    )
    from ._app_live_payloads import (
        IvaWalletPullEvidenceResult,
        LiveIvaAuthOutcomePayload,
        LiveIvaSurfaceOutcomePayload,
    )

    result = IvaWalletPullEvidenceResult(
        output_root=report.output_root,
        year_from=report.year_from,
        year_to=report.year_to,
        target_year=report.target_year,
        target_period=report.target_period,
        acquisition_manifest_id=report.acquisition_manifest_id or "",
        auth=LiveIvaAuthOutcomePayload(
            status=report.auth.status,
            outcome_mode=report.auth.outcome_mode,
            failure_mode=report.auth.failure_mode,
            failure_type=report.auth.failure_type,
            diagnostic_ref=report.auth.diagnostic_ref,
            provider_kind=report.auth.provider_kind,
            reused_persisted_session=report.auth.reused_persisted_session,
            fresh=report.auth.fresh,
        ),
        filed_history_succeeded=report.filed_history_succeeded,
        wallet_succeeded=report.wallet_succeeded,
        outcomes=[
            LiveIvaSurfaceOutcomePayload(
                surface=outcome.surface,
                status=outcome.status,
                outcome_mode=outcome.outcome_mode,
                failure_mode=outcome.failure_mode,
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
        command="app.live.iva_wallet.pull_evidence",
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


async def _run_live_iva_evidence_pull_command[T](
    awaitable: Awaitable[T],
    *,
    timeout_ms: int | None = None,
) -> T:
    """Run the combined IVA evidence pull under a CLI-level watchdog."""
    from ...application.live import LiveIvaReadSurface, LiveIvaSurfaceTimeoutError
    from ...core.config import load_settings

    resolved_timeout_ms = (
        timeout_ms if timeout_ms is not None else load_settings().cadrumo_live_iva_cli_watchdog_timeout_ms
    )
    baseline_inventory = _process_command_inventory()
    # None (not an empty set) when the process table could not be read, so the
    # reaper can refuse to kill rather than treat every browser as newly ours.
    preexisting_profiles = None if baseline_inventory is None else _playwright_profile_tokens(baseline_inventory)
    pre_timeout_auth_context = _live_iva_auth_watchdog_context(stage="before")
    try:
        return await asyncio.wait_for(awaitable, timeout=resolved_timeout_ms / 1000)
    except TimeoutError as exc:
        killed_processes, inventory_available = _reap_new_playwright_profile_processes(
            preexisting_profiles=preexisting_profiles,
        )
        post_timeout_auth_context = _live_iva_auth_watchdog_context(stage="after")
        raise LiveIvaSurfaceTimeoutError(
            f"live IVA evidence pull command did not complete within {resolved_timeout_ms} ms",
            surface="iva_evidence_command",
            timeout_ms=resolved_timeout_ms,
            progress_context={
                "stage": "cli_watchdog",
                "surface": LiveIvaReadSurface.FILED_HISTORY.value,
                "watchdog_reaped_process_count": killed_processes,
                # Without this an operator cannot tell "reaped nothing because
                # there was nothing to reap" from "never managed to look", which
                # are opposite conclusions about whether a browser leaked.
                "watchdog_process_inventory_available": inventory_available,
                **pre_timeout_auth_context,
                **post_timeout_auth_context,
            },
        ) from exc


def _live_iva_evidence_pull_command_timeout_ms(*, year_from: int, year_to: int) -> int:
    """Return the CLI watchdog budget for one combined IVA evidence pull command."""
    from ...core.config import load_settings

    settings = load_settings()
    year_count = max(1, year_to - year_from + 1)
    filed_history_budget_ms = settings.cadrumo_live_iva_surface_timeout_ms * year_count
    wallet_budget_ms = settings.cadrumo_live_iva_surface_timeout_ms
    auth_budget_ms = settings.cadrumo_clave_movil_timeout_ms
    cleanup_budget_ms = settings.cadrumo_live_iva_cli_watchdog_timeout_ms
    return max(
        settings.cadrumo_live_iva_cli_watchdog_timeout_ms,
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
#: Budget for ONE OS process-table read.
#:
#: Derived from measurement, not guessed, and the measurement is bimodal. On
#: Windows the read shells out to PowerShell running ``Get-CimInstance
#: Win32_Process``, which costs 1.1-2.0s once the CIM subsystem is WARM but was
#: measured at 30.3s on a COLD first query -- the assemblies and the WMI service
#: have to spin up, and a machine with ~1000 processes makes that first
#: enumeration expensive. The former 2s budget did not even cover the warm case
#: with headroom, and never had a chance at the cold one.
#:
#: That mattered because the expiry is swallowed (see
#: :func:`_process_command_inventory`): the watchdog silently reaped nothing and
#: reported "0 processes", so a leaked headless browser and its profile
#: directory survived unnoticed. The cold path is the LIKELY one in production --
#: this runs once, after a live pull has already timed out, often as the first
#: CIM query of the session.
#:
#: 60s is roughly twice the worst observed cold read. Two reads at this bound
#: stay inside the cleanup phase's own configured ceiling,
#: ``cadrumo_live_iva_cli_watchdog_timeout_ms`` (240s by default). The cleanup
#: path runs only after the operation has ALREADY failed, so a slower error path
#: is far cheaper than leaking a browser -- and if even this bound expires, the
#: caller is now TOLD rather than shown a misleading zero.
_PROCESS_INVENTORY_TIMEOUT_SECONDS = 60


def _process_command_inventory() -> tuple[_ProcessCommand, ...] | None:
    """Return local process command lines for watchdog cleanup.

    Returns ``None`` when the OS process table could NOT be inspected (the
    helper is missing, the query timed out, or its output did not parse) --
    deliberately distinct from an empty tuple, which asserts that the table WAS
    read and held nothing of interest. Collapsing the two is what let the
    watchdog report "reaped 0" when the truth was "never managed to look", and
    it is what made a failed baseline read look like "no pre-existing browsers",
    which would have licensed the reaper to kill processes it never created.
    """
    try:
        if platform.system() == "Windows":
            powershell = shutil.which("powershell") or shutil.which("pwsh")
            if powershell is None:
                return None
            script = "Get-CimInstance Win32_Process | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
            completed = subprocess.run(  # noqa: S603 - executable resolved with shutil.which; argv is fixed
                [powershell, "-NoProfile", "-Command", script],
                check=True,
                capture_output=True,
                timeout=_PROCESS_INVENTORY_TIMEOUT_SECONDS,
            )
            payload = completed.stdout.decode("utf-8", errors="replace").strip()
            if not payload:
                # Win32_Process can never legitimately be empty -- there is always
                # at least this process -- so empty output means the query failed.
                return None
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
            return None
        completed = subprocess.run(  # noqa: S603 - executable resolved with shutil.which; argv is fixed
            [ps, "-axo", "pid=,args="],
            check=True,
            capture_output=True,
            text=True,
            timeout=_PROCESS_INVENTORY_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None

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


def _reap_new_playwright_profile_processes(*, preexisting_profiles: frozenset[str] | None) -> tuple[int, bool]:
    """Terminate processes tied to Playwright temp profiles created by this command.

    Returns ``(killed, inventory_available)``. ``inventory_available`` is
    ``False`` when the process table could not be read either now or when the
    baseline was taken; the caller must not read a ``0`` count in that case as
    "there was nothing to reap".

    Reaping is fail-safe on a missing baseline: without the set of profiles that
    already existed before this command ran, every profile on the machine looks
    new, and reaping them would SIGTERM browsers this command never created --
    including a concurrent operator's. When the baseline is unknown this returns
    without killing anything, leaving the honest signal to the caller.
    """
    if preexisting_profiles is None:
        return 0, False
    processes = _process_command_inventory()
    if processes is None:
        return 0, False
    new_profiles = _playwright_profile_tokens(processes) - preexisting_profiles
    if not new_profiles:
        return 0, True

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
    return killed, True


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


def filed_list_cmd(
    ctx: typer.Context,
    modelo: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> None:
    """List :class:`FiledDataListingRow` register rows.

    The command reads AEAT's declaration register and emits
    :class:`FiledListResult` without downloading justificantes, submitted files,
    or declaration-copy artefacts. Single-modelo reads delegate to
    :func:`list_filed_data`; omitted ``--modelo`` uses :func:`list_filed_data_bulk`
    across every registry-configured modelo. Omitted year bounds default to the
    current calendar year.
    """
    from ...core.time import today_madrid

    resolved_from = year_from if year_from is not None else today_madrid().year
    resolved_to = year_to if year_to is not None else today_madrid().year
    _emit_live_auth_preflight()
    if modelo is None:
        bulk_report = asyncio.run(
            list_filed_data_bulk(
                year_from=resolved_from,
                year_to=resolved_to,
            ),
        )
        rows = bulk_report.rows
        failures = bulk_report.failures
        total_count = bulk_report.row_count
    else:
        report = asyncio.run(
            list_filed_data(
                modelo=modelo,
                year_from=resolved_from,
                year_to=resolved_to,
            ),
        )
        rows = report.rows
        failures = ()
        total_count = report.row_count
    result, lines = _filed_list_result_and_lines(
        modelo_filter=modelo,
        year_from=resolved_from,
        year_to=resolved_to,
        row_count=total_count,
        rows=rows,
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


def filed_discover_cmd(ctx: typer.Context) -> None:
    """Report which ``(modelo, ejercicio)`` pairs a history pull would walk.

    Reads the declaraciones register's own modelo and ejercicio option lists and
    unions them with the grid the active taxpayer's declared profile facts expect,
    tagging every pair with the signal(s) that nominated it. Nothing is captured
    and nothing is persisted, which is why the verb is ``discover`` rather than
    ``pull``.

    The two signals are reported separately on purpose. A pair the profile
    expected is a real expectation; a pair only the register offered is not, and
    the accompanying caveat notice says so rather than leaving the operator to
    read one number as though both signals meant the same thing.
    """
    profile = _active_taxpayer_profile_or_none()
    report = asyncio.run(discover_filed_history(profile=profile))
    result, lines = _filed_discover_result_and_lines(report)
    _emit_envelope(
        ctx,
        command="app.live.filed.discover",
        result=result,
        lines=lines,
        notices=_filed_discover_notices(report),
    )


def _active_taxpayer_profile_or_none() -> TaxpayerProfile | None:
    """Return the active taxpayer profile, or ``None`` when setup has not produced one.

    Discovery is useful before a profile is complete -- the register-options read
    needs no profile at all -- so a missing profile downgrades the report rather
    than refusing the verb. What it must NOT do is silently look like a complete
    answer, which is what the caveat notices exist to prevent.
    """
    from ...application.wizard import load_active_taxpayer_profile
    from ...application.workflow import workflow_state_repository

    try:
        return load_active_taxpayer_profile(workflow_state_repository().load())
    except CadrumoError:
        return None


def _filed_discover_result_and_lines(report: FiledHistoryDiscoveryReport) -> tuple[Any, tuple[str, ...]]:
    from ._app_live_payloads import FiledDiscoverResult, FiledHistoryDiscoveryPairPayload

    lines = [
        _metric_line("pair_count", len(report.pairs)),
        _metric_line("profile_expected_count", len(report.profile_expected_pairs)),
        _metric_line("register_options_only_count", len(report.register_options_only_pairs)),
    ]
    lines.extend(
        _metric_line(
            "pair",
            "\t".join(
                (
                    pair.modelo,
                    str(pair.ejercicio),
                    ",".join(signal.value for signal in pair.signals),
                    f"anomaly_if_empty={pair.zero_rows_is_an_anomaly}",
                ),
            ),
        )
        for pair in report.pairs
    )
    result = FiledDiscoverResult(
        pairs=[
            FiledHistoryDiscoveryPairPayload(
                modelo=pair.modelo,
                ejercicio=pair.ejercicio,
                signals=[signal.value for signal in pair.signals],
                zero_rows_is_an_anomaly=pair.zero_rows_is_an_anomaly,
            )
            for pair in report.pairs
        ],
        pair_count=len(report.pairs),
        profile_expected_count=len(report.profile_expected_pairs),
        register_options_only_count=len(report.register_options_only_pairs),
        profile_year_span_determined=report.profile_year_span_determined,
        register_options_read=report.register_options_read,
        carries_a_taxpayer_specific_denominator=report.carries_a_taxpayer_specific_denominator,
    )
    return result, tuple(lines)


def _filed_discover_notices(report: FiledHistoryDiscoveryReport) -> list[Notice]:
    """Say what each signal does and does not establish, before anything is walked.

    Two notices, because there are two different things an operator can get
    wrong. The first bounds the register's option list, which is the signal whose
    NIF-scoping nobody has confirmed. The second fires only when the report
    carries no taxpayer-specific denominator at all, which is the case where the
    pair count looks like coverage and is not.
    """
    notices = [
        Notice(
            severity=NoticeSeverity.INFO,
            code="live.filed.discover.register_options_scope_unconfirmed",
            message=tr("cli.app.live.filed.discover_register_scope_caveat"),
            context={
                "register_options_only_count": str(len(report.register_options_only_pairs)),
                "register_options_read": str(report.register_options_read),
            },
        ),
    ]
    if not report.carries_a_taxpayer_specific_denominator:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="live.filed.discover.no_taxpayer_specific_denominator",
                message=tr("cli.app.live.filed.discover_no_profile_denominator"),
                context={
                    "profile_year_span_determined": str(report.profile_year_span_determined),
                    "pair_count": str(len(report.pairs)),
                },
            ),
        )
    return notices


def filed_pull_all_cmd(
    ctx: typer.Context,
    output_root: Path | None = None,
    limit: int | None = None,
) -> None:
    """Pull this taxpayer's AEAT history in one sweep and report what it found.

    Sequences discovery, bulk filed capture, IVA wallet reconciliation and the
    notificaciones pull. Partial success is the expected outcome of a long
    authenticated sweep, so each stage is reported separately rather than one
    failure collapsing the run.

    The report carries no completeness percentage. Part of the walked grid comes
    from AEAT's offered option list, whose scoping to this NIF is unconfirmed, so
    a fraction over the grid would read as coverage while resting on a
    denominator that may have nothing to do with this taxpayer; the prose
    denominator note says what was actually measured.
    """
    from ...core.config import load_settings

    profile = _active_taxpayer_profile_or_none()
    resolved_root = resolve_optional_root(output_root, lambda: load_settings().cadrumo_filed_declarations_dir)
    _emit_live_auth_preflight()
    run = asyncio.run(
        pull_filed_history(
            output_root=resolved_root,
            profile=profile,
            limit=limit,
            sync_run_repository=SyncRunRecordRepository(),
        ),
    )
    result, lines = _filed_pull_all_result_and_lines(run)
    notices = _filed_pull_all_notices(run, limit=limit)
    _emit_envelope(
        ctx,
        command="app.live.filed.pull_all",
        result=result,
        lines=(*lines, *notice_lines(notices)),
        notices=notices,
    )


def _filed_pull_all_result_and_lines(run: FiledHistoryOnboardingRun) -> tuple[Any, tuple[str, ...]]:
    from ._app_live_payloads import FiledHistoryOnboardingResult, FiledHistoryPairOutcomePayload

    refused = run.refused_pairs
    empty = run.genuinely_empty_pairs
    lines = [
        _metric_line("pair_count", len(run.pairs)),
        _metric_line("captured_count", run.captured_count),
        _metric_line("reached_count", run.reached_count),
        _metric_line("refused_count", len(refused)),
        _metric_line("empty_count", len(empty)),
        _metric_line("iva_wallet_status", run.iva_wallet_status),
        _metric_line("notificaciones_status", run.notificaciones_status),
        _metric_line("denominator", run.denominator_note),
    ]
    lines.extend(
        _metric_line(
            "pair",
            "\t".join(
                (
                    pair.modelo,
                    str(pair.ejercicio),
                    ",".join(signal.value for signal in pair.signals),
                    f"rows={pair.row_count}",
                    f"refused={pair.refused}",
                ),
            ),
        )
        for pair in run.pairs
    )
    lines.extend(_metric_line("stage_failure", failure) for failure in run.stage_failures)
    result = FiledHistoryOnboardingResult(
        pairs=[
            FiledHistoryPairOutcomePayload(
                modelo=pair.modelo,
                ejercicio=pair.ejercicio,
                signals=[signal.value for signal in pair.signals],
                row_count=pair.row_count,
                captured_count=pair.captured_count,
                refused=pair.refused,
                failure_type=pair.failure_type,
                failure_message=pair.failure_message,
            )
            for pair in run.pairs
        ],
        pair_count=len(run.pairs),
        profile_expected_count=sum(1 for pair in run.pairs if pair.expected_by_profile),
        register_options_only_count=sum(1 for pair in run.pairs if not pair.expected_by_profile),
        refused_count=len(refused),
        empty_count=len(empty),
        captured_count=run.captured_count,
        reached_count=run.reached_count,
        scoping_signal=run.scoping_signal.value,
        denominator_note=run.denominator_note,
        iva_wallet_status=run.iva_wallet_status,
        iva_wallet_divergence=run.iva_wallet_divergence,
        iva_wallet_blocked=run.iva_wallet_blocked,
        notificaciones_status=run.notificaciones_status,
        notificaciones_row_count=run.notificaciones_row_count,
        stage_failures=list(run.stage_failures),
    )
    return result, tuple(lines)


def _limit_reached_notice(reached_count: int, *, limit: int | None) -> Notice | None:
    """Warn when a sweep stopped on its ``--limit`` rather than on running out.

    One authority for every ``--limit``-bearing filed read, because the silence
    is the same defect on each of them: an unwalked pair is indistinguishable
    from one AEAT holds nothing for, which reads as "nothing was filed".

    The predicate is the REACHED tally, never the captured one. ``captured_count``
    is ``len(observation_paths)``, appended only on the write path, so a preview
    leaves it at zero -- ``captured_count >= limit`` would read false exactly when
    a dry run was truncated, staying silent on the one surface where the operator
    has no other signal.
    """
    if limit is None or reached_count < limit:
        return None
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="live.filed.limit_reached",
        message=tr(
            "cli.app.live.filed.limit_reached",
            default=(
                "The sweep stopped at the --limit of {limit} after reaching {reached} declaration(s); "
                "pairs beyond that point were not walked. A missing pair is not evidence that nothing "
                "was filed -- re-run with a higher --limit or none."
            ),
            limit=limit,
            reached=reached_count,
        ),
        context={"limit": str(limit), "reached_count": str(reached_count)},
    )


def _filed_pull_all_notices(run: FiledHistoryOnboardingRun, *, limit: int | None = None) -> list[Notice]:
    """Collect the run's advisories, each from its own authority.

    Assembled rather than re-derived: the expected-but-not-found warning and the
    found-more-than-expected information both live beside the run model, so the
    asymmetry rule and the INFO-not-WARNING judgement are decided once and not
    restated at this transport boundary.
    """
    notices: list[Notice] = []
    # First, because truncation qualifies every advisory below it: a pair the
    # sweep never walked reads as "expected but not found".
    truncation = _limit_reached_notice(run.reached_count, limit=limit)
    if truncation is not None:
        notices.append(truncation)
    missing = expected_but_not_found_notice(run)
    if missing is not None:
        notices.append(missing)
    notices.extend(found_more_than_expected_notices(run))
    if refused := run.refused_pairs:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="live.filed.pull_all.pairs_refused",
                message=tr(
                    "cli.app.live.filed.pull_all_pairs_refused",
                    default=(
                        "{count} modelo/ejercicio pair(s) could not be read and were NOT reported as empty: "
                        "{pairs}. Re-run to retry; a refusal is not evidence that nothing was filed."
                    ),
                    count=len(refused),
                    pairs=", ".join(f"{pair.modelo}/{pair.ejercicio}" for pair in refused),
                ),
                context={
                    "refused_count": str(len(refused)),
                    "pairs": ", ".join(f"{pair.modelo}/{pair.ejercicio}" for pair in refused),
                },
            ),
        )
    # Three advisory sources, ONE channel. The justificante enrolment's typed
    # unreached-evidence reasons ride the same envelope notices list as this run's
    # own two advisories, forwarded verbatim so each of the six reasons stays
    # separately readable -- collapsing them into one "evidence not enrolled"
    # notice would rebuild, one layer up, the uniform silence they exist to undo.
    notices.extend(run.evidence_notices)
    # A re-capture is an unconditional upsert, so a corrected filing replaces
    # values the operator may already have calculated against. These were read
    # before each write, while the prior values still existed; without them the
    # sweep changes history silently.
    notices.extend(run.recapture_notices)
    if not run.carries_a_taxpayer_specific_denominator:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="live.filed.pull_all.no_taxpayer_specific_denominator",
                message=tr("cli.app.live.filed.discover_no_profile_denominator"),
                context={"pair_count": str(len(run.pairs))},
            ),
        )
    return notices


def _filed_capture_notices(
    report: FiledDataCaptureReport | BulkFiledDataCaptureReport | SourceFiledDataCaptureReport,
    *,
    limit: int | None = None,
) -> tuple[Notice, ...]:
    """Return capture-owned advisories for the envelope without touching result payloads.

    The truncation advisory leads, for the same reason it does on the sweep: it
    qualifies every count below it. ``reached_count`` is declared once on the
    tally all three reports share, so this reads the same field whichever report
    arrives.
    """
    truncation = _limit_reached_notice(report.reached_count, limit=limit)
    return ((truncation,) if truncation is not None else ()) + report.evidence_notices


def _emit_single_filed_pull(
    ctx: typer.Context,
    *,
    modelo: str,
    year: int,
    output_root: Path | None,
    period: str | None,
    expediente_id: str | None,
    limit: int | None,
) -> None:
    """Capture and emit one modelo/year filed-declaration report."""
    from ...core.config import load_settings
    from ._app_live_payloads import FiledCaptureResult

    resolved_period = _live_period_option(period, year=year)
    report = asyncio.run(
        capture_filed_data(
            modelo=modelo,
            year=year,
            output_root=resolve_optional_root(output_root, lambda: load_settings().cadrumo_filed_declarations_dir),
            period=resolved_period,
            expediente_id=expediente_id,
            limit=limit,
        ),
    )
    lines = _filed_capture_lines(report, mode="single", modelo=report.modelo, year=report.year)
    result = FiledCaptureResult(
        output_root=report.output_root,
        modelo=report.modelo,
        year=report.year,
        captured_count=report.captured_count,
        observation_paths=list(report.observation_paths),
        artefact_refs=list(report.artefact_refs),
        justificante_metadata_count=report.justificante_metadata_count,
        justificante_csvs=list(report.justificante_csvs),
        filing_evidence_stamped_count=report.filing_evidence_stamped_count,
        filing_record_ids=list(report.filing_record_ids),
        filing_evidence_conflict_count=report.filing_evidence_conflict_count,
        filing_evidence_conflict_record_ids=list(report.filing_evidence_conflict_record_ids),
        casilla_count=report.casilla_count,
        calculation_observation_count=report.calculation_observation_count,
        calculation_observation_keys=list(report.calculation_observation_keys),
    )
    notices = _filed_capture_notices(report, limit=limit)
    _emit_envelope(
        ctx,
        command="app.live.filed.pull",
        result=result,
        lines=(*lines, *notice_lines(notices)),
        notices=notices,
    )


def _emit_bulk_filed_pull(
    ctx: typer.Context,
    *,
    selected_modelos: tuple[str, ...],
    year: int | None,
    year_from: int | None,
    year_to: int | None,
    output_root: Path | None,
    limit: int | None,
    dry_run: bool,
) -> None:
    """Capture and emit a bulk filed-declaration report."""
    from ...core.config import load_settings
    from ._app_live_payloads import FiledCaptureFailurePayload, FiledCaptureResult

    resolved_from, resolved_to = resolve_pull_year_range(year=year, year_from=year_from, year_to=year_to)
    report = asyncio.run(
        capture_filed_data_bulk(
            year_from=resolved_from,
            year_to=resolved_to,
            output_root=resolve_optional_root(output_root, lambda: load_settings().cadrumo_filed_declarations_dir),
            modelos=selected_modelos or None,
            limit=limit,
            dry_run=dry_run,
            sync_run_repository=SyncRunRecordRepository(),
        ),
    )
    lines = _filed_capture_lines(
        report,
        mode="bulk",
        modelos=report.modelos,
        year_from=report.year_from,
        year_to=report.year_to,
        failures=report.failures,
    )
    result = FiledCaptureResult(
        mode="bulk",
        dry_run=report.dry_run,
        output_root=report.output_root,
        modelos=list(report.modelos),
        year_from=report.year_from,
        year_to=report.year_to,
        captured_count=report.captured_count,
        failed_count=report.failed_count,
        observation_paths=list(report.observation_paths),
        artefact_refs=list(report.artefact_refs),
        justificante_metadata_count=report.justificante_metadata_count,
        justificante_csvs=list(report.justificante_csvs),
        filing_evidence_stamped_count=report.filing_evidence_stamped_count,
        filing_record_ids=list(report.filing_record_ids),
        filing_evidence_conflict_count=report.filing_evidence_conflict_count,
        filing_evidence_conflict_record_ids=list(report.filing_evidence_conflict_record_ids),
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
    skipped = _skipped_casilla_notice(report.skipped_casillas)
    capture_notices = _filed_capture_notices(report, limit=limit)
    notices = [*capture_notices]
    # Rebuilt from the notice rather than written twice, so the text line and the
    # JSON notice cannot drift apart.
    if skipped is not None:
        lines = (*lines, skipped.message)
        notices.append(skipped)
    _emit_envelope(
        ctx,
        command="app.live.filed.pull",
        result=result,
        lines=(*lines, *notice_lines(capture_notices)),
        notices=notices,
    )


def filed_pull_cmd(
    ctx: typer.Context,
    modelos: list[str] | None = None,
    year: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    output_root: Path | None = None,
    period: str | None = None,
    expediente_id: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> None:
    """Capture filed-declaration observations through the read-only AEAT register.

    Single-modelo mode delegates to
    :func:`capture_filed_data`; range mode delegates to
    :func:`capture_filed_data_bulk`. Both flows emit :class:`FiledCaptureResult`,
    persist encrypted filed observations and artefact references, register parsed
    justificante metadata when available, and only stamp local
    :class:`ModeloRecord` evidence when an existing current filing record
    matches.
    """
    _emit_live_auth_preflight()
    selected_modelos = tuple(modelos or ())
    if len(selected_modelos) == 1 and year is not None and year_from is None and year_to is None:
        if dry_run:
            # Single-modelo capture has no dry-run path, so accepting the flag here
            # would hand an operator a real write under a flag whose whole promise
            # is leaving no trace. Refused rather than ignored, and rather than
            # extending single mode, which is a different decision.
            raise typer.BadParameter(tr("cli.app.live.filed.pull_dry_run_single_mode_error"))
        _emit_single_filed_pull(
            ctx,
            modelo=selected_modelos[0],
            year=year,
            output_root=output_root,
            period=period,
            expediente_id=expediente_id,
            limit=limit,
        )
        return

    if period is not None or expediente_id is not None:
        raise typer.BadParameter("--period and --expediente are only valid for one --modelo with --year")
    _emit_bulk_filed_pull(
        ctx,
        selected_modelos=selected_modelos,
        year=year,
        year_from=year_from,
        year_to=year_to,
        output_root=output_root,
        limit=limit,
        dry_run=dry_run,
    )


#: Casillas named individually in the not-enrolled notice; the count carries the rest.
_MAX_NOTICED_CASILLAS = 8


def _skipped_casilla_notice(skipped: Sequence[FiledCasillaSkipRow]) -> Notice | None:
    """Tell the operator which casillas of their own return could not be read.

    Returns ``None`` when nothing was skipped, so a clean capture stays quiet.

    The notice names each casilla and its registry label and NEVER its value. On
    Modelo 100 this set includes a referencia catastral and the taxpayer's street
    address; the notice is written to the operator's terminal and into the JSON
    envelope, so the value has no business here. The label says which field was
    skipped, which is what the operator needs to judge whether it mattered.

    The capture SUCCEEDED when this fires. These casillas are ones the filing
    carries that the registry's Decimal-only channel does not accept -- not a
    failure to read the artefact, which is what the failure rows report.
    """
    if not skipped:
        return None
    affected = ", ".join(f"{row.casilla_id} ({row.label})" for row in skipped[:_MAX_NOTICED_CASILLAS])
    if len(skipped) > _MAX_NOTICED_CASILLAS:
        affected += f", and {len(skipped) - _MAX_NOTICED_CASILLAS} more"
    return Notice(
        severity=NoticeSeverity.INFO,
        code="live.filed.pull.casillas_not_enrolled",
        message=tr(
            "cli.app.live.filed.casillas_not_enrolled",
            default=(
                "{count} casilla(s) in the captured filings hold values that are not amounts, "
                "so they were not enrolled as calculation evidence: {affected}. "
                "Everything numeric in those filings was enrolled normally."
            ),
            count=len(skipped),
            affected=affected,
        ),
        context={
            "skipped_casilla_count": str(len(skipped)),
            "casilla_ids": ", ".join(sorted({row.casilla_id for row in skipped})),
            "modelos": ", ".join(sorted({row.modelo for row in skipped})),
        },
    )


def filed_pull_sources_cmd(
    ctx: typer.Context,
    modelo: str,
    year: int,
    period: str,
    output_root: Path | None = None,
    registry_root: Path | None = None,
    source_root: Path | None = None,
) -> None:
    """Capture registry-selected source observations for a target :class:`Period`.

    Delegates to :func:`capture_source_filed_data`, which resolves dependencies
    from a validated registry snapshot before reading prior filed declarations.
    The emitted :class:`FiledCaptureSourcesResult` is local evidence only; the
    command does not submit or mutate AEAT state.
    """
    from ...core.config import load_settings
    from ._app_live_payloads import FiledCaptureSourcesResult

    _emit_live_auth_preflight()
    report = asyncio.run(
        capture_source_filed_data(
            modelo=modelo,
            year=year,
            period=_required_live_period_option(period, year=year),
            output_root=resolve_optional_root(output_root, lambda: load_settings().cadrumo_filed_declarations_dir),
            registry_root=registry_root,
            source_root=source_root,
        ),
    )
    lines = _source_filed_capture_lines(report)
    result = FiledCaptureSourcesResult(
        output_root=report.output_root,
        target_modelo=report.target_modelo,
        target_year=report.target_year,
        target_period=report.target_period,
        captured_count=report.captured_count,
        observation_paths=list(report.observation_paths),
        artefact_refs=list(report.artefact_refs),
        justificante_metadata_count=report.justificante_metadata_count,
        justificante_csvs=list(report.justificante_csvs),
        filing_evidence_stamped_count=report.filing_evidence_stamped_count,
        filing_record_ids=list(report.filing_record_ids),
        filing_evidence_conflict_count=report.filing_evidence_conflict_count,
        filing_evidence_conflict_record_ids=list(report.filing_evidence_conflict_record_ids),
        casilla_count=report.casilla_count,
        calculation_observation_count=report.calculation_observation_count,
        calculation_observation_keys=list(report.calculation_observation_keys),
    )
    notices = _filed_capture_notices(report)
    _emit_envelope(
        ctx,
        command="app.live.filed.pull_sources",
        result=result,
        lines=(*lines, *notice_lines(notices)),
        notices=notices,
    )


# ─────────────────────────────────────────────────────────────────────────


__all__ = [
    "filed_list_cmd",
    "filed_pull_all_cmd",
    "filed_pull_cmd",
    "filed_pull_sources_cmd",
    "iva_wallet_history_cmd",
    "iva_wallet_pull_cmd",
    "iva_wallet_pull_evidence_cmd",
    "iva_wallet_pull_history_cmd",
]
