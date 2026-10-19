"""Fingerprint everything that goes into each separately built native component.

A component is one set of native images that share their build inputs: the interpreter
hosts (with the console entrypoints, bundled images and the CPython bridge), the manager,
the installer adapter and the desktop. Its fingerprint is a content hash of:

- the checkout files compiled into those images: the Cargo crates it links (with their
  path dependencies), its C sources and headers, embedded assets, and the build
  definitions (CMake files, manifests, lockfiles, build scripts) that shape the images;
- the files the previous build actually read for them, from Cargo's dependency records
  and the MSVC compiler's read logs, so a file the declarations miss still counts;
- the generated contract and product identity, and the frontend bundle for the desktop;
- the selected toolchain (compiler, linker, SDK, Rust, CMake and generator identities,
  and Node and npm for the desktop) and the effective settings: per-configuration C
  compile and link options from the CMake file API, and the Rust target, flags and
  compiler environment every Cargo command receives;
- the identity of any other component it embeds.

Modification times never enter it, so touching a file or rebuilding unchanged sources
keeps the fingerprint and therefore the component's build number. Files written into a
build directory by the build itself are left out of the consumed set: they derive from
the declared inputs, and some carry the identity this fingerprint selects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT

from .build_directory import require_enrolled_build
from .build_paths import build_paths
from .hashing import digest, digest_cache

EXCLUDED_DIRECTORIES = frozenset({"target", "node_modules", "tests", "__pycache__", "test-results", "dist", ".vite"})
"""Build outputs, installed packages and test-only trees never reach a shipped image."""
EXCLUDED_SUFFIXES = frozenset({".pyc", ".md"})
"""Bytecode and prose beside native sources are not compiled into an image."""
STAGED_SUFFIXES = frozenset({".py"})
"""Python beside the C hosts is staged as package data, not compiled; crates may embed Python."""
FILE_API_QUERY = Path(".cmake/api/v1/query/client-cadrumo/query.json")
"""The CMake file API query the root project writes, relative to the binary directory."""
RUST_ENVIRONMENT = "rust-environment.json"
"""The Rust target and compiler environment CMake gives every Cargo command, in ``generated``."""
_DEPENDENCY_TABLES = ("dependencies", "build-dependencies")
_ESCAPED_SPACE = re.compile(r"(?<!\\) ")


@dataclass(frozen=True)
class Component:
    """The declared inputs of one component; paths are relative to the repository root."""

    crates: tuple[str, ...] = ()
    """Cargo package directories linked into the images, followed through path dependencies."""
    trees: tuple[str, ...] = ()
    """Source directories compiled or embedded whole, less their staged Python."""
    files: tuple[str, ...] = ()
    """Single source files: build definitions, embedded assets and resource generators."""
    outputs: tuple[tuple[str, str], ...] = ()
    """Build-directory members the images compile in, as (build path key, relative member)."""
    embeds: tuple[str, ...] = ()
    """Other components whose identity these images carry; a crate linked as a library carries none."""
    targets: tuple[str, ...] = ()
    """CMake target names, or ``prefix*`` patterns, whose compile and link settings shape the images."""
    records: tuple[str, ...] = ()
    """Globs, relative to the binary directory, of the dependency records the build leaves for them."""
    desktop_tools: bool = False
    """Whether the images are built with the desktop's Node and npm as well as the native tools."""
    snapshots: tuple[str, ...] = ()
    """Globs, relative to the binary directory, of source snapshots that compile ``native/`` in place."""
    features: tuple[str, ...] = ()
    """Cargo features the images are built with beyond the crates' defaults."""


_CONTRACT = (
    ("generated", "contract.rs"),
    ("generated", "contract.h"),
    ("generated", "contract.json"),
    ("generated", "identity.json"),
)
_SHARED_FILES = (
    "native/toolchain.json",
    "native/CMakeLists.txt",
    "native/cmake/Rust.cmake",
    "native/cmake/RustLinker.cmake",
    "native/cmake/WindowsToolchain.cmake",
    "native/cmake/platforms/Windows.cmake",
    "native/cmake/platforms/Posix.cmake",
)
_RUST_PROFILES = ("debug", "release")


def _cargo_records(directory: str, *names: str) -> tuple[str, ...]:
    return tuple(f"{directory}/{profile}/{name}.d" for profile in _RUST_PROFILES for name in names)


_NATIVE_CARGO = "cargo/native/*"
COMPONENTS: Mapping[str, Component] = {
    "interpreter": Component(
        crates=("native/platform", "native/launch_guard"),
        trees=("native/interpreter", "native/platforms"),
        files=(
            "native/package-layout.json",
            "native/cmake/CompilePolicy.cmake",
            "native/cmake/LaunchGuard.cmake",
            "docs/_static/cadrumo-icon.svg",
            "dev/packaging/native/metadata.py",
            "dev/packaging/native/platforms/windows.py",
            "dev/packaging/native/platforms/linux.py",
            "dev/packaging/native/platforms/macos.py",
        ),
        outputs=_CONTRACT,
        targets=(
            "cadrumo_python",
            "cadrumo_python_d",
            "cadrumo_python_bridge",
            "cadrumo_entrypoint_*",
            "cadrumo_bundled_*",
        ),
        records=(
            *_cargo_records(_NATIVE_CARGO, "cadrumo_platform", "cadrumo_launch_guard"),
            "native/cadrumo_python*.dir/*/*.tlog/CL.read.*.tlog",
            "native/cadrumo_entrypoint_*.dir/*/*.tlog/CL.read.*.tlog",
            "native/cadrumo_bundled_*.dir/*/*.tlog/CL.read.*.tlog",
        ),
    ),
    "installer": Component(
        crates=("native/installer",),
        files=(
            "native/manager/version_resource.rs",
            "native/interpreter/windows/host.manifest",
            "native/cmake/Installer.cmake",
        ),
        outputs=_CONTRACT,
        records=_cargo_records("cargo/native/installer/*", "cadrumo_installer", "cadrumo-msi-maintenance"),
    ),
    "manager": Component(
        crates=("native/manager",),
        files=(
            "native/interpreter/windows/host.manifest",
            "native/cmake/Manager.cmake",
            # The manager's desktop dispatch embeds the desktop's Python dispatcher.
            "native/desktop/src-tauri/src/python/manager_dispatch.py",
        ),
        outputs=_CONTRACT,
        records=_cargo_records(_NATIVE_CARGO, "cadrumo-manager"),
    ),
    "desktop": Component(
        crates=("native/desktop/src-tauri",),
        files=(
            "docs/_static/cadrumo-icon.svg",
            "native/desktop/CMakeLists.txt",
            "native/cmake/DesktopRust.cmake",
            "native/cmake/DesktopTools.cmake",
            "native/desktop/scripts/tauri.mjs",
            "native/desktop/scripts/configuration.mjs",
            "native/desktop/scripts/backend-snapshot.mjs",
            "native/desktop/scripts/content-build.mjs",
            "native/desktop/frontend/package.json",
            "native/desktop/frontend/package-lock.json",
            # The linked interpreter host compiles the C host source itself.
            "native/interpreter/launch_guard.h",
            "native/interpreter/launch_profile.h",
            "native/interpreter/windows/host.c",
            "native/interpreter/windows/host.manifest",
        ),
        outputs=(*_CONTRACT, ("desktop_frontend", "")),
        embeds=("interpreter",),
        records=tuple(f"cargo/desktop/{profile}/cadrumo.d" for profile in _RUST_PROFILES),
        desktop_tools=True,
        snapshots=("desktop/host",),
    ),
}
_DESKTOP = COMPONENTS["desktop"]
COMPONENTS = {
    **COMPONENTS,
    # The remote-debugging desktop the packaged end-to-end tests drive: the desktop's sources
    # and identity built with one more feature into its own testing directory, never shipped.
    "desktop-test-host": Component(
        crates=_DESKTOP.crates,
        files=(*_DESKTOP.files, "native/desktop/tests/packaged/host.mjs"),
        outputs=_DESKTOP.outputs,
        embeds=("interpreter", "desktop"),
        records=tuple(f"desktop/testing/*/cargo/{profile}/cadrumo.d" for profile in _RUST_PROFILES),
        desktop_tools=True,
        snapshots=("desktop/testing/*/host",),
        features=("webview2-remote-debugging",),
    ),
}


def crate_closure(crates: tuple[str, ...], *, root: Path = REPO_ROOT) -> list[str]:
    """Return each crate directory and every path dependency it builds or links, for any target."""
    pending = [(root / crate).resolve() for crate in crates]
    seen: dict[Path, None] = {}
    while pending:
        crate = pending.pop()
        if crate in seen:
            continue
        seen[crate] = None
        manifest = parse_toml((crate / "Cargo.toml").read_text(encoding="utf-8"))
        tables = [manifest.get(name, {}) for name in _DEPENDENCY_TABLES]
        for platform in manifest.get("target", {}).values():
            tables += [platform.get(name, {}) for name in _DEPENDENCY_TABLES]
        for table in tables:
            for dependency in table.values():
                if isinstance(dependency, dict) and isinstance(dependency.get("path"), str):
                    pending.append((crate / dependency["path"]).resolve())
    return sorted(path.relative_to(root.resolve()).as_posix() for path in seen)


def binary_sources(crate: Path) -> tuple[str, ...]:
    """Return the crate-relative roots of its binary targets, which a crate linking it never compiles."""
    manifest = parse_toml((crate / "Cargo.toml").read_text(encoding="utf-8"))
    declared = [target.get("path") for target in manifest.get("bin", []) if isinstance(target, dict)]
    return ("src/main.rs", "src/bin", *(PurePosixPath(path).as_posix() for path in declared if isinstance(path, str)))


def _digest(path: Path) -> str:
    """The one place component inventories hash a file, so a shared hash cache applies everywhere."""
    return digest(path)


def _tree(directory: Path, *, exclude: frozenset[str] | None) -> Iterator[Path]:
    for current, directories, files in os.walk(directory):
        if exclude is not None:
            directories[:] = [name for name in directories if name not in EXCLUDED_DIRECTORIES]
        for name in files:
            if exclude is None or Path(name).suffix not in exclude:
                yield Path(current) / name


def _entries(paths: list[tuple[str, Path]], *, exclude: frozenset[str] | None) -> dict[str, str]:
    entries: dict[str, str] = {}
    for label, path in paths:
        if path.is_dir():
            for member in _tree(path, exclude=exclude):
                entries[f"{label}/{member.relative_to(path).as_posix()}".removeprefix("/")] = _digest(member)
        elif path.is_file():
            entries[label] = _digest(path)
        else:
            entries[label] = "missing"
    return entries


def declared_inventory(name: str, *, root: Path = REPO_ROOT) -> dict[str, str]:
    """Hash every checkout file the component declares, keyed by its repository path."""
    component = COMPONENTS[name]
    crates = crate_closure(component.crates, root=root)
    sources = [(path, root / path) for path in crates]
    trees = [(path, root / path) for path in component.trees]
    files = [(path, root / path) for path in (*component.files, *_SHARED_FILES)]
    # A linked dependency contributes its library, not its own executables.
    binaries = tuple(
        f"{crate}/{target}"
        for crate in sorted(set(crates) - set(component.crates))
        for target in binary_sources(root / crate)
    )
    entries: dict[str, str] = {
        key: value
        for key, value in _entries(sources, exclude=EXCLUDED_SUFFIXES).items()
        if not any(key == prefix or key.startswith(f"{prefix}/") for prefix in binaries)
    }
    entries.update(_entries(trees, exclude=EXCLUDED_SUFFIXES | STAGED_SUFFIXES))
    entries.update(_entries(files, exclude=None))
    return entries


def dependency_record_paths(text: str, *, record: Path) -> list[Path]:
    """Return the input files one Cargo dependency record or MSVC compiler read log names."""
    if record.suffix == ".d":
        first = text.splitlines()[0] if text.strip() else ""
        _, separator, dependencies = first.partition(": ")
        if not separator:
            return []
        return [Path(token.replace("\\ ", " ")) for token in _ESCAPED_SPACE.split(dependencies.strip()) if token]
    return [Path(line.lstrip("^")) for line in text.splitlines() if line.strip()]


def _read_record(record: Path) -> str:
    raw = record.read_bytes()
    # The MSVC tracker writes UTF-16 logs; Cargo writes UTF-8 dependency records.
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


def consumed_inputs(name: str, build: Path, *, root: Path = REPO_ROOT) -> dict[str, Path]:
    """Return the checkout files the previous build of the component read, keyed by repository path.

    Files outside the checkout are pinned by the lockfiles and the toolchain identity, and
    files inside a build directory are derived; neither is listed. The desktop compiles a
    snapshot of the native sources in its build directory, which maps back to them.
    """
    root, build = root.resolve(), build.resolve()
    component = COMPONENTS[name]
    snapshots = [path for pattern in component.snapshots for path in build.glob(pattern)]
    builds = root / "build"
    consumed: dict[str, Path] = {}
    for pattern in component.records:
        for record in sorted(build.glob(pattern)):
            for listed in dependency_record_paths(_read_record(record), record=record):
                path = Path(os.path.normpath(listed))
                snapshot = next((base for base in snapshots if path.is_relative_to(base)), None)
                if snapshot is not None:
                    path = root / "native" / path.relative_to(snapshot)
                # A file only the snapshot holds was generated there, and a file since removed
                # is no longer read; neither is a checkout input.
                if (
                    not path.is_absolute()
                    or path.is_relative_to(build)
                    or path.is_relative_to(builds)
                    or not path.is_file()
                ):
                    continue
                try:
                    relative = path.resolve().relative_to(root)
                except ValueError:
                    continue
                if relative.parts and relative.parts[0] == "build":
                    continue
                consumed[relative.as_posix()] = path
    return consumed


def uncovered_inputs(name: str, build: Path, *, root: Path = REPO_ROOT) -> list[str]:
    """Name the files the previous build read that the component's declarations do not cover."""
    declared = {os.path.normcase(key) for key in declared_inventory(name, root=root)}
    return sorted(key for key in consumed_inputs(name, build, root=root) if os.path.normcase(key) not in declared)


def source_inventory(name: str, build: Path | None = None, *, root: Path = REPO_ROOT) -> dict[str, str]:
    """Hash the declared checkout files plus any the previous build read beyond them."""
    entries = declared_inventory(name, root=root)
    if build is not None:
        known = {os.path.normcase(key) for key in entries}
        for key, path in consumed_inputs(name, build, root=root).items():
            if os.path.normcase(key) not in known:
                entries[key] = _digest(path) if path.is_file() else "missing"
    return entries


def output_inventory(name: str, build: Path) -> dict[str, str]:
    """Hash the build-directory members the component compiles in, keyed by their build path."""
    paths = build_paths(build)
    members = [
        (f"<{key}>/{member}".rstrip("/"), paths[key] / member if member else paths[key])
        for key, member in COMPONENTS[name].outputs
    ]
    return _entries(members, exclude=None)


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def _cache_value(build: Path, name: str) -> str | None:
    try:
        lines = (build / "CMakeCache.txt").read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    prefix = f"{name}:"
    for line in lines:
        if line.startswith(prefix):
            return line.partition("=")[2]
    return None


def toolchain_identity(name: str, build: Path) -> dict[str, Any]:
    """Name the selected compilers, linkers, SDK and tools, by version and executable hash."""
    configured = _json(build_paths(build)["generated"] / "build-toolchain.json") or {}
    files = configured.get("builder_files", {})
    desktop = COMPONENTS[name].desktop_tools
    selected = {
        tool: record
        for tool, record in (files.items() if isinstance(files, dict) else ())
        if tool != "CADRUMO_UV" and (desktop or not tool.startswith("desktop/"))
    }
    identity: dict[str, Any] = {
        "builder_files": selected,
        "sysroots": configured.get("sysroots", {}),
        "tool_versions": configured.get("tool_versions", {}),
        "c_compiler_version": configured.get("CMAKE_C_COMPILER_VERSION"),
        "target": configured.get("CADRUMO_TARGET"),
        # CMake's C compile and link flags reach only the images CMake compiles itself.
        "target_configuration": configured.get("target_configuration", {}) if COMPONENTS[name].targets else None,
        "generator": _cache_value(build, "CMAKE_GENERATOR"),
        "generator_instance": _cache_value(build, "CMAKE_GENERATOR_INSTANCE"),
        "generator_toolset": _cache_value(build, "CMAKE_GENERATOR_TOOLSET"),
    }
    if desktop:
        tools = configured.get("desktop_tools", {})
        identity["desktop_tools"] = {key: tools.get(key) for key in ("npm_version",) if isinstance(tools, dict)}
    return identity


def _matches(target: str, patterns: Iterable[str]) -> bool:
    return any(target.startswith(pattern[:-1]) if pattern.endswith("*") else target == pattern for pattern in patterns)


def _portable(path: str, root: Path) -> str:
    candidate = Path(path)
    if candidate.is_absolute() and candidate.is_relative_to(root):
        return candidate.relative_to(root).as_posix()
    return candidate.as_posix()


def target_settings(name: str, build: Path, *, root: Path = REPO_ROOT) -> dict[str, Any]:
    """Return the per-configuration compile and link settings CMake generated for the component.

    The CMake file API reply of the last configure names every compile group's flags,
    defines, include directories and sources, and every link command fragment.
    """
    patterns = COMPONENTS[name].targets
    if not patterns:
        return {}
    reply = build / ".cmake/api/v1/reply"
    indexes = sorted(reply.glob("index-*.json"))
    if not indexes:
        return {"file_api": "missing"}
    index = _json(indexes[-1])
    codemodel = next(
        (
            entry
            for entry in index.get("reply", {}).get("client-cadrumo", {}).get("query.json", {}).get("responses", [])
            if entry.get("kind") == "codemodel"
        ),
        None,
    )
    if codemodel is None:
        return {"file_api": "no codemodel"}
    model = _json(reply / codemodel["jsonFile"])
    settings: dict[str, Any] = {}
    for configuration in model.get("configurations", []):
        for reference in configuration.get("targets", []):
            if not _matches(reference["name"], patterns):
                continue
            target = _json(reply / reference["jsonFile"])
            sources = [source.get("path", "") for source in target.get("sources", [])]
            settings[f"{configuration['name']}/{reference['name']}"] = {
                "type": target.get("type"),
                "name_on_disk": target.get("nameOnDisk"),
                "compile": [
                    {
                        "language": group.get("language"),
                        "fragments": [
                            fragment.get("fragment") for fragment in group.get("compileCommandFragments", [])
                        ],
                        "defines": [define.get("define") for define in group.get("defines", [])],
                        "includes": [_portable(include.get("path", ""), root) for include in group.get("includes", [])],
                        "sources": [_portable(sources[index], root) for index in group.get("sourceIndexes", [])],
                    }
                    for group in target.get("compileGroups", [])
                ],
                "link": [
                    {"role": fragment.get("role"), "fragment": fragment.get("fragment")}
                    for fragment in target.get("link", {}).get("commandFragments", [])
                ],
            }
    return settings


def rust_settings(build: Path) -> Any:
    """Return the Rust target and the compiler environment CMake passes to every Cargo command."""
    return _json(build_paths(build)["generated"] / RUST_ENVIRONMENT)


def _settings_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def inventory(name: str, build: Path, embedded: Mapping[str, str], *, root: Path = REPO_ROOT) -> dict[str, str]:
    """Return every input of one component as ``{key: sha256}``, given the fingerprints it embeds.

    Checkout files are keyed by repository path, build-directory members by
    ``<build path key>/member``, and the non-file inputs by ``@toolchain``, ``@settings/cmake``,
    ``@settings/rust``, ``@features`` and ``@embeds/<component>``. A reader compares two
    inventories key by key to name exactly which inputs changed.
    """
    component = COMPONENTS[name]
    missing = [dependency for dependency in component.embeds if dependency not in embedded]
    if missing:
        raise ValueError(f"Fingerprint {name} after the components it embeds: {', '.join(missing)}")
    # The build directory's shared cache re-reads only files whose size, time or identity moved.
    with digest_cache(build):
        entries = source_inventory(name, build, root=root)
        entries.update(output_inventory(name, build))
    entries["@toolchain"] = _settings_digest(toolchain_identity(name, build))
    entries["@settings/cmake"] = _settings_digest(target_settings(name, build, root=root))
    entries["@settings/rust"] = _settings_digest(rust_settings(build))
    if component.features:
        entries["@features"] = _settings_digest(sorted(component.features))
    for dependency in component.embeds:
        entries[f"@embeds/{dependency}"] = embedded[dependency]
    return entries


def inventory_fingerprint(entries: Mapping[str, str]) -> str:
    """Return the fingerprint an inventory names: the SHA-256 of its canonical JSON."""
    return hashlib.sha256(json.dumps(dict(sorted(entries.items())), sort_keys=True).encode("utf-8")).hexdigest()


def fingerprint(name: str, build: Path, embedded: Mapping[str, str], *, root: Path = REPO_ROOT) -> str:
    """Return the content fingerprint of one component given the fingerprints of what it embeds."""
    return inventory_fingerprint(inventory(name, build, embedded, root=root))


def current_fingerprints(build: Path, names: Iterable[str], *, root: Path = REPO_ROOT) -> dict[str, str]:
    """Fingerprint the named components, and what they embed, as their inputs stand now."""
    fingerprints: dict[str, str] = {}
    for name in resolution_order(tuple(names)):
        fingerprints[name] = fingerprint(name, build, fingerprints, root=root)
    return fingerprints


def resolution_order(names: list[str] | tuple[str, ...]) -> list[str]:
    """Order the requested components after every component they embed, adding those."""
    ordered: list[str] = []

    def visit(name: str, trail: tuple[str, ...]) -> None:
        if name not in COMPONENTS:
            raise ValueError(f"Unknown native component {name!r}; known: {', '.join(sorted(COMPONENTS))}")
        if name in trail:
            raise ValueError(f"Native components embed each other: {' -> '.join((*trail, name))}")
        for dependency in COMPONENTS[name].embeds:
            visit(dependency, (*trail, name))
        if name not in ordered:
            ordered.append(name)

    for name in names:
        visit(name, ())
    return ordered


SHIPPED = ("interpreter", "installer", "manager", "desktop")
"""Components every complete native build compiles; the test host is built on request."""


def coverage_failures(build: Path, *, root: Path = REPO_ROOT) -> dict[str, list[str]]:
    """Return each built component's undeclared consumed files; refuse a shipped one never built."""
    failures: dict[str, list[str]] = {}
    for name, component in COMPONENTS.items():
        if not any(path for pattern in component.records for path in build.glob(pattern)):
            if name in SHIPPED:
                raise FileNotFoundError(f"No dependency records for the {name} component under {build}; build it first")
            continue
        failures[name] = uncovered_inputs(name, build, root=root)
    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check that every component declares the files its last build read.")
    parser.add_argument("--build", type=require_enrolled_build, required=True)
    args = parser.parse_args()
    found = coverage_failures(args.build)
    for name, uncovered in found.items():
        for path in uncovered:
            print(f"{name}: {path} is compiled in but not declared in dev/packaging/native/build_fingerprint.py")
    raise SystemExit(1 if any(found.values()) else 0)
