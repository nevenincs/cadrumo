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
validates and the others take its verdict. The store follows the development
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
from pathlib import Path
from typing import Final

from cadrumo.core.atomic_write import atomic_write_best_effort_text
from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.type_guards import is_str_keyed_dict
from dev.cache_root import dev_cache_dir

VERDICT_CACHE_DIR_ENV: Final = "CADRUMO_REGISTRY_VERDICT_CACHE_DIR"
_SCHEMA: Final = "registry-validation-verdict/v1"
#: A lock older than this belongs to a process that died mid-validation.
_LOCK_STALE_SECONDS: Final = 900.0
_LOCK_POLL_SECONDS: Final = 0.25
_LOGGER = logging.getLogger(__name__)

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


def validation_verdict_scope(
    *,
    registry_root: Path,
    registry_identity_digest: str,
    fingerprints: FingerprintRows,
    source_receipt: str,
    compiler_identity_digest: str,
) -> ValidationVerdictScope:
    """Derive the verdict keys for one compilation from the inputs that decide its outcome."""
    registry_key = content_hash_hex(
        {
            "schema": _SCHEMA,
            "subject": "registry",
            "registry_identity_digest": registry_identity_digest,
            "source_receipt": source_receipt,
            "compiler_identity_digest": compiler_identity_digest,
        }
    )
    modelos_root = (registry_root / "modelos").resolve()
    shared_rows: list[tuple[str, int, int, str]] = []
    modelo_rows: dict[str, list[tuple[str, int, int, str]]] = {}
    for row in fingerprints:
        path = Path(row[0])
        try:
            relative = _relative_to_modelos_root(path, modelos_root)
        except (OSError, ValueError):
            shared_rows.append(row)
            continue
        if not relative.parts:
            shared_rows.append(row)
            continue
        member = relative.parts[0]
        modelo_rows.setdefault(member.removesuffix(".toml"), []).append(row)
    shared_digest = content_hash_hex([list(row) for row in shared_rows])
    modelo_keys = {
        modelo_id: content_hash_hex(
            {
                "schema": _SCHEMA,
                "subject": "modelo",
                "modelo_id": modelo_id,
                "modelo_rows": [list(row) for row in rows],
                "shared_rows_digest": shared_digest,
                "source_receipt": source_receipt,
                "compiler_identity_digest": compiler_identity_digest,
            }
        )
        for modelo_id, rows in modelo_rows.items()
    }
    return ValidationVerdictScope(registry_key=registry_key, modelo_keys=modelo_keys)


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


def _acquire_lock_file(path: Path) -> bool:
    """Create ``path`` exclusively, waiting out a live holder; ``False`` when no lock is possible."""
    while True:
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = time.time() - path.stat().st_mtime
            except FileNotFoundError:
                continue
            except OSError:
                return False
            if age > _LOCK_STALE_SECONDS:
                _LOGGER.warning("Breaking stale validation lock at %s", path)
                path.unlink(missing_ok=True)
                continue
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
def verdict_validation_lock(key: str) -> Iterator[None]:
    """Hold the cross-process lock for the first validation under ``key``.

    A caller checks :func:`is_validated` inside the lock, so a process that
    waited behind the validating one sees its verdict instead of validating
    again. An unusable cache directory degrades to no lock: the only cost is a
    duplicate validation, never a skipped one.
    """
    path = verdict_cache_dir() / f"verdict_{key}.lock"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        acquired = False
    else:
        acquired = _acquire_lock_file(path)
    try:
        yield
    finally:
        if acquired:
            path.unlink(missing_ok=True)


__all__ = [
    "VERDICT_CACHE_DIR_ENV",
    "ValidationVerdictScope",
    "is_validated",
    "record_validated",
    "validation_verdict_scope",
    "verdict_cache_dir",
    "verdict_validation_lock",
]
