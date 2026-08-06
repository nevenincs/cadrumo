"""Release-build bundled-verdict stamp: install-stability and content binding.

The release build stamps a verdict beside the bundled registry tree so an
install's first touch skips runtime validation. Its key must survive packaging
(the cohort builds from a ``git archive`` extraction and installation rewrites
mtimes and moves the tree into ``site-packages``), so these tests prove the
stamped key is invariant under an absolute-path move and an mtime rewrite while
still binding to file content size and the package version. They use only the
public stamp facade and a real on-disk tree; no wheel build is required.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from .._authority import stamp_bundled_registry_verdict
from .._loader import clear_fingerprint_cache
from .._validate_verdict import VERDICT_OUTCOME_GREEN, read_verdict, shipped_verdict_location

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _build_tiny_registry(root: Path) -> None:
    """Create a minimal on-disk registry tree the fingerprint walk can stat."""
    aeat = root / "aeat"
    (aeat / "legal").mkdir(parents=True)
    (aeat / "legal" / "is.toml").write_text('[legal."ley-27-2014:art-29"]\n', encoding="utf-8")
    modelos = aeat / "modelos"
    modelos.mkdir()
    (modelos / "303.toml").write_text('[[revisions]]\nid = "2023-y-siguientes"\n', encoding="utf-8")
    treaties = aeat / "treaties"
    treaties.mkdir()
    (treaties / "es-de.toml").write_text('[treaty]\nname = "es-de"\n', encoding="utf-8")


def _stamp_key(registry_root: Path, *, package_version: str) -> str:
    """Stamp the bundled verdict and return its (asserted-present) key."""
    written = stamp_bundled_registry_verdict(registry_root, package_version=package_version)
    verdict = read_verdict(written)
    assert verdict is not None
    return verdict.verdict_key


def _install_copy(source_registry: Path, destination_root: Path, *, mtime: float) -> Path:
    """Copy the tree to a new absolute path and rewrite every mtime (an install)."""
    shutil.copytree(source_registry.parent, destination_root)
    aeat = destination_root / "aeat"
    for path in sorted(aeat.rglob("*")):
        os.utime(path, (mtime, mtime))
    os.utime(aeat, (mtime, mtime))
    return aeat


def test_stamp_writes_a_green_verdict_at_the_sibling_location(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry" / "aeat"
    _build_tiny_registry(tmp_path / "registry")

    written = stamp_bundled_registry_verdict(registry_root, package_version="0.2.1")

    assert written == shipped_verdict_location(registry_root.resolve())
    assert written.is_file()
    verdict = read_verdict(written)
    assert verdict is not None
    assert verdict.outcome == VERDICT_OUTCOME_GREEN
    assert verdict.package_version == "0.2.1"
    assert verdict.verdict_key


def test_stamped_key_survives_an_absolute_path_move_and_mtime_rewrite(tmp_path: Path) -> None:
    """The crux install-stability property: same content, different path/mtime, same key."""
    build_registry = tmp_path / "build" / "registry" / "aeat"
    _build_tiny_registry(tmp_path / "build" / "registry")
    build_key = _stamp_key(build_registry, package_version="0.2.1")

    # Simulate installation: move the identical bytes to a new site-packages-like
    # path and rewrite every mtime, then re-stamp from the installed tree.
    installed_registry = _install_copy(build_registry, tmp_path / "site-packages" / "registry", mtime=10_000.0)
    installed_key = _stamp_key(installed_registry, package_version="0.2.1")

    assert installed_key == build_key


def test_stamped_key_binds_to_file_size(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry" / "aeat"
    _build_tiny_registry(tmp_path / "registry")
    before = _stamp_key(registry_root, package_version="0.2.1")

    # A content-size change to any registry file must break the match. Clear the
    # 1-second fingerprint TTL cache: a content edit does not bump the parent
    # directory mtime, so a rapid re-stamp would otherwise read stale sizes.
    modelo = registry_root / "modelos" / "303.toml"
    modelo.write_text(modelo.read_text(encoding="utf-8") + "period = 1\n", encoding="utf-8")
    clear_fingerprint_cache()
    after = _stamp_key(registry_root, package_version="0.2.1")

    assert before != after


def test_stamped_key_binds_to_package_version(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry" / "aeat"
    _build_tiny_registry(tmp_path / "registry")
    first = _stamp_key(registry_root, package_version="0.2.1")
    second = _stamp_key(registry_root, package_version="0.2.2")

    assert first != second


def test_stamped_key_binds_to_the_file_set(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry" / "aeat"
    _build_tiny_registry(tmp_path / "registry")
    before = _stamp_key(registry_root, package_version="0.2.1")

    # Adding a registry file changes the certified tree identity.
    (registry_root / "modelos" / "130.toml").write_text('[[revisions]]\nid = "2019"\n', encoding="utf-8")
    clear_fingerprint_cache()
    after = _stamp_key(registry_root, package_version="0.2.1")

    assert before != after
