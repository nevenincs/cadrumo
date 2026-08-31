"""Focused integration tests for the corpus_manifest module.

The corpus_manifest module implements the SHA-256 directory-level
integrity gate for CORPUS-class plaintext-at-rest reference material
(AEAT manuals, BOE corpora, legal-text caches). Currently zero
dedicated test coverage; a regression in the SHA-256 dispatch, the
manifest-self-attestation digest, or the drift detection would
silently allow tampered corpus material into operator-facing tax
computations.

Tests here are structural / contract assertions on the manifest
mechanism — they verify the build → save → load roundtrip, the four
drift categories (added / removed / changed / hidden-skip), and the
tamper-detection failure path. No calculation tautologies are
involved; the assertions check that the manifest mechanism preserves
integrity, not that any particular file's hash equals a hand-computed
expected value.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ..errors import CorpusManifestDriftError, CorpusManifestTamperError
from ..manifest import (
    assert_corpus_clean,
    build_corpus_manifest,
    load_corpus_manifest,
    manifest_path_for,
    save_corpus_manifest,
    verify_corpus_manifest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_GENERATED_AT = datetime(2026, 5, 12, 12, 0, 0, tzinfo=UTC)


def _seed_corpus(corpus_root: Path) -> dict[str, bytes]:
    """Seed a tmp corpus with two text files and one binary file.

    Returns the relative-path-to-bytes mapping so individual tests can
    assert on declared content vs manifest content.
    """
    corpus_root.mkdir(parents=True, exist_ok=True)
    files = {
        "manual.txt": b"Sample manual content for hashing.",
        "subdir/notes.txt": b"Nested note content with different bytes.",
        "subdir/binary.bin": bytes(range(256)),
    }
    for relative, content in files.items():
        path = corpus_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return files


def _build_seeded_manifest(corpus_root: Path):
    _seed_corpus(corpus_root)
    return build_corpus_manifest(
        corpus_root,
        corpus_root_name="manuals",
        generated_at=_GENERATED_AT,
    )


def test_build_save_load_roundtrip_preserves_sorted_entries(tmp_path: Path) -> None:
    corpus_root = tmp_path / "corpus"
    built = _build_seeded_manifest(corpus_root)
    save_corpus_manifest(built, manifest_path_for(corpus_root))
    loaded = load_corpus_manifest(manifest_path_for(corpus_root))

    paths = [entry.relative_path for entry in built.entries]
    assert paths == sorted(paths)
    assert loaded.corpus_root_name == "manuals"
    assert loaded.manifest_sha256 == built.manifest_sha256
    assert tuple(entry.relative_path for entry in loaded.entries) == tuple(
        entry.relative_path for entry in built.entries
    )
    assert tuple(entry.sha256 for entry in loaded.entries) == tuple(entry.sha256 for entry in built.entries)
    assert tuple(entry.content_length for entry in loaded.entries) == tuple(
        entry.content_length for entry in built.entries
    )


def test_verify_reports_each_drift_category(tmp_path: Path) -> None:
    scenarios = (
        ("added", "new-file.txt", "added"),
        ("removed", "subdir/notes.txt", "removed"),
        ("changed", "manual.txt", "changed"),
    )

    for scenario, expected_path, changed_category in scenarios:
        corpus_root = tmp_path / scenario
        manifest = _build_seeded_manifest(corpus_root)

        if changed_category == "added":
            (corpus_root / expected_path).write_bytes(b"appeared after manifest was built")
        elif changed_category == "removed":
            (corpus_root / expected_path).unlink()
        else:
            (corpus_root / expected_path).write_bytes(b"Mutated bytes do not match the original sha256.")

        diff = verify_corpus_manifest(corpus_root, manifest=manifest)

        assert diff.is_clean is False, scenario
        assert expected_path in getattr(diff, changed_category), scenario
        for clean_category in {"added", "removed", "changed"} - {changed_category}:
            assert getattr(diff, clean_category) == (), scenario


def test_iter_corpus_files_skips_hidden_entries_and_the_manifest_sidecar(tmp_path: Path) -> None:
    """Hidden dotfiles and the canonical manifest sidecar must not
    appear in the manifest's entry list; otherwise the manifest covers
    itself recursively or attests to editor cruft as canonical corpus
    content."""
    corpus_root = tmp_path / "corpus"
    _seed_corpus(corpus_root)
    # Hidden dot-prefixed file at root and inside subdir.
    (corpus_root / ".gitignore").write_bytes(b"editor cruft")
    (corpus_root / ".dotdir").mkdir()
    (corpus_root / ".dotdir" / "secret.txt").write_bytes(b"hidden directory file")

    manifest = build_corpus_manifest(corpus_root, corpus_root_name="manuals", generated_at=_GENERATED_AT)

    paths = {entry.relative_path for entry in manifest.entries}
    assert ".gitignore" not in paths
    assert ".dotdir/secret.txt" not in paths
    assert paths == {"manual.txt", "subdir/notes.txt", "subdir/binary.bin"}

    save_corpus_manifest(manifest, manifest_path_for(corpus_root))
    loaded_manifest = load_corpus_manifest(manifest_path_for(corpus_root))
    rewalk = verify_corpus_manifest(corpus_root, manifest=loaded_manifest)
    assert rewalk.is_clean is True


def test_load_raises_tamper_error_when_manifest_sha256_does_not_match_body(tmp_path: Path) -> None:
    """Mutating the recorded ``manifest_sha256`` on disk must trip the
    self-attesting digest check at load time."""
    corpus_root = tmp_path / "corpus"
    manifest = _build_seeded_manifest(corpus_root)
    target = manifest_path_for(corpus_root)
    save_corpus_manifest(manifest, target)

    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["manifest_sha256"] = "0" * 64
    target.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CorpusManifestTamperError) as tamper:
        load_corpus_manifest(target)

    # The refusal is catalogue-rendered, so the digest that failed is a fact on
    # the error rather than a phrase inside its sentence.
    context = tamper.value.context or {}
    assert context["digest_field"] == "manifest_sha256"
    assert context["manifest_sha256_matches_body"] is False
    assert context["manifest_path"] == str(target)


def test_assert_corpus_clean_passes_matching_manifest_and_raises_on_drift(tmp_path: Path) -> None:
    corpus_root = tmp_path / "corpus"
    manifest = _build_seeded_manifest(corpus_root)
    save_corpus_manifest(manifest, manifest_path_for(corpus_root))

    assert_corpus_clean(corpus_root)
    (corpus_root / "manual.txt").write_bytes(b"diverged corpus state")

    with pytest.raises(CorpusManifestDriftError) as drift:
        assert_corpus_clean(corpus_root)

    # Naming the diverged file is the whole value of the refusal: it now rides
    # the typed drift triple rather than an interpolated sentence.
    context = drift.value.context or {}
    assert context["changed"] == ("manual.txt",)
    assert context["added"] == ()
    assert context["removed"] == ()
