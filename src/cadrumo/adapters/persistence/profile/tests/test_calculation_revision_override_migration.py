"""Stored-data migration rekeying persisted relation overrides onto binding ids.

Every fixture value here is synthetic: an invented bucket uuid, a fabricated
work unit, and round euro figures chosen to be arithmetically obvious. No real
taxpayer identity, filed figure, or evidence blob appears.

The suite proves the four properties the migration claims, each against a case
that would fail if the property were absent:

* a revision carrying a pre-absorption relation-id override comes out keyed by
  the binding that inherited the join, under a RECOMPUTED content address;
* a second run over the already-migrated catalogue is a byte-level no-op,
  which is what makes the migration re-runnable after a partial failure;
* an override key the frozen join does not know is REFUSED, naming the key,
  rather than dropped -- the failure mode the migration exists to prevent;
* a revision carrying no overrides is untouched and keeps its content address,
  so the migration cannot churn revisions it has no business rewriting.
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
    derive_calculation_revision_id_from_revision,
)
from .....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from .....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ..calculation_revision_override_migration import (
    OrphanedRelationOverrideError,
    migrate_stored_relation_overrides_to_binding_ids,
    rekey_calculation_revision_overrides,
)
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from ..modelos_work_units import WorkUnitCatalogueRepository
from ..relation_binding_join import bundled_relation_binding_join

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "9a1c77e0-4b22-4c3e-9a0e-5f0b7c1d2e34"
_REGISTRY_SNAPSHOT_REF = bundled_authority().snapshot("303", filing_year=2026, period="1T").snapshot_ref
_WORK_UNIT_PERIOD = Period.from_year_and_code(_REGISTRY_SNAPSHOT_REF.modelo_year, _REGISTRY_SNAPSHOT_REF.period)
_WORK_UNIT_ID = derive_work_unit_id(
    bucket_id=_BUCKET_ID,
    modelo=_REGISTRY_SNAPSHOT_REF.modelo,
    filing_year=_REGISTRY_SNAPSHOT_REF.modelo_year,
    period=_WORK_UNIT_PERIOD,
    revision_id=_REGISTRY_SNAPSHOT_REF.revision_id,
)
_CASILLA_01: CasillaId = validated_casilla_id("casilla-01", surface="_CASILLA_01")

#: One retired relation id and the binding that absorbed it, read off the frozen
#: join rather than restated, so a table edit cannot leave this suite asserting
#: a correspondence the migration no longer implements.
_RETIRED_RELATION_ID = "modelo-303-rel-self-compensacion-anteriores"
_ABSORBING_BINDING_ID = "modelo-303-compensacion-pendiente-anteriores"
_OVERRIDE_VALUE = "50.00"
_CREATED_AT = datetime(2026, 4, 2, 9, 0, 0, tzinfo=UTC)


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
        registry_snapshot_ref=_REGISTRY_SNAPSHOT_REF,
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


def _parent_work_unit() -> WorkUnit:
    return WorkUnit(
        work_unit_id=_WORK_UNIT_ID,
        bucket_id=_BUCKET_ID,
        modelo=_REGISTRY_SNAPSHOT_REF.modelo,
        filing_year=_REGISTRY_SNAPSHOT_REF.modelo_year,
        period=_WORK_UNIT_PERIOD,
        revision_id=_REGISTRY_SNAPSHOT_REF.revision_id,
        name="303-2026-1T",
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
    )


def _seed_parent_work_unit(profile: TestRuntimeProfile) -> None:
    WorkUnitCatalogueRepository(objects=profile.repository).save(
        WorkUnitCatalogue.from_work_units((_parent_work_unit(),)),
    )


def test_frozen_join_carries_the_retired_relation_this_suite_migrates() -> None:
    """The fixture's relation-to-binding correspondence is the shipped table's own."""
    assert bundled_relation_binding_join()[_RETIRED_RELATION_ID] == _ABSORBING_BINDING_ID


def test_pre_cut_relation_override_is_rekeyed_and_the_revision_id_recomputed() -> None:
    """A stored pre-absorption override moves onto its binding under a new content address."""
    stored = _revision(relation_overrides={_RETIRED_RELATION_ID: _OVERRIDE_VALUE})

    result = rekey_calculation_revision_overrides(_catalogue(stored))

    assert result.changed
    (remap,) = result.rekeyed_revisions
    assert remap.previous_calculation_revision_id == stored.calculation_revision_id
    assert remap.calculation_revision_id != stored.calculation_revision_id
    assert remap.work_unit_id == _WORK_UNIT_ID

    migrated = result.catalogue.get(remap.calculation_revision_id)
    assert migrated is not None
    assert dict(migrated.relation_overrides) == {_ABSORBING_BINDING_ID: _OVERRIDE_VALUE}
    # The recomputed id is the canonical derivation of the migrated contents,
    # not a value the migration invented alongside them.
    assert derive_calculation_revision_id_from_revision(migrated) == remap.calculation_revision_id

    (move,) = result.rekeyed_override_keys
    assert (move.relation_id, move.binding_id) == (_RETIRED_RELATION_ID, _ABSORBING_BINDING_ID)
    assert move.calculation_revision_id == stored.calculation_revision_id


def test_override_value_appears_in_no_reported_field() -> None:
    """The run's report carries identifiers only, never the taxpayer's figure."""
    result = rekey_calculation_revision_overrides(
        _catalogue(_revision(relation_overrides={_RETIRED_RELATION_ID: _OVERRIDE_VALUE})),
    )

    reported = result.model_dump_json(exclude={"catalogue"})

    assert _OVERRIDE_VALUE not in reported


def test_second_run_over_a_migrated_catalogue_changes_nothing() -> None:
    """Idempotence: re-running rekeys nothing and moves no content address."""
    first = rekey_calculation_revision_overrides(
        _catalogue(_revision(relation_overrides={_RETIRED_RELATION_ID: _OVERRIDE_VALUE})),
    )

    second = rekey_calculation_revision_overrides(first.catalogue)

    assert not second.changed
    assert second.rekeyed_revisions == ()
    assert second.rekeyed_override_keys == ()
    assert second.unchanged_revision_ids == tuple(sorted(first.catalogue.revisions))
    assert second.catalogue == first.catalogue


def test_unknown_override_key_is_refused_rather_than_dropped() -> None:
    """An override the frozen join cannot resolve stops the run, naming the key."""
    orphan = "modelo-303-rel-self-this-relation-never-existed"
    stored = _revision(relation_overrides={orphan: _OVERRIDE_VALUE})

    with pytest.raises(OrphanedRelationOverrideError) as refusal:
        rekey_calculation_revision_overrides(_catalogue(stored))

    context = refusal.value.context
    assert context is not None
    assert context["reason"] == "orphaned_relation_override"
    assert orphan in str(context["override_keys"])
    # The refusal identifies the key, never the taxpayer figure behind it.
    assert _OVERRIDE_VALUE not in str(context)


def test_revision_without_overrides_is_untouched_and_keeps_its_id() -> None:
    """A revision the migration has no business rewriting keeps its content address."""
    stored = _revision(relation_overrides={})

    result = rekey_calculation_revision_overrides(_catalogue(stored))

    assert not result.changed
    assert result.unchanged_revision_ids == (stored.calculation_revision_id,)
    assert result.catalogue.get(stored.calculation_revision_id) is stored


def test_migration_rekeys_a_catalogue_through_encrypted_storage(tmp_path: Path) -> None:
    """End to end: the stored encrypted catalogue comes back binding-keyed."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_parent_work_unit(profile)
        repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        stored = _revision(relation_overrides={_RETIRED_RELATION_ID: _OVERRIDE_VALUE})
        repository.save(_catalogue(stored))

        result = migrate_stored_relation_overrides_to_binding_ids(repository)

        assert result.changed
        reloaded = repository.load()
        assert stored.calculation_revision_id not in reloaded
        (migrated,) = tuple(reloaded.values())
        assert dict(migrated.relation_overrides) == {_ABSORBING_BINDING_ID: _OVERRIDE_VALUE}

        # Re-running against the now-migrated encrypted row is a no-op, so a
        # migration interrupted after its write can simply be repeated.
        rerun = migrate_stored_relation_overrides_to_binding_ids(repository)
        assert not rerun.changed
        assert tuple(repository.load().revisions) == tuple(reloaded.revisions)
