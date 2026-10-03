"""Validate and extract closed runtime dependency archives."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from .runtime_wheelhouse_contract import (
    PLATFORM_FLOORS,
    SUPPORTED_TARGETS,
    WHEELHOUSE_MANIFEST,
    WHEELHOUSE_PREFIX,
    WHEELHOUSE_SCHEMA,
    RuntimeWheelhouse,
    _canonical_python_minor,
)

_UTF_8 = "utf-8"


def _validated_manifest(manifest: Any, expected_lock_sha256: str | None) -> dict[str, Any]:
    if not isinstance(manifest, dict) or set(manifest) != {"lock_sha256", "platform_floors", "runtimes", "schema"}:
        raise SystemExit("runtime wheelhouse manifest schema drifted")
    if manifest.get("schema") != WHEELHOUSE_SCHEMA:
        raise SystemExit("runtime wheelhouse identity drifted")
    if manifest.get("platform_floors") != PLATFORM_FLOORS:
        raise SystemExit("runtime wheelhouse platform support floor drifted")
    lock_sha256 = manifest.get("lock_sha256")
    if not isinstance(lock_sha256, str) or len(lock_sha256) != 64:
        raise SystemExit("runtime wheelhouse lock digest is invalid")
    if expected_lock_sha256 is not None and lock_sha256 != expected_lock_sha256:
        raise SystemExit("runtime wheelhouse does not bind the tested uv.lock")
    return manifest


def _manifest_runtimes(manifest: dict[str, Any], expected_python: str | None) -> dict[str, Any]:
    runtimes = manifest.get("runtimes")
    if not isinstance(runtimes, dict) or not runtimes:
        raise SystemExit("runtime wheelhouse declares no runtimes")
    if expected_python is not None:
        expected_runtime = _canonical_python_minor(expected_python)
        if expected_runtime not in runtimes:
            raise SystemExit(f"runtime wheelhouse has no entry for Python {expected_runtime}")
        selected = runtimes[expected_runtime]
        if not isinstance(selected, dict) or selected.get("status") != "ready":
            raise SystemExit(f"runtime wheelhouse has no ready entry for Python {expected_runtime}")
    return runtimes


def _validate_runtime_identity(python_version: Any, runtime: Any) -> None:
    canonical_runtime = _canonical_python_minor(python_version) if isinstance(python_version, str) else ""
    if canonical_runtime != python_version or not isinstance(runtime, dict):
        raise SystemExit(f"runtime wheelhouse runtime declaration is invalid: {python_version!r}")
    if runtime.get("python") != python_version:
        raise SystemExit(f"runtime wheelhouse runtime identity drifted: {python_version!r}")


def _valid_missing_attribution(item: Any) -> bool:
    return (
        isinstance(item, dict)
        and set(item) == {"distribution", "platform", "reason", "requirement"}
        and all(isinstance(item[key], str) and bool(item[key]) for key in item)
    )


def _validate_missing_runtime(python_version: str, runtime: dict[str, Any]) -> None:
    if set(runtime) != {"missing", "python", "status"}:
        raise SystemExit(f"runtime wheelhouse missing-wheel record drifted: {python_version!r}")
    missing = runtime.get("missing")
    if not isinstance(missing, list) or not missing:
        raise SystemExit(f"runtime wheelhouse missing-wheel record is empty: {python_version!r}")
    for item in missing:
        if not _valid_missing_attribution(item):
            raise SystemExit(f"runtime wheelhouse missing-wheel attribution is invalid: {python_version!r}")


def _ready_runtime_material(python_version: str, runtime: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if runtime.get("status") != "ready" or set(runtime) != {"platforms", "python", "status", "wheels"}:
        raise SystemExit(f"runtime wheelhouse runtime status is invalid: {python_version!r}")
    platforms = runtime.get("platforms")
    wheels = runtime.get("wheels")
    if not isinstance(platforms, dict) or set(platforms) != {target.name for target in SUPPORTED_TARGETS}:
        raise SystemExit(f"runtime wheelhouse platform closure is incomplete: {python_version!r}")
    if not isinstance(wheels, dict) or not wheels:
        raise SystemExit(f"runtime wheelhouse declares no wheels: {python_version!r}")
    return platforms, wheels


def _valid_wheel_digest(digest: Any) -> bool:
    return (
        isinstance(digest, str) and len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)
    )


def _valid_wheel_fields(raw: dict[str, Any]) -> bool:
    size = raw.get("size")
    distribution = raw.get("distribution")
    version = raw.get("version")
    return (
        isinstance(size, int)
        and size >= 0
        and isinstance(distribution, str)
        and bool(distribution)
        and isinstance(version, str)
        and bool(version)
    )


def _validate_wheel_record(filename: Any, raw: Any) -> None:
    if not isinstance(filename, str) or Path(filename).name != filename or not filename.endswith(".whl"):
        raise SystemExit(f"runtime wheelhouse wheel declaration is invalid: {filename!r}")
    if not isinstance(raw, dict) or set(raw) != {"distribution", "sha256", "size", "version"}:
        raise SystemExit(f"runtime wheelhouse wheel record drifted: {filename!r}")
    if not _valid_wheel_digest(raw.get("sha256")) or not _valid_wheel_fields(raw):
        raise SystemExit(f"runtime wheelhouse wheel record is invalid: {filename!r}")


def _validate_runtime_wheels(
    bundle: zipfile.ZipFile, python_version: str, wheels: dict[str, Any], declared: set[str]
) -> None:
    for filename, raw in wheels.items():
        _validate_wheel_record(filename, raw)
        member = f"{WHEELHOUSE_PREFIX}{python_version}/{filename}"
        declared.add(member)
        payload = bundle.read(member)
        if len(payload) != raw["size"] or hashlib.sha256(payload).hexdigest() != raw["sha256"]:
            raise SystemExit(f"runtime wheelhouse wheel bytes drifted: {python_version}/{filename!r}")


def _validate_target_wheel(
    python_version: str, target: str, distribution: Any, filename: Any, wheels: dict[str, Any]
) -> None:
    record = wheels.get(filename) if isinstance(filename, str) else None
    if (
        not isinstance(distribution, str)
        or not distribution
        or not isinstance(filename, str)
        or not isinstance(record, dict)
        or record.get("distribution") != distribution
    ):
        raise SystemExit(f"runtime wheelhouse target references an unknown wheel: {python_version}/{target!r}")


def _validate_target_rows(python_version: str, platforms: dict[str, Any], wheels: dict[str, Any]) -> None:
    for target, rows in platforms.items():
        if not isinstance(rows, dict) or not rows:
            raise SystemExit(f"runtime wheelhouse target closure is empty: {python_version}/{target!r}")
        for distribution, filename in rows.items():
            _validate_target_wheel(python_version, target, distribution, filename, wheels)


def load_runtime_wheelhouse(
    archive_path: Path,
    *,
    expected_lock_sha256: str | None = None,
    expected_python: str | None = None,
) -> RuntimeWheelhouse:
    """Validate a closed multi-runtime wheelhouse archive and every wheel byte."""
    archive = archive_path.resolve(strict=True)
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if names.count(WHEELHOUSE_MANIFEST) != 1 or len(names) != len(set(names)):
            raise SystemExit("runtime wheelhouse has a missing or duplicate manifest/member")
        manifest = _validated_manifest(json.loads(bundle.read(WHEELHOUSE_MANIFEST)), expected_lock_sha256)
        runtimes = _manifest_runtimes(manifest, expected_python)
        declared = {WHEELHOUSE_MANIFEST}
        for python_version, runtime in runtimes.items():
            _validate_runtime_identity(python_version, runtime)
            if runtime.get("status") == "missing-wheel":
                _validate_missing_runtime(python_version, runtime)
                continue
            platforms, wheels = _ready_runtime_material(python_version, runtime)
            _validate_runtime_wheels(bundle, python_version, wheels, declared)
            _validate_target_rows(python_version, platforms, wheels)
        if set(names) != declared:
            raise SystemExit("runtime wheelhouse member inventory drifted")
    return RuntimeWheelhouse(archive=archive, manifest=manifest)


def extract_runtime_wheelhouse(
    archive_path: Path,
    destination: Path,
    *,
    python_version: str | None = None,
) -> RuntimeWheelhouse:
    """Validate then extract one ready runtime's wheel bytes into a directory."""
    wheelhouse = load_runtime_wheelhouse(archive_path, expected_python=python_version)
    runtimes = wheelhouse.manifest["runtimes"]
    ready = [name for name, value in runtimes.items() if isinstance(value, dict) and value.get("status") == "ready"]
    if python_version is None:
        if len(ready) != 1:
            raise SystemExit("runtime-specific wheelhouse extraction requires --python-version")
        selected_runtime = ready[0]
    else:
        selected_runtime = _canonical_python_minor(python_version)
    runtime = runtimes.get(selected_runtime)
    if not isinstance(runtime, dict) or runtime.get("status") != "ready":
        raise SystemExit(f"runtime wheelhouse has no ready entry for Python {selected_runtime}")
    target = destination.resolve()
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    wheels = runtime["wheels"]
    with zipfile.ZipFile(wheelhouse.archive) as bundle:
        for filename in sorted(wheels):
            (target / filename).write_bytes(bundle.read(f"{WHEELHOUSE_PREFIX}{selected_runtime}/{filename}"))
        (target / WHEELHOUSE_MANIFEST).write_text(
            json.dumps(wheelhouse.manifest, indent=2, sort_keys=True) + "\n",
            encoding=_UTF_8,
            newline="\n",
        )
    return wheelhouse
