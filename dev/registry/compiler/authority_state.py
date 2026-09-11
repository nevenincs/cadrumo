"""Development-only ownership and cache state for mutable registry inputs.

This module is deliberately the only place that gives a filesystem root an
identity, caches a compilation, or invalidates a compiler generation. The
runtime authority owns neither a root nor a mutable-tree cache: it receives a
signed artifact and identifies captures by that artifact's digest.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import Condition, RLock
from typing import TYPE_CHECKING

from cadrumo.core.hashing import content_hash_hex
from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority


_PhysicalDirectoryIdentity = tuple[int, int]
_AuthoringRootKey = tuple[_PhysicalDirectoryIdentity, _PhysicalDirectoryIdentity]


@dataclass(frozen=True, slots=True)
class AuthoringRootPair:
    """Resolved physical identity for a mutable compiler input pair."""

    registry_root: Path
    source_root: Path
    key: _AuthoringRootKey


@dataclass(slots=True)
class _CompilerSlot:
    lock: RLock = field(default_factory=RLock, repr=False)
    receipt: str | None = None
    authority: ValidatedRegistryAuthority | None = None
    generation: int = 0


class _CompilerBarrier:
    """Drain compiler reads before a development cache reset."""

    def __init__(self) -> None:
        self._condition = Condition(RLock())
        self._readers = 0
        self._reset_pending = False

    @contextmanager
    def read(self) -> Generator[None]:
        with self._condition:
            while self._reset_pending:
                self._condition.wait()
            self._readers += 1
        try:
            yield
        finally:
            with self._condition:
                self._readers -= 1
                if self._readers == 0:
                    self._condition.notify_all()

    @contextmanager
    def reset(self) -> Generator[None]:
        with self._condition:
            while self._reset_pending:
                self._condition.wait()
            self._reset_pending = True
            while self._readers:
                self._condition.wait()
        try:
            yield
        finally:
            with self._condition:
                self._reset_pending = False
                self._condition.notify_all()


_state_lock = RLock()
_barrier = _CompilerBarrier()
_slots: dict[_AuthoringRootKey, _CompilerSlot] = {}
_authority_sources: dict[int, Path] = {}
_generation = 0


def canonical_authoring_root_pair(root: Path, source_root: Path) -> tuple[Path, Path]:
    """Resolve mutable compiler roots and refuse absent or non-directory inputs."""
    pair = authoring_root_pair(root, source_root)
    return pair.registry_root, pair.source_root


def authoring_root_pair(root: Path, source_root: Path) -> AuthoringRootPair:
    """Return the canonical physical owner pair for one compiler invocation."""
    try:
        resolved_root = root.expanduser().resolve(strict=True)
        resolved_source_root = source_root.expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise RegistrySnapshotError("registry compiler roots must resolve to existing physical paths") from exc
    if not resolved_root.is_dir() or not resolved_source_root.is_dir():
        raise RegistrySnapshotError("registry compiler roots must resolve to physical directories")
    root_stat = resolved_root.stat()
    source_stat = resolved_source_root.stat()
    return AuthoringRootPair(
        registry_root=resolved_root,
        source_root=resolved_source_root,
        key=((root_stat.st_dev, root_stat.st_ino), (source_stat.st_dev, source_stat.st_ino)),
    )


def source_evidence_receipt(fingerprints: tuple[tuple[str, int, int], ...]) -> str:
    """Digest exact source bytes before a mutable compilation may be reused."""
    entries: list[dict[str, object]] = []
    for raw_path, size, mtime_ns in fingerprints:
        digest = hashlib.sha256(Path(raw_path).read_bytes()).hexdigest()
        entries.append({"path": raw_path, "size": size, "mtime_ns": mtime_ns, "sha256": digest})
    return content_hash_hex({"schema": "registry-authoring-source-receipt/v1", "entries": entries})


def cached_compilation(
    pair: AuthoringRootPair,
    *,
    registry_identity_digest: str,
    source_receipt: str,
    build: Callable[[], ValidatedRegistryAuthority],
) -> ValidatedRegistryAuthority:
    """Compile once for an observed mutable-tree receipt, otherwise rebuild."""
    global _generation
    receipt = content_hash_hex(
        {
            "schema": "registry-authoring-compilation-receipt/v1",
            "registry_identity_digest": registry_identity_digest,
            "source_receipt": source_receipt,
        }
    )
    with _barrier.read():
        with _state_lock:
            slot = _slots.setdefault(pair.key, _CompilerSlot())
        with slot.lock:
            if slot.receipt == receipt and slot.authority is not None:
                return slot.authority
            authority = build()
            with _state_lock:
                _generation += 1
                slot.receipt = receipt
                slot.authority = authority
                slot.generation = _generation
            return authority


def register_authoring_authority(authority: ValidatedRegistryAuthority, *, source_root: Path) -> None:
    """Associate a development compilation result with its mutable evidence root."""
    with _state_lock:
        _authority_sources[id(authority)] = source_root


def source_root_for(authority: ValidatedRegistryAuthority) -> Path:
    """Return the explicit source root owned by a development compilation result."""
    with _state_lock:
        try:
            return _authority_sources[id(authority)]
        except KeyError as exc:
            raise RegistrySnapshotError("development source evidence requires a compiler-owned authority") from exc


@contextmanager
def compiler_reset() -> Generator[None]:
    """Exclusively invalidate every mutable compiler cache entry."""
    global _generation
    with _barrier.reset(), _state_lock:
        _generation += 1
        _slots.clear()
        _authority_sources.clear()
        yield


def compiler_generation() -> int:
    """Return the current development compiler generation."""
    with _state_lock:
        return _generation
