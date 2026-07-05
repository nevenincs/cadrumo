"""Output projection helpers for Modelo review-package CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._modelo_review_package_payloads import ModeloReviewPackageBuildResult

if TYPE_CHECKING:
    from ...application.modelo import ReviewPackageBuildResult


def review_package_build_result_payload(build_result: ReviewPackageBuildResult) -> ModeloReviewPackageBuildResult:
    """Project a review-package build result into the JSON envelope payload."""
    manifest = build_result.manifest
    return ModeloReviewPackageBuildResult(
        bucket_id=manifest.bucket_id,
        work_unit_id=manifest.work_unit_id,
        calculation_revision_id=manifest.calculation_revision_id,
        modelo=manifest.modelo,
        filing_year=manifest.filing_year,
        period=manifest.period,
        revision_state=manifest.revision_state,
        has_ledger_evidence=manifest.has_ledger_evidence,
        output_path=str(build_result.output_path),
        member_count=build_result.member_count,
        built_by=manifest.built_by,
        built_at=manifest.built_at.isoformat(),
    )


def review_package_build_result_lines(
    build_result: ReviewPackageBuildResult,
    *,
    export_bucket_event_id: str,
) -> list[str]:
    """Project a review-package build result into text output lines."""
    manifest = build_result.manifest
    return [
        "operation\tmodelo.review_package.build",
        f"work_unit_id\t{manifest.work_unit_id}",
        f"calculation_revision_id\t{manifest.calculation_revision_id}",
        f"bucket\t{manifest.bucket_id}",
        f"modelo\t{manifest.modelo}",
        f"filing_year\t{manifest.filing_year}",
        f"period\t{manifest.period}",
        f"output_path\t{build_result.output_path}",
        f"member_count\t{build_result.member_count}",
        f"has_ledger_evidence\t{manifest.has_ledger_evidence}",
        f"export_bucket_event_id\t{export_bucket_event_id}",
    ]


__all__ = [
    "review_package_build_result_lines",
    "review_package_build_result_payload",
]
