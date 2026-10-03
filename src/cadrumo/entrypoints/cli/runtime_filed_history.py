"""CLI client for one exact-profile recorded filed-history sweep."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import UUID

import typer

from ...application.live.filed_data_capture import FiledHistoryOnboardingRun, FiledHistoryPairOutcome
from ...application.live.filed_history_operation import (
    FILED_HISTORY_OPERATION_DEFINITION_ID,
    FiledHistoryOperationRequest,
    FiledHistoryPublicResultV1,
    settled_filed_history_effect,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.json_contract import Notice
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


@dataclass(frozen=True, slots=True)
class FiledHistoryRead:
    """Keep the correlated receipt with the reconstructed presentation report."""

    completion: RegisteredOperationCompletion[FiledHistoryPublicResultV1]
    report: FiledHistoryOnboardingRun


def _notice_from_projection(notice: object) -> Notice:
    from ...application.live.filed_history_operation import FiledHistoryEvidenceNoticeV1

    if not isinstance(notice, FiledHistoryEvidenceNoticeV1):
        raise ValueError("filed-history notice projection has an invalid type")
    source_context = notice.context
    context = None if source_context is None else dict(source_context)
    if source_context is not None and context is not None and len(context) != len(source_context):
        raise ValueError("filed-history notice projection has duplicate context keys")
    return Notice(severity=notice.severity, code=notice.code, message=notice.message, context=context)


def _presentation_report(projection: FiledHistoryPublicResultV1) -> FiledHistoryOnboardingRun:
    """Restore the canonical report helpers from the safe public projection."""
    _require_filed_history_pairs(projection)
    report = FiledHistoryOnboardingRun(
        pairs=tuple(
            FiledHistoryPairOutcome(
                modelo=pair.modelo,
                ejercicio=pair.ejercicio,
                signals=pair.signals,
                walk_attempted=pair.walk_attempted,
                walk_completed=pair.walk_completed,
                reached_count=pair.reached_count,
                row_count=pair.row_count,
                captured_count=pair.captured_count,
                refused=pair.refused,
                failure_type=pair.failure_type,
                failure_message=pair.failure_message,
            )
            for pair in projection.pairs
        ),
        dry_run=projection.dry_run,
        captured_count=projection.captured_count,
        reached_count=projection.reached_count,
        scoping_signal=projection.scoping_signal,
        carries_a_taxpayer_specific_denominator=projection.carries_a_taxpayer_specific_denominator,
        iva_wallet_status=projection.iva_wallet_status,
        iva_wallet_divergence=projection.iva_wallet_divergence,
        iva_wallet_blocked=projection.iva_wallet_blocked,
        notificaciones_status=projection.notificaciones_status,
        notificaciones_row_count=projection.notificaciones_row_count,
        stage_failures=projection.stage_failures,
        sync_run_ref=projection.sync_run_ref,
        evidence_notices=tuple(_notice_from_projection(notice) for notice in projection.evidence_notices),
        recapture_notices=tuple(_notice_from_projection(notice) for notice in projection.recapture_notices),
    )
    if report.denominator_note != projection.denominator_note:
        raise ValueError("filed-history denominator note does not match the pair signals")
    if report.carries_a_taxpayer_specific_denominator != any(pair.expected_by_profile for pair in report.pairs):
        raise ValueError("filed-history denominator flag does not match the pair signals")
    return report


def read_filed_history_for_cli(
    ctx: typer.Context,
    *,
    output_root: Path,
    limit: int | None,
    today: date,
) -> FiledHistoryRead:
    """Return only the exact-profile settled result from the registered worker."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    completed = run_registered_operation(
        client,
        FiledHistoryOperationRequest(
            profile_id=client.profile_id,
            output_root=output_root,
            today=today,
            limit=limit,
            dry_run=False,
        ),
        definition_id=FILED_HISTORY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=FiledHistoryPublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    try:
        report = _presentation_report(completed.projection)
        expected_effect = settled_filed_history_effect(report)
        if (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or report.dry_run
            or (
                completed.effect is not expected_effect
                and not (expected_effect is OperationEffect.NONE and completed.effect is OperationEffect.UPDATED)
            )
        ):
            raise ValueError("filed-history result disagrees with its settled receipt")
    except Exception:
        raise invalid_completion_error(completed) from None
    return FiledHistoryRead(completion=completed, report=report)


def _require_filed_history_pairs(projection: FiledHistoryPublicResultV1) -> None:
    """Validate unique pair coordinates and outcomes before reconciling global capture counts."""
    coordinates: set[tuple[str, int]] = set()
    for pair in projection.pairs:
        coordinate = (pair.modelo, pair.ejercicio)
        if coordinate in coordinates:
            raise ValueError("filed-history result contains duplicate pair coordinates")
        coordinates.add(coordinate)
        FiledHistoryPairOutcome(
            modelo=pair.modelo,
            ejercicio=pair.ejercicio,
            signals=pair.signals,
            walk_attempted=pair.walk_attempted,
            walk_completed=pair.walk_completed,
            row_count=pair.row_count,
            reached_count=pair.reached_count,
            captured_count=pair.captured_count,
            refused=pair.refused,
            failure_type=pair.failure_type,
            failure_message=pair.failure_message,
        ).require_consistent()
    # The bulk acquisition can walk rectangular extras outside discovery; the
    # global counts must retain those actual effects rather than equal this join.
    if (
        projection.captured_count > projection.reached_count
        or sum(pair.captured_count for pair in projection.pairs) > projection.captured_count
        or sum(pair.reached_count for pair in projection.pairs) > projection.reached_count
    ):
        raise ValueError("filed-history global counts contradict its pair outcomes")
