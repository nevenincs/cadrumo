"""The migration capability preserves real encrypted writes and stale-row refusal."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.modelos.calculation_repository import CalculationRevisionPersistenceError
from .....domain.modelos.calculation_revision import derive_calculation_revision_id_from_revision
from ...storage.errors import SecureObjectRevisionConflictError
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..calculation_revision_override_migration import OrphanedRelationOverrideError
from ..guarded_calculation_revision_migration import GuardedCalculationRevisionMigration
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from .test_calculation_revision_override_migration import (
    _ABSORBING_BINDING_ID,
    _BUCKET_ID,
    _OVERRIDE_VALUE,
    _RETIRED_RELATION_ID,
    _catalogue,
    _revision,
    _seed_parent_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_prepare_then_commit_migrates_the_observed_encrypted_row(tmp_path: Path) -> None:
    with (
        bundled_indexed_authority().operation() as operation,
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile,
    ):
        _seed_parent_work_unit(profile)
        repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        legacy = _revision(relation_overrides={_RETIRED_RELATION_ID: _OVERRIDE_VALUE})
        repository.save(_catalogue(legacy))
        observed = repository.load_revisioned(operation=operation)
        migration = GuardedCalculationRevisionMigration()

        plan = migration.prepare(repository, operation=operation)

        assert repository.load_revisioned(operation=operation) == observed
        assert plan.changed
        assert plan.expected_revision_id == observed[1]
        (migrated,) = tuple(plan.catalogue.values())
        assert dict(migrated.relation_overrides) == {_ABSORBING_BINDING_ID: _OVERRIDE_VALUE}
        assert migrated.calculation_revision_id == derive_calculation_revision_id_from_revision(migrated)
        assert migrated.calculation_revision_id != legacy.calculation_revision_id
        assert plan.revision_id_pairs == ((legacy.calculation_revision_id, migrated.calculation_revision_id),)
        assert plan.override_key_pairs == ((_RETIRED_RELATION_ID, _ABSORBING_BINDING_ID),)

        migration.commit(repository, plan)

        committed = repository.load_revisioned(operation=operation)
        assert committed[0] == plan.catalogue
        assert committed[1] != observed[1]
        migration.assert_current(repository, operation=operation)
        unchanged = migration.prepare(repository, operation=operation)
        assert not unchanged.changed
        assert unchanged.revision_id_pairs == ()
        assert unchanged.override_key_pairs == ()
        with pytest.raises(ValueError, match="an unchanged calculation catalogue has no migration write"):
            migration.commit(repository, unchanged)
        assert repository.load_revisioned(operation=operation) == committed


def test_commit_refuses_a_real_intervening_catalogue_write(tmp_path: Path) -> None:
    with (
        bundled_indexed_authority().operation() as operation,
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile,
    ):
        _seed_parent_work_unit(profile)
        repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        repository.save(_catalogue(_revision(relation_overrides={_RETIRED_RELATION_ID: _OVERRIDE_VALUE})))
        migration = GuardedCalculationRevisionMigration()
        plan = migration.prepare(repository, operation=operation)
        intervening = _catalogue(_revision(relation_overrides={}))
        repository.save(intervening)
        observed = repository.load_revisioned(operation=operation)
        assert observed[1] != plan.expected_revision_id

        with pytest.raises(SecureObjectRevisionConflictError):
            migration.commit(repository, plan)

        assert repository.load_revisioned(operation=operation) == observed
        assert observed[0] == intervening


def test_assert_current_refuses_a_new_legacy_row_without_writing(tmp_path: Path) -> None:
    with (
        bundled_indexed_authority().operation() as operation,
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile,
    ):
        _seed_parent_work_unit(profile)
        repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        repository.save(_catalogue(_revision(relation_overrides={})))
        migration = GuardedCalculationRevisionMigration()
        assert not migration.prepare(repository, operation=operation).changed
        repository.save(_catalogue(_revision(relation_overrides={_RETIRED_RELATION_ID: _OVERRIDE_VALUE})))
        observed = repository.load_revisioned(operation=operation)

        with pytest.raises(CalculationRevisionPersistenceError) as refusal:
            migration.assert_current(repository, operation=operation)

        assert str(refusal.value) == "calculation revisions changed after migration preparation"
        assert refusal.value.translated_message == "errors.fail.fail_modelo_calculation_revision_persistence"
        assert refusal.value.context == {"reason": "relation_override_migration_required_after_preparation"}
        assert repository.load_revisioned(operation=operation) == observed


def test_prepare_preserves_orphan_refusal_and_the_encrypted_row(tmp_path: Path) -> None:
    with (
        bundled_indexed_authority().operation() as operation,
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile,
    ):
        _seed_parent_work_unit(profile)
        repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        orphan = "modelo-303-rel-self-this-relation-never-existed"
        repository.save(_catalogue(_revision(relation_overrides={orphan: _OVERRIDE_VALUE})))
        observed = repository.load_revisioned(operation=operation)

        with pytest.raises(OrphanedRelationOverrideError) as refusal:
            GuardedCalculationRevisionMigration().prepare(repository, operation=operation)

        assert refusal.value.context is not None
        assert refusal.value.context["reason"] == "orphaned_relation_override"
        assert orphan in str(refusal.value.context["override_keys"])
        assert _OVERRIDE_VALUE not in str(refusal.value.context)
        assert repository.load_revisioned(operation=operation) == observed
