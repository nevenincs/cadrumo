"""Release-build registry stamp: install-stability and content binding.

The release build stamps a tree IDENTITY and a verdict keyed on it beside the
bundled registry tree, so an install's first touch establishes which tree it has
without a walk and skips runtime validation. The stamped identity must survive
packaging (the cohort builds from a ``git archive`` extraction and installation
rewrites mtimes and moves the tree into ``site-packages``), so these tests prove
it is invariant under an absolute-path move and an mtime rewrite while still
binding to file content size, the file set, and the package version. They use
only the public stamp facade and a real on-disk tree; no wheel build is
required.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from .._authority import stamp_bundled_registry_release
from .._identity import read_registry_identity_stamp, registry_identity_stamp_location
from .._loader import clear_fingerprint_cache
from .._verdict_cache import VERDICT_OUTCOME_GREEN, read_verdict, shipped_verdict_location

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _build_tiny_registry(root: Path) -> None:
    """Create a minimal on-disk registry tree the fingerprint walk can stat."""
    aeat = root / "aeat"
    (aeat / "legal").mkdir(parents=True)
    (aeat / "legal" / "is.toml").write_text('[legal."ley-27-2014:art-29"]\n', encoding="utf-8")
    modelos = aeat / "modelos"
    modelos.mkdir()
    (modelos / "303.toml").write_text('[[revisions]]\nid = "2023"\n', encoding="utf-8")
    treaties = aeat / "treaties"
    treaties.mkdir()
    (treaties / "es-de.toml").write_text('[treaty]\nname = "es-de"\n', encoding="utf-8")


def _stamp_key(registry_root: Path, *, package_version: str) -> str:
    """Stamp the release records and return the (asserted-present) tree identity.

    The identity is what every downstream key now derives from, so binding these
    properties to it rather than to the verdict key tests the thing that moved.
    """
    stamped = stamp_bundled_registry_release(registry_root, package_version=package_version)
    assert stamped.identity_path.is_file()
    identity = _read_stamp_bypassing_version_gate(registry_root, package_version=package_version)
    return identity


def _read_stamp_bypassing_version_gate(registry_root: Path, *, package_version: str) -> str:
    """Read the written stamp's digest without going through the runtime version gate.

    :func:`read_registry_identity_stamp` deliberately refuses a stamp whose
    ``package_version`` is not the running package's, which is correct at runtime
    and unhelpful here: these tests stamp explicit versions like ``0.2.1`` to
    prove the key BINDS to the version. So the file is parsed directly, and the
    runtime gate gets its own test below rather than being worked around
    silently.
    """
    import json

    raw = json.loads(registry_identity_stamp_location(registry_root.resolve()).read_text(encoding="utf-8"))
    assert raw["package_version"] == package_version
    digest = raw["tree_digest"]
    assert isinstance(digest, str) and digest
    return digest


def _install_copy(source_registry: Path, destination_root: Path, *, mtime: float) -> Path:
    """Copy the tree to a new absolute path and rewrite every mtime (an install)."""
    shutil.copytree(source_registry.parent, destination_root)
    aeat = destination_root / "aeat"
    for path in scan_directory(aeat, recursive=True):
        os.utime(path, (mtime, mtime))
    os.utime(aeat, (mtime, mtime))
    return aeat


def test_stamp_writes_both_records_at_their_sibling_locations(tmp_path: Path) -> None:
    registry_root = tmp_path / "registry" / "aeat"
    _build_tiny_registry(tmp_path / "registry")

    stamped = stamp_bundled_registry_release(registry_root, package_version="0.2.1")

    resolved = registry_root.resolve()
    assert stamped.identity_path == registry_identity_stamp_location(resolved)
    assert stamped.verdict_path == shipped_verdict_location(resolved)
    assert stamped.identity_path.is_file()
    assert stamped.verdict_path.is_file()
    # Both records sit BESIDE the tree, never inside it: a record within the root
    # would be walked by the very fingerprint it describes, so stamping would
    # change the thing being stamped.
    assert stamped.identity_path.parent == resolved.parent
    assert stamped.verdict_path.parent == resolved.parent

    verdict = read_verdict(stamped.verdict_path)
    assert verdict is not None
    assert verdict.outcome == VERDICT_OUTCOME_GREEN
    assert verdict.package_version == "0.2.1"
    assert verdict.verdict_key


def test_the_runtime_refuses_a_stamp_from_a_different_package_version(tmp_path: Path) -> None:
    """A stamp is honoured only for the running package, so an upgrade re-walks.

    The stamp asserts "the build packaged exactly this tree"; that claim is
    scoped to the release that made it. Without the version gate, an upgraded
    package would trust the previous release's identity for a tree it never
    checked.
    """
    registry_root = tmp_path / "registry" / "aeat"
    _build_tiny_registry(tmp_path / "registry")
    stamp_bundled_registry_release(registry_root, package_version="0.0.0-not-this-build")

    assert registry_identity_stamp_location(registry_root.resolve()).is_file()
    assert read_registry_identity_stamp(registry_root.resolve()) is None


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
