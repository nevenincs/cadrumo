"""Review-package builder used by the adapter-boundary test cluster."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cadrumo.application.modelo.review_package import build_review_package
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.work_unit import WorkUnit

__all__ = ["build_package_bytes", "build_package_path"]


def build_package_path(
    tmp_path: Path,
    *,
    bucket_id: str,
    work_unit_factory: Callable[..., WorkUnit],
    revision_factory: Callable[[WorkUnit], CalculationRevision],
    draft_bytes: bytes,
    filename_template: str = "review-package.zip",
) -> Path:
    """Build a review package and return the written path."""
    work_unit = work_unit_factory(bucket_id=bucket_id)
    revision = revision_factory(work_unit)
    output_path = tmp_path / filename_template.format(bucket_id=bucket_id)
    build_review_package(
        revision=revision,
        work_unit=work_unit,
        draft_bytes=draft_bytes,
        output_path=output_path,
        built_by="operator",
    )
    return output_path


def build_package_bytes(
    tmp_path: Path,
    *,
    bucket_id: str,
    work_unit_factory: Callable[..., WorkUnit],
    revision_factory: Callable[[WorkUnit], CalculationRevision],
    draft_bytes: bytes,
) -> bytes:
    """Build a review package and return its raw bytes."""
    return build_package_path(
        tmp_path,
        bucket_id=bucket_id,
        work_unit_factory=work_unit_factory,
        revision_factory=revision_factory,
        draft_bytes=draft_bytes,
    ).read_bytes()
