"""Real-behavior gates for the content-addressed proof cache."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.directory_scan import iter_directory

from ..._paths import UTF_8
from ..proof_cache import (
    PROOF_SCOPE_PATHS,
    environment_fingerprint,
    lookup,
    record,
    source_fingerprint,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_UTF_8: Final[str] = UTF_8


def _git(repo: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603 - fixed git argv over an in-test temp repo
        ["git", *args],  # noqa: S607 - git resolved from PATH like every dev gate
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def scoped_repo(tmp_path: Path) -> Path:
    """A real git repo carrying one committed file in the proof scope."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "dev" / "packaging").mkdir(parents=True)
    (repo / "src" / "module.py").write_text("VALUE = 1\n", encoding=_UTF_8)
    (repo / "dev" / "packaging" / "smoke_probe.py").write_text("PROBE = 1\n", encoding=_UTF_8)
    (repo / "pyproject.toml").write_text('[project]\nname = "sample"\n', encoding=_UTF_8)
    _git(repo, "init", "--quiet")
    _git(repo, "-c", "user.email=proof@test", "-c", "user.name=proof", "add", "--", "src", "dev", "pyproject.toml")
    _git(repo, "-c", "user.email=proof@test", "-c", "user.name=proof", "commit", "--quiet", "-m", "seed")
    return repo


def test_fingerprint_tracks_committed_scope_content(scoped_repo: Path) -> None:
    """Clean scope fingerprints deterministically; a scope commit changes it."""
    first = source_fingerprint(scoped_repo)
    assert first is not None
    assert source_fingerprint(scoped_repo) == first

    (scoped_repo / "src" / "module.py").write_text("VALUE = 2\n", encoding=_UTF_8)
    # Uncommitted drift in scope: no stable identity, no fingerprint.
    assert source_fingerprint(scoped_repo) is None

    _git(scoped_repo, "-c", "user.email=proof@test", "-c", "user.name=proof", "add", "--", "src")
    _git(scoped_repo, "-c", "user.email=proof@test", "-c", "user.name=proof", "commit", "--quiet", "-m", "bump")
    second = source_fingerprint(scoped_repo)
    assert second is not None
    assert second != first


def test_strengthened_prober_invalidates_carried_proofs(scoped_repo: Path) -> None:
    """A committed probe change under dev/packaging changes the fingerprint.

    A proof minted by a weaker prober must never keep satisfying pushes the
    strengthened probe would fail, so the prober is part of the proof scope.
    """
    before = source_fingerprint(scoped_repo)
    assert before is not None
    (scoped_repo / "dev" / "packaging" / "smoke_probe.py").write_text("PROBE = 2\n", encoding=_UTF_8)
    assert source_fingerprint(scoped_repo) is None
    _git(scoped_repo, "-c", "user.email=proof@test", "-c", "user.name=proof", "add", "--", "dev")
    _git(scoped_repo, "-c", "user.email=proof@test", "-c", "user.name=proof", "commit", "--quiet", "-m", "probe")
    after = source_fingerprint(scoped_repo)
    assert after is not None
    assert after != before


def test_out_of_scope_drift_keeps_the_fingerprint(scoped_repo: Path) -> None:
    """Docs/vault-style drift outside the wheel scope never invalidates a proof."""
    baseline = source_fingerprint(scoped_repo)
    (scoped_repo / "NOTES.md").write_text("out of scope\n", encoding=_UTF_8)
    assert source_fingerprint(scoped_repo) == baseline
    assert {"src", "packaging", "dev/packaging", "pyproject.toml", "uv.lock"} <= set(PROOF_SCOPE_PATHS)


def test_record_then_lookup_roundtrip_with_provenance(scoped_repo: Path, tmp_path: Path) -> None:
    """A recorded proof is served back for its exact key with its origin intact."""
    cache = tmp_path / "cache"
    source_fp = source_fingerprint(scoped_repo)
    assert source_fp is not None
    env_fp = environment_fingerprint()

    assert lookup(cache, "quick-core-install", source_fp, env_fp) is None
    path = record(cache, "quick-core-install", source_fp, env_fp, scoped_repo)
    assert path.is_file()

    carried = lookup(cache, "quick-core-install", source_fp, env_fp)
    assert carried is not None
    assert carried.source_fingerprint == source_fp
    assert carried.environment_fingerprint == env_fp
    assert len(carried.origin.commit) == 40

    # A different source identity, kind, or environment is a miss, never a
    # cross-served proof.
    assert lookup(cache, "quick-core-install", "0" * 64, env_fp) is None
    assert lookup(cache, "other-kind", source_fp, env_fp) is None
    assert lookup(cache, "quick-core-install", source_fp, "deadbeefdeadbeef") is None


def test_store_is_bounded_with_oldest_first_eviction(scoped_repo: Path, tmp_path: Path) -> None:
    """The cap holds and eviction drops the oldest records, never the fresh one."""
    cache = tmp_path / "cache"
    source_fp = source_fingerprint(scoped_repo)
    assert source_fp is not None
    env_fp = environment_fingerprint()
    paths = []
    for index in range(5):
        path = record(cache, f"kind-{index}", source_fp, env_fp, scoped_repo, max_records=3)
        # Deterministic ascending ages: same-millisecond writes would otherwise
        # tie on st_mtime and make the oldest-first order platform-dependent.
        os.utime(path, (1_000_000 + index, 1_000_000 + index))
        paths.append(path)
    survivors = sorted(p.name for p in iter_directory(cache, pattern="*.json"))
    assert len(survivors) == 3
    assert paths[-1].name in survivors
    assert paths[0].name not in survivors and paths[1].name not in survivors


def test_externally_pruned_record_is_a_plain_miss(scoped_repo: Path, tmp_path: Path) -> None:
    """Fleet cleanup hooks may delete records at any time; that is a miss, not an error."""
    cache = tmp_path / "cache"
    source_fp = source_fingerprint(scoped_repo)
    assert source_fp is not None
    env_fp = environment_fingerprint()
    path = record(cache, "quick-core-install", source_fp, env_fp, scoped_repo)
    path.unlink()
    assert lookup(cache, "quick-core-install", source_fp, env_fp) is None


def test_corrupt_record_is_a_miss_not_a_crash(scoped_repo: Path, tmp_path: Path) -> None:
    """A tampered or truncated record never serves a carried proof."""
    cache = tmp_path / "cache"
    source_fp = source_fingerprint(scoped_repo)
    assert source_fp is not None
    env_fp = environment_fingerprint()
    path = record(cache, "quick-core-install", source_fp, env_fp, scoped_repo)
    path.write_text("{not json", encoding=_UTF_8)
    assert lookup(cache, "quick-core-install", source_fp, env_fp) is None
