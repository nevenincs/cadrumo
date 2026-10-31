"""Review-package builder used by the adapter-boundary test cluster."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from cadrumo.application.modelo.review_package import build_review_package
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import CasillaObservation
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id

__all__ = ["build_package_bytes", "build_package_path", "review_package_revision", "review_package_work_unit"]

_NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
_SURFACE = "review_package_bytes_support"
_BASE_CASILLA = validated_casilla_id("base", surface=_SURFACE)
_CUOTA_CASILLA = validated_casilla_id("cuota", surface=_SURFACE)


def review_package_work_unit(*, bucket_id: str) -> WorkUnit:
    """Return the 303 second-quarter 2026 draft work unit used by the package tests."""
    period = Period.from_year_and_code(2026, "2T")
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="2026-y-siguientes",
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_id="2026-y-siguientes",
        name="303-2026-2T",
        created_at=_NOW,
        updated_at=_NOW,
        state=WorkUnitState.BORRADOR,
    )


def review_package_revision(work_unit: WorkUnit) -> CalculationRevision:
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
                source_refs=("test-review-package",),
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
    filename_template: str = "review-package.zip",
) -> Path:
    """Build a review package and return the written path."""
    work_unit = work_unit_factory(bucket_id=bucket_id)
    revision = revision_factory(work_unit)
    output_path = tmp_path / filename_template.format(bucket_id=bucket_id)
    with bundled_indexed_authority().operation() as operation:
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
) -> bytes:
    """Build a review package and return its raw bytes."""
    return build_package_path(
        tmp_path,
        bucket_id=bucket_id,
        work_unit_factory=work_unit_factory,
        revision_factory=revision_factory,
        draft_bytes=draft_bytes,
    ).read_bytes()
