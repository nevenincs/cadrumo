"""Validation-verdict cache location and helper roundtrip behavior.

These tests exercise the real filesystem helpers of ``_validate_verdict``:
the settings-derived writable location, the shipped bundled-tree location, the
atomic write/read roundtrip, foreign-file tolerance, and the delete-on-mismatch
branch. The authority-integration regression pin (skip-validation on a hit,
corpus-cache write counts, re-validation on a fingerprint change) lives in the
sibling ``test_validation_verdict_cache`` module.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.config import override_settings
from .....core.resources import bundled_path
from .._validate_verdict import (
    VERDICT_OUTCOME_GREEN,
    ValidationVerdict,
    bundled_verdict_path,
    certify_registry_validation,
    compute_verdict_key,
    read_verdict,
    registry_validation_is_certified,
    verdict_cache_path,
    write_verdict,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_verdict_cache_path_derives_under_cache_namespace(tmp_path: Path) -> None:
    root = tmp_path / "registry" / "aeat"
    with override_settings(cadrumo_local_storage_root=tmp_path / "state"):
        path = verdict_cache_path(root)
    assert path.parent == tmp_path / "state" / "cache" / "registry-verdict"
    assert path.name.startswith("cadrumo_validation_verdict_")
    assert path.suffix == ".json"


def test_distinct_roots_get_distinct_verdict_files(tmp_path: Path) -> None:
    with override_settings(cadrumo_validation_verdict_cache_dir=tmp_path / "verdicts"):
        first = verdict_cache_path(tmp_path / "registry-a" / "aeat")
        second = verdict_cache_path(tmp_path / "registry-b" / "aeat")
    assert first != second


def test_bundled_verdict_path_is_a_sibling_of_the_bundled_tree() -> None:
    bundled_root = bundled_path("registry", "aeat").resolve()
    shipped = bundled_verdict_path(bundled_root)
    assert shipped is not None
    assert shipped == bundled_root.parent / "aeat-validation-verdict.json"
    # The shipped verdict is never inside the fingerprinted tree it certifies.
    assert bundled_root not in shipped.parents


def test_bundled_verdict_path_is_none_for_a_mutable_authoring_tree(tmp_path: Path) -> None:
    assert bundled_verdict_path(tmp_path / "registry" / "aeat") is None


def test_write_read_roundtrip_preserves_the_verdict(tmp_path: Path) -> None:
    path = tmp_path / "verdict.json"
    verdict = ValidationVerdict(verdict_key="abc123", package_version="9.9.9", outcome=VERDICT_OUTCOME_GREEN)
    write_verdict(path, verdict)
    assert path.is_file()
    assert read_verdict(path) == verdict


def test_read_verdict_ignores_a_foreign_file(tmp_path: Path) -> None:
    path = tmp_path / "verdict.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert read_verdict(path) is None
    # A green-shaped but extra-field payload is rejected by the strict model.
    path.write_text('{"verdict_key": "k", "package_version": "1", "outcome": "green", "extra": 1}', encoding="utf-8")
    assert read_verdict(path) is None


def test_read_verdict_returns_none_when_absent(tmp_path: Path) -> None:
    assert read_verdict(tmp_path / "missing.json") is None


def test_certify_then_matching_key_is_certified(tmp_path: Path) -> None:
    root = tmp_path / "registry" / "aeat"
    key = compute_verdict_key(
        registry_fingerprints=(("a.toml", 1, 2, "digest-a"),),
        source_evidence_fingerprints=(("b.pdf", 3, 4),),
        package_version="1.2.3",
    )
    with override_settings(cadrumo_validation_verdict_cache_dir=tmp_path / "verdicts"):
        written = certify_registry_validation(root, verdict_key=key, package_version="1.2.3")
        assert written.is_file()
        assert registry_validation_is_certified(root, verdict_key=key, registry_fingerprints=()) is True


def test_mismatched_key_is_not_certified_and_deletes_the_stale_verdict(tmp_path: Path) -> None:
    root = tmp_path / "registry" / "aeat"
    with override_settings(cadrumo_validation_verdict_cache_dir=tmp_path / "verdicts"):
        written = certify_registry_validation(root, verdict_key="stored-key", package_version="1.2.3")
        assert written.is_file()
        assert registry_validation_is_certified(root, verdict_key="different-key", registry_fingerprints=()) is False
        # Delete-not-migrate: the stale writable verdict is removed so the next
        # load re-validates rather than trusting a superseded fingerprint.
        assert not written.exists()


def test_compute_verdict_key_is_sensitive_to_every_input() -> None:
    reg = (("a.toml", 1, 2, "digest-a"),)
    src = (("b.pdf", 3, 4),)
    key = compute_verdict_key(registry_fingerprints=reg, source_evidence_fingerprints=src, package_version="1.0.0")
    assert key != compute_verdict_key(
        registry_fingerprints=reg, source_evidence_fingerprints=src, package_version="1.0.1"
    )
    assert key != compute_verdict_key(
        registry_fingerprints=(("a.toml", 1, 3, "digest-a"),),
        source_evidence_fingerprints=src,
        package_version="1.0.0",
    )
    # A same-size, same-mtime content change re-keys via the digest slot alone.
    assert key != compute_verdict_key(
        registry_fingerprints=(("a.toml", 1, 2, "digest-b"),),
        source_evidence_fingerprints=src,
        package_version="1.0.0",
    )
    assert key != compute_verdict_key(
        registry_fingerprints=reg,
        source_evidence_fingerprints=(("b.pdf", 9, 4),),
        package_version="1.0.0",
    )
    # A tuple moving between the two groups must not collide (group label mixed
    # in). The registry copy carries the empty bundled-tree digest so its hashed
    # byte stream matches the source-evidence tuple's exactly but for the label.
    swapped = compute_verdict_key(
        registry_fingerprints=(("b.pdf", 3, 4, ""),),
        source_evidence_fingerprints=(("a.toml", 1, 2),),
        package_version="1.0.0",
    )
    assert key != swapped
