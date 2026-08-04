"""Real-behavior tests for the migration source fingerprint and inventory."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.resources import bundled_path
from dev.registry.migration import (
    CorpusFileFingerprint,
    CorpusFingerprint,
    build_source_inventory,
    fingerprint_registry_corpus,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def test_bundled_inventory_pins_the_real_supported_revision_population() -> None:
    """The complete bundled registry yields the measured source population and layouts."""
    root = bundled_path("registry", "aeat")
    inventory = build_source_inventory(root)

    assert inventory.modelo_count == 73
    assert inventory.revision_count == 90
    assert inventory.corpus_fingerprint.file_count == 16_519
    assert inventory.corpus_fingerprint.locale_file_count == 281
    assert len(inventory.corpus_fingerprint.sha256) == 64
    assert inventory.modelo_ids == tuple(sorted(inventory.modelo_ids))
    assert all(item.modelo_source_layout == "directory" for item in inventory.supported_revisions)
    assert all(item.revision_source_layout == "fragment_directory" for item in inventory.supported_revisions)
    assert all(item.revision_source_paths for item in inventory.supported_revisions)

    modelo_100 = tuple(item for item in inventory.supported_revisions if item.modelo_id == "100")
    assert tuple(item.revision_id for item in modelo_100) == ("2020", "2021", "2022", "2023", "2024", "2025")
    assert all(path.startswith("modelos/100/") for item in modelo_100 for path in item.revision_source_paths)


def test_fingerprint_is_repeatable_across_roots_and_detects_same_size_content_drift(tmp_path: Path) -> None:
    """The digest excludes machine paths but changes when file content changes."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    for root in (first, second):
        (root / "nested").mkdir(parents=True)
        (root / "nested" / "a.toml").write_bytes(b"[a]\nvalue = 1\n")
        (root / "b.toml").write_bytes(b"[b]\nvalue = 22\n")

    first_fingerprint = fingerprint_registry_corpus(first)
    second_fingerprint = fingerprint_registry_corpus(second)
    assert first_fingerprint == second_fingerprint

    (second / "b.toml").write_bytes(b"[b]\nvalue = 33\n")
    changed = fingerprint_registry_corpus(second)
    assert changed.sha256 != first_fingerprint.sha256
    assert changed.files != first_fingerprint.files


def test_fingerprint_record_rejects_tampered_aggregate() -> None:
    """Strict validation prevents an evidence record from carrying a false digest."""
    file_record = CorpusFileFingerprint(relative_path="modelos/100/manifest.toml", byte_count=3, sha256="a" * 64)
    with pytest.raises(ValidationError, match="sha256 does not match"):
        CorpusFingerprint(
            file_count=1,
            byte_count=3,
            locale_file_count=0,
            sha256="b" * 64,
            files=(file_record,),
        )


def test_inventory_roundtrip_and_real_source_tree_stays_unchanged() -> None:
    """The strict inventory round-trips and leaves the live source tree untouched."""
    root = bundled_path("registry", "aeat")
    before = {
        path.relative_to(root).as_posix(): path.stat().st_mtime_ns for path in root.rglob("*.toml") if path.is_file()
    }
    inventory = build_source_inventory(root)
    round_tripped = type(inventory).model_validate_json(inventory.model_dump_json(indent=2))
    after = {
        path.relative_to(root).as_posix(): path.stat().st_mtime_ns for path in root.rglob("*.toml") if path.is_file()
    }

    assert round_tripped == inventory
    assert after == before
