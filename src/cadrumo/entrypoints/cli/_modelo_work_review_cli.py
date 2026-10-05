"""Behavior for the canonical modelo work review read surface."""

from __future__ import annotations

import json

import typer

from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.external_constants import OutputLanguage
from ...domain.modelos.codes import ModeloCode
from ._modelo_payloads import WorkReviewPayload, WorkReviewResult
from ._modelo_rendering import verification_findings_notices
from .common import activate_subcommand_output_language, emit_envelope
from .registered_operation_errors import submitted_operation_error
from .runtime_modelo_metadata import read_modelo_work_unit
from .runtime_modelo_work_review import read_modelo_work_review


def _review_lines(result: WorkReviewResult) -> list[str]:
    """Render a compact text summary from the canonical review record."""
    review = result.review
    lines = [
        "operation\tmodelo.work.review",
        f"modelo\t{review.modelo}",
        f"filing_year\t{review.filing_year}",
        f"period\t{review.period.registry_token}",
        f"registry_revision_id\t{review.registry_revision_id}",
        f"work_unit_id\t{review.work_unit_id}",
        f"calculation_revision_id\t{review.calculation_revision_id or ''}",
        f"lifecycle_state\t{(review.lifecycle_state.value if review.lifecycle_state is not None else '')}",
        "verification_outcome\t"
        f"{(review.verification_outcome.value if review.verification_outcome is not None else '')}",
        f"progress_state\t{review.progress.state.value}",
        "materialised_count\t"
        f"{(review.progress.materialised_count if review.progress.materialised_count is not None else '')}",
        f"target_count\t{(review.progress.target_count if review.progress.target_count is not None else '')}",
        f"casilla_count\t{review.casilla_count}",
        f"finding_count\t{len(review.findings)}",
        f"blocker_count\t{len(review.blockers)}",
    ]
    lines.extend(
        "\t".join(
            (
                "blocker",
                blocker.axis.value,
                blocker.native_code,
                json.dumps(dict(blocker.facts), ensure_ascii=False, sort_keys=True, default=str),
            )
        )
        for blocker in review.blockers
    )
    lines.append(f"row_source_fingerprint_count\t{review.row_source_fingerprint_count}")
    return lines


__all__ = ["work_review"]


def work_review(
    ctx: typer.Context,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Emit the canonical application review for one persisted work target."""
    activate_subcommand_output_language(ctx, output_language)
    unit = read_modelo_work_unit(
        ctx,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    reviewed = read_modelo_work_review(ctx, unit=unit)
    review = reviewed.review
    try:
        result = WorkReviewResult(
            review=WorkReviewPayload(
                bucket_id=review.bucket_id,
                modelo=ModeloCode(review.modelo),
                filing_year=review.filing_year,
                period=review.period.to_period(),
                registry_revision_id=review.registry_revision_id,
                work_unit_id=review.work_unit_id,
                calculation_revision_id=review.calculation_revision_id,
                lifecycle_state=review.lifecycle_state,
                verification_outcome=review.verification_outcome,
                progress=review.progress.to_progress(),
                casilla_count=review.casilla_count,
                findings=tuple(item.to_finding() for item in review.findings),
                blockers=tuple(item.to_blocker() for item in review.blockers),
                row_source_fingerprint_count=review.row_source_fingerprint_count,
            )
        )
        lines = _review_lines(result)
        notices = verification_findings_notices(result.review.findings)
        emit_envelope(
            ctx,
            command="modelo.work.review",
            result=result,
            lines=lines,
            notices=notices,
        )
    except Exception:
        receipt = reviewed.completion
        raise submitted_operation_error(
            receipt.operation_id,
            RuntimeRefusalCode.UNAVAILABLE.value,
            terminal_condition=receipt.terminal_condition,
            effect=receipt.effect,
            refusal_code=receipt.refusal_code,
        ) from None
