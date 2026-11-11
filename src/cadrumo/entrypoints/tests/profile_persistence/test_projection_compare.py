"""Application compare-service provenance regression tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from cadrumo.application.modelo.projection import ModeloProjectionCasillaObservation
from cadrumo.application.modelo.projection_compare import ModeloCompareDeltaRow, compare_modelo_years
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.entrypoints.adapter_composition_work_ports import (
    build_calculation_action_ports,
    build_work_lifecycle_ports,
)

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.ready_profile_support import seed_ready_profile
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, open_ended_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon
_PRIOR_YEAR = _YEAR - 1
_T0 = datetime(_YEAR, 6, 25, 9, 0, tzinfo=UTC)
_BUCKET_ID = "13013013-0130-4130-8130-130130130130"
_M130_REVISION_ID = str(open_ended_revision("130").id)


_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="projection compare test casilla id")


def _m130_ingresos_registry_provenance() -> tuple[tuple[str, ...], tuple[str, ...]]:
    registry_casilla = next(
        item
        for item in published_authority_operation().snapshot("130", filing_year=_YEAR, period="1T").revision.casillas
        if item.id == _M130_INGRESOS_CASILLA
    )
    return tuple(registry_casilla.legal_refs), tuple(registry_casilla.source_refs)


def _seed_work_unit(
    repository: WorkUnitCatalogueRepository,
    *,
    bucket_id: str,
    filing_year: int,
    clock: datetime,
    operation: PinnedAuthorityOperation,
) -> WorkUnit:
    return create_work_unit(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "1T"),
        revision_id=_M130_REVISION_ID,
        ports=build_work_lifecycle_ports(bucket_id=bucket_id),
        clock=clock,
        operation=operation,
    )


def _seed_consecutive_work_units(
    profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> tuple[CalculationRevisionCatalogueRepository, WorkUnit, WorkUnit]:
    """Open the profile's calculation catalogue and seed its prior-year work unit and, a minute later, the current-year one."""
    work_repository = WorkUnitCatalogueRepository(objects=profile.repository)
    calculation_repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
    work_prior = _seed_work_unit(
        work_repository,
        bucket_id=profile.bucket_id,
        filing_year=_PRIOR_YEAR,
        clock=_T0,
        operation=operation,
    )
    work_current = _seed_work_unit(
        work_repository,
        bucket_id=profile.bucket_id,
        filing_year=_YEAR,
        clock=_T0 + timedelta(minutes=1),
        operation=operation,
    )
    return calculation_repository, work_prior, work_current


def _seed_revision(
    repository: CalculationRevisionCatalogueRepository,
    *,
    work_unit: WorkUnit,
    value: Decimal,
    clock: datetime,
) -> CalculationRevision:
    values = {_M130_INGRESOS_CASILLA: value}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={_M130_INGRESOS_CASILLA: str(value)},
        binding_overrides={},
        casilla_values=values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_M130_INGRESOS_CASILLA: str(value)},
        binding_overrides={},
        casilla_values=values,
        observations=registry_grounded_observations(
            modelo="130",
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=values,
        ),
        created_at=clock,
        updated_at=clock,
        verified_at=clock,
        verified_by="operator",
        filing_instance_evidence=None,
        source_provenance=(),
    )
    repository.save(upsert_calculation_revision(repository.load(), revision))
    return revision


def test_compare_uses_revision_observation_rowsfrom_registry_snapshot(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Comparison rows must not lose registry-grounded provenance."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        seed_ready_profile(bucket_id=profile.bucket_id, at=_T0)
        calculation_repository, work_prior, work_current = _seed_consecutive_work_units(profile, operation)
        revision_prior = _seed_revision(
            calculation_repository,
            work_unit=work_prior,
            value=Decimal("1000.00"),
            clock=_T0 + timedelta(minutes=2),
        )
        revision_current = _seed_revision(
            calculation_repository,
            work_unit=work_current,
            value=Decimal("1500.00"),
            clock=_T0 + timedelta(minutes=3),
        )

        assert revision_prior.observations
        assert revision_current.observations
        with bundled_indexed_authority().operation() as operation:
            result = compare_modelo_years(
                modelo="130",
                years=(_PRIOR_YEAR, _YEAR),
                ports=build_calculation_action_ports(bucket_id=profile.bucket_id, operation=operation),
                operation=operation,
            )

    row = next(item for item in result.delta_rows if item.casilla_id == _M130_INGRESOS_CASILLA)
    registry_casilla = next(
        item
        for item in published_authority_operation().snapshot("130", filing_year=_YEAR, period="1T").revision.casillas
        if item.id == _M130_INGRESOS_CASILLA
    )
    assert row.delta == Decimal("500.00")
    assert row.legal_refs == tuple(registry_casilla.legal_refs)
    assert row.source_refs == tuple(registry_casilla.source_refs)
    assert row.legal_refs, "comparison rows must not emit blank legal_refs"
    assert row.source_refs, "comparison rows must not emit blank source_refs"


def test_compare_reports_a_one_cent_delta_exactly_with_no_tolerance_absorption(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The revision-vs-revision delta is the application's own arithmetic on both sides.

    Modelo 130's 1T revision publishes a real, non-zero tolerance
    (``0.01``) for the OTHER per-casilla comparators that compare against
    AEAT, where rounding is an artefact. This comparator must NOT read that
    same tolerance: two of the app's OWN revisions differing by exactly that
    published cent differ by a cent, and absorbing it would hide a real
    change. Pinned against the real published value rather than a hardcoded
    literal, so this proves the comparator is genuinely exact rather than
    merely never having been fed a value small enough to matter.
    """
    published_tolerance = (
        published_authority_operation().snapshot("130", filing_year=_YEAR, period="1T").verification_policy().tolerance
    )
    assert published_tolerance == Decimal("0.01"), (
        "test precondition: modelo 130 1T must publish a real, non-zero tolerance "
        "for this proof to demonstrate the delta comparator does NOT absorb it"
    )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        seed_ready_profile(bucket_id=profile.bucket_id, at=_T0)
        calculation_repository, work_prior, work_current = _seed_consecutive_work_units(profile, operation)
        _seed_revision(
            calculation_repository,
            work_unit=work_prior,
            value=Decimal("1000.00"),
            clock=_T0 + timedelta(minutes=2),
        )
        _seed_revision(
            calculation_repository,
            work_unit=work_current,
            value=Decimal("1000.00") + published_tolerance,
            clock=_T0 + timedelta(minutes=3),
        )

        with bundled_indexed_authority().operation() as operation:
            result = compare_modelo_years(
                modelo="130",
                years=(_PRIOR_YEAR, _YEAR),
                ports=build_calculation_action_ports(bucket_id=profile.bucket_id, operation=operation),
                operation=operation,
            )

    row = next(item for item in result.delta_rows if item.casilla_id == _M130_INGRESOS_CASILLA)
    assert row.delta == published_tolerance, (
        "the delta comparator absorbed a genuine one-cent change, which the tree's other "
        "comparators are correct to do against AEAT-sourced data but which this comparator "
        "must never do against the application's own arithmetic on both sides"
    )


def test_projection_rows_reject_blank_registry_provenance_entries() -> None:
    """Projection result models must not accept whitespace provenance."""
    legal_refs, source_refs = _m130_ingresos_registry_provenance()

    with pytest.raises(ValidationError):
        ModeloProjectionCasillaObservation(
            casilla_id=_M130_INGRESOS_CASILLA,
            value=Decimal("1"),
            legal_refs=(" ",),
            source_refs=source_refs,
        )

    with pytest.raises(ValidationError):
        ModeloProjectionCasillaObservation(
            casilla_id=_M130_INGRESOS_CASILLA,
            value=Decimal("1"),
            legal_refs=legal_refs,
            source_refs=("",),
        )

    with pytest.raises(ValidationError):
        ModeloCompareDeltaRow(
            casilla_id=_M130_INGRESOS_CASILLA,
            label="Ingresos",
            section="Actividades economicas",
            year_a_value=Decimal("1"),
            year_b_value=Decimal("2"),
            delta=Decimal("1"),
            pct_change=Decimal("100.00"),
            formula_id=" ",
            legal_refs=legal_refs,
            source_refs=source_refs,
        )

    with pytest.raises(ValidationError):
        ModeloCompareDeltaRow(
            casilla_id=_M130_INGRESOS_CASILLA,
            label="Ingresos",
            section="Actividades economicas",
            year_a_value=Decimal("1"),
            year_b_value=Decimal("2"),
            delta=Decimal("1"),
            pct_change=Decimal("100.00"),
            legal_refs=legal_refs,
            source_refs=(" ",),
        )
