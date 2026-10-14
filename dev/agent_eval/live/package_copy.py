"""Verify the staged bundle, keep an unmodified copy of it, and tell whether it matches the checkout.

The staged ``bundle`` output is never written to. A copy is taken only from a
staged package whose file set and digests equal its own manifest, is verified
the same way, and is discarded whenever it stops matching. One copy is kept per
manifest digest and re-verified before every run, and again after it.

A package measures the package, not the checkout. :func:`compare_with_checkout`
compares the first-party Python modules the package carries with the
checkout's, so a run can refuse a stale package or say plainly that it measured
one.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from dev.first_party_source import is_test_source
from dev.packaging.native.hashing import digest
from dev.packaging.native.package_inventory import package_inventory

from .outcome import UnavailableError

_FROZEN = ConfigDict(frozen=True, strict=True, extra="forbid")
MANIFEST: Final = "data/package-manifest.json"
BUILD_METADATA: Final = "data/build.json"
FIRST_PARTY_PACKAGES: Final = ("cadrumo", "cadrumo_harness")
_PACKAGES_DIRECTORY: Final = "cadrumo/site-packages"
_SAMPLE: Final = 12


class PackageCopyError(Exception):
    """A package tree does not equal its manifest."""


class PackageIdentity(BaseModel):
    """What a verified package is: its manifest digest, size and build metadata."""

    model_config = _FROZEN

    root: str = Field(min_length=1)
    manifest_digest: str = Field(min_length=64, max_length=64)
    file_count: int = Field(ge=1)
    build: dict[str, Any]


class CheckoutComparison(BaseModel):
    """The first-party modules of a package compared with the checkout's sources."""

    model_config = _FROZEN

    compared: int = Field(ge=0)
    differing: tuple[str, ...] = ()
    only_in_package: tuple[str, ...] = ()
    only_in_checkout: tuple[str, ...] = ()

    @property
    def current(self) -> bool:
        """True when every first-party module is byte-identical in both."""
        return not (self.differing or self.only_in_package or self.only_in_checkout)

    def summary(self) -> str:
        """Counts plus a short sample of paths, for a receipt or a refusal."""
        parts = [f"{self.compared} modules compared"]
        for label, paths in (
            ("differ", self.differing),
            ("only in package", self.only_in_package),
            ("only in checkout", self.only_in_checkout),
        ):
            if paths:
                parts.append(f"{len(paths)} {label} (e.g. {', '.join(paths[:3])})")
        return "; ".join(parts)


def _relative_files(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def verify_package(root: Path) -> PackageIdentity:
    """Require ``root`` to hold exactly its manifest's files, each with its recorded digest."""
    manifest_path = root / MANIFEST
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        files = package_inventory(root, manifest)
    except (OSError, ValueError, KeyError) as error:
        raise PackageCopyError(f"package manifest unreadable or inconsistent: {error}") from error
    expected = set(files) | {MANIFEST}
    actual = _relative_files(root)
    if actual != expected:
        missing = sorted(expected - actual)[:_SAMPLE]
        extra = sorted(actual - expected)[:_SAMPLE]
        raise PackageCopyError(f"package file set differs from its manifest: missing {missing}, extra {extra}")
    for name, checksum in files.items():
        if digest(root / PurePosixPath(name)) != checksum:
            raise PackageCopyError(f"package file differs from its manifest: {name}")
    build_path = root / BUILD_METADATA
    build = json.loads(build_path.read_text(encoding="utf-8")) if build_path.is_file() else {}
    return PackageIdentity(
        root=str(root),
        manifest_digest=hashlib.sha256(manifest_bytes).hexdigest(),
        file_count=len(expected),
        build=build if isinstance(build, dict) else {},
    )


def verified_copy(staged: Path, copies_root: Path) -> PackageIdentity:
    """Return a verified copy of the verified staged package, reusing one only while it still matches.

    The staged tree is read, never written. A kept copy that no longer matches
    is removed and copied again. A new copy is assembled beside its final name
    and renamed into place only after it verifies.
    """
    try:
        source = verify_package(staged)
    except PackageCopyError as error:
        raise UnavailableError(
            "package_unverified", f"the staged package at {staged} is not as built: {error}"
        ) from error
    copies_root.mkdir(parents=True, exist_ok=True)
    destination = copies_root / f"package-{source.manifest_digest[:16]}"
    if destination.exists():
        try:
            kept = verify_package(destination)
        except PackageCopyError:
            shutil.rmtree(destination)
        else:
            if kept.manifest_digest == source.manifest_digest:
                return kept
            shutil.rmtree(destination)
    partial = copies_root / f"{destination.name}.partial"
    if partial.exists():
        shutil.rmtree(partial)
    shutil.copytree(staged, partial)
    try:
        copied = verify_package(partial)
    except PackageCopyError:
        shutil.rmtree(partial)
        raise
    if copied.manifest_digest != source.manifest_digest:
        shutil.rmtree(partial)
        raise PackageCopyError("the copy's manifest differs from the staged manifest")
    partial.rename(destination)
    return verify_package(destination)


def reverify_copy(identity: PackageIdentity) -> None:
    """Re-verify a copy after a run and discard it when its contents changed."""
    root = Path(identity.root)
    try:
        after = verify_package(root)
    except PackageCopyError:
        shutil.rmtree(root, ignore_errors=True)
        raise
    if after.manifest_digest != identity.manifest_digest:
        shutil.rmtree(root, ignore_errors=True)
        raise PackageCopyError("the copy's manifest changed during the run")


def _python_sources(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*.py")
        if path.is_file() and "__pycache__" not in path.parts
    }


def _shipped(relative: str) -> bool:
    """Tests and pytest configuration never ship, so their absence from a package is not staleness."""
    return not is_test_source(relative)


def compare_with_checkout(package_root: Path, source_root: Path) -> CheckoutComparison:
    """Compare every first-party ``.py`` module in the package with ``source_root/<package>``."""
    differing: list[str] = []
    only_package: list[str] = []
    only_checkout: list[str] = []
    compared = 0
    for name in FIRST_PARTY_PACKAGES:
        packaged = _python_sources(package_root / _PACKAGES_DIRECTORY / name)
        checkout = {
            relative: path for relative, path in _python_sources(source_root / name).items() if _shipped(relative)
        }
        for relative in sorted(packaged.keys() | checkout.keys()):
            label = f"{name}/{relative}"
            if relative not in checkout:
                only_package.append(label)
            elif relative not in packaged:
                only_checkout.append(label)
            else:
                compared += 1
                if digest(packaged[relative]) != digest(checkout[relative]):
                    differing.append(label)
    return CheckoutComparison(
        compared=compared,
        differing=tuple(differing),
        only_in_package=tuple(only_package),
        only_in_checkout=tuple(only_checkout),
    )


def require_current(comparison: CheckoutComparison, *, measure_stale: bool) -> None:
    """Refuse a package that differs from the checkout unless the operator asked to measure it."""
    if not comparison.current and not measure_stale:
        raise UnavailableError(
            "package_stale",
            "the package differs from the checkout; rebuild with `just build-native Release bundle`, or pass "
            f"--measure-stale-package to measure it as built ({comparison.summary()})",
        )


def receipt_fields(
    identity: PackageIdentity, comparison: CheckoutComparison, *, measure_stale: bool
) -> Mapping[str, Any]:
    """The build facts a run receipt records about the package it measured."""
    return {
        "manifest_digest": identity.manifest_digest,
        "file_count": identity.file_count,
        "build": identity.build,
        "checkout_comparison": comparison.model_dump(mode="json"),
        "checkout_current": comparison.current,
        "measured_stale_package_on_request": measure_stale and not comparison.current,
    }
