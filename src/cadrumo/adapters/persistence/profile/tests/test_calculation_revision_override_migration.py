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

import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.modelos.tests.work_unit_catalogue_support import build_work_unit_catalogue

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.calculations.registry.bindings import CasillaObservation
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
    derive_calculation_revision_id_from_revision,
)
from .....domain.modelos.work_unit import WorkUnit
from ...storage.secure_object_namespaces import MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE
from ...storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile, secure_object_select_log
from ..calculation_revision_override_migration import (
    OrphanedRelationOverrideError,
    migrate_stored_relation_overrides_to_binding_ids,
    rekey_calculation_revision_overrides,
)
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from ..modelos_work_units import WorkUnitCatalogueRepository
from ..relation_binding_join import bundled_relation_binding_join
from .m303_parent_coordinate_support import parent_work_unit_id, registry_snapshot_ref, work_unit_period
from .override_migration_support import override_migration_catalogue

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

BUCKET_ID = "9a1c77e0-4b22-4c3e-9a0e-5f0b7c1d2e34"


_CASILLA_01: CasillaId = validated_casilla_id("casilla-01", surface="_CASILLA_01")

#: One retired relation id and the binding that absorbed it, read off the frozen
#: join rather than restated, so a table edit cannot leave this suite asserting
#: a correspondence the migration no longer implements.
RETIRED_RELATION_ID = "modelo-303-rel-self-compensacion-anteriores"
ABSORBING_BINDING_ID = "modelo-303-compensacion-pendiente-anteriores"
OVERRIDE_VALUE = "50.00"
_CREATED_AT = datetime(_YEAR, 4, 2, 9, 0, 0, tzinfo=UTC)


def revision(*, relation_overrides: dict[str, str]) -> CalculationRevision:
    """Build one synthetic revision whose content address matches its contents."""
    casilla_values = {_CASILLA_01: Decimal("1000.00")}
    revision_id = derive_calculation_revision_id(
        work_unit_id=parent_work_unit_id(BUCKET_ID),
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        relation_overrides=relation_overrides,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=parent_work_unit_id(BUCKET_ID),
        registry_snapshot_ref=registry_snapshot_ref(),
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


def _parent_work_unit() -> WorkUnit:
    return WorkUnit(
        work_unit_id=parent_work_unit_id(BUCKET_ID),
        bucket_id=BUCKET_ID,
        modelo=registry_snapshot_ref().modelo,
        filing_year=registry_snapshot_ref().modelo_year,
        period=work_unit_period(),
        revision_id=registry_snapshot_ref().revision_id,
        name="303-2026-1T",
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
    )


def seed_parent_work_unit(profile: TestRuntimeProfile) -> None:
    WorkUnitCatalogueRepository(objects=profile.repository).save(
        build_work_unit_catalogue((_parent_work_unit(),)),
    )


def test_frozen_join_carries_the_retired_relation_this_suite_migrates() -> None:
    """The fixture's relation-to-binding correspondence is the shipped table's own."""
    assert bundled_relation_binding_join()[RETIRED_RELATION_ID] == ABSORBING_BINDING_ID


def test_pre_cut_relation_override_is_rekeyed_and_the_revision_id_recomputed() -> None:
    """A stored pre-absorption override moves onto its binding under a new content address."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        stored = revision(relation_overrides={RETIRED_RELATION_ID: OVERRIDE_VALUE})

        result = rekey_calculation_revision_overrides(
            override_migration_catalogue(stored), operation=_authority_operation_for_test
        )

        assert result.changed
        (remap,) = result.rekeyed_revisions
        assert remap.previous_calculation_revision_id == stored.calculation_revision_id
        assert remap.calculation_revision_id != stored.calculation_revision_id
        assert remap.work_unit_id == parent_work_unit_id(BUCKET_ID)

        migrated = result.catalogue.get(remap.calculation_revision_id)
        assert migrated is not None
        assert dict(migrated.relation_overrides) == {ABSORBING_BINDING_ID: OVERRIDE_VALUE}
        # The recomputed id is the canonical derivation of the migrated contents,
        # not a value the migration invented alongside them.
        assert derive_calculation_revision_id_from_revision(migrated) == remap.calculation_revision_id

        (move,) = result.rekeyed_override_keys
        assert (move.relation_id, move.binding_id) == (RETIRED_RELATION_ID, ABSORBING_BINDING_ID)
        assert move.calculation_revision_id == stored.calculation_revision_id


def test_override_value_appears_in_no_reported_field() -> None:
    """The run's report carries identifiers only, never the taxpayer's figure."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        result = rekey_calculation_revision_overrides(
            override_migration_catalogue(revision(relation_overrides={RETIRED_RELATION_ID: OVERRIDE_VALUE})),
            operation=_authority_operation_for_test,
        )

        reported = result.model_dump_json(exclude={"catalogue"})

        assert OVERRIDE_VALUE not in reported


def test_second_run_over_a_migrated_catalogue_changes_nothing() -> None:
    """Idempotence: re-running rekeys nothing and moves no content address."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        first = rekey_calculation_revision_overrides(
            override_migration_catalogue(revision(relation_overrides={RETIRED_RELATION_ID: OVERRIDE_VALUE})),
            operation=_authority_operation_for_test,
        )

        second = rekey_calculation_revision_overrides(first.catalogue, operation=_authority_operation_for_test)

        assert not second.changed
        assert second.rekeyed_revisions == ()
        assert second.rekeyed_override_keys == ()
        assert second.unchanged_revision_ids == tuple(sorted(first.catalogue.revisions))
        assert second.catalogue == first.catalogue


def test_unknown_override_key_is_refused_rather_than_dropped() -> None:
    """An override the frozen join cannot resolve stops the run, naming the key."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        orphan = "modelo-303-rel-self-this-relation-never-existed"
        stored = revision(relation_overrides={orphan: OVERRIDE_VALUE})

        with pytest.raises(OrphanedRelationOverrideError) as refusal:
            rekey_calculation_revision_overrides(
                override_migration_catalogue(stored), operation=_authority_operation_for_test
            )

        context = refusal.value.context
        assert context is not None
        assert context["reason"] == "orphaned_relation_override"
        assert orphan in str(context["override_keys"])
        # The refusal identifies the key, never the taxpayer figure behind it.
        assert OVERRIDE_VALUE not in str(context)


def test_revision_without_overrides_is_untouched_and_keeps_its_id() -> None:
    """A revision the migration has no business rewriting keeps its content address."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        stored = revision(relation_overrides={})

        result = rekey_calculation_revision_overrides(
            override_migration_catalogue(stored), operation=_authority_operation_for_test
        )

        assert not result.changed
        assert result.unchanged_revision_ids == (stored.calculation_revision_id,)
        assert result.catalogue.get(stored.calculation_revision_id) is stored


def test_migration_rekeys_a_catalogue_through_encrypted_storage(tmp_path: Path) -> None:
    """End to end: the stored encrypted catalogue comes back binding-keyed."""
    with (
        bundled_indexed_authority().operation() as _authority_operation_for_test,
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile,
    ):
        seed_parent_work_unit(profile)
        repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        stored = revision(relation_overrides={RETIRED_RELATION_ID: OVERRIDE_VALUE})
        repository.save(override_migration_catalogue(stored))

        result = migrate_stored_relation_overrides_to_binding_ids(repository, operation=_authority_operation_for_test)

        assert result is not None
        assert result.changed
        reloaded = repository.load()
        assert stored.calculation_revision_id not in reloaded
        (migrated,) = tuple(reloaded.values())
        assert dict(migrated.relation_overrides) == {ABSORBING_BINDING_ID: OVERRIDE_VALUE}

        # Re-running against the now-migrated encrypted row is a no-op, so a
        # migration interrupted after its write can simply be repeated.
        rerun = migrate_stored_relation_overrides_to_binding_ids(
            CalculationRevisionCatalogueRepository(objects=profile.repository),
            operation=_authority_operation_for_test,
        )
        assert rerun is not None
        assert not rerun.changed
        assert tuple(repository.load().revisions) == tuple(reloaded.revisions)


def test_one_operation_reads_the_catalogue_for_migration_once(tmp_path: Path) -> None:
    with (
        bundled_indexed_authority().operation() as operation,
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile,
    ):
        seed_parent_work_unit(profile)
        repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        repository.save(
            override_migration_catalogue(revision(relation_overrides={ABSORBING_BINDING_ID: OVERRIDE_VALUE}))
        )

        first = migrate_stored_relation_overrides_to_binding_ids(repository, operation=operation)
        second = migrate_stored_relation_overrides_to_binding_ids(repository, operation=operation)

    assert first is not None
    assert second is None


def test_the_next_operation_still_refuses_an_unknown_stored_override_key(tmp_path: Path) -> None:
    with (
        bundled_indexed_authority().operation() as operation,
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile,
    ):
        seed_parent_work_unit(profile)
        settled = CalculationRevisionCatalogueRepository(objects=profile.repository)
        settled.save(override_migration_catalogue(revision(relation_overrides={ABSORBING_BINDING_ID: OVERRIDE_VALUE})))
        migrate_stored_relation_overrides_to_binding_ids(settled, operation=operation)
        next_operation = CalculationRevisionCatalogueRepository(objects=profile.repository)
        next_operation.save(
            override_migration_catalogue(revision(relation_overrides={"not-a-known-key": OVERRIDE_VALUE}))
        )

        for _attempt in range(2):
            # A refused run settles nothing, so the operation's next caller is refused too.
            with pytest.raises(OrphanedRelationOverrideError):
                migrate_stored_relation_overrides_to_binding_ids(next_operation, operation=operation)


def _stored_catalogue_payload_selects(selects: list[str]) -> list[str]:
    """Keep only the reads that fetch the encrypted payload column, not its stored digest."""
    return [statement for statement in selects if re.search(r"\bpayload\b", statement.lower().split(" from ", 1)[0])]


def test_a_new_repository_reads_no_payload_for_a_catalogue_published_without_overrides(tmp_path: Path) -> None:
    """Each calculation composes a new repository; the bytes it published need no second read."""
    with (
        bundled_indexed_authority().operation() as operation,
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile,
    ):
        seed_parent_work_unit(profile)
        publisher = CalculationRevisionCatalogueRepository(objects=profile.repository)
        publisher.save_with_secure_object_writes(override_migration_catalogue(revision(relation_overrides={})), ())

        next_calculation = CalculationRevisionCatalogueRepository(objects=profile.repository)
        with secure_object_select_log(profile.repository.engine) as selects:
            result = migrate_stored_relation_overrides_to_binding_ids(next_calculation, operation=operation)

    assert result is None
    assert _stored_catalogue_payload_selects(selects) == []


def _catalogue_bytes_written_by_another_process(tmp_path: Path) -> bytes:
    """An override-free catalogue in bytes this process never wrote.

    The same envelope with different JSON spacing stands in for another
    process's writer: the meaning is equal while the exact bytes are new here.
    """
    with isolated_runtime_profile(tmp_path=tmp_path / "writer", bucket_id=BUCKET_ID) as writer:
        seed_parent_work_unit(writer)
        CalculationRevisionCatalogueRepository(objects=writer.repository).save(
            override_migration_catalogue(revision(relation_overrides={}))
        )
        record = writer.repository.load(
            MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.namespace,
            MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.require_default_object_key(),
            expected_class=MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.sensitivity,
            max_supported_version=MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.schema_version,
        )
    assert record is not None
    return json.dumps(json.loads(record.payload), indent=1).encode()


def test_a_catalogue_learned_override_free_by_a_read_needs_no_second_read(tmp_path: Path) -> None:
    """A row this process did not write is read once, then its exact bytes are known."""
    payload = _catalogue_bytes_written_by_another_process(tmp_path)
    with (
        bundled_indexed_authority().operation() as operation,
        isolated_runtime_profile(tmp_path=tmp_path / "reader", bucket_id=BUCKET_ID) as profile,
    ):
        seed_parent_work_unit(profile)
        profile.repository.save(
            namespace=MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.namespace,
            object_key=MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.require_default_object_key(),
            classification=MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.sensitivity,
            schema_version=MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.schema_version,
            written_at=datetime(_YEAR, 11, 9, 12, 0, 0, tzinfo=UTC),
            payload=payload,
        )

        first = migrate_stored_relation_overrides_to_binding_ids(
            CalculationRevisionCatalogueRepository(objects=profile.repository), operation=operation
        )
        second = migrate_stored_relation_overrides_to_binding_ids(
            CalculationRevisionCatalogueRepository(objects=profile.repository), operation=operation
        )

    assert first is not None
    assert not first.changed
    assert second is None


def test_a_retired_key_landing_after_an_override_free_proof_is_still_migrated(tmp_path: Path) -> None:
    """Another writer moving the row off the proven bytes makes the next run do the work."""
    with (
        bundled_indexed_authority().operation() as operation,
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile,
    ):
        seed_parent_work_unit(profile)
        proven = CalculationRevisionCatalogueRepository(objects=profile.repository)
        proven.save_with_secure_object_writes(override_migration_catalogue(revision(relation_overrides={})), ())
        assert migrate_stored_relation_overrides_to_binding_ids(proven, operation=operation) is None

        CalculationRevisionCatalogueRepository(objects=profile.repository).save(
            override_migration_catalogue(revision(relation_overrides={RETIRED_RELATION_ID: OVERRIDE_VALUE}))
        )

        next_calculation = CalculationRevisionCatalogueRepository(objects=profile.repository)
        result = migrate_stored_relation_overrides_to_binding_ids(next_calculation, operation=operation)
        reloaded = next_calculation.load(operation=operation)

    assert result is not None
    assert result.changed
    (migrated,) = tuple(reloaded.values())
    assert dict(migrated.relation_overrides) == {ABSORBING_BINDING_ID: OVERRIDE_VALUE}


def test_a_published_catalogue_holding_a_retired_key_earns_no_proof(tmp_path: Path) -> None:
    """Bytes holding any override are never remembered, so publishing one cannot skip its migration."""
    with (
        bundled_indexed_authority().operation() as operation,
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile,
    ):
        seed_parent_work_unit(profile)
        CalculationRevisionCatalogueRepository(objects=profile.repository).save_with_secure_object_writes(
            override_migration_catalogue(revision(relation_overrides={RETIRED_RELATION_ID: OVERRIDE_VALUE})),
            (),
        )

        repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
        assert not repository.stored_catalogue_is_known_override_free()
        result = migrate_stored_relation_overrides_to_binding_ids(repository, operation=operation)

    assert result is not None
    assert result.changed


def test_a_proof_for_one_store_does_not_skip_another_store_of_the_same_bucket(tmp_path: Path) -> None:
    """A second store carrying the same bucket id is judged by its own row's bytes."""
    with (
        bundled_indexed_authority().operation() as operation,
        isolated_runtime_profile(tmp_path=tmp_path / "proven", bucket_id=BUCKET_ID) as profile,
    ):
        seed_parent_work_unit(profile)
        CalculationRevisionCatalogueRepository(objects=profile.repository).save_with_secure_object_writes(
            override_migration_catalogue(revision(relation_overrides={})), ()
        )
        assert CalculationRevisionCatalogueRepository(
            objects=profile.repository
        ).stored_catalogue_is_known_override_free()
    with (
        bundled_indexed_authority().operation() as operation,
        isolated_runtime_profile(tmp_path=tmp_path / "other", bucket_id=BUCKET_ID) as other,
    ):
        seed_parent_work_unit(other)
        CalculationRevisionCatalogueRepository(objects=other.repository).save(
            override_migration_catalogue(revision(relation_overrides={RETIRED_RELATION_ID: OVERRIDE_VALUE}))
        )

        result = migrate_stored_relation_overrides_to_binding_ids(
            CalculationRevisionCatalogueRepository(objects=other.repository), operation=operation
        )

    assert result is not None
    assert result.changed
