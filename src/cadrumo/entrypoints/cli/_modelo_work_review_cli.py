# ruff: noqa: E501
"""Behavior for the canonical modelo work review read surface."""

from __future__ import annotations

import json

import typer

from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...application.modelo.work_review import build_modelo_work_review
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language as resolved_output_language
from ._common import activate_subcommand_output_language, emit_envelope
from ._modelo_behavior_support import require_active_profile, resolve_work_unit_for_cli
from ._modelo_payloads import WorkReviewPayload, WorkReviewResult
from ._modelo_rendering import verification_findings_notices
from ._tui_policy import tui_was_requested


def _run_review_destination(*, work_unit_id: str, bucket_id: str) -> None:
    """Open the sole C1 bounded-review destination for one resolved unit.

    Kept as its own seam so a test can substitute a non-blocking stand-in for
    the real full-screen session without touching the resolution logic above
    it.

    Only the unit's IDENTIFIERS cross. The destination runs out of process,
    because a CLI entrypoint may not import the dedicated full-screen
    frontend, and a built review record cannot cross that boundary as an
    object; the session re-reads the review from the identifiers it is given.
    """
    from ..full_screen_session_protocol import FullScreenDestination
    from ._tui_session import run_destination_session

    run_destination_session(
        destination=FullScreenDestination.MODELO_WORK_REVIEW,
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        output_language=resolved_output_language(),
    )


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
        f"verification_outcome\t{(review.verification_outcome.value if review.verification_outcome is not None else '')}",
        f"progress_state\t{review.progress.state.value}",
        f"materialised_count\t{(review.progress.materialised_count if review.progress.materialised_count is not None else '')}",
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
    require_active_profile()
    unit = resolve_work_unit_for_cli(
        work_unit_id=work_unit_id, modelo=modelo, year=year, period=period, revision=revision, bucket_id=bucket_id
    )
    work_repository = WorkUnitCatalogueRepository()
    calculation_repository = CalculationRevisionCatalogueRepository()
    review = build_modelo_work_review(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        work_unit_repository=work_repository,
        calculation_repository=calculation_repository,
        verification_repository=VerificationReportCatalogueRepository(),
    )
    if tui_was_requested(ctx):
        _run_review_destination(work_unit_id=unit.work_unit_id, bucket_id=unit.bucket_id)
    result = WorkReviewResult(review=WorkReviewPayload.from_review(review))
    emit_envelope(
        ctx,
        command="modelo.work.review",
        result=result,
        lines=_review_lines(result),
        notices=verification_findings_notices(review.findings),
    )
