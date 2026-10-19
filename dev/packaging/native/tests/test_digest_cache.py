"""The shared digest cache answers only for files it could have seen change, across real processes."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ...command_execution import run_command
from ..hashing import CACHE_VARIABLE, SETTLED_NS, digest, digest_cache

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LONG_AGO = time.time_ns() - 3600 * 1_000_000_000


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _settled(path: Path, content: bytes, *, at: int = _LONG_AGO) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    os.utime(path, ns=(at, at))
    return path


def _entries(build: Path) -> dict[str, list[object]]:
    entries = json.loads((build / "cache" / "digests.json").read_text(encoding="utf-8"))["entries"]
    assert isinstance(entries, dict)
    return {str(name): list(entry) for name, entry in entries.items()}


def test_the_digest_is_the_files_sha256_with_or_without_the_cache(tmp_path: Path) -> None:
    source = _settled(tmp_path / "a.py", b"print('a')\n")
    assert digest(source) == _sha256(source)
    with digest_cache(tmp_path / "build"):
        assert digest(source) == _sha256(source)
        assert digest(source) == _sha256(source)
    assert digest(source) == _sha256(source)


def test_a_settled_unchanged_file_is_answered_from_the_cache(tmp_path: Path) -> None:
    build = tmp_path / "build"
    source = _settled(tmp_path / "a.py", b"first\n")
    with digest_cache(build):
        first = digest(source)
    assert os.path.normcase(os.path.abspath(source)) in _entries(build)
    # Only the cache can answer with the old digest: the bytes differ, but the
    # size, time and file identity the cache keys on were put back.
    with source.open("r+b") as stream:
        stream.write(b"FIRST\n")
    os.utime(source, ns=(_LONG_AGO, _LONG_AGO))
    with digest_cache(build):
        assert digest(source) == first
    assert digest(source) != first


def test_a_changed_file_is_hashed_again(tmp_path: Path) -> None:
    build = tmp_path / "build"
    source = _settled(tmp_path / "a.py", b"first\n")
    with digest_cache(build):
        first = digest(source)
    _settled(source, b"second, longer\n", at=_LONG_AGO + 1_000_000_000)
    with digest_cache(build):
        assert digest(source) == _sha256(source) != first


def test_a_file_written_within_the_clocks_reach_of_its_hashing_is_never_reused(tmp_path: Path) -> None:
    build = tmp_path / "build"
    source = tmp_path / "fresh.py"
    source.write_bytes(b"first\n")
    written = source.stat().st_mtime_ns
    with digest_cache(build):
        first = digest(source)
    # Rewritten within the same clock tick: the size, time and identity look unchanged.
    with source.open("r+b") as stream:
        stream.write(b"FIRST\n")
    os.utime(source, ns=(written, written))
    assert time.time_ns() - written < SETTLED_NS
    with digest_cache(build):
        assert digest(source) == _sha256(source) != first


_WORKER = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from dev.packaging.native.hashing import digest, digest_cache
build = Path(sys.argv[2])
with digest_cache(build):
    for name in sys.argv[3:]:
        digest(Path(name))
"""

_CHILD = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from dev.packaging.native.hashing import digest
for name in sys.argv[2:]:
    digest(Path(name))
"""


def test_concurrent_processes_keep_every_entry_the_others_recorded(tmp_path: Path) -> None:
    build = tmp_path / "build"
    groups = [
        [
            _settled(tmp_path / f"worker{index}" / f"file{member}.py", f"{index}:{member}\n".encode())
            for member in range(40)
        ]
        for index in range(6)
    ]
    # Real processes, all at once: each records its own files into the one cache file.
    with ThreadPoolExecutor(max_workers=len(groups)) as pool:
        results = list(
            pool.map(
                lambda group: run_command(
                    [sys.executable, "-c", _WORKER, str(REPO_ROOT), str(build), *map(str, group)],
                    cwd=tmp_path,
                    timeout_seconds=120,
                ),
                groups,
            )
        )
    assert [result.returncode for result in results] == [0] * len(groups)
    entries = _entries(build)
    for group in groups:
        for path in group:
            assert entries[os.path.normcase(os.path.abspath(path))][4] == _sha256(path)


def test_a_child_started_inside_the_cache_uses_and_extends_it(tmp_path: Path) -> None:
    build = tmp_path / "build"
    files = [_settled(tmp_path / f"child{member}.py", f"{member}\n".encode()) for member in range(5)]
    with digest_cache(build) as cache:
        assert os.environ[CACHE_VARIABLE] == str(cache)
        child = run_command(
            [sys.executable, "-c", _CHILD, str(REPO_ROOT), *map(str, files)], cwd=tmp_path, timeout_seconds=120
        )
        assert child.returncode == 0
    assert CACHE_VARIABLE not in os.environ
    entries = _entries(build)
    assert {os.path.normcase(os.path.abspath(path)) for path in files} <= set(entries)
