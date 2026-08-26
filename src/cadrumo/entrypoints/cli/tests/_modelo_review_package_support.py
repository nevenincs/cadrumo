"""Shared real persistence support for modelo review-package CLI tests.

Scenario modules retain their own casilla maps and operator assertions. This
module owns the repeated setup of a real work unit and verified-complete
calculation revision suitable for export and review-package operations, and
the repeated plumbing of building a review package through the live
``review-package build`` CLI verb (seed a revision, invoke the verb, assert
success) -- three scenario modules each drove that exact sequence, differing
only in which profile facts, casilla inputs and cached-CLI invoker they
supply.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from click.testing import Result

from cadrumo.application.workflow.persistence import workflow_state_repository

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....application.modelo.work_addressing import law_selected_revision_for_work_target
from ....core import CasillaId, Period
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    WorkUnit,
    derive_calculation_revision_id,
    derive_work_unit_id,
    upsert_calculation_revision,
    upsert_work_unit,
)


def seed_exportable_modelo_revision(
    *,
    input_values_by_casilla_id: Mapping[CasillaId, str],
    modelo: str = "111",
    filing_year: int = 2026,
    period: str = "1T",
) -> tuple[str, str]:
    """Persist a real verified-complete revision ready for export or packaging."""
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    filing_period = Period.from_year_and_code(filing_year, period)
    revision_id = law_selected_revision_for_work_target(
        modelo=modelo,
        filing_year=filing_year,
        period=filing_period,
        registry_revision_id=None,
    )
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
    )
    now = datetime.now(UTC)
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period}",
        created_at=now,
        updated_at=now,
    )
    work_units = WorkUnitCatalogueRepository()
    work_units.save(upsert_work_unit(work_units.load(), work_unit))

    inputs = dict(input_values_by_casilla_id)
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=inputs,
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id=inputs,
        created_at=now,
        updated_at=now,
        verified_at=now,
        verified_by="operator",
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revisions = CalculationRevisionCatalogueRepository()
    revisions.save(upsert_calculation_revision(revisions.load(), revision))
    return work_unit_id, calculation_revision_id


def build_review_package_via_cli(
    tmp_path: Path,
    *,
    invoke: Callable[[Sequence[str]], Result],
    input_values_by_casilla_id: Mapping[CasillaId, str],
    name: str = "review-package.zip",
) -> tuple[Path, str, str]:
    """Seed an exportable revision, build its package through the live CLI verb, and return it.

    Args:
        tmp_path: The test's isolated temp directory; the package is written
            to ``name`` inside it.
        invoke: The caller's own cached-CLI invoker.
        input_values_by_casilla_id: The caller's own casilla-input fixture.
        name: The output filename.

    Returns:
        The written package path, the seeded work unit id, and the seeded
        calculation revision id.
    """
    work_unit_id, calculation_revision_id = seed_exportable_modelo_revision(
        input_values_by_casilla_id=input_values_by_casilla_id,
    )
    package_path = tmp_path / name
    build_result = invoke(
        ["app", "modelo", "review-package", "build", work_unit_id, "--output", str(package_path)],
    )
    assert build_result.exit_code == 0, build_result.output
    return package_path, work_unit_id, calculation_revision_id
