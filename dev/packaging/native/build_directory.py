"""Admit only configured CMake binary directories enrolled by repository presets."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dev._paths import REPO_ROOT

from .build_paths import build_paths

_PRESET_PROJECTS = (
    (Path("CMakePresets.json"), Path(".")),
    (Path("native/desktop/CMakePresets.json"), Path("native/desktop")),
    (Path("native/cmake/distribution/CMakePresets.json"), Path("native/cmake/distribution")),
)
_CACHE_SETTING = re.compile(r"^(CMAKE_HOME_DIRECTORY|CMAKE_CACHEFILE_DIR):[^=]*=(.*)$")


def _is_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.normpath(str(left))) == os.path.normcase(os.path.normpath(str(right)))


def _require_physical(path: Path, root: Path, description: str) -> None:
    """Reject linked components between *root* and *path*, including Windows junctions."""
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{description} is outside the repository: {path}") from error
    member = root
    for part in relative.parts:
        member = member / part
        if _is_link(member):
            raise ValueError(f"{description} must not use symlinks or junctions: {member}")


def _preset_sources(source_root: Path) -> dict[str, Path]:
    enrolled: dict[str, Path] = {}
    for relative_file, relative_project in _PRESET_PROJECTS:
        preset_file = source_root / relative_file
        _require_physical(preset_file, source_root, "CMake preset file")
        if not preset_file.is_file():
            raise ValueError(f"CMake preset file is missing: {preset_file}")
        try:
            document = json.loads(preset_file.read_text(encoding="utf-8"))
            presets = document["configurePresets"]
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise ValueError(f"CMake preset file is invalid: {preset_file}") from error
        if not isinstance(presets, list):
            raise ValueError(f"CMake preset file has no configure preset list: {preset_file}")
        project_root = (source_root / relative_project).resolve(strict=True)
        for preset in presets:
            if not isinstance(preset, dict) or preset.get("hidden", False):
                continue
            name = preset.get("name")
            if (
                not isinstance(name, str)
                or not name
                or name.startswith(".")
                or name in {".", ".."}
                or "/" in name
                or "\\" in name
                or ":" in name
            ):
                raise ValueError(f"CMake configure preset has an invalid enrolled name: {name!r}")
            previous = enrolled.get(name)
            if previous is not None and not _same_path(previous, project_root):
                raise ValueError(f"CMake configure preset name is ambiguous: {name}")
            enrolled[name] = project_root
    if not enrolled:
        raise ValueError("The repository has no visible CMake configure presets")
    return enrolled


def _configured_sources(build: Path, *, require_cache: bool) -> tuple[Path, Path | None]:
    manifest = build / "build-paths.json"
    cache = build / "CMakeCache.txt"
    if _is_link(manifest) or not manifest.is_file():
        raise ValueError(f"CMake build-path manifest is missing or linked: {manifest}")
    if _is_link(cache) or (cache.exists() and not cache.is_file()) or (require_cache and not cache.is_file()):
        raise ValueError(f"CMake cache is missing or linked; configure the enrolled build first: {cache}")
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
        source_value = document["source"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError(f"CMake build-path manifest is invalid: {manifest}") from error
    if not isinstance(source_value, str):
        raise ValueError(f"CMake build-path manifest has no source directory: {manifest}")
    try:
        manifest_source = Path(source_value).resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError(f"CMake build-path manifest source is unavailable: {manifest}") from error
    if not cache.is_file():
        return manifest_source, None
    settings: dict[str, str] = {}
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _CACHE_SETTING.match(line)
        if match:
            settings[match.group(1)] = match.group(2)
    try:
        cache_source = Path(settings["CMAKE_HOME_DIRECTORY"]).resolve(strict=True)
        cache_build = Path(settings["CMAKE_CACHEFILE_DIR"]).resolve(strict=True)
    except (KeyError, OSError, RuntimeError) as error:
        raise ValueError(f"CMake cache or build-path manifest is incomplete: {build}") from error
    if not _same_path(manifest_source, cache_source):
        raise ValueError(f"CMake cache and build-path manifest disagree about the source directory: {build}")
    if not _same_path(cache_build, build):
        raise ValueError(f"CMake cache belongs to another binary directory: {build}")
    return manifest_source, cache_source


def require_enrolled_build(build: Path | str, *, configured: bool = True) -> Path:
    """Admit a repository preset directory before a CLI build action writes."""
    source_root = REPO_ROOT.resolve(strict=True)
    selected = Path(build)
    if ".." in selected.parts:
        raise ValueError("Native build directory must not contain traversal components")
    enrolled = _preset_sources(source_root)
    owner = source_root / "build"
    _require_physical(owner, source_root, "Repository build directory")
    if not owner.is_dir():
        raise ValueError(f"Repository build directory is missing: {owner}")

    lexical = selected.absolute()
    try:
        relative = lexical.relative_to(owner)
    except ValueError as error:
        raise ValueError(f"Native build directory must be beneath {owner}: {selected}") from error
    if len(relative.parts) != 1 or relative.name not in enrolled:
        choices = ", ".join(sorted(enrolled))
        raise ValueError(f"Native build directory must be build/<visible configure preset>; enrolled: {choices}")
    canonical = owner / relative.name
    _require_physical(canonical, source_root, "Native build directory")
    if not canonical.is_dir():
        raise ValueError(f"Native build directory is missing: {canonical}")
    resolved = canonical.resolve(strict=True)
    if not _same_path(lexical, canonical) or not _same_path(resolved, canonical):
        raise ValueError(f"Native build directory is not its enrolled physical path: {selected}")

    manifest_source, _cache_source = _configured_sources(canonical, require_cache=configured)
    expected_source = enrolled[relative.name]
    if not _same_path(manifest_source, expected_source):
        raise ValueError(f"Configured build source does not match preset {relative.name!r}: {canonical}")
    try:
        build_paths(canonical)
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"Configured CMake output manifest is invalid: {canonical}: {error}") from error
    return canonical


def require_enrolled_output(output: Path | str) -> Path:
    """Admit a path strictly beneath a declared output of an enrolled CMake build."""
    selected = Path(output)
    if ".." in selected.parts:
        raise ValueError("Native output path must not contain traversal components")
    destination = selected.absolute()
    source_root = REPO_ROOT.resolve(strict=True)
    owner_root = source_root / "build"
    _require_physical(owner_root, source_root, "Repository build directory")
    if not owner_root.is_dir():
        raise ValueError(f"Repository build directory is missing: {owner_root}")

    try:
        relative = destination.relative_to(owner_root)
    except ValueError as error:
        raise ValueError(f"Native output must be inside a declared repository build output: {selected}") from error
    if not relative.parts:
        raise ValueError("Native output must be below an enrolled preset build directory")
    preset_name = relative.parts[0]
    build = require_enrolled_build(owner_root / preset_name, configured=False)
    paths = build_paths(build)

    _require_physical(destination, source_root, "Native output path")
    resolved = destination.resolve(strict=False)
    if not _same_path(destination, resolved):
        raise ValueError(f"Native output path is not its physical path: {selected}")
    for declared_root in paths.values():
        if destination.is_relative_to(declared_root):
            return destination
    raise ValueError(f"Native output is not below a declared CMake output directory: {selected}")
