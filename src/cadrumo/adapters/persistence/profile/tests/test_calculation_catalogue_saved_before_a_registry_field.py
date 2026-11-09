"""A calculation catalogue saved before a registry field existed stays readable.

The fixture is the decrypted catalogue payload a released build wrote for a
synthetic Modelo 303 2026 1T revision, under that build's own published
authority, before ``BindingDefinition.absence_attestation`` was declared. Each
revision embeds its registry snapshot and binds it by digests of that
snapshot's dumps, so a field the current models add must not change those dumps
for a snapshot that never held it: if it did, every revision the taxpayer had
saved would refuse to load after the upgrade.

The payload goes into an encrypted profile through the same secure-object store
the application uses and is read back through the production repository.
"""

from __future__ import annotations

import gzip
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from .....core.classification.policies import SensitivityClass
from ...storage.secure_object_namespaces import MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE
from ...storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from .test_calculation_repository_roundtrip import _BUCKET_ID, _seed_parent_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter, pytest.mark.usefixtures("authority_operation")]

_FIXTURE = Path(__file__).parent / "fixtures" / "calculation_catalogue_303_saved_before_absence_attestation.json.gz"
_WRITTEN_AT = datetime(2026, 11, 8, 12, 0, 0, tzinfo=UTC)


def _saved_payload() -> bytes:
    return gzip.decompress(_FIXTURE.read_bytes())


class _SavedRendering(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    authority_generation: str
    registry_digest: str
    rendering_digest: str


class _SavedRevision(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    rendering_snapshot: _SavedRendering


class _SavedCatalogue(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    revisions: dict[str, _SavedRevision]


class _SavedEnvelope(BaseModel):
    """Only what this test compares, read from the stored bytes as written."""

    model_config = ConfigDict(extra="ignore", frozen=True)
    payload: _SavedCatalogue


def _saved_renderings(payload: bytes) -> dict[str, tuple[str, str, str]]:
    """Each saved revision's id with the generation and digests its rendering was saved under."""
    revisions = _SavedEnvelope.model_validate_json(payload).payload.revisions
    return {
        revision_id: (
            revision.rendering_snapshot.authority_generation,
            revision.rendering_snapshot.registry_digest,
            revision.rendering_snapshot.rendering_digest,
        )
        for revision_id, revision in revisions.items()
    }


def _store_saved_payload(profile: TestRuntimeProfile, payload: bytes) -> None:
    profile.repository.save(
        namespace=MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.namespace,
        object_key=MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.require_default_object_key(),
        classification=SensitivityClass.FINANCIAL,
        schema_version=MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.schema_version,
        written_at=_WRITTEN_AT,
        payload=payload,
    )


@pytest.mark.parametrize("revisioned", (False, True))
def test_a_catalogue_saved_before_a_registry_field_existed_loads_with_its_saved_identity(
    tmp_path: Path, revisioned: bool
) -> None:
    payload = _saved_payload()
    saved = _saved_renderings(payload)
    assert saved, "the fixture holds at least one saved revision"

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_parent_work_unit(profile)
        _store_saved_payload(profile, payload)
        reader = CalculationRevisionCatalogueRepository(objects=profile.repository)
        loaded = reader.load_revisioned()[0] if revisioned else reader.load()

    assert set(loaded.revisions) == set(saved)
    for revision_id, revision in loaded.revisions.items():
        assert revision.calculation_revision_id == revision_id
        rendering = revision.rendering_snapshot
        assert rendering is not None
        assert (rendering.authority_generation, rendering.registry_digest, rendering.rendering_digest) == saved[
            revision_id
        ]
        assert all(binding.absence_attestation is None for binding in rendering.registry_snapshot.revision.bindings)


def test_a_catalogue_saved_before_a_registry_field_existed_is_written_again_unchanged_in_meaning(
    tmp_path: Path,
) -> None:
    payload = _saved_payload()
    saved = _saved_renderings(payload)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_parent_work_unit(profile)
        _store_saved_payload(profile, payload)
        legacy = CalculationRevisionCatalogueRepository(objects=profile.repository).load()
        # The next ordinary write re-serializes every saved snapshot with the
        # current models; the digests it was saved under must still hold.
        CalculationRevisionCatalogueRepository(objects=profile.repository).save(legacy)
        reread = CalculationRevisionCatalogueRepository(objects=profile.repository).load()
        record = profile.repository.load(
            MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.namespace,
            MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.require_default_object_key(),
            expected_class=MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.sensitivity,
            max_supported_version=MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.schema_version,
        )

    assert reread == legacy
    assert record is not None
    assert _saved_renderings(record.payload) == saved
    assert b"absence_attestation" not in record.payload
