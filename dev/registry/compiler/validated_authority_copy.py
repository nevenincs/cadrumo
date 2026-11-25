"""Cross-process copy of the compiled, validated bundled registry authority.

A process that asked for the bundled authority compiled it afresh. The tree
load came from the compiled-tree pickle, but compiling facts, catalogues and
annual orders on top of it, and re-walking the loaded payload, cost about ten
seconds per process even when a clean validation was already on record. Every
test worker paid that once per invocation. This copy holds the finished
components under a key folding everything that decides them, so a later
process observing the same inputs reads them back instead of compiling.

Only the package-bundled registry tree compiled against the bundled evidence
root is copied, on the same premise as the compiled-tree cache: a mutable or
synthetic tree, which a run may edit under its own feet, compiles in every
process. A copy is published only while a clean validation is on record for
its exact inputs and is served only while that record still stands, so the
copy never stands in for a validation that did not happen.

The key folds the registry identity, the source receipt, the compiler source
tree digest, the validation key and the loader-code fingerprint. Modules the
compiling process had loaded from outside the hashed compiler trees are
recorded in the copy with their content digests and re-checked on every read,
so an edit to one of them refuses the copy. Because the key fixes the source of
every class the copy can hold, the stale-shape walk the tree pickle runs on
every read is run here once, on publication.

Publication is atomic: the bytes are staged beside the destination and moved
into place, and one process per key holds a publication claim so a cold start
across many workers writes the copy once. A reader that finds a torn,
corrupt, foreign or stale copy compiles instead.
"""

from __future__ import annotations

import json
import logging
import os
import pickle
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.atomic_write import atomic_write_best_effort_bytes
from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.hashing import content_hash_hex, sha256_hex
from cadrumo.core.lockfile_unlink import unlink_lockfile
from cadrumo.core.paths import select_filesystem_retention_survivors
from cadrumo.core.pid_liveness import pid_is_alive
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.type_guards import is_object_tuple
from cadrumo.domain.calculations.registry.governed_fact_scope import (
    CandidateFactAuthority,
    validating_governed_facts,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from cadrumo.domain.user_profile.schema import ProfileSchemaDefinition

from .compiled_cache import loader_code_fingerprint
from .compiled_cache_support import has_current_pydantic_shape, load_first_party_pickle, read_cache_bytes
from .compiler_source_tree import compiler_source_roots, normalized_source_digest
from .loader_cache import is_bundled_registry_root, registry_disk_cache_dir, registry_disk_cache_enabled

__all__ = [
    "ValidatedAuthorityCopy",
    "publish_validated_authority_copy",
    "read_validated_authority_copy",
    "validated_authority_copy_key",
    "validated_authority_copy_path",
]

_SCHEMA: Final = "cadrumo-validated-authority-copy/v1"
_FILENAME_PREFIX: Final = "cadrumo_authority_"
_FILENAME_SUFFIX: Final = ".pkl"
_CLAIM_SUFFIX: Final = ".claim"
#: Each copy of the bundled registry is over a hundred megabytes; two cover the
#: current inputs and the ones a concurrent edit just replaced.
_MAX_RETAINED_COPIES: Final = 2
_FRAME_SEPARATOR: Final = b"\n"
_SEGMENT_LENGTHS: Final = struct.Struct("!QQQ")
_EXCLUDED_SEGMENTS: Final = frozenset({"tests", "__pycache__"})
_LOGGER = logging.getLogger(__name__)

type ModuleClosure = tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ValidatedAuthorityCopy:
    """The components one validated compile of the bundled registry produced."""

    modelos: tuple[ModeloDefinition, ...]
    catalogues: RegistryCatalogues
    identity_digest: str
    profile_schema: ProfileSchemaDefinition


def validated_authority_copy_key(
    *,
    registry_root: Path,
    source_root: Path,
    registry_identity_digest: str,
    source_receipt: str,
    compiler_source_tree_digest: str,
    validation_key: str | None,
) -> str | None:
    """Return the copy key for these compiler inputs, or ``None`` when no copy may exist.

    ``registry_root`` and ``source_root`` are the resolved roots the compile
    reads. Anything but the bundled pair, and any compile without a validation
    key, is refused a copy.
    """
    if validation_key is None:
        return None
    try:
        bundled_sources = source_root == bundled_path().resolve()
    except (ImportError, OSError, ValueError):
        bundled_sources = False
    if not registry_disk_cache_enabled(is_bundled=bundled_sources and is_bundled_registry_root(registry_root)):
        return None
    return content_hash_hex(
        {
            "schema": _SCHEMA,
            "registry_root": registry_root.as_posix(),
            "registry_identity_digest": registry_identity_digest,
            "source_receipt": source_receipt,
            "compiler_source_tree_digest": compiler_source_tree_digest,
            "validation_key": validation_key,
            "loader_code_fingerprint": loader_code_fingerprint(),
        }
    )


def validated_authority_copy_path(key: str) -> Path:
    """Return where the copy published under ``key`` lives."""
    return registry_disk_cache_dir() / f"{_FILENAME_PREFIX}{key}{_FILENAME_SUFFIX}"


def read_validated_authority_copy(key: str) -> ValidatedAuthorityCopy | None:
    """Return the copy published under ``key``, or ``None`` when the caller must compile.

    A copy whose frame, digest, key, recorded module sources or decoded shape
    does not hold is deleted, so the next publication replaces it.
    """
    path = validated_authority_copy_path(key)
    if not path.is_file():
        return None
    raw = read_cache_bytes(path)
    if raw is None:
        return None
    copy = _decode(raw, key=key)
    if copy is None:
        _LOGGER.info("Refusing the validated registry copy at %s; compiling instead", path)
        _delete(path)
    return copy


def publish_validated_authority_copy(key: str, copy: ValidatedAuthorityCopy) -> bool:
    """Publish ``copy`` under ``key`` unless a peer already holds or published it.

    Returns whether this call wrote the copy. Every failure is absorbed: the
    copy is an optimisation, and its absence only costs a later compile.
    """
    path = validated_authority_copy_path(key)
    if path.is_file():
        return False
    claim = path.with_name(path.name + _CLAIM_SUFFIX)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    if not _claim(claim):
        return False
    try:
        if path.is_file():
            return False
        if not has_current_pydantic_shape((*copy.modelos, copy.catalogues, copy.profile_schema)):
            _LOGGER.warning("Not publishing a registry copy whose models miss current fields")
            return False
        atomic_write_best_effort_bytes(path, _encode(key, copy, _module_closure()))
        _evict_older_copies(path.parent)
    except Exception:
        _LOGGER.warning("Could not publish the validated registry copy at %s", path, exc_info=True)
        return False
    finally:
        _release(claim)
    return True


def _module_closure() -> ModuleClosure:
    """Digest every loaded first-party source the compiler source key does not already hash."""
    keyed_roots = tuple(compiler_source_roots().values())
    rows: dict[str, str] = {}
    for name, module in tuple(sys.modules.items()):
        if name.split(".", 1)[0] not in {"cadrumo", "dev"} or "conftest" in name.split("."):
            continue
        source = getattr(module, "__file__", None)
        if not isinstance(source, str) or not source.endswith(".py"):
            continue
        path = Path(source).resolve()
        if _EXCLUDED_SEGMENTS.intersection(path.parts) or any(path.is_relative_to(root) for root in keyed_roots):
            continue
        try:
            rows[path.as_posix()] = normalized_source_digest(path)
        except OSError:
            rows[path.as_posix()] = "unreadable"
    return tuple(sorted(rows.items()))


def _closure_is_current(closure: ModuleClosure) -> bool:
    for source, digest in closure:
        try:
            if normalized_source_digest(Path(source)) != digest:
                return False
        except OSError:
            return False
    return True


def _encode(key: str, copy: ValidatedAuthorityCopy, closure: ModuleClosure) -> bytes:
    header = json.dumps(
        {"identity_digest": copy.identity_digest, "closure": [list(row) for row in closure]},
        sort_keys=True,
    ).encode("utf-8")
    catalogues = pickle.dumps(copy.catalogues, protocol=pickle.HIGHEST_PROTOCOL)
    modelos = pickle.dumps(copy.modelos, protocol=pickle.HIGHEST_PROTOCOL)
    profile = pickle.dumps(copy.profile_schema, protocol=pickle.HIGHEST_PROTOCOL)
    body = _SEGMENT_LENGTHS.pack(len(header), len(catalogues), len(modelos)) + header + catalogues + modelos + profile
    return _FRAME_SEPARATOR.join((_SCHEMA.encode("ascii"), key.encode("ascii"), _body_digest(body), body))


def _body_digest(body: bytes) -> bytes:
    return sha256_hex(_SCHEMA.encode("ascii") + body).encode("ascii")


def _decode(raw: bytes, *, key: str) -> ValidatedAuthorityCopy | None:
    parts = raw.split(_FRAME_SEPARATOR, 3)
    if len(parts) != 4:
        return None
    schema, recorded_key, digest, body = parts
    if schema != _SCHEMA.encode("ascii") or recorded_key != key.encode("ascii") or digest != _body_digest(body):
        return None
    try:
        return _decode_body(body)
    except Exception:
        _LOGGER.debug("Validated registry copy could not be restored", exc_info=True)
        return None


def _decode_body(body: bytes) -> ValidatedAuthorityCopy | None:
    if len(body) < _SEGMENT_LENGTHS.size:
        return None
    header_length, catalogues_length, modelos_length = _SEGMENT_LENGTHS.unpack_from(body)
    header_end = _SEGMENT_LENGTHS.size + header_length
    catalogues_end = header_end + catalogues_length
    modelos_end = catalogues_end + modelos_length
    if modelos_end > len(body):
        return None
    header = json.loads(body[_SEGMENT_LENGTHS.size : header_end].decode("utf-8"))
    identity_digest = header.get("identity_digest") if isinstance(header, dict) else None
    closure_rows = header.get("closure") if isinstance(header, dict) else None
    if not isinstance(identity_digest, str) or not isinstance(closure_rows, list):
        return None
    closure = tuple((str(row[0]), str(row[1])) for row in closure_rows if isinstance(row, list) and len(row) == 2)
    if len(closure) != len(closure_rows) or not _closure_is_current(closure):
        return None
    catalogues = load_first_party_pickle(body[header_end:catalogues_end])
    if not isinstance(catalogues, RegistryCatalogues):
        return None
    with validating_governed_facts(
        CandidateFactAuthority(catalogues.facts, catalogues.require_supported_filing_years())
    ):
        modelos = load_first_party_pickle(body[catalogues_end:modelos_end])
        profile_schema = load_first_party_pickle(body[modelos_end:])
    if not is_object_tuple(modelos) or not isinstance(profile_schema, ProfileSchemaDefinition):
        return None
    typed_modelos = tuple(modelo for modelo in modelos if isinstance(modelo, ModeloDefinition))
    if len(typed_modelos) != len(modelos):
        return None
    return ValidatedAuthorityCopy(
        modelos=typed_modelos,
        catalogues=catalogues,
        identity_digest=identity_digest,
        profile_schema=profile_schema,
    )


def _claim(path: Path) -> bool:
    """Take the one publication claim for a key, reclaiming it from a dead holder once."""
    for _attempt in range(2):
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            holder = _claim_holder(path)
            if holder is not None and pid_is_alive(holder):
                return False
            if not _drop(path, reason="authority_copy_claim_reclaim"):
                return False
            continue
        except OSError:
            return False
        try:
            os.write(handle, str(os.getpid()).encode("ascii"))
        finally:
            os.close(handle)
        return True
    return False


def _claim_holder(path: Path) -> int | None:
    try:
        raw = path.read_bytes().decode("ascii").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return int(raw) if raw.isdigit() else None


def _release(path: Path) -> None:
    if _claim_holder(path) in (os.getpid(), None):
        _drop(path, reason="authority_copy_claim_release")


def _drop(path: Path, *, reason: str) -> bool:
    try:
        return unlink_lockfile(path, reason=reason)
    except OSError:
        _LOGGER.debug("Could not remove the registry copy claim at %s", path, exc_info=True)
        return False


def _delete(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        _LOGGER.debug("Could not delete the refused registry copy at %s", path, exc_info=True)


def _evict_older_copies(directory: Path) -> None:
    entries: list[tuple[Path, int]] = []
    try:
        for candidate in iter_directory(directory, pattern=f"{_FILENAME_PREFIX}*{_FILENAME_SUFFIX}", require_root=True):
            try:
                entries.append((candidate, candidate.stat().st_mtime_ns))
            except OSError:
                continue
    except OSError:
        return
    entries.sort(key=lambda pair: pair[0], reverse=True)
    _keep, stale = select_filesystem_retention_survivors(
        entries,
        timestamp=lambda pair: pair[1],
        max_count=_MAX_RETAINED_COPIES,
    )
    for candidate, _modified in stale:
        _delete(candidate)
