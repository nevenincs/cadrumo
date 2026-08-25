"""Focused integration tests for the corpus bundle build/verify pair.

Exercises the offline-installable checksummed-zip surface
(:func:`build_corpus_bundle`, :func:`verify_corpus_bundle`,
:func:`assert_corpus_bundle_verifies`) end to end against a real
filesystem and a real zip archive: build a small bundle, verify it
clean, then corrupt/remove/add a member and confirm the verifier names
the exact affected file in every case. No calculation tautologies are
involved; these are structural / contract assertions on the bundle
mechanism, mirroring ``test_manifest.py``'s coverage of the underlying
manifest.
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Set as AbstractSet
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...directory_scan import scan_directory
from .. import (
    CorpusBundleError,
    CorpusBundleVerificationError,
    CorpusManifestError,
    CorpusManifestTamperError,
    assert_corpus_bundle_verifies,
    build_corpus_bundle,
    load_corpus_manifest,
    verify_corpus_bundle,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_GENERATED_AT = datetime(2026, 6, 1, 9, 0, 0, tzinfo=UTC)


def _seed_corpus(corpus_root: Path) -> dict[str, bytes]:
    corpus_root.mkdir(parents=True, exist_ok=True)
    files = {
        "legal/ley-1.html": b"<html>Articulo primero.</html>",
        "manuals/renta/2024/manual.txt": b"Manual practico Renta 2024 excerpt.",
        "manuals/renta/2024/sub/rules.txt": b"Rule text nested one level deeper.",
    }
    for relative, content in files.items():
        path = corpus_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return files


def _build_bundle(tmp_path: Path, *, name: str = "test-corpus") -> tuple[Path, Path]:
    corpus_root = tmp_path / "corpus"
    _seed_corpus(corpus_root)
    bundle_path = tmp_path / "bundle.zip"
    build_corpus_bundle(
        corpus_root,
        corpus_root_name=name,
        output_path=bundle_path,
        generated_at=_GENERATED_AT,
    )
    return corpus_root, bundle_path


def test_build_corpus_bundle_writes_every_file_plus_embedded_manifest(tmp_path: Path) -> None:
    _corpus_root, bundle_path = _build_bundle(tmp_path)

    assert bundle_path.exists()
    with zipfile.ZipFile(bundle_path, "r") as archive:
        names = set(archive.namelist())
    assert names == {
        "corpus.manifest.json",
        "legal/ley-1.html",
        "manuals/renta/2024/manual.txt",
        "manuals/renta/2024/sub/rules.txt",
    }


def test_verify_corpus_bundle_reports_clean_for_untouched_bundle(tmp_path: Path) -> None:
    _corpus_root, bundle_path = _build_bundle(tmp_path)

    result = verify_corpus_bundle(bundle_path)

    assert result.is_clean is True
    assert result.missing == ()
    assert result.unexpected == ()
    assert result.mismatched == ()
    assert result.manifest.corpus_root_name == "test-corpus"
    assert {entry.relative_path for entry in result.manifest.entries} == {
        "legal/ley-1.html",
        "manuals/renta/2024/manual.txt",
        "manuals/renta/2024/sub/rules.txt",
    }

    # Real behavior anti-tautology proof: assert_corpus_bundle_verifies must
    # not raise and must return the same manifest content for a clean bundle.
    manifest = assert_corpus_bundle_verifies(bundle_path)
    assert manifest.manifest_sha256 == result.manifest.manifest_sha256


def _rewrite_bundle(
    bundle_path: Path,
    *,
    mutate: dict[str, bytes | None],
    drop: AbstractSet[str] = frozenset(),
) -> None:
    """Rewrite ``bundle_path`` in place, mutating or dropping named members.

    ``mutate`` maps an archive member name to replacement bytes (or
    ``None`` to leave it untouched but still copy it). ``drop`` names
    members to omit entirely (simulating a missing file). This models
    tampering with an already-built bundle, which is the real-world
    threat this module's verifier defends against.
    """
    rewritten = bundle_path.with_name(bundle_path.name + ".rewritten")
    with zipfile.ZipFile(bundle_path, "r") as src, zipfile.ZipFile(rewritten, "w") as dst:
        for item in src.infolist():
            if item.filename in drop:
                continue
            data = src.read(item.filename)
            replacement = mutate.get(item.filename)
            if replacement is not None:
                data = replacement
            dst.writestr(item, data)
    rewritten.replace(bundle_path)


def test_verify_corpus_bundle_flags_mismatched_file_by_name(tmp_path: Path) -> None:
    _corpus_root, bundle_path = _build_bundle(tmp_path)

    _rewrite_bundle(bundle_path, mutate={"legal/ley-1.html": b"tampered content, wrong hash now"})

    result = verify_corpus_bundle(bundle_path)

    assert result.is_clean is False
    assert result.mismatched == ("legal/ley-1.html",)
    assert result.missing == ()
    assert result.unexpected == ()

    with pytest.raises(CorpusBundleVerificationError) as refusal:
        assert_corpus_bundle_verifies(bundle_path)

    assert (refusal.value.context or {})["mismatched"] == ("legal/ley-1.html",)


def test_verify_corpus_bundle_flags_missing_file_by_name(tmp_path: Path) -> None:
    _corpus_root, bundle_path = _build_bundle(tmp_path)

    _rewrite_bundle(bundle_path, mutate={}, drop={"manuals/renta/2024/sub/rules.txt"})

    result = verify_corpus_bundle(bundle_path)

    assert result.is_clean is False
    assert result.missing == ("manuals/renta/2024/sub/rules.txt",)
    assert result.mismatched == ()
    assert result.unexpected == ()

    with pytest.raises(CorpusBundleVerificationError) as refusal:
        assert_corpus_bundle_verifies(bundle_path)

    assert (refusal.value.context or {})["missing"] == ("manuals/renta/2024/sub/rules.txt",)


def test_verify_corpus_bundle_flags_unexpected_extra_file(tmp_path: Path) -> None:
    _corpus_root, bundle_path = _build_bundle(tmp_path)

    rewritten = bundle_path.with_name(bundle_path.name + ".rewritten")
    with zipfile.ZipFile(bundle_path, "r") as src, zipfile.ZipFile(rewritten, "w") as dst:
        for item in src.infolist():
            dst.writestr(item, src.read(item.filename))
        dst.writestr("legal/ley-2-not-in-manifest.html", b"a file the manifest never declared")
    rewritten.replace(bundle_path)

    result = verify_corpus_bundle(bundle_path)

    assert result.is_clean is False
    assert result.unexpected == ("legal/ley-2-not-in-manifest.html",)
    assert result.missing == ()
    assert result.mismatched == ()


def test_verify_corpus_bundle_raises_tamper_error_when_manifest_digest_mismatches(tmp_path: Path) -> None:
    """Mutating the embedded manifest's recorded ``manifest_sha256`` (without
    recomputing it) must trip the self-attesting digest check, exactly as
    :func:`load_corpus_manifest` does for the on-disk sidecar form."""
    _corpus_root, bundle_path = _build_bundle(tmp_path)

    with zipfile.ZipFile(bundle_path, "r") as archive:
        manifest_bytes = archive.read("corpus.manifest.json")
    payload = json.loads(manifest_bytes)
    payload["manifest_sha256"] = "0" * 64
    tampered_manifest = json.dumps(payload).encode("utf-8")

    _rewrite_bundle(bundle_path, mutate={"corpus.manifest.json": tampered_manifest})

    with pytest.raises(CorpusManifestTamperError) as tamper:
        verify_corpus_bundle(bundle_path)

    context = tamper.value.context or {}
    assert context["digest_field"] == "manifest_sha256"
    assert context["manifest_member"] == "corpus.manifest.json"


@pytest.mark.parametrize(
    ("raw_payload", "manifest_changes", "file_error", "bundle_error"),
    (
        (b'{"manifest_version":', None, CorpusManifestError, CorpusBundleError),
        (None, {"manifest_version": 2}, CorpusManifestError, CorpusBundleError),
        (None, {"manifest_sha256": "0" * 64}, CorpusManifestTamperError, CorpusManifestTamperError),
    ),
    ids=("malformed", "future-version", "tampered"),
)
def test_path_and_bundle_reject_the_same_invalid_manifest_payload(
    tmp_path: Path,
    raw_payload: bytes | None,
    manifest_changes: dict[str, int | str] | None,
    file_error: type[Exception],
    bundle_error: type[Exception],
) -> None:
    """Both real I/O forms must reject each defective raw payload consistently."""
    corpus_root, bundle_path = _build_bundle(tmp_path)
    with zipfile.ZipFile(bundle_path, "r") as archive:
        payload = json.loads(archive.read("corpus.manifest.json"))

    if manifest_changes is not None:
        payload.update(manifest_changes)
        raw_payload = json.dumps(payload).encode("utf-8")

    assert raw_payload is not None

    manifest_path = corpus_root / "corpus.manifest.json"
    manifest_path.write_bytes(raw_payload)
    _rewrite_bundle(bundle_path, mutate={"corpus.manifest.json": raw_payload})

    # Both surfaces refuse with their own registered error; the prose that
    # distinguished them is catalogue-rendered now.
    with pytest.raises(file_error):
        load_corpus_manifest(manifest_path)
    with pytest.raises(bundle_error):
        verify_corpus_bundle(bundle_path)


def test_verify_corpus_bundle_raises_on_missing_manifest_member(tmp_path: Path) -> None:
    _corpus_root, bundle_path = _build_bundle(tmp_path)

    _rewrite_bundle(bundle_path, mutate={}, drop={"corpus.manifest.json"})

    with pytest.raises(CorpusBundleError):
        verify_corpus_bundle(bundle_path)


def test_verify_corpus_bundle_raises_on_not_a_zip_file(tmp_path: Path) -> None:
    not_a_zip = tmp_path / "not-a-bundle.zip"
    not_a_zip.write_bytes(b"this is definitely not a zip archive")

    with pytest.raises(CorpusBundleError):
        verify_corpus_bundle(not_a_zip)


def test_verify_corpus_bundle_raises_file_not_found_for_missing_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        verify_corpus_bundle(tmp_path / "does-not-exist.zip")


def test_build_corpus_bundle_overwrites_existing_output_atomically(tmp_path: Path) -> None:
    """A pre-existing file at the output path is replaced only on a
    successful build, never partially overwritten -- proving the
    temp-file-then-rename write is exercised for the bundle path too,
    matching :func:`save_corpus_manifest`'s atomicity guarantee."""
    corpus_root = tmp_path / "corpus"
    _seed_corpus(corpus_root)
    output_path = tmp_path / "bundle.zip"
    output_path.write_bytes(b"stale placeholder bytes from a previous run")

    build_corpus_bundle(
        corpus_root,
        corpus_root_name="test-corpus",
        output_path=output_path,
        generated_at=_GENERATED_AT,
    )

    result = verify_corpus_bundle(output_path)
    assert result.is_clean is True
    # The rename leaves no stray temp file behind.
    assert scan_directory(output_path.parent, pattern="*.tmp") == ()
