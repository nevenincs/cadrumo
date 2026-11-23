"""Build deterministic sealed runtime dependency archives from the tested lock."""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dev.paths import REPO_ROOT
from dev.temporary_output import prepare_temp_root

from .hashing import sha256_path
from .runtime_wheel_acquisition import (
    acquire_all,
    cache_holds,
    grouped_wheel_requests,
    prune_wheel_cache,
    wheel_cache_dir,
)
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


def _acquire_plans(plans: Sequence[RuntimeWheelhousePlan], wheel_dir: Path, cache: Path | None) -> int:
    """Place every plan's lock-pinned wheels under ``wheel_dir`` and bound the cache.

    Returns:
        How many distinct wheels the cache served without reaching the index.
    """
    for plan in plans:
        (wheel_dir / plan.python_version).mkdir()
    served_from_cache = acquire_all(plans, wheel_dir, cache)
    prune_wheel_cache(cache)
    return served_from_cache


@dataclass(frozen=True)
class WarmedWheelCache:
    """What one cache warm found and left: every distinct lock-pinned wheel, re-verified."""

    cache: Path
    runtimes: tuple[str, ...]
    wheels: int
    served_from_cache: int


def warm_runtime_wheel_cache(repo_root: Path) -> WarmedWheelCache:
    """Fill the runtime wheel cache with exactly the wheels a cohort build selects.

    The plans are the ones :func:`build_runtime_wheelhouse` acquires, from the
    same lock and runtime inventory, so a later cohort build -- including one
    under the test network guard -- is served from the cache without reaching
    the index. Every entry is re-hashed against the lock afterwards, because a
    cache store tolerates storage refusals silently and a warm that left a gap
    would only surface as a network refusal in the run that relied on it.
    """
    root = repo_root.resolve(strict=True)
    cache = wheel_cache_dir()
    _manifest, plans = _manifest_document(root)
    with tempfile.TemporaryDirectory(prefix="cadrumo-runtime-wheel-warm-", dir=prepare_temp_root()) as temporary:
        served_from_cache = _acquire_plans(plans, Path(temporary), cache)
    requests = grouped_wheel_requests(plans)
    absent = sorted(wheel.filename for wheel, _destinations in requests if not cache_holds(cache, wheel))
    if absent:
        raise SystemExit(f"runtime wheel cache does not hold the lock-recorded bytes of: {', '.join(absent)}")
    return WarmedWheelCache(
        cache=cache,
        runtimes=tuple(plan.python_version for plan in plans),
        wheels=len(requests),
        served_from_cache=served_from_cache,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Warm the runtime wheel cache from this checkout's lock."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("command", choices=("warm-cache",))
    parser.parse_args(argv)
    warmed = warm_runtime_wheel_cache(REPO_ROOT)
    print(
        f"runtime wheel cache: {warmed.wheels} distinct lock-pinned wheels for runtimes "
        f"{', '.join(warmed.runtimes)}; {warmed.served_from_cache} served from the cache, "
        f"{warmed.wheels - warmed.served_from_cache} downloaded; all {warmed.wheels} re-verified "
        f"against the uv.lock SHA-256 in {warmed.cache}"
    )
    return 0


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
    with tempfile.TemporaryDirectory(prefix="cadrumo-runtime-wheelhouse-", dir=prepare_temp_root()) as temporary:
        wheel_dir = Path(temporary)
        _acquire_plans(plans, wheel_dir, cache)
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


if __name__ == "__main__":
    raise SystemExit(main())
