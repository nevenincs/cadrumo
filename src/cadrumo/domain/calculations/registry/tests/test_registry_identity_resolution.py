"""Stamped-versus-walked identity resolution, proven behaviourally.

The saving D1 delivers is a walk that does not happen, and "did not happen" is
the one property a timing figure cannot establish on a contended machine. So
these tests inject a collector that RAISES: if the stamped path ever falls
through to the walk, the test explodes rather than merely getting slower.

The corresponding refusals matter just as much. A stamp is honoured only for the
package-bundled root, and only for the running package's version. Neither half is
sufficient alone, and both are asserted here against a real on-disk tree with the
bundled root really redirected -- nothing about the resolver is stubbed.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from ..... import __version__
from .....tests.attribute_scope import scoped_attribute
from .. import _loader_cache as loader_cache
from .._identity import (
    FingerprintTuples,
    RegistryIdentityOrigin,
    compute_installed_tree_digest,
    read_registry_identity_stamp,
    registry_identity_stamp_location,
    resolve_registry_identity,
    stamped_cache_key_tuples,
    write_registry_identity_stamp,
)
from .._loader import clear_fingerprint_cache
from .._loader_cache import _bundled_registry_root, _bundled_root_match

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _WalkNotPermittedError(AssertionError):
    """Raised by the injected collector when a walk happens that must not."""


def _exploding_collector(_root: Path) -> FingerprintTuples:
    """A fingerprint collector that must never be reached on the stamped path."""
    raise _WalkNotPermittedError("the stamped path walked the tree; the whole saving is the walk not happening")


def _recording_collector(calls: list[Path]) -> Callable[[Path], FingerprintTuples]:
    """A collector that records its invocations and returns one fixed tuple."""

    def _collect(root: Path) -> FingerprintTuples:
        calls.append(root)
        return ((str(root / "a.toml"), 1, 2, "digest-a"),)

    return _collect


@pytest.fixture
def bundled_root_pointing_at() -> Iterator[Callable[[Path], None]]:
    """Redirect ``bundled_path("registry", "aeat")`` at a caller-chosen real tree.

    The only way to exercise the bundled-root branch without editing the shipped
    registry. Everything under test -- the stamp read, the version gate, the
    predicate, the resolver -- stays real.

    Rebinds the name inside ``_loader_cache`` rather than on ``core.resources``,
    because that module does ``from ...resources import bundled_path`` and so
    holds its OWN reference: patching the source module leaves the predicate
    calling the original. Both memoised roots are cleared on every repoint --
    ``_bundled_root_match`` caches a normcased string pair derived from the same
    root, and leaving it warm would answer for the previous tree.
    """
    real_bundled_path = loader_cache.bundled_path
    target: dict[str, Path] = {}

    def _redirected(*parts: str) -> Path:
        if tuple(parts) == ("registry", "aeat") and "root" in target:
            return target["root"]
        return real_bundled_path(*parts)

    def _clear() -> None:
        _bundled_registry_root.cache_clear()
        _bundled_root_match.cache_clear()
        clear_fingerprint_cache()

    def _point_at(root: Path) -> None:
        target["root"] = root.resolve()
        _clear()

    with scoped_attribute(loader_cache, "bundled_path", _redirected):
        yield _point_at
    _clear()


def _tree(tmp_path: Path) -> Path:
    """Create a real registry root with one file, and return it."""
    root = tmp_path / "registry" / "aeat"
    root.mkdir(parents=True)
    (root / "manifest.toml").write_text("modelos = []\n", encoding="utf-8")
    return root


def _stamp(root: Path, *, package_version: str = __version__) -> str:
    """Write a real identity stamp for ``root`` and return its digest.

    Sizes come from the real files rather than being hardcoded: the installed
    derivation folds ``(relative-path, size, content)``, so a helper that
    invented a constant size would hand every tree the same shape and quietly
    make a distinctness assertion unprovable.
    """
    manifest = root / "manifest.toml"
    stamp = write_registry_identity_stamp(
        registry_fingerprints=((str(manifest), manifest.stat().st_size, manifest.stat().st_mtime_ns, ""),),
        registry_root=root,
        package_version=package_version,
    )
    return stamp.tree_digest


def test_a_stamped_bundled_root_resolves_without_walking(
    tmp_path: Path,
    bundled_root_pointing_at: Callable[[Path], None],
) -> None:
    """The whole point: a stamped install reads one file instead of the tree."""
    root = _tree(tmp_path)
    bundled_root_pointing_at(root)
    digest = _stamp(root)

    identity = resolve_registry_identity(root, collect_fingerprints=_exploding_collector)

    assert identity.origin is RegistryIdentityOrigin.STAMPED
    assert identity.is_stamped
    assert identity.digest == digest
    assert identity.fingerprints == (), "a stamped identity must carry no tuples; collecting them is the cost removed"


def test_a_bundled_root_with_no_stamp_walks(
    tmp_path: Path,
    bundled_root_pointing_at: Callable[[Path], None],
) -> None:
    """Being the bundled root is not by itself an immutability claim.

    Under an editable install the bundled root IS the live source directory, so
    resolving on that predicate alone would serve a frozen identity for a tree
    being edited. The stamp is what the build adds, and a checkout has none.
    """
    root = _tree(tmp_path)
    bundled_root_pointing_at(root)
    assert not registry_identity_stamp_location(root).exists(), "sanity: this tree must carry no stamp"
    calls: list[Path] = []

    identity = resolve_registry_identity(root, collect_fingerprints=_recording_collector(calls))

    assert identity.origin is RegistryIdentityOrigin.WALKED
    assert calls == [root.resolve()]
    assert identity.fingerprints


def test_a_stamp_beside_a_non_bundled_tree_is_ignored(tmp_path: Path) -> None:
    """A planted stamp cannot make an arbitrary tree behave as immutable.

    Defence in depth against the stamp being the sole discriminator: a stamp is
    a file, and a file can be copied next to any tree. Only the build writes one
    beside the tree the package actually ships.
    """
    root = _tree(tmp_path)
    _stamp(root)
    assert registry_identity_stamp_location(root).is_file(), "sanity: the stamp must exist for this to prove anything"
    calls: list[Path] = []

    identity = resolve_registry_identity(root, collect_fingerprints=_recording_collector(calls))

    assert identity.origin is RegistryIdentityOrigin.WALKED
    assert calls == [root.resolve()]


def test_a_stamp_from_another_package_version_is_ignored(
    tmp_path: Path,
    bundled_root_pointing_at: Callable[[Path], None],
) -> None:
    """An upgraded package re-walks rather than trusting the old release's claim."""
    root = _tree(tmp_path)
    bundled_root_pointing_at(root)
    _stamp(root, package_version="0.0.0-some-other-release")
    assert registry_identity_stamp_location(root).is_file()
    assert read_registry_identity_stamp(root) is None
    calls: list[Path] = []

    identity = resolve_registry_identity(root, collect_fingerprints=_recording_collector(calls))

    assert identity.origin is RegistryIdentityOrigin.WALKED
    assert calls == [root.resolve()]


def test_a_corrupt_stamp_falls_back_rather_than_refusing(
    tmp_path: Path,
    bundled_root_pointing_at: Callable[[Path], None],
) -> None:
    """A damaged stamp costs a walk, never a crash.

    Delete-not-migrate applied to a read: the stamp is derived data, so an
    unreadable one means "recompute", not "fail the load". A load that refused
    here would make a corrupted cache file break the application outright.
    """
    root = _tree(tmp_path)
    bundled_root_pointing_at(root)
    _stamp(root)
    registry_identity_stamp_location(root).write_text("{not json at all", encoding="utf-8")
    calls: list[Path] = []

    identity = resolve_registry_identity(root, collect_fingerprints=_recording_collector(calls))

    assert identity.origin is RegistryIdentityOrigin.WALKED
    assert calls == [root.resolve()]


def test_the_stamped_cache_key_is_distinct_per_tree_and_refuses_a_walked_identity(
    tmp_path: Path,
    bundled_root_pointing_at: Callable[[Path], None],
) -> None:
    """Two stamped trees never share a cache entry, and a walked one cannot use this key.

    The synthetic key exists so downstream caches keep their tuple type. If it
    ever answered for a walked identity, every distinct authoring tree would
    collapse onto one entry -- serving one tree's compile for another.
    """
    first = _tree(tmp_path / "one")
    second = _tree(tmp_path / "two")
    (second / "manifest.toml").write_text("modelos = []\nextra = 1\n", encoding="utf-8")

    bundled_root_pointing_at(first)
    _stamp(first)
    first_identity = resolve_registry_identity(first, collect_fingerprints=_exploding_collector)

    bundled_root_pointing_at(second)
    _stamp(second)
    second_identity = resolve_registry_identity(second, collect_fingerprints=_exploding_collector)

    assert stamped_cache_key_tuples(first_identity) != stamped_cache_key_tuples(second_identity)

    calls: list[Path] = []
    bundled_root_pointing_at(tmp_path / "absent")
    walked = resolve_registry_identity(first, collect_fingerprints=_recording_collector(calls))
    assert walked.origin is RegistryIdentityOrigin.WALKED
    with pytest.raises(ValueError, match="requires a stamped identity"):
        stamped_cache_key_tuples(walked)


def test_the_installed_digest_ignores_mtime_and_absolute_path(tmp_path: Path) -> None:
    """Install-stability, asserted on the derivation the build actually stamps.

    The stamp is computed on the build machine and matched on every install, so
    a derivation sensitive to mtime or absolute path would never match anywhere.
    """
    build = _tree(tmp_path / "build")
    installed = _tree(tmp_path / "site-packages")

    build_fingerprints = ((str(build / "manifest.toml"), 12, 111, ""),)
    installed_fingerprints = ((str(installed / "manifest.toml"), 12, 999, ""),)

    assert compute_installed_tree_digest(
        build_fingerprints, registry_root=build, package_version="1.2.3"
    ) == compute_installed_tree_digest(installed_fingerprints, registry_root=installed, package_version="1.2.3")


def test_the_installed_digest_binds_to_content_at_identical_size(tmp_path: Path) -> None:
    """A same-length edit changes the identity.

    Path and size alone cannot separate two files of equal length, so a stamp
    keyed on those would let a same-size edit to an installed tree pass as the
    tree the build packaged. The content digest is what makes the stamp an
    identity; without this assertion the derivation could silently drop it and
    every other test here would still pass.
    """
    root = _tree(tmp_path)
    manifest = root / "manifest.toml"
    fingerprints = ((str(manifest), manifest.stat().st_size, 111, ""),)
    before = compute_installed_tree_digest(fingerprints, registry_root=root, package_version="1.2.3")

    original = manifest.read_text(encoding="utf-8")
    edited = original[:-2] + "1\n"
    manifest.write_text(edited, encoding="utf-8")
    assert len(edited) == len(original), "sanity: the edit must preserve length or this tests the size field instead"

    after = compute_installed_tree_digest(fingerprints, registry_root=root, package_version="1.2.3")

    assert before != after
