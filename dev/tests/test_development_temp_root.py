"""Developer scratch cannot escape the checkout or become source-local build output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dev import temporary_output

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "checkout"
    root.mkdir()
    distribution = root / "native/cmake/distribution"
    distribution.mkdir(parents=True)
    (root / "CMakePresets.json").write_text(
        json.dumps({"configurePresets": [{"name": "windows-x64"}]}), encoding="utf-8"
    )
    (distribution / "CMakePresets.json").write_text(
        json.dumps({"configurePresets": [{"name": "distribution-windows-x64"}]}), encoding="utf-8"
    )
    monkeypatch.setattr(temporary_output, "REPO_ROOT", root)
    monkeypatch.setattr(temporary_output, "TEMP_ROOT", root / ".tmp")
    monkeypatch.delenv("CADRUMO_TEMP_DIR", raising=False)
    return root


def test_general_temporary_output_uses_only_the_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _checkout(tmp_path, monkeypatch)
    external = tmp_path / "external-scratch"
    monkeypatch.setenv("CADRUMO_TEMP_DIR", str(external))
    assert temporary_output.prepare_temp_root() == root / ".tmp"
    assert not external.exists()


def test_temporary_output_refuses_traversal_before_writing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _checkout(tmp_path, monkeypatch)
    monkeypatch.setenv("CADRUMO_TEMP_DIR", str(root / ".tmp" / ".." / "escaped"))
    with pytest.raises(ValueError, match="escapes"):
        temporary_output.prepare_temp_root()
    assert not (root / "escaped").exists()


def test_native_temporary_override_requires_its_build_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _checkout(tmp_path, monkeypatch)
    destination = root / "build" / "windows-x64" / "temporary"
    monkeypatch.setenv("CADRUMO_TEMP_DIR", str(destination))
    with pytest.raises(ValueError, match="manifest"):
        temporary_output.prepare_temp_root()
    assert not destination.exists()


def test_native_temporary_output_remains_in_the_declared_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _checkout(tmp_path, monkeypatch)
    build = root / "build" / "windows-x64"
    build.mkdir(parents=True)
    (build / "build-paths.json").write_text(
        json.dumps({"source": str(root), "paths": {"temporary": "temporary"}}), encoding="utf-8"
    )
    destination = build / "temporary"
    monkeypatch.setenv("CADRUMO_TEMP_DIR", str(destination))
    assert temporary_output.prepare_temp_root() == destination
    assert not (root / ".tmp").exists()


def test_distribution_temporary_output_accepts_its_preset_source_during_configure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _checkout(tmp_path, monkeypatch)
    build = root / "build/distribution-windows-x64"
    build.mkdir(parents=True)
    manifest = build / "build-paths.json"
    manifest.write_text(
        json.dumps({"source": str(root / "native/cmake/distribution"), "paths": {"temporary": "temporary"}}),
        encoding="utf-8",
    )
    assert temporary_output.prepare_temp_root(override=build / "temporary") == build / "temporary"
    manifest.write_text(json.dumps({"source": str(root), "paths": {"temporary": "temporary"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="matching build-path manifest"):
        temporary_output.resolve_temporary_output(override=build / "temporary")


def test_unenrolled_build_manifest_cannot_admit_temporary_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _checkout(tmp_path, monkeypatch)
    build = root / "build/unlisted"
    build.mkdir(parents=True)
    (build / "build-paths.json").write_text(
        json.dumps({"source": str(root), "paths": {"temporary": "temporary"}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="matching build-path manifest"):
        temporary_output.prepare_temp_root(override=build / "temporary")
    assert not (build / "temporary").exists()


def test_linked_temporary_root_is_refused_without_writing_to_its_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _checkout(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / ".tmp").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="link"):
        temporary_output.prepare_temp_root()
    assert not list(outside.iterdir())


def test_native_temporary_output_cannot_invent_an_undeclared_build_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _checkout(tmp_path, monkeypatch)
    build = root / "build" / "windows-x64"
    build.mkdir(parents=True)
    (build / "build-paths.json").write_text(
        json.dumps({"source": str(root), "paths": {"temporary": "temporary"}}), encoding="utf-8"
    )
    destination = build / "unregistered"
    with pytest.raises(ValueError, match="declared build member"):
        temporary_output.prepare_temp_root(override=destination)
    assert not destination.exists()
