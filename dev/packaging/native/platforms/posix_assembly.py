"""Assemble and relocate POSIX SDK and wheel native images."""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable, Mapping
from fnmatch import fnmatchcase
from pathlib import Path
from typing import TypedDict, cast

from ..hashing import digest
from .posix_images import native_image


class ExtensionExclusion(TypedDict):
    """One reviewed excluded SDK extension."""

    pattern: str
    reason: str


class ExcludedExtension(TypedDict):
    """One skipped SDK extension with its digest and declared reasons."""

    file: str
    sha256: str
    reasons: list[str]


class PosixAssemblyResult(TypedDict):
    """The staged native inventory and relocation evidence."""

    modules: dict[str, str]
    python_paths: list[str]
    relocation: dict[str, str]
    patches: list[dict[str, str]]
    sdk_extension_exclusions: list[ExcludedExtension]


def _valid_exclusion(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    record = cast(dict[str, object], entry)
    pattern, reason = record.get("pattern"), record.get("reason")
    return (
        isinstance(pattern, str)
        and bool(pattern)
        and "/" not in pattern
        and "\\" not in pattern
        and isinstance(reason, str)
        and bool(reason)
    )


def _validate_sdk_extensions(sdk: dict[str, object]) -> tuple[str, list[ExtensionExclusion]]:
    suffix = cast(str, sdk["extension_suffix"])
    if not suffix.endswith(".so") or suffix == ".so":
        raise ValueError("The target CPython extension suffix must identify its ABI")
    exclusions = sdk.get("extension_exclusions", [])
    if not isinstance(exclusions, list) or any(not _valid_exclusion(entry) for entry in cast(list[object], exclusions)):
        raise ValueError("SDK extension exclusions require basename patterns and reasons")
    return suffix, cast(list[ExtensionExclusion], cast(object, exclusions))


def _copy_sdk_images(python: Path, native: Path, sdk: dict[str, object]) -> None:
    # B1 supplies exact SDK-relative native inputs; no host library discovery.
    for relative in cast(list[str], sdk["native_files"]):
        source = (python / relative).resolve()
        if not source.is_relative_to(python.resolve()) or not native_image(source):
            raise ValueError(f"Invalid SDK native image: {relative}")
        target = native / Path(relative).name
        if target.exists() and digest(target) != digest(source):
            raise ValueError(f"Conflicting SDK native image: {target.name}")
        shutil.copy2(source, target)


def _copy_sdk_extension(
    source: Path, python: Path, native: Path, root: Path, suffix: str, modules: dict[str, str]
) -> None:
    if (
        not source.name.endswith(suffix)
        or not source.resolve().is_relative_to(python.resolve())
        or not native_image(source)
    ):
        raise ValueError(f"Invalid SDK extension image or release ABI: {source.name}")
    target = native / source.name
    if target.exists():
        raise ValueError(f"Duplicate SDK extension: {source.name}")
    shutil.copy2(source, target)
    modules[source.name.split(".")[0]] = target.relative_to(root).as_posix()


def _copy_sdk_extensions(
    python: Path,
    native: Path,
    root: Path,
    sdk: dict[str, object],
    suffix: str,
    exclusions: list[ExtensionExclusion],
    modules: dict[str, str],
) -> list[ExcludedExtension]:
    excluded: list[ExcludedExtension] = []
    extensions = (python / cast(str, sdk["extensions"])).resolve()
    if not extensions.is_relative_to(python.resolve()) or not extensions.is_dir():
        raise ValueError("SDK extension directory is missing or outside the SDK")
    for source in sorted(extensions.glob("*.so")):
        matches = [entry for entry in exclusions if fnmatchcase(source.name, entry["pattern"])]
        if matches:
            excluded.append(
                {
                    "file": source.relative_to(python).as_posix(),
                    "sha256": digest(source),
                    "reasons": [entry["reason"] for entry in matches],
                }
            )
            continue
        _copy_sdk_extension(source, python, native, root, suffix, modules)
    return excluded


def _move_wheel_images(
    packages: Path, native: Path, root: Path, suffix: str, modules: dict[str, str], relocation: dict[str, str]
) -> None:
    for source in sorted(packages.rglob("*")):
        if not native_image(source):
            continue
        if source.is_symlink():
            raise ValueError(f"Wheel native symlink requires explicit admission: {source}")
        relative = source.relative_to(packages)
        target = native / "packages" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError(f"Duplicate native destination: {target}")
        shutil.move(source, target)
        relocation[source.relative_to(root).as_posix()] = target.relative_to(root).as_posix()
        if source.name.endswith((suffix, ".abi3.so")):
            parts = [*relative.parts[:-1], relative.name.split(".")[0]]
            if parts[-1] == "__init__":
                parts.pop()
            identity = ".".join(parts)
            if identity in modules:
                raise ValueError(f"Duplicate extension identity: {identity}")
            modules[identity] = target.relative_to(root).as_posix()


def _patch_native_loaders(
    packages: Path, native: Path, root: Path, contract: Mapping[str, object]
) -> list[dict[str, str]]:
    patches: list[dict[str, str]] = []
    bindings = packages / "pypdfium2_raw/bindings.py"
    if bindings.is_file():
        candidates = list((native / "packages/pypdfium2_raw").glob("*pdfium*"))
        if len(candidates) != 1:
            raise ValueError("PDFium must have exactly one bundled native library")
        source = bindings.read_text(encoding="utf-8")
        # ctypesgen has written this line with either quote style across pypdfium2 releases.
        loader = re.compile(r"libpaths\s*=\s*\(\s*(['\"])\./\{prefix\}\{name\}\.\{suffix\}\1,?\s*\),")
        if len(loader.findall(source)) != 1:
            raise ValueError("Unrecognized pypdfium2 ctypesgen loader")
        before = digest(bindings)
        relative = candidates[0].relative_to(root).as_posix()
        parent = contract["package_root_from_executable"]
        replacement = f"libpaths = (str(pathlib.Path(sys.executable).parent / {parent!r} / {relative!r}),),"
        bindings.write_text(loader.sub(lambda _match: replacement, source, count=1), encoding="utf-8")
        patches.append(
            {
                "file": bindings.relative_to(root).as_posix(),
                "before": before,
                "after": digest(bindings),
                "reason": "Relocated explicit PDFium library path",
            }
        )
    # Playwright starts its Node driver from beside the package; point that default at
    # the relocated executable while keeping its own PLAYWRIGHT_NODEJS_PATH override.
    driver = packages / "playwright/_impl/_driver.py"
    if driver.is_file():
        before = digest(driver)
        source = driver.read_text(encoding="utf-8")
        old = 'str(driver_path / "node")'
        node = native / "packages/playwright/driver/node"
        if source.count(old) != 1 or not node.is_file():
            raise ValueError("Unrecognized Playwright driver loader")
        parent = contract["package_root_from_executable"]
        relative = node.relative_to(root).as_posix()
        replacement = f"str(Path(sys.executable).parent / {parent!r} / {relative!r})"
        driver.write_text(source.replace(old, replacement), encoding="utf-8")
        patches.append(
            {
                "file": driver.relative_to(root).as_posix(),
                "before": before,
                "after": digest(driver),
                "reason": "Relocated Playwright Node driver path",
            }
        )
    return patches


def assemble(
    python: Path,
    packages: Path,
    native: Path,
    root: Path,
    contract: Mapping[str, object],
    relocate: Callable[[list[Path], Path, dict[str, object]], None],
) -> PosixAssemblyResult:
    """Stage declared SDK images and wheel native files before per-object relocation."""
    modules: dict[str, str] = {}
    relocation: dict[str, str] = {}
    if list(packages.glob("*.pth")):
        raise ValueError("POSIX wheel .pth files require explicit review")
    sdk = cast(dict[str, object], contract["sdk"])
    suffix, exclusions = _validate_sdk_extensions(sdk)
    _copy_sdk_images(python, native, sdk)
    excluded = _copy_sdk_extensions(python, native, root, sdk, suffix, exclusions, modules)
    _move_wheel_images(packages, native, root, suffix, modules, relocation)
    patches = _patch_native_loaders(packages, native, root, contract)
    images = [path for path in root.rglob("*") if native_image(path)]
    relocate(images, root, cast(dict[str, object], contract))
    return {
        "modules": modules,
        "python_paths": [packages.relative_to(root).as_posix()],
        "relocation": relocation,
        "patches": patches,
        "sdk_extension_exclusions": excluded,
    }
