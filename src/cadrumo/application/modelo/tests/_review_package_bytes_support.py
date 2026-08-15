"""Shared review-package-bytes builder for the review-package test cluster.

Three suites each build a fresh review package to a real ``.zip`` on disk and
read its bytes back for assertions -- identical plumbing every time, differing
only in which module-scoped work unit, revision and draft-bytes fixtures feed
it. This module owns the plumbing; each consuming test module still supplies
its own fixtures, so what bytes actually go into the package is unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ....domain.modelos import CalculationRevision, WorkUnit
from .._review_package import build_review_package

__all__ = ["build_package_bytes"]


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
    work_unit = work_unit_factory(bucket_id=bucket_id)
    revision = revision_factory(work_unit)
    output_path = tmp_path / "review-package.zip"
    build_review_package(
        revision=revision,
        work_unit=work_unit,
        draft_bytes=draft_bytes,
        output_path=output_path,
        built_by="operator",
    )
    return output_path.read_bytes()
