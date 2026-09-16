"""Read-only SQLite storage for generation-pinned authority components."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from queue import LifoQueue
from secrets import token_hex
from threading import RLock
from typing import Final

from ....core.errors.hierarchy import CadrumoError
from ....core.file_change_time import file_change_time_ns
from ....core.hashing import reject_duplicate_json_members, reject_json_constant, sha256_hex
from ....core.type_guards import is_str_keyed_dict
from .authority_artifact import (
    AuthorityComponentQuery,
    AuthorityGenerationPin,
    authority_component_identity,
    authority_query_from_identity,
    decode_authority_component,
)
from .authority_cache import (
    AccountedAuthorityCache,
    AuthorityCacheTelemetry,
    RetainedAuthorityValue,
)

AUTHORITY_DATABASE_FORMAT: Final = "cadrumo-authority-sqlite-v1"
AUTHORITY_DESCRIPTOR_FORMAT: Final = "cadrumo-authority-descriptor-v1"
_DESCRIPTOR_MEMBERS: Final = frozenset({"format", "database", "database_size", "database_sha256", "logical_generation"})
_DATABASE_NAME = re.compile(r"authority-([0-9a-f]{64})\.sqlite3")


class AuthorityStoreError(CadrumoError):
    """A published SQLite authority cannot be admitted or queried safely."""


class AuthorityStoreCutoverError(AuthorityStoreError):
    """A pin names another legitimate reader generation or incarnation."""


class AuthorityStoreCorruptionError(AuthorityStoreError):
    """Content-addressed bytes or their declared component closure changed."""


@dataclass(frozen=True, slots=True)
class AuthorityDescriptor:
    """Small control record selecting one exact content-addressed database."""

    database: str
    database_size: int
    database_sha256: str
    logical_generation: str
    format: str = AUTHORITY_DESCRIPTOR_FORMAT

    @classmethod
    def read(cls, path: Path) -> AuthorityDescriptor:
        """Read a closed canonical descriptor and confine its target to one directory."""
        try:
            raw = path.read_bytes()
            document = json.loads(
                raw,
                object_pairs_hook=reject_duplicate_json_members,
                parse_constant=reject_json_constant,
            )
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise AuthorityStoreError(f"authority descriptor is unavailable or malformed at {path}") from exc
        if not is_str_keyed_dict(document) or frozenset(document) != _DESCRIPTOR_MEMBERS:
            raise AuthorityStoreError("authority descriptor has unexpected or missing members")
        try:
            format_name = document["format"]
            database = document["database"]
            database_size = document["database_size"]
            database_sha256 = document["database_sha256"]
            logical_generation = document["logical_generation"]
            if not isinstance(format_name, str):
                raise TypeError
            if not isinstance(database, str):
                raise TypeError
            if not isinstance(database_sha256, str):
                raise TypeError
            if not isinstance(logical_generation, str):
                raise TypeError
            if not isinstance(database_size, int) or isinstance(database_size, bool):
                raise TypeError
            descriptor = cls(database, database_size, database_sha256, logical_generation, format_name)
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthorityStoreError("authority descriptor has invalid typed members") from exc
        descriptor._validate(path.parent)
        if descriptor.to_bytes() != raw:
            raise AuthorityStoreError("authority descriptor is not canonical JSON")
        return descriptor

    def _validate(self, directory: Path) -> None:
        """Reject unsupported formats, traversal, and incoherent content-addressed names."""
        if self.format != AUTHORITY_DESCRIPTOR_FORMAT:
            raise AuthorityStoreError(f"unsupported authority descriptor format {self.format!r}")
        match = _DATABASE_NAME.fullmatch(self.database)
        if match is None or match.group(1) != self.database_sha256:
            raise AuthorityStoreError("authority descriptor database name does not match its physical digest")
        if self.database_size <= 0:
            raise AuthorityStoreError("authority descriptor database size must be positive")
        if _DATABASE_NAME.fullmatch(Path(self.database).name) is None or Path(self.database).name != self.database:
            raise AuthorityStoreError("authority descriptor database must be a confined basename")
        if len(self.logical_generation) != 64 or any(
            char not in "0123456789abcdef" for char in self.logical_generation
        ):
            raise AuthorityStoreError("authority descriptor logical generation must be a lowercase SHA-256 digest")
        target = (directory / self.database).resolve()
        if target.parent != directory.resolve():
            raise AuthorityStoreError("authority descriptor database escapes its resource directory")

    def to_bytes(self) -> bytes:
        """Return canonical descriptor bytes containing no registry records."""
        from ....core.hashing import canonical_json_bytes

        return canonical_json_bytes(
            {
                "format": self.format,
                "database": self.database,
                "database_size": self.database_size,
                "database_sha256": self.database_sha256,
                "logical_generation": self.logical_generation,
            }
        )


@dataclass(frozen=True, slots=True)
class _DatabaseIdentity:
    device: int
    inode: int
    size: int
    modified_ns: int
    changed_ns: int
    digest: str


class SQLiteAuthorityReader:
    """Admitted reader with bounded connection checkout and generation-pinned loads."""

    def __init__(self, descriptor_path: Path, *, max_connections: int = 4) -> None:
        """Admit one exact database without hydrating any domain payload."""
        if sqlite3.sqlite_version_info < (3, 37, 0) or sqlite3.threadsafety == 0:
            raise AuthorityStoreError("authority SQLite requires SQLite 3.37+ with a thread-safe build")
        if not 1 <= max_connections <= 4:
            raise ValueError("authority reader permits between one and four connection checkouts")
        self._descriptor_path = descriptor_path.resolve()
        self._descriptor = AuthorityDescriptor.read(self._descriptor_path)
        self._database_path = self._descriptor_path.parent / self._descriptor.database
        self._identity = self._read_database_identity()
        self._incarnation = sha256_hex(f"{self._descriptor.logical_generation}:{token_hex(32)}".encode("ascii"))
        self._connections: LifoQueue[sqlite3.Connection] = LifoQueue(max_connections)
        self._all_connections: list[sqlite3.Connection] = []
        self._state_lock = RLock()
        self._active_leases = 0
        self._closed = False
        self._component_queries: tuple[AuthorityComponentQuery, ...] | None = None
        for _ in range(max_connections):
            connection = self._open_connection()
            self._all_connections.append(connection)
            self._connections.put(connection)
        self._admit_database()
        self._cache: AccountedAuthorityCache[tuple[AuthorityGenerationPin, AuthorityComponentQuery], object] = (
            AccountedAuthorityCache()
        )

    def pin(self) -> AuthorityGenerationPin:
        """Return this reader's immutable logical-generation/incarnation identity."""
        self._require_open()
        self._verify_database_identity()
        return AuthorityGenerationPin(self._descriptor.logical_generation, self._incarnation)

    @contextmanager
    def lease(self) -> Generator[AuthorityGenerationPin]:
        """Keep this reader resource alive for one top-level operation."""
        with self._state_lock:
            self._require_open()
            self._active_leases += 1
        try:
            yield self.pin()
        finally:
            with self._state_lock:
                self._active_leases -= 1

    def load(self, query: AuthorityComponentQuery, *, pin: AuthorityGenerationPin) -> object:
        """Load and decode one component from exactly this admitted generation.

        Identity is verified wherever this reader touches the database: when the
        lease takes its pin, and inside every uncached load. A cache hit reads
        no file and is served under the pin the lease already verified, so it
        does not re-stat the database. That is what keeps a command that loads
        thousands of components from paying a metadata query for each one.
        """
        self._require_pin(pin)
        return self._cache.get_or_load(
            (pin, query),
            lambda: self._load_uncached(query, pin=pin),
        )

    def telemetry(self) -> AuthorityCacheTelemetry:
        """Return retained component accounting, excluding connections and leases."""
        return self._cache.telemetry()

    def component_queries(self) -> tuple[AuthorityComponentQuery, ...]:
        """Iterate the complete component directory without hydrating payloads.

        The directory is read once per admitted database: an admitted
        generation is immutable, and identity verification still runs on every
        call so a swapped file is refused rather than served from memory.
        """
        self._verify_database_identity()
        with self._state_lock:
            if self._component_queries is not None:
                return self._component_queries
        with self._checkout() as connection:
            rows = connection.execute("SELECT kind, key FROM components ORDER BY kind, key").fetchall()
        queries = tuple(authority_query_from_identity(kind, key) for kind, key in rows)
        with self._state_lock:
            self._component_queries = queries
        return queries

    @property
    def active_leases(self) -> int:
        """Return the separately accounted number of top-level operation leases."""
        with self._state_lock:
            return self._active_leases

    def close(self) -> None:
        """Close an unleased reader deterministically."""
        with self._state_lock:
            if self._active_leases:
                raise AuthorityStoreError("cannot close an authority reader while operations hold leases")
            if self._closed:
                return
            self._closed = True
            self._cache.clear()
            for connection in self._all_connections:
                connection.close()

    def _load_uncached(
        self,
        query: AuthorityComponentQuery,
        *,
        pin: AuthorityGenerationPin,
    ) -> RetainedAuthorityValue[object]:
        kind, key = authority_component_identity(query)
        with self._checkout() as connection:
            row = connection.execute(
                "SELECT codec, payload_sha256, retained_weight, payload FROM components WHERE kind = ? AND key = ?",
                (kind.value, key),
            ).fetchone()
            dependency_rows = connection.execute(
                "SELECT dependency_kind, dependency_key FROM dependencies "
                "WHERE component_kind = ? AND component_key = ? ORDER BY ordinal",
                (kind.value, key),
            ).fetchall()
        self._verify_database_identity()
        if row is None:
            raise LookupError(f"authority component {kind.value}/{key} is unavailable")
        codec, payload_digest, retained_weight, payload = row
        if codec != "cadrumo-authority-component-v1" or not isinstance(payload, bytes):
            raise AuthorityStoreCorruptionError(f"authority component {kind.value}/{key} has invalid storage metadata")
        if sha256_hex(payload) != payload_digest:
            raise AuthorityStoreCorruptionError(f"authority component {kind.value}/{key} failed its digest check")
        dependencies = tuple(
            self.load(authority_query_from_identity(dependency_kind, dependency_key), pin=pin)
            for dependency_kind, dependency_key in dependency_rows
        )
        decoded = decode_authority_component(query, payload, dependencies=dependencies)
        # Publication measured the decoded graph once; re-walking millions of
        # members on every load would repeat that work for every operation.
        return RetainedAuthorityValue(decoded, int(retained_weight))

    def _open_connection(self) -> sqlite3.Connection:
        uri = self._database_path.resolve().as_uri() + "?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True, check_same_thread=False, isolation_level=None)
            connection.execute("PRAGMA query_only = ON")
            connection.execute("PRAGMA foreign_keys = ON")
            return connection
        except sqlite3.Error as exc:
            raise AuthorityStoreError(
                f"authority database could not be opened read-only at {self._database_path}"
            ) from exc

    @contextmanager
    def _checkout(self) -> Generator[sqlite3.Connection]:
        self._require_open()
        connection = self._connections.get()
        try:
            yield connection
        finally:
            self._connections.put(connection)

    def _admit_database(self) -> None:
        """Bind the opened database to its descriptor's format and generation.

        Structural integrity -- page checks, foreign-key closure, a complete
        component count and an acyclic dependency graph -- is proved once, at
        publication, before the descriptor naming these bytes is written. The
        size and SHA-256 identity check has already tied the opened file to
        exactly those published bytes, so repeating the scans here would only
        re-prove what the digest guarantees.
        """
        with self._checkout() as connection:
            row = connection.execute(
                "SELECT format, logical_generation FROM authority_manifest WHERE singleton = 1"
            ).fetchone()
        if row is None or row[0] != AUTHORITY_DATABASE_FORMAT or row[1] != self._descriptor.logical_generation:
            raise AuthorityStoreCorruptionError("authority database manifest disagrees with its descriptor")

    def _read_database_identity(self) -> _DatabaseIdentity:
        try:
            status = self._database_path.stat()
            payload = self._database_path.read_bytes()
        except OSError as exc:
            raise AuthorityStoreError(f"authority database is unavailable at {self._database_path}") from exc
        identity = _DatabaseIdentity(
            device=status.st_dev,
            inode=status.st_ino,
            size=status.st_size,
            modified_ns=status.st_mtime_ns,
            changed_ns=file_change_time_ns(self._database_path, status),
            digest=sha256_hex(payload),
        )
        if identity.size != self._descriptor.database_size or identity.digest != self._descriptor.database_sha256:
            raise AuthorityStoreCorruptionError("authority database bytes disagree with the published descriptor")
        return identity

    def _verify_database_identity(self) -> None:
        try:
            status = self._database_path.stat()
            observed = (
                status.st_dev,
                status.st_ino,
                status.st_size,
                status.st_mtime_ns,
                file_change_time_ns(self._database_path, status),
            )
        except OSError as exc:
            self._cache.clear()
            raise AuthorityStoreCorruptionError(
                "content-addressed authority database disappeared after admission"
            ) from exc
        accepted = (
            self._identity.device,
            self._identity.inode,
            self._identity.size,
            self._identity.modified_ns,
            self._identity.changed_ns,
        )
        if observed != accepted:
            self._cache.clear()
            raise AuthorityStoreCorruptionError("content-addressed authority database changed after admission")

    def _require_pin(self, pin: AuthorityGenerationPin) -> None:
        expected = AuthorityGenerationPin(self._descriptor.logical_generation, self._incarnation)
        if pin != expected:
            raise AuthorityStoreCutoverError(
                "authority operation pin belongs to another generation or reader incarnation"
            )
        self._require_open()

    def _require_open(self) -> None:
        if self._closed:
            raise AuthorityStoreError("authority reader is closed")
