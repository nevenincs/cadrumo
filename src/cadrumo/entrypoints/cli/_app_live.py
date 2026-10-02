"""Explicit read-only AEAT live observation CLI commands.

Filed-declaration listing, discovery and capture and combined IVA evidence
acquisition use registered profile workers.
It emits graph-declared payload schemas such as :class:`FiledListResult`,
:class:`FiledCaptureResult`, and :class:`FiledCaptureSourcesResult` through
:func:`emit_envelope`. The commands collect or render local evidence only; live
submission, payment, acknowledgement, and representative write actions remain
outside this CLI surface.

The filed-discovery worker resolves the bound :class:`TaxpayerProfile` because
which modelos a filer is asked about follows their declared profile facts.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

import typer

from ...application.live.capture_mode import LiveCaptureMode
from ...application.live.errors import LiveIvaAcquisitionFailureMode
from ...application.live.filed_data import FiledDataListingRow
from ...application.live.filed_data_capture import (
    FiledHistoryDiscoveryReport,
    FiledHistoryOnboardingRun,
    expected_but_not_found_notice,
)
from ...application.live.remote_state_models import (
    BulkFiledDataCaptureReport,
    FiledCasillaSkipRow,
    FiledDataCaptureFailureRow,
    FiledDataCaptureReport,
    IvaCompensationHistoryReport,
    IvaRemoteStateAcquisitionReport,
    IvaWalletCaptureReport,
    SourceFiledDataCaptureReport,
)
from ...application.operator_actions.models import ActionReference
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.period import Period, PeriodError
from ...core.type_guards import is_str_keyed_dict
from ...domain.iva_compensation.reconciliation import IvaCompensationDecisionReason
from ._app_live_auth_preflight import emit_live_auth_preflight, metric_line
from ._app_live_rendering import _filed_capture_lines, _source_filed_capture_lines
from ._filing_chain_payloads import (
    filing_reconciliation_lines,
    filing_reconciliation_notices,
    filing_reconciliation_payload,
)
from .common import (
    emit_envelope,
    notice_lines,
    resolve_notice_action,
    resolve_optional_root,
    resolve_pull_year_range,
)


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
    normalized = str(token or LiveIvaAcquisitionFailureMode.UNKNOWN.value)
    try:
        outcome_mode = LiveIvaAcquisitionFailureMode(normalized)
    except ValueError:
        outcome_mode = LiveIvaAcquisitionFailureMode.UNKNOWN
    return tr(
        f"cli.app.live.iva_wallet.acquisition.outcome.{outcome_mode.value}",
    )


_IVA_WALLET_LIVE_SAFETY_LINES = (
    metric_line("safety_policy", "read_only_fail_closed"),
    metric_line("representation_gate_policy", "own_name_only_no_represented_taxpayer_choice"),
    metric_line(
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

    Delegates to its registered profile worker and emits
    :class:`IvaWalletPullResult`. The command can trigger the configured
    authentication provider, including Cl@ve Móvil manual approval, but the only
    remote action is the guarded wallet read query; reconciliation and blocking
    decisions are profile-local evidence.
    """
    from .runtime_iva_wallet_capture import read_iva_wallet_capture_for_cli

    emit_live_auth_preflight(ctx)
    target_period = _required_live_period_option(period, year=year)
    read = read_iva_wallet_capture_for_cli(
        ctx,
        target_year=year,
        target_period=target_period,
        taxpayer_nif=taxpayer_nif,
    )
    projection = read.projection
    try:
        # The public worker projection carries the period as a bare registry
        # token. Restore the canonical typed period used by this CLI payload.
        report = IvaWalletCaptureReport(
            taxpayer_ref=projection.taxpayer_ref,
            target_year=projection.target_year,
            target_period=Period.from_year_and_code(projection.target_year, projection.target_period),
            observation_path=projection.observation_path,
            decision_key=projection.decision_key,
            row_count=projection.row_count,
            total_pending=projection.total_pending,
            selected_authority=projection.selected_authority,
            selected_amount=projection.selected_amount,
            local_recurrence_amount=projection.local_recurrence_amount,
            divergence=projection.divergence,
            blocked=projection.blocked,
            captured_at=projection.captured_at,
        )
        from ._app_live_iva_wallet_payloads import IvaWalletPullResult

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
        emit_envelope(ctx, command="app.live.iva_wallet.pull", result=result, lines=_iva_wallet_pull_lines(report))
    except Exception:
        from ...application.runtime.contracts import RuntimeRefusalCode
        from .runtime_registered_operation import submitted_operation_error

        completed = read.completion
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None


def _iva_wallet_pull_lines(report: IvaWalletCaptureReport) -> tuple[str, ...]:
    return (
        *_IVA_WALLET_LIVE_SAFETY_LINES,
        *(
            metric_line("taxpayer_ref", report.taxpayer_ref),
            metric_line("target_year", report.target_year),
            metric_line("target_period", report.target_period),
            metric_line("row_count", report.row_count),
            metric_line("total_pending", report.total_pending),
            metric_line("selected_authority", report.selected_authority),
            metric_line("selected_amount", report.selected_amount),
            metric_line("local_recurrence_amount", report.local_recurrence_amount),
            metric_line("divergence", report.divergence),
            metric_line("blocked", report.blocked),
            metric_line("captured_at", report.captured_at.isoformat()),
            metric_line("observation_path", report.observation_path),
        ),
    )


def iva_wallet_history_cmd(
    ctx: typer.Context,
    as_of_year: int | None = None,
) -> None:
    """List stored :class:`IvaCompensationHistoryReport` evidence.

    Delegates to the registered profile worker and emits
    :class:`IvaWalletHistoryResult`. This local-only read reloads compensation
    history, carry-forward lots, and wallet authority decisions from secure
    profile storage without contacting AEAT.
    """
    from .runtime_iva_wallet_history import read_iva_wallet_history_for_cli

    read = read_iva_wallet_history_for_cli(ctx, as_of_year=as_of_year)
    try:
        result = _iva_wallet_history_result(read.report)
        lines = _iva_wallet_history_lines(read.report)
        emit_envelope(ctx, command="app.live.iva_wallet.history", result=result, lines=lines)
    except Exception:
        from ...application.runtime.contracts import RuntimeRefusalCode
        from .runtime_registered_operation import submitted_operation_error

        completed = read.completion
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None


def _iva_wallet_history_result(report: IvaCompensationHistoryReport) -> Any:
    from ._app_live_iva_wallet_payloads import (
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
        metric_line("row_count", report.row_count),
        metric_line("as_of_year", report.as_of_year),
        metric_line("carry_forward_lot_count", report.carry_forward_lot_count),
        metric_line("unallocated_applied_amount", report.unallocated_applied_amount),
        metric_line("authority_decision_count", report.authority_decision_count),
    ]
    for row in report.rows:
        lines.append(
            metric_line(
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
            metric_line(
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
            metric_line(
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
                metric_line(
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

    Delegates to its registered profile worker and emits
    :class:`IvaWalletCaptureHistoryResult`. The live read captures filed-history
    evidence, promotes calculation observations, then verifies the secure
    profile-local reload count. It does not query the wallet/cartera surface or
    submit AEAT form choices.
    """
    from ...core.config import load_settings
    from .runtime_iva_history_capture import read_iva_wallet_history_capture_for_cli

    emit_live_auth_preflight(ctx)
    resolved_root = resolve_optional_root(
        output_root,
        lambda: load_settings().cadrumo_iva_compensation_history_dir,
    )
    read = read_iva_wallet_history_capture_for_cli(
        ctx,
        year_from=year_from,
        year_to=year_to,
        output_root=resolved_root,
    )
    projection = read.projection
    try:
        lines = (
            *_IVA_WALLET_LIVE_SAFETY_LINES,
            metric_line("year_from", projection.year_from),
            metric_line("year_to", projection.year_to),
            metric_line("captured_count", projection.captured_count),
            metric_line("calculation_observation_count", projection.calculation_observation_count),
            metric_line("reloaded_history_count", projection.reloaded_history_count),
            metric_line("failed_declaration_count", projection.failed_declaration_count),
            metric_line("output_root", projection.output_root),
        )
        from ._app_live_iva_wallet_payloads import IvaWalletCaptureHistoryResult

        result = IvaWalletCaptureHistoryResult(
            output_root=projection.output_root,
            year_from=projection.year_from,
            year_to=projection.year_to,
            captured_count=projection.captured_count,
            calculation_observation_count=projection.calculation_observation_count,
            reloaded_history_count=projection.reloaded_history_count,
            casilla_count=projection.casilla_count,
            observation_paths=list(projection.observation_paths),
            artefact_refs=list(projection.artefact_refs),
            calculation_observation_keys=list(projection.calculation_observation_keys),
            failed_declaration_count=projection.failed_declaration_count,
            failed_declarations=list(projection.failed_declarations),
        )
        emit_envelope(ctx, command="app.live.iva_wallet.pull_history", result=result, lines=lines)
    except Exception:
        from ...application.runtime.contracts import RuntimeRefusalCode
        from .runtime_registered_operation import submitted_operation_error

        completed = read.completion
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None


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

    Delegates to its registered profile worker and emits
    :class:`IvaWalletPullEvidenceResult`, returns a redacted
    :class:`IvaRemoteStateAcquisitionReport`, persists a
    :class:`IvaRemoteStateAcquisitionManifest`, and keeps
    :class:`LiveIvaReadOutcome` rows separate per surface. Filed-history evidence
    can therefore survive a wallet/cartera failure and vice versa. The command
    never performs AEAT filing, payment, or representative submission actions.
    """
    from ...core.config import load_settings
    from .runtime_iva_remote_state_capture import read_iva_remote_state_capture_for_cli

    resolved_target_period = _required_live_period_option(target_period, year=target_year)
    emit_live_auth_preflight(ctx)
    resolved_root = resolve_optional_root(output_root, lambda: load_settings().cadrumo_iva_read_evidence_dir)
    read = read_iva_remote_state_capture_for_cli(
        ctx,
        output_root=resolved_root,
        year_from=year_from,
        year_to=year_to,
        target_year=target_year,
        target_period=resolved_target_period,
        taxpayer_nif=taxpayer_nif,
    )
    report = read.report
    try:
        from ._app_live_iva_wallet_payloads import (
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
        emit_envelope(
            ctx,
            command="app.live.iva_wallet.pull_evidence",
            result=result,
            lines=_iva_remote_state_capture_lines(report),
        )
    except Exception:
        from ...application.runtime.contracts import RuntimeRefusalCode
        from .runtime_registered_operation import submitted_operation_error

        completed = read.completion
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None


def _iva_remote_state_capture_lines(report: IvaRemoteStateAcquisitionReport) -> tuple[str, ...]:
    lines = [
        *_IVA_WALLET_LIVE_SAFETY_LINES,
        metric_line("year_from", report.year_from),
        metric_line("year_to", report.year_to),
        metric_line("target_year", report.target_year),
        metric_line("target_period", report.target_period),
        metric_line("acquisition_manifest_id", report.acquisition_manifest_id or ""),
        metric_line("auth_status", report.auth.status.value),
        metric_line("auth_outcome", report.auth.outcome_mode.value),
        metric_line("auth_outcome_label", _live_iva_outcome_label(report.auth.outcome_mode)),
        metric_line("auth_failure_mode", report.auth.failure_mode.value if report.auth.failure_mode else ""),
        metric_line("auth_failure_type", report.auth.failure_type or ""),
        metric_line("auth_provider_kind", report.auth.provider_kind or ""),
        metric_line("auth_reused_persisted_session", report.auth.reused_persisted_session),
        metric_line("auth_fresh", report.auth.fresh),
        metric_line("filed_history_succeeded", report.filed_history_succeeded),
        metric_line("wallet_succeeded", report.wallet_succeeded),
        metric_line("output_root", report.output_root),
    ]
    for outcome in report.outcomes:
        calculation_count = (
            outcome.calculation_observation_count if outcome.calculation_observation_count is not None else ""
        )
        lines.append(
            metric_line(
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


def _compact_failure_context(context: dict[str, object] | None) -> str:
    if not context:
        return ""
    parts: list[str] = []
    for key in sorted(context):
        value = context[key]
        if is_str_keyed_dict(value):
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
    or declaration-copy artefacts. Omitted year bounds default to the current
    calendar year.
    """
    from ...core.time.clock import today_madrid
    from .runtime_filed_read import read_filed_list_for_cli

    resolved_from = year_from if year_from is not None else today_madrid().year
    resolved_to = year_to if year_to is not None else today_madrid().year
    emit_live_auth_preflight(ctx)
    read = read_filed_list_for_cli(
        ctx,
        modelo=modelo,
        year_from=resolved_from,
        year_to=resolved_to,
    )
    try:
        result, lines = _filed_list_result_and_lines(
            modelo_filter=read.projection.modelo_filter,
            year_from=read.projection.year_from,
            year_to=read.projection.year_to,
            row_count=read.projection.row_count,
            rows=read.rows,
            failures=read.failures,
        )
        emit_envelope(ctx, command="app.live.filed.list", result=result, lines=lines)
    except Exception:
        from ...application.runtime.contracts import RuntimeRefusalCode
        from .runtime_registered_operation import submitted_operation_error

        completed = read.completion
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None


def _filed_list_result_and_lines(
    *,
    modelo_filter: str | None,
    year_from: int,
    year_to: int,
    row_count: int,
    rows: Sequence[FiledDataListingRow],
    failures: Sequence[FiledDataCaptureFailureRow],
) -> tuple[Any, tuple[str, ...]]:
    from ._app_live_filed_payloads import FiledCaptureFailurePayload, FiledListingRowPayload, FiledListResult

    lines = [metric_line("row_count", row_count), metric_line("failed_count", len(failures))]
    for row in rows:
        lines.append(
            metric_line(
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
        metric_line(
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
    from .runtime_filed_read import read_filed_discover_for_cli

    read = read_filed_discover_for_cli(ctx)
    try:
        result, lines = _filed_discover_result_and_lines(read.report)
        notices = _filed_discover_notices(read.report)
        emit_envelope(
            ctx,
            command="app.live.filed.discover",
            result=result,
            lines=lines,
            notices=notices,
        )
    except Exception:
        from ...application.runtime.contracts import RuntimeRefusalCode
        from .runtime_registered_operation import submitted_operation_error

        completed = read.completion
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None


def _filed_discover_result_and_lines(report: FiledHistoryDiscoveryReport) -> tuple[Any, tuple[str, ...]]:
    from ._app_live_filed_payloads import FiledDiscoverResult, FiledHistoryDiscoveryPairPayload

    lines = [
        metric_line("pair_count", len(report.pairs)),
        metric_line("profile_expected_count", len(report.profile_expected_pairs)),
        metric_line("register_options_only_count", len(report.register_options_only_pairs)),
    ]
    lines.extend(
        metric_line(
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
    from ...core.time.clock import today_madrid
    from .runtime_filed_history import read_filed_history_for_cli

    resolved_root = resolve_optional_root(output_root, lambda: load_settings().cadrumo_filed_declarations_dir)
    read = read_filed_history_for_cli(ctx, output_root=resolved_root, limit=limit, today=today_madrid())
    try:
        result, lines = _filed_pull_all_result_and_lines(read.report)
        notices = _filed_pull_all_notices(read.report, limit=limit)
        emit_envelope(
            ctx,
            command="app.live.filed.pull_all",
            result=result,
            lines=(*lines, *notice_lines(notices)),
            notices=notices,
        )
    except Exception:
        from ...application.runtime.contracts import RuntimeRefusalCode
        from .runtime_registered_operation import submitted_operation_error

        completed = read.completion
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None


def _filed_pull_all_result_and_lines(run: FiledHistoryOnboardingRun) -> tuple[Any, tuple[str, ...]]:
    from ._app_live_filed_payloads import FiledHistoryOnboardingResult, FiledHistoryPairOutcomePayload

    refused = run.refused_pairs
    empty = run.genuinely_empty_pairs
    lines = [
        metric_line("pair_count", len(run.pairs)),
        metric_line("captured_count", run.captured_count),
        metric_line("reached_count", run.reached_count),
        metric_line("refused_count", len(refused)),
        metric_line("empty_count", len(empty)),
        metric_line("iva_wallet_status", run.iva_wallet_status),
        metric_line("notificaciones_status", run.notificaciones_status),
        metric_line("denominator", run.denominator_note),
    ]
    lines.extend(
        metric_line(
            "pair",
            "\t".join(
                (
                    pair.modelo,
                    str(pair.ejercicio),
                    ",".join(signal.value for signal in pair.signals),
                    f"walk_attempted={pair.walk_attempted}",
                    f"walk_completed={pair.walk_completed}",
                    f"rows={pair.row_count}",
                    f"reached={pair.reached_count}",
                    f"captured={pair.captured_count}",
                    f"refused={pair.refused}",
                ),
            ),
        )
        for pair in run.pairs
    )
    lines.extend(metric_line("stage_failure", failure) for failure in run.stage_failures)
    result = FiledHistoryOnboardingResult(
        pairs=[
            FiledHistoryPairOutcomePayload(
                modelo=pair.modelo,
                ejercicio=pair.ejercicio,
                signals=[signal.value for signal in pair.signals],
                walk_attempted=pair.walk_attempted,
                walk_completed=pair.walk_completed,
                reached_count=pair.reached_count,
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
            "cli.app.live.filed.limit_reached_factual",
            limit=limit,
            reached=reached_count,
        ),
        action=resolve_notice_action(action=ActionReference(action_id="operator.live.filed.pull_all")),
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
    if refused := run.refused_pairs:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="live.filed.pull_all.pairs_refused",
                message=tr(
                    "cli.app.live.filed.pull_all_pairs_refused_factual",
                    count=len(refused),
                    pairs=", ".join(f"{pair.modelo}/{pair.ejercicio}" for pair in refused),
                ),
                action=resolve_notice_action(action=ActionReference(action_id="operator.live.filed.pull_all")),
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
    from ._app_live_filed_payloads import FiledCaptureResult
    from .runtime_filed_single import read_filed_single_capture_for_cli

    resolved_period = _live_period_option(period, year=year)
    resolved_root = resolve_optional_root(output_root, lambda: load_settings().cadrumo_filed_declarations_dir)
    read = read_filed_single_capture_for_cli(
        ctx,
        modelo=modelo,
        year=year,
        output_root=resolved_root,
        period=resolved_period,
        expediente_id=expediente_id,
        limit=limit,
    )
    report = read.report
    try:
        lines = _filed_capture_lines(report, mode=LiveCaptureMode.SINGLE, modelo=report.modelo, year=report.year)
        result = FiledCaptureResult(
            output_root=report.output_root,
            modelo=report.modelo,
            year=report.year,
            captured_count=report.captured_count,
            reached_count=report.reached_count,
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
            reconciliations=[filing_reconciliation_payload(item) for item in report.reconciliation_results],
        )
        notices = (
            *_filed_capture_notices(report, limit=limit),
            *filing_reconciliation_notices(report.reconciliation_results),
        )
        emit_envelope(
            ctx,
            command="app.live.filed.pull",
            result=result,
            lines=(*lines, *filing_reconciliation_lines(report.reconciliation_results), *notice_lines(notices)),
            notices=notices,
        )
    except Exception:
        from ...application.runtime.contracts import RuntimeRefusalCode
        from .runtime_registered_operation import submitted_operation_error

        completed = read.completion
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None


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
    from ._app_live_filed_payloads import FiledCaptureFailurePayload, FiledCaptureResult
    from .runtime_filed_bulk import read_filed_bulk_capture_for_cli

    resolved_from, resolved_to = resolve_pull_year_range(year=year, year_from=year_from, year_to=year_to)
    resolved_root = resolve_optional_root(output_root, lambda: load_settings().cadrumo_filed_declarations_dir)
    read = read_filed_bulk_capture_for_cli(
        ctx,
        year_from=resolved_from,
        year_to=resolved_to,
        output_root=resolved_root,
        modelos=selected_modelos or None,
        limit=limit,
        dry_run=dry_run,
    )
    report = read.report
    lines = _filed_capture_lines(
        report,
        mode=LiveCaptureMode.BULK,
        modelos=report.modelos,
        year_from=report.year_from,
        year_to=report.year_to,
        failures=report.failures,
    )
    result = FiledCaptureResult(
        mode=LiveCaptureMode.BULK,
        dry_run=report.dry_run,
        pair_outcomes=list(report.pair_outcomes),
        output_root=report.output_root,
        modelos=list(report.modelos),
        year_from=report.year_from,
        year_to=report.year_to,
        captured_count=report.captured_count,
        reached_count=report.reached_count,
        failed_count=report.failed_count,
        sync_run_ref=report.sync_run_ref,
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
        reconciliations=[filing_reconciliation_payload(item) for item in report.reconciliation_results],
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
    capture_notices = (
        *_filed_capture_notices(report, limit=limit),
        *report.recapture_notices,
        *filing_reconciliation_notices(report.reconciliation_results),
    )
    notices = [*capture_notices]
    # Rebuilt from the notice rather than written twice, so the text line and the
    # JSON notice cannot drift apart.
    if skipped is not None:
        lines = (*lines, skipped.message)
        notices.append(skipped)
    emit_envelope(
        ctx,
        command="app.live.filed.pull",
        result=result,
        lines=(*lines, *filing_reconciliation_lines(report.reconciliation_results), *notice_lines(capture_notices)),
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

    Single-modelo and range modes delegate to registered profile workers.
    Both flows emit :class:`FiledCaptureResult`,
    persist encrypted filed observations and artefact references, register parsed
    justificante metadata when available, and only stamp local
    :class:`ModeloRecord` evidence when an existing current filing record
    matches.
    """
    emit_live_auth_preflight(ctx)
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
) -> None:
    """Capture registry-selected source observations for a target :class:`Period`.

    Delegates to its registered profile worker, which resolves dependencies from
    a validated registry snapshot before reading prior filed declarations.
    The emitted :class:`FiledCaptureSourcesResult` is local evidence only; the
    command does not submit or mutate AEAT state.
    """
    from ...core.config import load_settings
    from ._app_live_filed_payloads import FiledCaptureSourcesResult
    from .runtime_filed_source import read_filed_source_capture_for_cli

    resolved_root = resolve_optional_root(output_root, lambda: load_settings().cadrumo_filed_declarations_dir)
    read = read_filed_source_capture_for_cli(
        ctx,
        modelo=modelo,
        year=year,
        period=_required_live_period_option(period, year=year),
        output_root=resolved_root,
    )
    report = read.report
    try:
        reconciliations = report.reconciliation_results
        result = FiledCaptureSourcesResult(
            output_root=report.output_root,
            target_modelo=report.target_modelo,
            target_year=report.target_year,
            target_period=report.target_period,
            captured_count=report.captured_count,
            reached_count=report.reached_count,
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
            reconciliations=[filing_reconciliation_payload(item) for item in reconciliations],
        )
        notices = (*_filed_capture_notices(report), *filing_reconciliation_notices(reconciliations))
        emit_envelope(
            ctx,
            command="app.live.filed.pull_sources",
            result=result,
            lines=(
                *_source_filed_capture_lines(report),
                *filing_reconciliation_lines(reconciliations),
                *notice_lines(notices),
            ),
            notices=notices,
        )
    except Exception:
        from ...application.runtime.contracts import RuntimeRefusalCode
        from .runtime_registered_operation import submitted_operation_error

        completed = read.completion
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None


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
