"""A ciphertext mirror publishes or withholds co-readable namespaces as one unit.

The calculation-revision catalogue refers to rendering-snapshot rows by digest
and refuses to load without them, so a mirror that held one namespace of the
pair without the other would restore rows that refuse to load.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text

from .....adapters.outbound.storage.errors import OutboundStorageNotFoundError
from .....adapters.outbound.storage.local import LocalFileSystemProvider
from .....adapters.outbound.storage.mirror_manifest import (
    remote_mirror_object_key_hmac,
    remote_mirror_object_label,
)
from .....adapters.persistence.storage.secure_object_namespaces import (
    MODELO_CALCULATION_RENDERING_SNAPSHOT_NAMESPACE,
    MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE,
)
from .....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from .....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....tests.path_obstruction import obstructed_path
from ..mirror_push import co_readable_namespace_unit, push_secure_object_mirror_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_CATALOGUE = MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE
_SNAPSHOTS = MODELO_CALCULATION_RENDERING_SNAPSHOT_NAMESPACE
_DIGEST = "a" * 64
_WRITTEN_AT = datetime(filing_year_envelope().horizon, 5, 28, 12, 0, tzinfo=UTC)


def _seed_unit(repository: SecureObjectRepository) -> None:
    # The mirror moves ciphertext and never decodes it, so opaque payloads
    # exercise exactly the rows it reads.
    repository.save(
        namespace=_CATALOGUE.namespace,
        object_key=_CATALOGUE.require_default_object_key(),
        classification=_CATALOGUE.sensitivity,
        schema_version=_CATALOGUE.schema_version,
        written_at=_WRITTEN_AT,
        payload=b"catalogue-ciphertext-source",
    )
    repository.save(
        namespace=_SNAPSHOTS.namespace,
        object_key=_DIGEST,
        classification=_SNAPSHOTS.sensitivity,
        schema_version=_SNAPSHOTS.schema_version,
        written_at=_WRITTEN_AT,
        payload=b"rendering-body-ciphertext-source",
    )


def _raw_key(repository: SecureObjectRepository, namespace: str) -> bytes:
    return next(row.object_key for row in repository.iter_all_records_raw() if row.namespace == namespace)


def _push(repository: SecureObjectRepository, provider: LocalFileSystemProvider, namespace_filter: str | None):
    return push_secure_object_mirror_rows(
        provider=provider,
        repository=repository,
        namespace_filter=namespace_filter,
        limit=None,
        dry_run=False,
    )


def test_the_catalogue_and_its_rendering_snapshots_form_one_unit() -> None:
    unit = frozenset({_CATALOGUE.namespace, _SNAPSHOTS.namespace})
    assert co_readable_namespace_unit(_CATALOGUE.namespace) == unit
    assert co_readable_namespace_unit(_SNAPSHOTS.namespace) == unit
    assert co_readable_namespace_unit("cadrumo.domain.modelos.work_units") == frozenset(
        {"cadrumo.domain.modelos.work_units"}
    )


@pytest.mark.parametrize("selected", (_CATALOGUE.namespace, _SNAPSHOTS.namespace))
def test_a_namespace_filter_pushes_the_whole_unit(tmp_path: Path, selected: str) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="0f0e7a5c-3e2b-4c55-9d1e-6b1f0b4a2c71") as profile:
        _seed_unit(profile.repository)
        provider = LocalFileSystemProvider(tmp_path / "mirror")

        result = _push(profile.repository, provider, selected)

    expected = {_CATALOGUE.namespace: 1, _SNAPSHOTS.namespace: 1}
    assert result["pushed_by_namespace"] == expected
    assert result["manifest_pushed_by_namespace"] == expected
    assert result["failed_objects"] == []
    assert result["failed_manifests"] == []


def test_an_upload_failure_in_one_namespace_withholds_the_manifest_of_the_unit(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="5c2d9e41-7a3b-4f60-8e1d-2b9c4a6f1e03") as profile:
        _seed_unit(profile.repository)
        provider = LocalFileSystemProvider(tmp_path / "mirror")
        snapshot_hmac = remote_mirror_object_key_hmac(
            _SNAPSHOTS.namespace, _raw_key(profile.repository, _SNAPSHOTS.namespace)
        )
        blocked_target = (
            provider.root
            / _SNAPSHOTS.namespace
            / f"{snapshot_hmac[:8]}--{remote_mirror_object_label(_SNAPSHOTS.namespace)}.bin"
        )

        with obstructed_path(blocked_target):
            result = _push(profile.repository, provider, None)

    assert [failure[0] for failure in result["failed_objects"]] == [_SNAPSHOTS.namespace]
    for namespace in (_CATALOGUE.namespace, _SNAPSHOTS.namespace):
        assert namespace not in result["manifest_pushed_by_namespace"]
        assert namespace not in result["pushed_by_namespace"]
    assert (_CATALOGUE.namespace, "withheld_with_co_readable_namespace") in result["failed_manifests"]
    # Namespaces outside the unit publish as before.
    assert result["manifest_pushed_by_namespace"]


def test_a_preflight_block_in_one_namespace_blocks_the_unit_before_any_upload(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="9e4b1c7d-2f8a-4d36-b5e0-1a7c3d9f6b28") as profile:
        repository = profile.repository
        _seed_unit(repository)
        with repository._engine.begin() as connection:
            changed = connection.execute(
                text("UPDATE secure_objects SET payload_hash = :value WHERE namespace = :ns"),
                {"value": "f" * 64, "ns": _SNAPSHOTS.namespace},
            ).rowcount
        assert changed == 1
        provider = LocalFileSystemProvider(tmp_path / "mirror")

        result = _push(repository, provider, None)
        catalogue_hmac = remote_mirror_object_key_hmac(_CATALOGUE.namespace, _raw_key(repository, _CATALOGUE.namespace))

        failed_by_namespace = dict(result["failed_manifests"])
        assert "revision_lineage_inconsistent" in failed_by_namespace[_SNAPSHOTS.namespace]
        assert failed_by_namespace[_CATALOGUE.namespace] == "withheld_with_co_readable_namespace"
        assert result["failed_objects"] == []
        for namespace in (_CATALOGUE.namespace, _SNAPSHOTS.namespace):
            assert namespace not in result["pushed_by_namespace"]
            assert namespace not in result["manifest_pushed_by_namespace"]
        with pytest.raises(OutboundStorageNotFoundError):
            provider.get(_CATALOGUE.namespace, catalogue_hmac)
