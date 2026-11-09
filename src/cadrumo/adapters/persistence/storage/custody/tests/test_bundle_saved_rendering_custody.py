"""A portable profile bundle carries saved renderings whole and imports them back by reference.

Renderings are stored once per profile in their own namespace and referenced
by digest from the calculation-revision catalogue. The bundle exports each
calculation revision with its rendering whole, so the snapshot namespace
travels inside that typed category; an import saves the revisions through
the ordinary repository and stores each rendering again. A catalogue restored
without its rendering rows cannot be read.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.embedded_rendering_fixture import (
    EMBEDDED_RENDERING_FIXTURE_BUCKET_ID,
    install_embedded_rendering_fixture,
)
from cadrumo.adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from cadrumo.adapters.persistence.storage.secure_object_namespaces import (
    MODELO_CALCULATION_RENDERING_SNAPSHOT_NAMESPACE,
    MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    profile_authority_contexts,
    seed_test_profile_record,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from cadrumo.application.user_profile.bundle import serialize_profile_bundle
from cadrumo.core.storage_taxonomy import StorageCustodyProfile
from cadrumo.domain.modelos.calculation_repository import CalculationRevisionPersistenceError
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionCatalogue
from cadrumo.domain.modelos.work_unit import WorkUnitCatalogue
from cadrumo.domain.user_profile.portable_export import UserProfilePortableExport
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, create_user_profile_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_BUCKET_ID = EMBEDDED_RENDERING_FIXTURE_BUCKET_ID
_CATALOGUE = MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE
_SNAPSHOTS = MODELO_CALCULATION_RENDERING_SNAPSHOT_NAMESPACE


def _converted_source(profile: TestRuntimeProfile) -> CalculationRevisionCatalogue:
    """Install the embedded fixture and write it once, so the source stores renderings by reference."""
    operation = published_authority_operation()
    install_embedded_rendering_fixture(profile)
    repository = CalculationRevisionCatalogueRepository(objects=profile.repository)
    repository.save(repository.load(operation=operation))
    return CalculationRevisionCatalogueRepository(objects=profile.repository).load(operation=operation)


def _seed_profile_record() -> None:
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.INCOMPLETE,
            profile_id=_BUCKET_ID,
            facts=(),
            context=profile_creation_context_for_test(),
        ),
    )


def test_a_full_bundle_carries_saved_renderings_whole_and_imports_them_by_reference(tmp_path: Path) -> None:
    operation = published_authority_operation()
    _create_context, decode_context = profile_authority_contexts()
    with isolated_runtime_profile(tmp_path=tmp_path / "source", bucket_id=_BUCKET_ID) as source:
        _seed_profile_record()
        stored = _converted_source(source)
        assert len(source.repository.list_keys(_SNAPSHOTS.namespace)) == 2
        with bound_test_profile_record(_BUCKET_ID):
            bundle = serialize_profile_bundle(
                bucket_id=_BUCKET_ID,
                custody_profile=StorageCustodyProfile.FULL,
                profile_decode_context=decode_context,
                authority_operation=operation,
            )
        work_units = WorkUnitCatalogueRepository(objects=source.repository).load()
    transported = bundle.model_dump_json()

    with isolated_runtime_profile(tmp_path=tmp_path / "target", bucket_id=_BUCKET_ID) as target:
        imported = UserProfilePortableExport.model_validate_json(transported, context=decode_context)
        WorkUnitCatalogueRepository(objects=target.repository).save(
            WorkUnitCatalogue(work_units={unit.work_unit_id: unit for unit in imported.work_units})
        )
        CalculationRevisionCatalogueRepository(objects=target.repository).save(
            CalculationRevisionCatalogue(
                revisions={revision.calculation_revision_id: revision for revision in imported.calculation_revisions}
            )
        )
        restored = CalculationRevisionCatalogueRepository(objects=target.repository).load(operation=operation)
        restored_snapshot_keys = target.repository.list_keys(_SNAPSHOTS.namespace)

    assert tuple(imported.work_units) == tuple(work_units)
    assert imported.calculation_revisions == tuple(stored)
    exported = json.loads(transported)["calculation_revisions"]
    assert sum(revision.get("rendering_snapshot") is not None for revision in exported) == 3
    assert all(
        "registry_snapshot" in revision["rendering_snapshot"]
        for revision in exported
        if revision.get("rendering_snapshot") is not None
    )
    assert _SNAPSHOTS.namespace not in {carried.namespace for carried in bundle.carried_objects}
    assert _SNAPSHOTS.namespace in bundle.coverage_manifest.excluded_namespaces
    assert restored == stored
    assert len(restored_snapshot_keys) == 2


def test_a_catalogue_restored_without_its_rendering_rows_refuses(tmp_path: Path) -> None:
    operation = published_authority_operation()
    with isolated_runtime_profile(tmp_path=tmp_path / "source", bucket_id=_BUCKET_ID) as source:
        _converted_source(source)
        record = source.repository.load(
            _CATALOGUE.namespace,
            _CATALOGUE.require_default_object_key(),
            expected_class=_CATALOGUE.sensitivity,
            max_supported_version=_CATALOGUE.schema_version,
        )
        assert record is not None

    with isolated_runtime_profile(tmp_path=tmp_path / "target", bucket_id=_BUCKET_ID) as target:
        install_embedded_rendering_fixture(target, with_calculations=False)
        target.repository.save(
            namespace=_CATALOGUE.namespace,
            object_key=_CATALOGUE.require_default_object_key(),
            classification=record.classification,
            schema_version=record.schema_version,
            written_at=record.written_at,
            payload=record.payload,
        )
        with pytest.raises(CalculationRevisionPersistenceError) as refused:
            CalculationRevisionCatalogueRepository(objects=target.repository).load(operation=operation)

    assert refused.value.context == {"reason": "rendering_snapshot_missing"}
