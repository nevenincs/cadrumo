"""Build deterministic sealed runtime dependency archives from the tested lock."""

from __future__ import annotations

import json
import tempfile
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from dev._paths import prepare_temporary_directory

from .hashing import sha256_path
from .runtime_wheel_acquisition import _acquire_all, prune_wheel_cache, wheel_cache_dir
from .runtime_wheel_selection import plan_runtime_wheelhouses
from .runtime_wheelhouse_contract import (
    PLATFORM_FLOORS,
    WHEELHOUSE_MANIFEST,
    WHEELHOUSE_PREFIX,
    WHEELHOUSE_SCHEMA,
    RuntimeWheelhouse,
    RuntimeWheelhousePlan,
)
from .runtime_wheelhouse_reader import load_runtime_wheelhouse

_UTF_8 = "utf-8"
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _manifest_document(
    repo_root: Path,
    *,
    python_versions: Sequence[str] | None = None,
) -> tuple[dict[str, Any], tuple[RuntimeWheelhousePlan, ...]]:
    plans_by_runtime = plan_runtime_wheelhouses(repo_root, python_versions=python_versions)
    entries: dict[str, dict[str, Any]] = {}
    ready_plans: list[RuntimeWheelhousePlan] = []
    for python_version, plan in sorted(plans_by_runtime.items()):
        if plan.missing:
            entries[python_version] = {
                "missing": list(plan.missing),
                "python": python_version,
                "status": "missing-wheel",
            }
            continue
        ready_plans.append(plan)
        entries[python_version] = {
            "platforms": plan.platforms,
            "python": python_version,
            "status": "ready",
            "wheels": {
                wheel.filename: {
                    "distribution": wheel.distribution,
                    "sha256": wheel.sha256,
                    "size": wheel.size,
                    "version": wheel.version,
                }
                for wheel in plan.wheels
            },
        }
    return (
        {
            "lock_sha256": sha256_path(repo_root / "uv.lock"),
            "platform_floors": PLATFORM_FLOORS,
            "runtimes": entries,
            "schema": WHEELHOUSE_SCHEMA,
        },
        tuple(ready_plans),
    )


def build_runtime_wheelhouse(
    repo_root: Path,
    destination: Path,
    *,
    python_versions: Sequence[str] | None = None,
) -> RuntimeWheelhouse:
    """Download lock-selected wheels and write one deterministic multi-runtime archive."""
    root = repo_root.resolve(strict=True)
    output = destination.resolve()
    if output.exists():
        raise FileExistsError(output)
    manifest, plans = _manifest_document(root, python_versions=python_versions)
    output.parent.mkdir(parents=True, exist_ok=True)
    cache = wheel_cache_dir()
    with tempfile.TemporaryDirectory(
        prefix="cadrumo-runtime-wheelhouse-", dir=prepare_temporary_directory()
    ) as temporary:
        wheel_dir = Path(temporary)
        for plan in plans:
            (wheel_dir / plan.python_version).mkdir()
        _acquire_all(plans, wheel_dir, cache)
        prune_wheel_cache(cache)
        with zipfile.ZipFile(output, mode="x", compression=zipfile.ZIP_STORED) as archive:
            manifest_info = zipfile.ZipInfo(WHEELHOUSE_MANIFEST, date_time=_ZIP_TIMESTAMP)
            manifest_info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(
                manifest_info,
                json.dumps(manifest, indent=2, sort_keys=True).encode(_UTF_8) + b"\n",
            )
            for plan in plans:
                for wheel in plan.wheels:
                    info = zipfile.ZipInfo(
                        f"{WHEELHOUSE_PREFIX}{plan.python_version}/{wheel.filename}",
                        date_time=_ZIP_TIMESTAMP,
                    )
                    info.external_attr = (0o100644 & 0xFFFF) << 16
                    archive.writestr(info, (wheel_dir / plan.python_version / wheel.filename).read_bytes())
    return load_runtime_wheelhouse(output, expected_lock_sha256=manifest["lock_sha256"])
