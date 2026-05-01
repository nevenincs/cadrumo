"""Tests for the CORPUS-class directory-level integrity manifest."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from . import (
    CorpusEntry,
    CorpusManifest,
    assert_corpus_clean,
    build_corpus_manifest,
    load_corpus_manifest,
    manifest_path_for,
    save_corpus_manifest,
    verify_corpus_manifest,
)
from .errors import (
    CorpusManifestDriftError,
    CorpusManifestError,
    CorpusManifestTamperError,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def _seed_corpus(root: Path) -> None:
    """Lay down a deterministic three-file corpus tree under ``root``."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "100" / "2026A.json").parent.mkdir(parents=True, exist_ok=True)
    (root / "100" / "2026A.json").write_text(
        '{"records": [{"casilla_id": "01", "label": "Ingresos"}]}',
        encoding="utf-8",
    )
    (root / "130" / "2026Q1.json").parent.mkdir(parents=True, exist_ok=True)
    (root / "130" / "2026Q1.json").write_text(
        '{"records": [{"casilla_id": "01", "label": "Rendimiento neto"}]}',
        encoding="utf-8",
    )
    (root / "303" / "2026Q1.json").parent.mkdir(parents=True, exist_ok=True)
    (root / "303" / "2026Q1.json").write_text(
        '{"records": [{"casilla_id": "01", "label": "Base imponible"}]}',
        encoding="utf-8",
    )


class TestBuildAndVerify:
    def test_build_then_verify_clean(self, tmp_path: Path) -> None:
        root = tmp_path / "casillas"
        _seed_corpus(root)
        manifest = build_corpus_manifest(root, corpus_root_name="casillas")
        assert manifest.corpus_root_name == "casillas"
        assert len(manifest.entries) == 3
        # Entries are sorted by relative path so the manifest_sha256 is
        # deterministic across operating systems.
        paths = [entry.relative_path for entry in manifest.entries]
        assert paths == sorted(paths)

        diff = verify_corpus_manifest(root, manifest=manifest)
        assert diff.is_clean
        assert diff.added == ()
        assert diff.removed == ()
        assert diff.changed == ()

    def test_build_skips_dotfiles_and_manifest_sidecar(self, tmp_path: Path) -> None:
        root = tmp_path / "manuals"
        root.mkdir()
        (root / "real.json").write_text("{}", encoding="utf-8")
        (root / ".hidden").write_text("ignore me", encoding="utf-8")
        (root / "corpus.manifest.json").write_text("{}", encoding="utf-8")

        manifest = build_corpus_manifest(root, corpus_root_name="manuals")
        assert len(manifest.entries) == 1
        assert manifest.entries[0].relative_path == "real.json"

    def test_build_recurses_subdirectories(self, tmp_path: Path) -> None:
        root = tmp_path / "manuals"
        root.mkdir()
        nested = root / "irpf-2026" / "section-1"
        nested.mkdir(parents=True)
        (nested / "rule-1.json").write_text("{}", encoding="utf-8")
        (nested / "rule-2.json").write_text("{}", encoding="utf-8")
        manifest = build_corpus_manifest(root, corpus_root_name="manuals")
        relpaths = sorted(entry.relative_path for entry in manifest.entries)
        assert relpaths == [
            "irpf-2026/section-1/rule-1.json",
            "irpf-2026/section-1/rule-2.json",
        ]


class TestDriftDetection:
    def test_changed_file_is_reported(self, tmp_path: Path) -> None:
        root = tmp_path / "casillas"
        _seed_corpus(root)
        manifest = build_corpus_manifest(root, corpus_root_name="casillas")

        # Mutate one byte in one file.
        target = root / "130" / "2026Q1.json"
        target.write_text(target.read_text(encoding="utf-8") + " ", encoding="utf-8")

        diff = verify_corpus_manifest(root, manifest=manifest)
        assert not diff.is_clean
        assert diff.changed == ("130/2026Q1.json",)
        assert diff.added == ()
        assert diff.removed == ()

    def test_added_file_is_reported(self, tmp_path: Path) -> None:
        root = tmp_path / "casillas"
        _seed_corpus(root)
        manifest = build_corpus_manifest(root, corpus_root_name="casillas")

        (root / "390" / "2026A.json").parent.mkdir(parents=True, exist_ok=True)
        (root / "390" / "2026A.json").write_text("{}", encoding="utf-8")

        diff = verify_corpus_manifest(root, manifest=manifest)
        assert diff.added == ("390/2026A.json",)
        assert diff.removed == ()
        assert diff.changed == ()

    def test_removed_file_is_reported(self, tmp_path: Path) -> None:
        root = tmp_path / "casillas"
        _seed_corpus(root)
        manifest = build_corpus_manifest(root, corpus_root_name="casillas")
        (root / "130" / "2026Q1.json").unlink()

        diff = verify_corpus_manifest(root, manifest=manifest)
        assert diff.removed == ("130/2026Q1.json",)
        assert diff.added == ()
        assert diff.changed == ()


class TestSelfAttesting:
    def test_round_trip_through_disk(self, tmp_path: Path) -> None:
        root = tmp_path / "casillas"
        _seed_corpus(root)
        manifest = build_corpus_manifest(root, corpus_root_name="casillas")
        target = manifest_path_for(root)
        save_corpus_manifest(manifest, target)
        loaded = load_corpus_manifest(target)
        assert loaded == manifest

    def test_tampered_manifest_body_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "casillas"
        _seed_corpus(root)
        manifest = build_corpus_manifest(root, corpus_root_name="casillas")
        target = manifest_path_for(root)
        save_corpus_manifest(manifest, target)

        # Substitute one entry's hash without recomputing the
        # manifest_sha256 — simulates an attacker editing the body.
        text = target.read_text(encoding="utf-8")
        tampered = text.replace(manifest.entries[0].sha256, "f" * 64)
        # That replace is in the inner entry sha256; the manifest_sha256
        # is at the top of the JSON body. We deliberately do NOT update
        # the manifest_sha256.
        target.write_text(tampered, encoding="utf-8")

        with pytest.raises(CorpusManifestTamperError):
            load_corpus_manifest(target)

    def test_unknown_manifest_version_rejected(self, tmp_path: Path) -> None:
        root = tmp_path / "casillas"
        _seed_corpus(root)
        manifest = build_corpus_manifest(root, corpus_root_name="casillas")
        target = manifest_path_for(root)
        save_corpus_manifest(manifest, target)

        # Swap the version on disk to one beyond what the consumer
        # supports. Recompute the digest so we know the rejection comes
        # from the version gate, not the tamper gate.
        import hashlib
        import json

        loaded = json.loads(target.read_text(encoding="utf-8"))
        loaded["manifest_version"] = 999
        canonical = {
            "manifest_version": loaded["manifest_version"],
            "corpus_root_name": loaded["corpus_root_name"],
            "generated_at": loaded["generated_at"],
            "entries": loaded["entries"],
        }
        loaded["manifest_sha256"] = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        target.write_text(json.dumps(loaded), encoding="utf-8")

        with pytest.raises(CorpusManifestError):
            load_corpus_manifest(target)


class TestAssertCorpusClean:
    def test_passes_on_clean_corpus(self, tmp_path: Path) -> None:
        root = tmp_path / "casillas"
        _seed_corpus(root)
        save_corpus_manifest(
            build_corpus_manifest(root, corpus_root_name="casillas"),
            manifest_path_for(root),
        )
        assert_corpus_clean(root)  # no raise

    def test_raises_on_drift(self, tmp_path: Path) -> None:
        root = tmp_path / "casillas"
        _seed_corpus(root)
        save_corpus_manifest(
            build_corpus_manifest(root, corpus_root_name="casillas"),
            manifest_path_for(root),
        )
        # Add a new file post-manifest.
        (root / "390" / "2026A.json").parent.mkdir(parents=True, exist_ok=True)
        (root / "390" / "2026A.json").write_text("{}", encoding="utf-8")

        with pytest.raises(CorpusManifestDriftError) as exc_info:
            assert_corpus_clean(root)
        assert "casillas" in str(exc_info.value)
        assert "390/2026A.json" in str(exc_info.value)


class TestCorpusEntryValidation:
    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "/abs/path",
            "..",
            "../escape",
            "a/../b",
            ".",
        ],
    )
    def test_unsafe_relative_path_rejected(self, bad: str) -> None:
        with pytest.raises(ValueError):
            CorpusEntry(relative_path=bad, sha256="0" * 64, content_length=0)

    def test_invalid_sha256_rejected(self) -> None:
        with pytest.raises(ValueError):
            CorpusEntry(relative_path="x", sha256="not-hex", content_length=0)


class TestCorpusManifestValidation:
    def test_naive_timestamp_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            CorpusManifest(
                corpus_root_name="x",
                generated_at=datetime(2026, 4, 30, 0, 0, 0),  # tz-naive
                entries=(),
                manifest_sha256="0" * 64,
            )

    def test_aware_timestamp_accepted(self, tmp_path: Path) -> None:
        manifest = CorpusManifest(
            corpus_root_name="x",
            generated_at=datetime(2026, 4, 30, 0, 0, 0, tzinfo=UTC),
            entries=(),
            manifest_sha256="0" * 64,
        )
        assert manifest.corpus_root_name == "x"


class TestStreamingHash:
    """Manuals PDFs are large — verify the streaming hash works on a
    multi-chunk file without inflating memory."""

    def test_large_file_hashes_correctly(self, tmp_path: Path) -> None:
        import hashlib

        root = tmp_path / "manuals"
        root.mkdir()
        # 200 KiB of deterministic bytes (3+ chunks of the 64 KiB read loop).
        payload = (b"A" * 1024) * 200
        (root / "big.bin").write_bytes(payload)
        manifest = build_corpus_manifest(root, corpus_root_name="manuals")
        assert len(manifest.entries) == 1
        entry = manifest.entries[0]
        assert entry.content_length == len(payload)
        assert entry.sha256 == hashlib.sha256(payload).hexdigest()
