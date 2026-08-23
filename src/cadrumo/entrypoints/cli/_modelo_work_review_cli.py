"""Typer registration for the canonical modelo work review read surface."""

from __future__ import annotations

import json

import typer

from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...application.modelo import build_modelo_work_review
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ._common import (
    _emit_envelope,  # pyright: ignore[reportPrivateUsage]
    activate_subcommand_output_language,
)
from ._modelo_behavior_support import (
    require_active_profile,
    resolve_work_unit_for_cli,
)
from ._modelo_payloads import WorkReviewResult
from ._modelo_rendering import verification_findings_notices
from ._modelo_work_options import (
    _BucketIdOpt,  # pyright: ignore[reportPrivateUsage]
    _ModeloOpt,  # pyright: ignore[reportPrivateUsage]
    _PeriodOpt,  # pyright: ignore[reportPrivateUsage]
    _RevisionOpt,  # pyright: ignore[reportPrivateUsage]
    _WorkUnitIdArg,  # pyright: ignore[reportPrivateUsage]
    _YearOpt,  # pyright: ignore[reportPrivateUsage]
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
        f"lifecycle_state\t{review.lifecycle_state.value if review.lifecycle_state is not None else ''}",
        f"verification_outcome\t{review.verification_outcome.value if review.verification_outcome is not None else ''}",
        f"progress_state\t{review.progress.state.value}",
        "materialised_count\t"
        f"{review.progress.materialised_count if review.progress.materialised_count is not None else ''}",
        f"target_count\t{review.progress.target_count if review.progress.target_count is not None else ''}",
        f"casilla_count\t{len(review.casillas)}",
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
            ),
        )
        for blocker in review.blockers
    )
    return lines


__all__ = ["register_work_review_command"]


def work_review(
    ctx: typer.Context,
    work_unit_id: _WorkUnitIdArg = None,
    modelo: _ModeloOpt = None,
    year: _YearOpt = None,
    period: _PeriodOpt = None,
    revision: _RevisionOpt = None,
    bucket_id: _BucketIdOpt = None,
    output_language: OutputLanguage | None = typer.Option(
        None, "--output-language", "--language", help=tr("cli.config.auth.output_language_help")
    ),
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
    result = WorkReviewResult(review=review)
    _emit_envelope(
        ctx,
        command="modelo.work.review",
        result=result,
        lines=_review_lines(result),
        notices=verification_findings_notices(review.findings),
    )
