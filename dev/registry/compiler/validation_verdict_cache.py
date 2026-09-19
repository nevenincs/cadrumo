"""Cross-process record of registry validations that found nothing.

Validation is the compile's dominant cost once loading is served from the
compiled-tree cache. Its outcome is a pure function of the registry tree, the
source evidence, the profile schema and the compiler code, so a clean verdict
is recorded under a key folding all four and served to any later process
observing the same inputs: the whole registry when nothing changed, and each
unchanged modelo when only some modelos changed.

Only the package-bundled registry tree is recorded, on the same premise as the
compiled-tree cache: a mutable or synthetic tree is validated afresh in every
process. A failed validation is never recorded, so a defect is re-detected
until its inputs change. Processes that start together on the same inputs
serialise their first validation through a per-key lock file, so one of them
validates and the others take its verdict. Waiting for that verdict is bounded:
a lock stamped by a dead process is reclaimed at once, a peer that outlasts the
wait ceiling is left to it, and locks stranded under keys nothing asks for again
are swept. The store follows the development
cache convention:
an explicit ``CADRUMO_REGISTRY_VERDICT_CACHE_DIR`` wins, otherwise the
checkout's own ``.cache`` holds it, outside the application's storage root.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Final

from cadrumo.core.atomic_write import atomic_write_best_effort_text
from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.lockfile_unlink import LOCKFILE_UNLINK_RETRY_SECONDS, unlink_lockfile
from cadrumo.core.pid_liveness import pid_is_alive
from cadrumo.core.type_guards import is_str_keyed_dict
from dev.cache_root import dev_cache_dir

VERDICT_CACHE_DIR_ENV: Final = "CADRUMO_REGISTRY_VERDICT_CACHE_DIR"
_SCHEMA: Final = "registry-validation-verdict/v1"
#: No validation runs this long; an older lock is abandoned whoever stamped it.
_LOCK_STALE_SECONDS: Final = 900.0
#: Waiting longer than this for a peer costs more than validating again.
_LOCK_WAIT_CEILING_SECONDS: Final = 300.0
_LOCK_POLL_SECONDS: Final = 0.25
_LOGGER = logging.getLogger(__name__)
_swept_lock_stores: Final[set[Path]] = set()

type FingerprintRows = tuple[tuple[str, int, int, str], ...]


def verdict_cache_dir() -> Path:
    """Resolve the runner-local validation verdict directory."""
    override = os.environ.get(VERDICT_CACHE_DIR_ENV)
    if override:
        return Path(override)
    return dev_cache_dir("registry-validation-verdicts")


@dataclass(frozen=True, slots=True)
class ValidationVerdictScope:
    """The verdict keys one compilation may consult and record.

    ``registry_key`` covers the whole tree; ``modelo_keys`` maps a modelo id to
    the key covering that modelo together with everything outside the
    ``modelos`` directory. A stamped identity carries no per-file rows, so its
    scope has a registry key only.
    """

    registry_key: str
    modelo_keys: Mapping[str, str]

    def modelo_key(self, modelo_id: str) -> str | None:
        """Return the per-modelo key, or ``None`` when the modelo is not individually keyed."""
        return self.modelo_keys.get(modelo_id)


def _relative_to_modelos_root(path: Path, modelos_root: Path) -> Path:
    """Locate one fingerprint row under the resolved ``modelos`` root.

    Rows are recorded as absolute paths below the already-resolved registry
    root, so the lexical test answers almost every row without touching the
    filesystem; only a row that fails it pays for a real-path resolution.
    """
    try:
        return path.relative_to(modelos_root)
    except ValueError:
        return path.resolve().relative_to(modelos_root)


def _content_row(row: tuple[str, int, int, str], candidate: Path, registry_root: Path) -> tuple[str, int, str]:
    """Reduce one fingerprint row to what decides a validation outcome.

    A verdict is a statement about CONTENT: the same declarations validate the
    same way wherever they sit and whenever they were written. The row is
    therefore keyed by its path relative to the registry root, its size and its
    content digest, with the modification time dropped. Keyed on the absolute
    path and mtime instead, a staged candidate -- a copy of these bytes under a
    temporary root, with fresh mtimes -- shared no verdict with the tree it was
    copied from, so every candidate re-validated the whole corpus.
    """
    _path, size, _modified_ns, digest = row
    try:
        relative = candidate.relative_to(registry_root)
    except ValueError:
        try:
            relative = candidate.resolve().relative_to(registry_root)
        except (OSError, ValueError):
            # Outside the registry root: keep the absolute spelling, which is
            # stable for a shared corpus root and still content-checked.
            return candidate.as_posix(), size, digest
    return relative.as_posix(), size, digest


@lru_cache(maxsize=16)
def validation_verdict_scope(
    *,
    registry_root: Path,
    fingerprints: FingerprintRows,
    source_receipt: str,
    compiler_identity_digest: str,
) -> ValidationVerdictScope:
    """Derive the verdict keys for one compilation from the inputs that decide its outcome.

    Memoized on its whole argument tuple, which is legitimate because every
    argument is an immutable value and the result is derived from nothing else:
    no filesystem read decides a key, only the fingerprint rows already collected
    by the caller. A repeat call therefore cannot observe a tree the first call
    could not, and the rows change whenever the tree does.

    The memo is what makes a warm compile warm. Deriving this scope over the
    bundled corpus costs ~0.22 s -- 2,990 rows, each paying two
    ``Path.relative_to`` walks -- and it was paid again on EVERY
    :func:`compile_validated_authority` call, including the cache hits, where it
    was about 70% of the whole hit. With 415 call sites across 194 test modules,
    that recomputation was the dominant cost of an already-compiled registry.
    """
    registry_root_resolved = registry_root.resolve()
    modelos_root = (registry_root / "modelos").resolve()
    shared_rows: list[tuple[str, int, str]] = []
    modelo_rows: dict[str, list[tuple[str, int, str]]] = {}
    for row in fingerprints:
        path = Path(row[0])
        keyed = _content_row(row, path, registry_root_resolved)
        try:
            relative = _relative_to_modelos_root(path, modelos_root)
        except (OSError, ValueError):
            shared_rows.append(keyed)
            continue
        if not relative.parts:
            shared_rows.append(keyed)
            continue
        member = relative.parts[0]
        modelo_rows.setdefault(member.removesuffix(".toml"), []).append(keyed)
    shared_digest = content_hash_hex(sorted([list(row) for row in shared_rows]))
    registry_key = content_hash_hex(
        {
            "schema": _SCHEMA,
            "subject": "registry",
            "tree_rows_digest": content_hash_hex(
                sorted([list(row) for row in (*shared_rows, *(r for rows in modelo_rows.values() for r in rows))])
            ),
            "source_receipt": source_receipt,
            "compiler_identity_digest": compiler_identity_digest,
        }
    )
    modelo_keys = {
        modelo_id: content_hash_hex(
            {
                "schema": _SCHEMA,
                "subject": "modelo",
                "modelo_id": modelo_id,
                "modelo_rows": sorted([list(row) for row in rows]),
                "shared_rows_digest": shared_digest,
                "source_receipt": source_receipt,
                "compiler_identity_digest": compiler_identity_digest,
            }
        )
        for modelo_id, rows in modelo_rows.items()
    }
    # Read-only, because the memo above hands the SAME instance to every caller:
    # a mutable mapping shared that way lets one consumer rewrite another's keys.
    return ValidationVerdictScope(registry_key=registry_key, modelo_keys=MappingProxyType(modelo_keys))


def _verdict_path(key: str) -> Path:
    return verdict_cache_dir() / f"verdict_{key}.json"


def is_validated(key: str) -> bool:
    """Whether a clean validation was recorded under ``key``."""
    path = _verdict_path(key)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return False
    except ValueError:
        _LOGGER.warning("Ignoring unreadable validation verdict at %s", path)
        return False
    return is_str_keyed_dict(payload) and payload.get("schema") == _SCHEMA and payload.get("key") == key


def record_validated(key: str, *, subject: str) -> None:
    """Record that validation under ``key`` found nothing; a failed write only costs a re-validation."""
    path = _verdict_path(key)
    payload = {
        "schema": _SCHEMA,
        "key": key,
        "subject": subject,
        "validated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_best_effort_text(path, json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        _LOGGER.warning("Could not record validation verdict at %s", path, exc_info=True)


def _lock_holder(path: Path) -> int | None:
    """Return the pid stamped in ``path``, or ``None`` when it cannot be read."""
    try:
        raw = path.read_bytes().decode("ascii").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return int(raw) if raw.isdigit() else None


def _drop_lock(path: Path, *, reason: str, retry_seconds: float = 0.0) -> bool:
    """Remove a lock file, reporting rather than raising when the removal fails.

    No removal here is load-bearing for correctness: a lock that survives is
    re-examined by the next acquirer, and the cache is an optimisation whose
    failures must never surface as a compile error.
    """
    try:
        return unlink_lockfile(path, retry_seconds=retry_seconds, reason=reason)
    except OSError:
        _LOGGER.warning("Could not remove the validation lock at %s", path, exc_info=True)
        return False


def _abandoned(path: Path) -> bool:
    """Whether ``path`` was left behind by a holder that will never release it.

    Two independent tests, because either alone leaves a class of lock
    immortal. A stamp naming a dead process is abandoned at once, rather than
    blocking every later process for the staleness window. Age still condemns a
    lock whose stamp reads as alive: pids are recycled, and a lock stamped with
    a pid some unrelated process now carries would otherwise never be broken --
    one on this checkout had survived 37 hours that way. No validation runs for
    the staleness window, so an older lock is abandoned whoever holds it.
    """
    holder = _lock_holder(path)
    if holder is not None and pid_is_alive(holder):
        return _older_than_stale(path)
    if holder is None:
        return _older_than_stale(path)
    # Re-read before reporting a dead stamp abandoned: a peer that reclaimed
    # this same lock and stamped its own live pid in between must not lose it.
    return _lock_holder(path) == holder


def _older_than_stale(path: Path) -> bool:
    """Whether ``path`` has outlived any validation that could still be running."""
    try:
        return time.time() - path.stat().st_mtime > _LOCK_STALE_SECONDS
    except OSError:
        return False


def _sweep_abandoned_locks() -> None:
    """Remove every lock in the store whose holder is gone.

    A verdict key folds the tree, the sources and the compiler, so a lock
    stranded by a crashed or killed process is keyed to inputs no later process
    asks for again: nothing revisits it, and it accumulates. The sweep is what
    collects those, once per process, since the acquire path only ever sees the
    one key it wants.
    """
    store = verdict_cache_dir()
    if store in _swept_lock_stores:
        return
    _swept_lock_stores.add(store)
    try:
        locks = tuple(store.glob("verdict_*.lock"))
    except OSError:
        return
    for lock in locks:
        if _abandoned(lock):
            _LOGGER.debug("Sweeping abandoned validation lock at %s", lock)
            _drop_lock(lock, reason="verdict_lock_sweep")


def _acquire_lock_file(path: Path, *, key: str, wait_seconds: float) -> bool:
    """Create ``path`` exclusively, waiting out a live holder; ``False`` when no lock is held.

    The wait is bounded in both directions. A holder that died is reclaimed at
    once rather than after the staleness window, and a waiter gives up at
    ``_LOCK_WAIT_CEILING_SECONDS`` instead of queueing behind an unbroken
    succession of peers: on a busy checkout the lock rotates continuously, and
    an unbounded wait turns an optimisation into a hang. Giving up costs one
    duplicate validation. A verdict that lands while waiting ends the wait
    immediately, because the verdict is the whole reason to wait.
    """
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if is_validated(key):
                return False
            if _abandoned(path):
                _LOGGER.warning("Breaking abandoned validation lock at %s", path)
                if not _drop_lock(path, reason="verdict_lock_reclaim"):
                    time.sleep(_LOCK_POLL_SECONDS)
                continue
            if time.monotonic() >= deadline:
                _LOGGER.warning(
                    "Validating without the lock at %s; a peer held it for over %.0fs",
                    path,
                    wait_seconds,
                )
                return False
            time.sleep(_LOCK_POLL_SECONDS)
        except PermissionError:
            # Windows refuses the create while a peer's read handle or pending
            # delete is open; both clear on their own, so keep polling.
            if time.monotonic() >= deadline:
                return False
            time.sleep(_LOCK_POLL_SECONDS)
        except OSError:
            return False
        else:
            try:
                os.write(handle, str(os.getpid()).encode("ascii"))
            finally:
                os.close(handle)
            return True


@contextmanager
def verdict_validation_lock(key: str, *, wait_seconds: float = _LOCK_WAIT_CEILING_SECONDS) -> Iterator[None]:
    """Hold the cross-process lock for the first validation under ``key``.

    A caller checks :func:`is_validated` inside the lock, so a process that
    waited behind the validating one sees its verdict instead of validating
    again. An unusable cache directory, or a wait that outlasts
    ``wait_seconds``, degrades to no lock: the only cost is a duplicate
    validation, never a skipped one.
    """
    path = verdict_cache_dir() / f"verdict_{key}.lock"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        acquired = False
    else:
        _sweep_abandoned_locks()
        acquired = _acquire_lock_file(path, key=key, wait_seconds=wait_seconds)
    try:
        yield
    finally:
        if acquired:
            _release_lock_file(path)


def _release_lock_file(path: Path) -> None:
    """Drop a lock this process stamped, waiting out a waiter's open read handle.

    Releasing a lock stamped by somebody else would admit a second validator;
    failing to release one stamped by this live process would strand it, since
    no peer reclaims a lock whose holder is alive.
    """
    if _lock_holder(path) not in (os.getpid(), None):
        return
    if not _drop_lock(path, reason="verdict_lock_release", retry_seconds=LOCKFILE_UNLINK_RETRY_SECONDS):
        _LOGGER.warning("Could not release the validation lock at %s", path)


__all__ = [
    "VERDICT_CACHE_DIR_ENV",
    "ValidationVerdictScope",
    "is_validated",
    "record_validated",
    "validation_verdict_scope",
    "verdict_cache_dir",
    "verdict_validation_lock",
]
