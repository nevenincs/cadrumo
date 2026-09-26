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
from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo.domain.modelos.tests.work_unit_catalogue_support import build_work_unit_catalogue

from ....adapters.persistence.profile.calculation_revision_override_migration import (
    rekey_calculation_revision_overrides,
)
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.relation_binding_join import (
    bundled_relation_binding_join,
    bundled_relation_binding_join_targets,
)
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "1d4f2a60-5c31-4b7e-8a2d-6e0f9c3b1a77"


@cache
def _snapshot() -> RegistrySnapshot:
    # Compiled on first use, not at import: collection must stay cheap.
    return published_authority_operation().snapshot("303", filing_year=2026, period="1T")


@cache
def _snapshot_ref() -> RegistrySnapshotRef:
    return _snapshot().snapshot_ref


@cache
def _period() -> Period:
    ref = _snapshot_ref()
    return Period.from_year_and_code(ref.modelo_year, ref.period)


@cache
def _work_unit_id() -> str:
    ref = _snapshot_ref()
    return derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo=ref.modelo,
        filing_year=ref.modelo_year,
        period=_period(),
        revision_id=ref.revision_id,
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
    declared = sorted(binding.id for binding in _snapshot().revision.bindings)
    candidates = [binding_id for binding_id in declared if binding_id not in targets]
    assert candidates, "the active revision declares no binding outside the frozen join"
    return candidates[0]


def _revision(*, relation_overrides: dict[str, str]) -> CalculationRevision:
    """Build one synthetic revision whose content address matches its contents."""
    casilla_values = {_CASILLA_01: Decimal("1000.00")}
    revision_id = derive_calculation_revision_id(
        work_unit_id=_work_unit_id(),
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        relation_overrides=relation_overrides,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=_work_unit_id(),
        registry_snapshot_ref=_snapshot_ref(),
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
        build_work_unit_catalogue(
            (
                WorkUnit(
                    work_unit_id=_work_unit_id(),
                    bucket_id=_BUCKET_ID,
                    modelo=_snapshot_ref().modelo,
                    filing_year=_snapshot_ref().modelo_year,
                    period=_period(),
                    revision_id=_snapshot_ref().revision_id,
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
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        binding_id = _post_cut_binding_id()
        assert binding_id not in bundled_relation_binding_join()
        stored = _revision(relation_overrides={binding_id: _OVERRIDE_VALUE})

        result = rekey_calculation_revision_overrides(_catalogue(stored), operation=_authority_operation_for_test)

        assert not result.changed
        assert result.unchanged_revision_ids == (stored.calculation_revision_id,)
        carried = result.catalogue.get(stored.calculation_revision_id)
        assert carried is not None
        assert dict(carried.relation_overrides) == {binding_id: _OVERRIDE_VALUE}


def test_calculation_read_path_migrates_the_stored_catalogue(tmp_path: Path) -> None:
    """The production calculation path rekeys a pre-cut store it finds on disk.

    The entry point is the real calculation read path, not the migration
    helper: it is invoked exactly as the calculate actions invoke it, with no
    repository injected, so the assertion is that the wiring exists rather than
    that the migration works in isolation.
    """
    from ....application.modelo.calculation_actions import list_calculation_revisions
    from .file_flow_test_support import calculation_ports_for_test

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_parent_work_unit(profile)
        repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        stored = _revision(relation_overrides={_RETIRED_RELATION_ID: _OVERRIDE_VALUE})
        repository.save(_catalogue(stored))

        work_unit = WorkUnitCatalogueRepository(objects=profile.repository).load().get(_work_unit_id())
        assert work_unit is not None
        with calculation_ports_for_test(bucket_id=work_unit.bucket_id) as ports:
            list_calculation_revisions(ports=ports, work_unit_id=work_unit.work_unit_id)

        reloaded = repository.load()
        assert stored.calculation_revision_id not in reloaded
        (migrated,) = tuple(reloaded.values())
        assert dict(migrated.relation_overrides) == {
            bundled_relation_binding_join()[_RETIRED_RELATION_ID]: _OVERRIDE_VALUE,
        }
