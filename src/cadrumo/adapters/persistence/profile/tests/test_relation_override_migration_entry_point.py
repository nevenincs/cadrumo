"""The override migration must be reached by the calculation path, and must not
refuse an override written after the cut.

Two properties the pure rekey cannot prove on its own:

*It runs.* A forward stored-data migration that nothing invokes is a function,
not a migration: the stored catalogue keeps its retired keys, the operator's
figure keeps not applying, and every test of the pure half keeps passing. This
suite drives it through the production source-mesh entry point that constructs
the calculation-revision repository, over an encrypted store, and asserts the
stored bytes changed.

*It does not over-refuse.* The frozen join describes the vocabulary as it stood
at the cut. A binding authored AFTER it is unknown to the join, so an override
keyed by one would be classified as an orphan and refused on every future run --
permanently unreachable, which is the same lost figure the migration exists to
prevent, reached from the other side. The classification therefore also admits
what the revision's own registry snapshot declares.

Every value here is synthetic: an invented bucket uuid, a fabricated work unit,
and a round euro figure.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.period import Period
from .....domain.calculations.registry.authority import bundled_authority
from .....domain.calculations.registry.bindings import CasillaObservation
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from .....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ..calculation_revision_override_migration import rekey_calculation_revision_overrides
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from ..modelos_work_units import WorkUnitCatalogueRepository
from ..relation_binding_join import bundled_relation_binding_join, bundled_relation_binding_join_targets

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "1d4f2a60-5c31-4b7e-8a2d-6e0f9c3b1a77"
_SNAPSHOT = bundled_authority().snapshot("303", filing_year=2026, period="1T")
_SNAPSHOT_REF = _SNAPSHOT.snapshot_ref
_PERIOD = Period.from_year_and_code(_SNAPSHOT_REF.modelo_year, _SNAPSHOT_REF.period)
_WORK_UNIT_ID = derive_work_unit_id(
    bucket_id=_BUCKET_ID,
    modelo=_SNAPSHOT_REF.modelo,
    filing_year=_SNAPSHOT_REF.modelo_year,
    period=_PERIOD,
    revision_id=_SNAPSHOT_REF.revision_id,
)
_CASILLA_01: CasillaId = validated_casilla_id("casilla-01", surface="_CASILLA_01")
_CREATED_AT = datetime(2026, 4, 2, 9, 0, 0, tzinfo=UTC)
_OVERRIDE_VALUE = "125.00"

#: Read off the frozen join rather than restated, so a table edit cannot leave
#: this suite asserting a correspondence the migration no longer implements.
_RETIRED_RELATION_ID = "modelo-303-rel-self-compensacion-anteriores"


def _post_cut_binding_id() -> str:
    """A binding the active revision declares that the frozen join never names.

    This is the shape the over-refusal would hit: current vocabulary, absent
    from the pre-cut table. It is derived from the live snapshot rather than
    hard-coded so it cannot quietly become a join target and stop testing
    anything.
    """
    targets = bundled_relation_binding_join_targets()
    declared = sorted(binding.id for binding in _SNAPSHOT.revision.bindings)
    candidates = [binding_id for binding_id in declared if binding_id not in targets]
    assert candidates, "the active revision declares no binding outside the frozen join"
    return candidates[0]


def _revision(*, relation_overrides: dict[str, str]) -> CalculationRevision:
    """Build one synthetic revision whose content address matches its contents."""
    casilla_values = {_CASILLA_01: Decimal("1000.00")}
    revision_id = derive_calculation_revision_id(
        work_unit_id=_WORK_UNIT_ID,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        relation_overrides=relation_overrides,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=_WORK_UNIT_ID,
        registry_snapshot_ref=_SNAPSHOT_REF,
        state=CalculationRevisionState.BORRADOR,
        filing_instance_evidence=None,
        casilla_values=casilla_values,
        observations=(
            CasillaObservation(
                casilla_id=_CASILLA_01,
                value=Decimal("1000.00"),
                formula_id=None,
                operand_refs=(),
                operand_casilla_refs=(),
                operand_values=(),
                legal_refs=("ley-37-1992:art-78",),
                source_refs=("aeat-modelo-303-instrucciones-2026",),
            ),
        ),
        relation_overrides=relation_overrides,
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
        source_provenance=(),
    )


def _catalogue(revision: CalculationRevision) -> CalculationRevisionCatalogue:
    return CalculationRevisionCatalogue(revisions={revision.calculation_revision_id: revision})


def _seed_parent_work_unit(profile: TestRuntimeProfile) -> None:
    WorkUnitCatalogueRepository(objects=profile.repository).save(
        WorkUnitCatalogue.from_work_units(
            (
                WorkUnit(
                    work_unit_id=_WORK_UNIT_ID,
                    bucket_id=_BUCKET_ID,
                    modelo=_SNAPSHOT_REF.modelo,
                    filing_year=_SNAPSHOT_REF.modelo_year,
                    period=_PERIOD,
                    revision_id=_SNAPSHOT_REF.revision_id,
                    name="303-2026-1T",
                    created_at=_CREATED_AT,
                    updated_at=_CREATED_AT,
                ),
            ),
        ),
    )


def test_post_cut_binding_override_is_preserved_unchanged() -> None:
    """An override keyed by a binding authored after the cut survives the rekey.

    The join cannot know the key, so the classification falls to the revision's
    own registry snapshot. Getting this wrong refuses the revision forever.
    """
    binding_id = _post_cut_binding_id()
    assert binding_id not in bundled_relation_binding_join()
    stored = _revision(relation_overrides={binding_id: _OVERRIDE_VALUE})

    result = rekey_calculation_revision_overrides(_catalogue(stored))

    assert not result.changed
    assert result.unchanged_revision_ids == (stored.calculation_revision_id,)
    carried = result.catalogue.get(stored.calculation_revision_id)
    assert carried is not None
    assert dict(carried.relation_overrides) == {binding_id: _OVERRIDE_VALUE}


def test_calculation_source_mesh_migrates_the_stored_catalogue(tmp_path: Path) -> None:
    """The production calculation path rekeys a pre-cut store it finds on disk.

    The entry point is the real source-mesh resolution, not the migration
    helper: it is invoked exactly as a calculate run invokes it, with no
    repository injected, so the assertion is that the wiring exists rather than
    that the migration works in isolation.
    """
    from .....application.modelo.calculation_actions import resolve_bucket_source_mesh

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_parent_work_unit(profile)
        repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        stored = _revision(relation_overrides={_RETIRED_RELATION_ID: _OVERRIDE_VALUE})
        repository.save(_catalogue(stored))

        work_unit = WorkUnitCatalogueRepository(objects=profile.repository).load().get(_WORK_UNIT_ID)
        assert work_unit is not None
        resolve_bucket_source_mesh(
            _SNAPSHOT,
            work_unit,
            transaction_repository=None,
            invoice_repository=None,
            foreign_asset_observations=(),
            foreign_asset_row_observations=(),
        )

        reloaded = repository.load()
        assert stored.calculation_revision_id not in reloaded
        (migrated,) = tuple(reloaded.values())
        assert dict(migrated.relation_overrides) == {
            bundled_relation_binding_join()[_RETIRED_RELATION_ID]: _OVERRIDE_VALUE,
        }
