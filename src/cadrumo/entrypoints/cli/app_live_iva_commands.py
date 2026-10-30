"""Read-only authenticated IVA wallet and remote evidence commands.

Registered profile workers acquire observations without submitting a return.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import typer

from cadrumo_client.commands.registered_operation_errors import invalid_completion_error

from ...application.live.errors import LiveIvaAcquisitionFailureMode
from ...application.live.remote_state_models import (
    IvaCompensationHistoryReport,
    IvaRemoteStateAcquisitionReport,
    IvaWalletCaptureReport,
    LiveIvaReadOutcome,
)
from ...core.i18n.render import tr
from ...core.period import Period
from ...core.type_guards import is_str_keyed_dict
from ...domain.iva_compensation.reconciliation import IvaCompensationDecisionReason
from ._app_live_auth_preflight import emit_live_auth_preflight, metric_line
from .app_live_period import required_live_period_option
from .common import (
    emit_envelope,
    resolve_optional_root,
)


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
    from .operation_iva_wallet_capture import read_iva_wallet_capture_for_cli

    emit_live_auth_preflight(ctx)
    target_period = required_live_period_option(period, year=year)
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
        from .app_live_iva_wallet_results import IvaWalletPullResult

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
        completed = read.completion
        raise invalid_completion_error(completed) from None


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
    from .operation_iva_wallet_history import read_iva_wallet_history_for_cli

    read = read_iva_wallet_history_for_cli(ctx, as_of_year=as_of_year)
    try:
        result = _iva_wallet_history_result(read.report)
        lines = _iva_wallet_history_lines(read.report)
        emit_envelope(ctx, command="app.live.iva_wallet.history", result=result, lines=lines)
    except Exception:
        completed = read.completion
        raise invalid_completion_error(completed) from None


def _iva_wallet_history_result(report: IvaCompensationHistoryReport) -> Any:
    from .app_live_iva_wallet_results import (
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
    from .operation_iva_history_capture import read_iva_wallet_history_capture_for_cli

    emit_live_auth_preflight(ctx)
    read = read_iva_wallet_history_capture_for_cli(
        ctx,
        year_from=year_from,
        year_to=year_to,
        output_root=output_root,
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
        from .app_live_iva_wallet_results import IvaWalletCaptureHistoryResult

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
        completed = read.completion
        raise invalid_completion_error(completed) from None


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
    from ...core.storage_taxonomy import StorageCategory
    from ...core.storage_taxonomy_locations import storage_path
    from .operation_iva_remote_state_capture import read_iva_remote_state_capture_for_cli

    resolved_target_period = required_live_period_option(target_period, year=target_year)
    emit_live_auth_preflight(ctx)
    resolved_root = resolve_optional_root(output_root, lambda: storage_path(StorageCategory.IVA_READ_EVIDENCE))
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
        from .app_live_iva_wallet_results import (
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
        completed = read.completion
        raise invalid_completion_error(completed) from None


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
        metric_line(
            "auth_failure_mode",
            report.auth.failure_mode.value
            if (report.auth.failure_mode is not None and report.auth.failure_mode)
            else "",
        ),
        metric_line("auth_failure_type", report.auth.failure_type or ""),
        metric_line("auth_provider_kind", report.auth.provider_kind or ""),
        metric_line("auth_reused_persisted_session", report.auth.reused_persisted_session),
        metric_line("auth_fresh", report.auth.fresh),
        metric_line("filed_history_succeeded", report.filed_history_succeeded),
        metric_line("wallet_succeeded", report.wallet_succeeded),
        metric_line("output_root", report.output_root),
    ]
    lines.extend(_iva_surface_outcome_line(outcome) for outcome in report.outcomes)
    return tuple(lines)


def _iva_surface_outcome_line(outcome: LiveIvaReadOutcome) -> str:
    failure_mode = outcome.failure_mode
    failure_mode_value = failure_mode.value if failure_mode is not None and failure_mode else ""
    calculation_count = (
        outcome.calculation_observation_count if outcome.calculation_observation_count is not None else ""
    )
    return metric_line(
        "surface_outcome",
        "\t".join(
            (
                outcome.surface.value,
                f"status={outcome.status.value}",
                f"outcome={outcome.outcome_mode.value}",
                f"outcome_label={_live_iva_outcome_label(outcome.outcome_mode)}",
                f"failure_mode={failure_mode_value}",
                f"failure_type={outcome.failure_type or ''}",
                f"failure_context={_compact_failure_context(outcome.failure_context)}",
                f"captured_count={outcome.captured_count if outcome.captured_count is not None else ''}",
                f"calculation_observation_count={calculation_count}",
            ),
        ),
    )


def _compact_failure_context(context: dict[str, object] | None) -> str:
    if not (context is not None and context):
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


__all__ = [
    "iva_wallet_history_cmd",
    "iva_wallet_pull_cmd",
    "iva_wallet_pull_evidence_cmd",
    "iva_wallet_pull_history_cmd",
]
