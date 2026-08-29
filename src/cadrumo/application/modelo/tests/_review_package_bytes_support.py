"""Shared review-package builders for the review-package test cluster.

Six suites each build a fresh review package to a real ``.zip`` on disk --
identical work-unit / revision / ``build_review_package`` plumbing every time,
differing only in which module-scoped fixtures feed it and whether the caller
wants the raw bytes back (three suites) or the package path itself (three
more, which build multiple packages per test and need distinct filenames).
This module owns the shared plumbing; each consuming test module still
supplies its own fixtures, so what bytes actually go into the package is
unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ....domain.modelos import WorkUnit
from ....domain.modelos.calculation_revision import CalculationRevision
from ..review_package import build_review_package

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
    """Build a review package for ``bucket_id`` and return the written path.

    Args:
        tmp_path: The test's isolated temp directory; the package is written
            inside it.
        bucket_id: The bucket id the caller's own ``work_unit_factory`` scopes
            the built work unit to.
        work_unit_factory: The caller's own ``_work_unit``-shaped builder.
        revision_factory: The caller's own ``_revision``-shaped builder.
        draft_bytes: The caller's own draft-bytes fixture, unchanged.
        filename_template: The output filename, formatted with ``bucket_id``.
            Callers that build several packages under one ``tmp_path`` in a
            single test bind ``"review-package-{bucket_id}.zip"`` so the
            files never collide; the single-package callers keep the static
            default.

    Returns:
        The path the package was written to.
    """
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
    """Build a review package for ``bucket_id`` and return its raw bytes.

    Args:
        tmp_path: The test's isolated temp directory; the package is written
            to ``review-package.zip`` inside it.
        bucket_id: The bucket id the caller's own ``work_unit_factory`` scopes
            the built work unit to.
        work_unit_factory: The caller's own ``_work_unit``-shaped builder.
        revision_factory: The caller's own ``_revision``-shaped builder.
        draft_bytes: The caller's own draft-bytes fixture, unchanged.

    Returns:
        The built package's raw bytes, read back from disk.
    """
    return build_package_path(
        tmp_path,
        bucket_id=bucket_id,
        work_unit_factory=work_unit_factory,
        revision_factory=revision_factory,
        draft_bytes=draft_bytes,
    ).read_bytes()
