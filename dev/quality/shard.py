"""Deterministic file-level sharding for the CI unit suite (pytest plugin).

Loaded with ``pytest -p dev.quality.shard --num-shards N --shard-index I``.
Every test module is assigned to exactly one shard by a stable CRC-32 of its
repo-relative POSIX path, so the N shards partition the suite: their union is
the whole suite and their intersection is empty, independent of platform,
ordering, or timing. Sharding happens at collection-ignore time (not by argv
file lists) because the suite's ~1900 test-file paths exceed the Windows
process argument limit.

This is a scheduling device only: it never deselects a test — a test absent
from one shard is, by construction, present in exactly one sibling shard of
the same run. With ``--num-shards 1`` (the default) the plugin is inert.
"""

from __future__ import annotations

import zlib
from pathlib import Path
from typing import Final

import pytest

from .._paths import UTF_8

_UTF_8: Final[str] = UTF_8


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the shard-selection options."""
    group = parser.getgroup("shard", "deterministic unit-suite sharding")
    group.addoption("--num-shards", type=int, default=1, help="total shard count (1 disables sharding)")
    group.addoption("--shard-index", type=int, default=0, help="zero-based index of this shard")


def shard_of(relative_posix_path: str, num_shards: int) -> int:
    """Return the shard index owning ``relative_posix_path``."""
    return zlib.crc32(relative_posix_path.encode(_UTF_8)) % num_shards


@pytest.hookimpl
def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    """Ignore test modules owned by a different shard."""
    num_shards = config.getoption("--num-shards")
    if num_shards <= 1:
        return None
    shard_index = config.getoption("--shard-index")
    if not 0 <= shard_index < num_shards:
        raise pytest.UsageError(f"--shard-index {shard_index} outside 0..{num_shards - 1}")
    if collection_path.is_dir() or not collection_path.name.startswith("test_") or collection_path.suffix != ".py":
        return None
    try:
        relative = collection_path.resolve().relative_to(Path(str(config.rootpath)).resolve())
    except ValueError:
        # Outside the rootdir there is no stable cross-runner key (absolute
        # paths differ per checkout), so such a file collects in EVERY shard:
        # duplicated work is acceptable, a silently-lost test is not.
        return None
    if shard_of(relative.as_posix(), num_shards) != shard_index:
        return True
    return None
