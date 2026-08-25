"""Content-addressed proof memoization for packaging campaign lanes.

Operator directive (2026-07-20): installability and tests are ascertained
ONCE — repeated work is done once and reused. The wheel cohort is a pure
function of the committed wheel-relevant sources, so an installability proof
is addressed by ``(proof kind, source fingerprint, environment fingerprint)``:

- the **source fingerprint** hashes the committed git object listing of the
  wheel-relevant paths (``src``, ``packaging``, ``pyproject.toml``,
  ``uv.lock``). Uncommitted drift in that scope yields NO fingerprint — a
  dirty tree has no stable identity, so it is never cached against and never
  served from cache;
- the **environment fingerprint** covers what changes install behavior on a
  runner: OS, architecture, OS release, the exact CPython version, and the
  exact uv version. A toolchain bump invalidates every cached proof by
  construction — that is the whole invalidation policy; there is no TTL.

A carried proof is honest bookkeeping, not silent re-stamping: the stored
record carries its origin (commit, CI run id and attempt, timestamp), and the
campaign driver prints that provenance when it reuses one. Records live in a
runner-local store (``CADRUMO_PROOF_CACHE_DIR`` or ``~/.cadrumo/proof-cache``)
that never leaves the machine and is not evidence: the full campaign's
promotable ``DistributionEvidence`` rows are always minted fresh from real
runs — this cache only lets the per-push quick profile answer "this exact
byte-identity was already proven on this exact toolchain" in seconds.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, ValidationError

from cadrumo.core import iter_directory

from .._paths import UTF_8

_UTF_8: Final[str] = UTF_8
_CACHE_DIR_ENV: Final[str] = "CADRUMO_PROOF_CACHE_DIR"
_MAX_RECORDS_ENV: Final[str] = "CADRUMO_PROOF_CACHE_MAX_RECORDS"
# Hard cap on stored records (operator directive: every persistent cache is
# bounded). Records are ~0.5 KiB, so the default cap keeps the store under a
# megabyte; eviction is oldest-first by modification time. The store also
# tolerates EXTERNAL pruning (the fleet's job-completed cleanup hooks): a
# pruned or truncated record is simply a cache miss, never an error.
_DEFAULT_MAX_RECORDS: Final[int] = 512
_SCHEMA: Final[str] = "cadrumo.packaging.proof-record.v1"
# The committed inputs a proof is a function of: everything the wheel cohort
# is built from, PLUS the prober itself (`dev/packaging` carries the smoke
# modules, the cohort builder, the campaign driver, and this cache) — a
# strengthened probe must invalidate every carried proof, or a proof minted
# by the weaker prober would keep satisfying pushes the new probe would fail.
# Anything outside this scope (docs, vault, workflows, other dev tooling)
# cannot change the cohort bytes or the probe, so it never invalidates.
PROOF_SCOPE_PATHS: Final[tuple[str, ...]] = (
    "src",
    "packaging",
    "dev/packaging",
    "pyproject.toml",
    "uv.lock",
)


class ProofOrigin(BaseModel):
    """Where a proof was minted, for honest carried-proof provenance."""

    model_config = ConfigDict(extra="forbid")

    commit: str
    run_id: str | None = None
    run_attempt: str | None = None


class ProofRecord(BaseModel):
    """One memoized proof: a key's evidence that its work already ran green."""

    model_config = ConfigDict(extra="forbid")

    schema_id: str = _SCHEMA
    proof_kind: str
    source_fingerprint: str
    environment_fingerprint: str
    created_at: str
    origin: ProofOrigin


def _git_output(repo_root: Path, *args: str) -> str:
    result = subprocess.run(  # noqa: S603 - fixed git argv over the repo root
        ["git", *args],  # noqa: S607 - git resolved from PATH like every dev gate
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def source_fingerprint(repo_root: Path) -> str | None:
    """Return the committed-scope fingerprint, or ``None`` when the scope is dirty."""
    drift = _git_output(repo_root, "status", "--porcelain", "--", *PROOF_SCOPE_PATHS)
    if drift.strip():
        return None
    listing = _git_output(repo_root, "ls-files", "-s", "--", *PROOF_SCOPE_PATHS)
    return hashlib.sha256(listing.encode(_UTF_8)).hexdigest()


def environment_fingerprint() -> str:
    """Fingerprint the install-relevant toolchain of this runner.

    Known uncovered axis: the build backend's RESOLVED version. ``pyproject.toml``
    pins which backend is required and is covered by the source fingerprint, but
    ``hatchling`` is fetched into an isolated build environment at build time and
    appears in neither this environment's installed metadata nor ``uv.lock``, so
    its resolved version cannot be read here without performing a resolve. A
    backend release can therefore change wheel contents while every fingerprinted
    input stays identical, and a quick proof would carry across it. The window is
    bounded: only the quick profile memoizes, and no promotable evidence row does.
    """
    uv = shutil.which("uv")
    uv_version = "uv-absent"
    if uv is not None:
        uv_version = subprocess.run(  # noqa: S603 - fixed argv on the resolved uv
            [uv, "--version"], capture_output=True, text=True, check=True
        ).stdout.strip()
    parts = (
        platform.system(),
        platform.machine(),
        platform.release(),
        platform.python_version(),
        uv_version,
    )
    return hashlib.sha256("|".join(parts).encode(_UTF_8)).hexdigest()[:16]


def default_cache_dir() -> Path:
    """Resolve the runner-local proof store."""
    override = os.environ.get(_CACHE_DIR_ENV)
    if override:
        return Path(override)
    return Path.home() / ".cadrumo" / "proof-cache"


def _record_path(cache_dir: Path, proof_kind: str, source_fp: str, env_fp: str) -> Path:
    return cache_dir / f"{proof_kind}-{source_fp[:24]}-{env_fp}.json"


def lookup(cache_dir: Path, proof_kind: str, source_fp: str, env_fp: str) -> ProofRecord | None:
    """Return the stored proof for the key, or ``None`` (corrupt records are ignored)."""
    path = _record_path(cache_dir, proof_kind, source_fp, env_fp)
    if not path.is_file():
        return None
    try:
        record = ProofRecord.model_validate_json(path.read_text(encoding=_UTF_8))
    except (ValidationError, ValueError, OSError):
        return None
    matches = (
        record.proof_kind == proof_kind
        and record.source_fingerprint == source_fp
        and record.environment_fingerprint == env_fp
    )
    return record if matches else None


def record(
    cache_dir: Path,
    proof_kind: str,
    source_fp: str,
    env_fp: str,
    repo_root: Path,
    max_records: int | None = None,
) -> Path:
    """Persist a fresh proof record for the key and return its path."""
    commit = _git_output(repo_root, "rev-parse", "HEAD").strip()
    proof = ProofRecord(
        proof_kind=proof_kind,
        source_fingerprint=source_fp,
        environment_fingerprint=env_fp,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        origin=ProofOrigin(
            commit=commit,
            run_id=os.environ.get("GITHUB_RUN_ID"),
            run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT"),
        ),
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _record_path(cache_dir, proof_kind, source_fp, env_fp)
    path.write_text(proof.model_dump_json(indent=2), encoding=_UTF_8, newline="\n")
    _evict_beyond_cap(cache_dir, keep=path, cap=max_records if max_records is not None else _max_records())
    return path


def _max_records() -> int:
    override = os.environ.get(_MAX_RECORDS_ENV)
    if override:
        return max(1, int(override))
    return _DEFAULT_MAX_RECORDS


def _evict_beyond_cap(cache_dir: Path, keep: Path, cap: int) -> None:
    """Delete oldest records beyond the size cap; the fresh record survives."""
    records = sorted(iter_directory(cache_dir, pattern="*.json"), key=lambda p: p.stat().st_mtime)
    excess = len(records) - cap
    for stale in records:
        if excess <= 0:
            break
        if stale == keep:
            continue
        try:
            stale.unlink()
        except OSError:
            continue
        excess -= 1
