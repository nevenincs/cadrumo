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
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, revision_serving_period
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from ..review_package import build_review_package

if TYPE_CHECKING:
    from ....domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = ["build_package_bytes", "build_package_path", "review_package_revision", "review_package_work_unit"]

_EXERCISE = filing_year_envelope().horizon
_NOW = datetime(_EXERCISE, 7, 3, 12, 0, tzinfo=UTC)
_SURFACE = "review_package_bytes_support"
_BASE_CASILLA = validated_casilla_id("base", surface=_SURFACE)
_CUOTA_CASILLA = validated_casilla_id("cuota", surface=_SURFACE)


def review_package_work_unit(*, bucket_id: str) -> WorkUnit:
    """Return the 303 second-quarter draft work unit of the horizon exercise the package suites sign."""
    period = Period.from_year_and_code(_EXERCISE, "2T")
    revision_id = str(revision_serving_period("303", _EXERCISE, "2T").id)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=_EXERCISE,
        period=period,
        revision_id=revision_id,
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=_EXERCISE,
        period=period,
        revision_id=revision_id,
        name=f"303-{_EXERCISE}-2T",
        created_at=_NOW,
        updated_at=_NOW,
        state=WorkUnitState.BORRADOR,
    )


def review_package_revision(work_unit: WorkUnit, *, source_ref: str) -> CalculationRevision:
    """Return the fully verified calculation revision for ``work_unit``."""
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        binding_overrides={},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        source_transaction_ids=(),
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        observations=(
            CasillaObservation(
                casilla_id=_CUOTA_CASILLA,
                value=Decimal("21.00"),
                legal_refs=("ley-37-1992:art-99",),
                source_refs=(source_ref,),
            ),
        ),
        ledger_filing_evidence=None,
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        filed_at=None,
        filed_by=None,
        superseded_at=None,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def build_package_path(
    tmp_path: Path,
    *,
    bucket_id: str,
    work_unit_factory: Callable[..., WorkUnit],
    revision_factory: Callable[[WorkUnit], CalculationRevision],
    draft_bytes: bytes,
    operation: PinnedAuthorityOperation,
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
        operation: The pinned authority operation for registry carry validation.
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
        operation=operation,
    )
    return output_path


def build_package_bytes(
    tmp_path: Path,
    *,
    bucket_id: str,
    work_unit_factory: Callable[..., WorkUnit],
    revision_factory: Callable[[WorkUnit], CalculationRevision],
    draft_bytes: bytes,
    operation: PinnedAuthorityOperation,
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
        operation=operation,
    ).read_bytes()
