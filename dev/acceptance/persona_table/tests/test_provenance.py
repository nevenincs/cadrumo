"""A table runs only on a private authority proven current for the tree under test.

Descriptors are installed through the real SQLite publisher and judged by the real
currency function; only the minutes-long publication subprocess is replaced.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from cadrumo.core.hashing import sha256_hex
from cadrumo.core.resources.bundled_data import bundled_path
from dev.registry.pipeline.authority_publication import authority_source_identity, install_validated_authority_database
from dev.registry.tests.authority_generation_support import synthetic_authority_artifact

from ..provenance import (
    AUTHORITY_ROOT_VARIABLE,
    DESCRIPTOR_NAME,
    ProvenanceError,
    RunProvenance,
    meta_path,
    prepare_authority,
    read_meta,
    write_meta,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TREE = "0123456789abcdef"
_STALE_IDENTITY = sha256_hex(b"an older registry tree")


def _tree_identity() -> str:
    return authority_source_identity(
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        profile_schema_path=bundled_path("registry", "cadrumo", "user_profile", "schema.toml"),
    )


@pytest.fixture(scope="module")
def tree_identity() -> str:
    return _tree_identity()


def _publish(root: Path, identity: str) -> None:
    install_validated_authority_database(
        replace(synthetic_authority_artifact(), identity_digest=identity),
        destination=root,
        require_current=lambda: None,
    )


class _Publisher:
    """Stands in for the minutes-long publication, recording the destinations it was asked to publish."""

    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls: list[Path] = []

    def __call__(self, destination: Path) -> None:
        self.calls.append(destination)
        if self.failure is not None:
            raise self.failure


def test_current_authority_passes_and_records_descriptor_digests(tmp_path: Path, tree_identity: str) -> None:
    root = tmp_path / "authority"
    _publish(root, tree_identity)
    publisher = _Publisher()
    provenance = prepare_authority({AUTHORITY_ROOT_VARIABLE: str(root)}, tree=_TREE, publisher=publisher)
    descriptor = json.loads((root / DESCRIPTOR_NAME).read_text(encoding="utf-8"))
    assert provenance == RunProvenance(_TREE, descriptor["logical_generation"], descriptor["database_sha256"])
    assert provenance.logical_generation == tree_identity
    assert publisher.calls == [root.resolve()]


def test_authority_published_from_another_tree_aborts_naming_both_digests(tmp_path: Path, tree_identity: str) -> None:
    root = tmp_path / "authority"
    _publish(root, _STALE_IDENTITY)
    with pytest.raises(ProvenanceError) as refusal:
        prepare_authority({AUTHORITY_ROOT_VARIABLE: str(root)}, tree=_TREE, publisher=_Publisher())
    assert _STALE_IDENTITY in str(refusal.value)
    assert tree_identity in str(refusal.value)


def test_failed_publication_aborts_before_any_check(tmp_path: Path) -> None:
    root = tmp_path / "authority"
    publisher = _Publisher(failure=OSError("snapshot has no uv.lock"))
    with pytest.raises(ProvenanceError, match=r"snapshot has no uv.lock"):
        prepare_authority({AUTHORITY_ROOT_VARIABLE: str(root)}, tree=_TREE, publisher=publisher)


def test_missing_descriptor_after_publication_aborts(tmp_path: Path) -> None:
    with pytest.raises(ProvenanceError, match="not current"):
        prepare_authority({AUTHORITY_ROOT_VARIABLE: str(tmp_path / "empty")}, tree=_TREE, publisher=_Publisher())


@pytest.mark.parametrize("environment", [{}, {AUTHORITY_ROOT_VARIABLE: "  "}])
def test_unset_authority_root_aborts_without_publishing(environment: dict[str, str]) -> None:
    publisher = _Publisher()
    with pytest.raises(ProvenanceError, match=AUTHORITY_ROOT_VARIABLE):
        prepare_authority(environment, tree=_TREE, publisher=publisher)
    assert publisher.calls == []


def test_sidecar_round_trips_beside_the_rows_file(tmp_path: Path) -> None:
    rows = tmp_path / "out" / "rows.jsonl"
    provenance = RunProvenance(_TREE, "generation", "digest")
    written = write_meta(rows, provenance)
    assert written == meta_path(rows)
    assert read_meta(written) == {"tree": _TREE, "logical_generation": "generation", "database_sha256": "digest"}
    assert read_meta(meta_path(tmp_path / "absent.jsonl")) is None
