"""Shared lifecycle base classes and helpers for live snapshot services.

This module factors the duplicated state-machine, supersession, and content-
addressed-id derivation logic shared across the bucket-scoped live snapshot
services (Borrador100, Census, and — in later phases — file-based legacy
services).

Design notes:

* ``SnapshotLifecycleState`` carries the three operator-visible states all
  stateful snapshot services share. Domain-specific enums may continue to exist
  as aliases (Borrador100SnapshotState aliases this enum) to preserve their
  public name on import surfaces.
* ``SnapshotRepository`` is a Protocol — not an abstract class — so concrete
  per-service repositories (which need to bind a specific TPayload model and a
  domain-specific object-key prefix) do not need to inherit from it. The
  service base accepts any object that structurally satisfies the protocol.
* ``SnapshotService`` is a generic abstract base whose ``capture`` template
  method coordinates the dedup-by-content-id, auto-supersession, and
  late-arrival demotion flow. Subclasses implement ``_payload_axis_key`` and
  ``_build_active_payload`` to express their domain axis and construction
  contract; everything else (state transitions, repository orchestration) is
  shared.
* ``StatelessSnapshotService`` is the append-only base for services
  (Expedientes, Notifications) with no state machine. It accepts
  ``bucket_id`` per call and constructs a fresh repository for the call
  from an injected ``repository_factory`` — the natural shape for
  services whose public verbs are themselves multi-bucket. Supersession
  and discard helpers are deliberately absent.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from ._errors import LiveApplicationInputError


class SnapshotNotFoundError(KeyError):
    """Shared base for per-service snapshot-lookup-miss errors.

    Per-service subclasses (BorradorSnapshotNotFoundError,
    ExpedientesSnapshotNotFoundError, NotificationsSnapshotNotFoundError,
    and future siblings) inherit from this base alongside
    :class:`aeat.core.errors.AeatError` so callers can either catch the
    domain-specific class name or the shared parent. The per-service
    classes list ``AeatError`` first in their bases so MRO routes
    ``__init__`` through :meth:`AeatError.__init__` (which accepts the
    structured ``suggestion=`` / ``context=`` kwargs) rather than
    :class:`KeyError`'s C-level constructor.
    """


class SnapshotLifecycleState(StrEnum):
    """Lifecycle states shared across stateful live snapshot services.

    * ``ACTIVE``    — current valid capture; readers consume this.
    * ``SUPERSEDED`` — replaced by a newer ACTIVE capture on the same axis;
      retained for audit. Carries ``superseded_by_snapshot_id``.
    * ``DISCARDED`` — explicitly retired by an operator; carries actor +
      reason audit metadata.
    """

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DISCARDED = "discarded"


TPayload = TypeVar("TPayload", bound=BaseModel)


@runtime_checkable
class SnapshotRepository(Protocol, Generic[TPayload]):
    """Structural contract for bucket-scoped snapshot persistence backends.

    Implementations may be SecureObjectRepository-backed (Borrador100, Census)
    or file-system-backed (legacy stateless services in Phase 3).
    """

    @property
    def bucket_id(self) -> str: ...

    def exists(self, snapshot_id: str) -> bool: ...

    def load(self, snapshot_id: str) -> TPayload: ...

    def list_snapshots(self) -> tuple[TPayload, ...]: ...

    def resolve(self, snapshot_id: str) -> TPayload: ...

    def save(self, snapshot: TPayload) -> None: ...


_CanonicalScalar = str | int | float | bool | None
_CanonicalValue = _CanonicalScalar | list[Any] | dict[str, Any]


def derive_snapshot_id_from_json(parts: dict[str, _CanonicalValue]) -> str:
    """Return a SHA-256 content-addressed id for a canonical JSON dict.

    ``parts`` is serialized with ``sort_keys=True``, ASCII-safe, and the
    compact ``(",", ":")`` separator, then hashed. Callers must pre-coerce
    Decimals / datetimes / typed-IDs to JSON-safe scalars; the helper does
    not introspect Pydantic models.
    """

    canonical = json.dumps(
        parts,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def enforce_snapshot_state_invariants(
    *,
    state: SnapshotLifecycleState,
    has_supersession_pointer: bool,
    discarded_at: datetime | None,
    discarded_by: str,
    discard_reason: str = "",
) -> None:
    """Enforce the three-state lifecycle invariants for any snapshot payload.

    ACTIVE: no supersession pointer, no discard audit metadata.
    SUPERSEDED: requires supersession pointer, no discard audit metadata.
    DISCARDED: forbids supersession pointer, requires actor + timestamp.

    Domain-specific Pydantic model validators wrap this helper so the same
    rules apply across Borrador100, Census, and future stateful services.
    """

    discard_metadata_present = (
        discarded_at is not None or bool(discarded_by) or bool(discard_reason)
    )
    if state is SnapshotLifecycleState.ACTIVE:
        if has_supersession_pointer:
            raise LiveApplicationInputError(
                "active snapshots cannot carry supersession pointers"
            )
        if discard_metadata_present:
            raise LiveApplicationInputError(
                "only discarded snapshots can carry discard metadata"
            )
        return
    if state is SnapshotLifecycleState.SUPERSEDED:
        if not has_supersession_pointer:
            raise LiveApplicationInputError(
                "superseded snapshots must carry superseded_by_snapshot_id"
            )
        if discard_metadata_present:
            raise LiveApplicationInputError(
                "only discarded snapshots can carry discard metadata"
            )
        return
    # DISCARDED
    if has_supersession_pointer:
        raise LiveApplicationInputError(
            "discarded snapshots cannot carry supersession pointers"
        )
    if discarded_at is None or not discarded_by.strip():
        raise LiveApplicationInputError(
            "discarded snapshots require discarded_at and discarded_by"
        )


class SnapshotService(ABC, Generic[TPayload]):
    """Abstract lifecycle service base for stateful bucket-scoped snapshots.

    Subclasses bind ``TPayload`` to their concrete Pydantic snapshot model and
    implement two hooks:

    * ``_payload_axis_key`` — returns a tuple identifying the domain axis on
      which prior ACTIVE snapshots are superseded (e.g. ``(modelo, year,
      period)`` for Borrador100, ``(profile_id,)`` for Census).
    * ``_build_active_payload`` — constructs an ACTIVE snapshot from
      keyword-only capture arguments and a derived snapshot id.

    The ``capture`` template orchestrates dedup, auto-supersession of prior
    ACTIVE snapshots, and late-arrival demotion when a freshly-captured
    snapshot arrives older than the current ACTIVE on the same axis.
    """

    def __init__(self, *, bucket_id: str, repository: SnapshotRepository[TPayload]) -> None:
        if repository.bucket_id != bucket_id.strip():
            raise LiveApplicationInputError(
                f"snapshot service bucket_id={bucket_id!r} does not match repository bucket "
                f"{repository.bucket_id!r}"
            )
        self._repository: SnapshotRepository[TPayload] = repository

    # ---- subclass hooks ----------------------------------------------------

    @abstractmethod
    def _derive_snapshot_id(self, **kwargs: Any) -> str:
        """Derive a content-addressed id from capture kwargs."""

    @abstractmethod
    def _build_active_payload(self, *, snapshot_id: str, **kwargs: Any) -> TPayload:
        """Construct an ACTIVE snapshot payload for fresh captures."""

    @abstractmethod
    def _payload_axis_key(self, payload: TPayload) -> tuple[Any, ...]:
        """Return the domain axis tuple used for supersession matching."""

    @abstractmethod
    def _payload_captured_at(self, payload: TPayload) -> datetime:
        """Return the capture timestamp for ordering comparisons."""

    @abstractmethod
    def _payload_snapshot_id(self, payload: TPayload) -> str:
        """Return the snapshot id from a payload (avoids requiring a base model)."""

    @abstractmethod
    def _payload_state(self, payload: TPayload) -> SnapshotLifecycleState:
        """Return the lifecycle state from a payload."""

    @abstractmethod
    def _demote_to_superseded(self, payload: TPayload, *, superseded_by: str) -> TPayload:
        """Return a SUPERSEDED clone of ``payload`` pointing at ``superseded_by``."""

    # ---- template methods --------------------------------------------------

    def _capture_with_lifecycle(self, **kwargs: Any) -> TPayload:
        """Template method: subclasses expose a typed ``capture`` wrapper.

        Phase 1 deviation from the proposal: the proposal placed ``capture``
        directly on the base with ``**kwargs``. That forces every concrete
        subclass to either accept ``**kwargs`` (losing type safety on
        operator-visible signatures) or override ``capture`` with a narrower
        signature (LSP-violating). Renaming the base hook resolves the
        Liskov conflict while preserving the operator-facing keyword-only
        signatures on each service.
        """

        snapshot_id = self._derive_snapshot_id(**kwargs)
        if self._repository.exists(snapshot_id):
            return self._repository.load(snapshot_id)
        candidate = self._build_active_payload(snapshot_id=snapshot_id, **kwargs)
        active_snapshot = self._latest_active_for_axis(candidate)
        if active_snapshot is not None and self._payload_captured_at(
            active_snapshot
        ) > self._payload_captured_at(candidate):
            # Late-arriving capture: demote the incoming snapshot to SUPERSEDED.
            demoted = self._demote_to_superseded(
                candidate, superseded_by=self._payload_snapshot_id(active_snapshot)
            )
            self._repository.save(demoted)
            return demoted
        self._supersede_current_for_axis(candidate)
        self._repository.save(candidate)
        return candidate

    def list_snapshots(self) -> tuple[TPayload, ...]:
        return self._repository.list_snapshots()

    def resolve_snapshot(self, snapshot_id: str) -> TPayload:
        return self._repository.resolve(snapshot_id)

    # ---- supersession helpers ---------------------------------------------

    def _supersede_current_for_axis(self, replacement: TPayload) -> None:
        replacement_id = self._payload_snapshot_id(replacement)
        replacement_axis = self._payload_axis_key(replacement)
        for snapshot in self._repository.list_snapshots():
            if (
                self._payload_snapshot_id(snapshot) != replacement_id
                and self._payload_axis_key(snapshot) == replacement_axis
                and self._payload_state(snapshot) is SnapshotLifecycleState.ACTIVE
            ):
                self._repository.save(
                    self._demote_to_superseded(snapshot, superseded_by=replacement_id)
                )

    def _latest_active_for_axis(self, snapshot: TPayload) -> TPayload | None:
        snapshot_id = self._payload_snapshot_id(snapshot)
        axis = self._payload_axis_key(snapshot)
        active = [
            candidate
            for candidate in self._repository.list_snapshots()
            if (
                self._payload_snapshot_id(candidate) != snapshot_id
                and self._payload_axis_key(candidate) == axis
                and self._payload_state(candidate) is SnapshotLifecycleState.ACTIVE
            )
        ]
        if not active:
            return None
        return max(
            active,
            key=lambda candidate: (
                self._payload_captured_at(candidate),
                self._payload_snapshot_id(candidate),
            ),
        )


class StatelessSnapshotService(ABC, Generic[TPayload]):
    """Append-only base for stateless snapshot services with per-call buckets.

    Subclasses inject a ``repository_factory`` that returns a fresh
    :class:`SnapshotRepository` for a given bucket id; each public verb
    accepts ``bucket_id`` and materialises the repository on demand. The
    per-bucket repository is responsible for storage layout and bucket
    isolation; the base provides the shared dedup, list, and resolve
    logic.

    Subclasses implement two hooks: ``_derive_snapshot_id`` and
    ``_build_payload``. ``_build_payload`` receives the resolved
    ``bucket_id`` so payload models can record it on the persisted
    record.
    """

    def __init__(
        self,
        *,
        repository_factory: Callable[[str], SnapshotRepository[TPayload]],
    ) -> None:
        self._repository_factory = repository_factory

    def _repository_for(self, bucket_id: str) -> SnapshotRepository[TPayload]:
        repository = self._repository_factory(bucket_id)
        if repository.bucket_id != bucket_id.strip():
            raise LiveApplicationInputError(
                f"snapshot repository for bucket_id={bucket_id!r} reported "
                f"bucket {repository.bucket_id!r}"
            )
        return repository

    @abstractmethod
    def _derive_snapshot_id(self, **kwargs: Any) -> str: ...

    @abstractmethod
    def _build_payload(
        self, *, snapshot_id: str, bucket_id: str, **kwargs: Any
    ) -> TPayload: ...

    def _capture_stateless(self, *, bucket_id: str, **kwargs: Any) -> TPayload:
        repository = self._repository_for(bucket_id)
        snapshot_id = self._derive_snapshot_id(**kwargs)
        if repository.exists(snapshot_id):
            return repository.load(snapshot_id)
        payload = self._build_payload(
            snapshot_id=snapshot_id, bucket_id=repository.bucket_id, **kwargs
        )
        repository.save(payload)
        return payload

    def list_snapshots(self, *, bucket_id: str) -> tuple[TPayload, ...]:
        return self._repository_for(bucket_id).list_snapshots()

    def resolve_snapshot(self, *, bucket_id: str, snapshot_id: str) -> TPayload:
        return self._repository_for(bucket_id).resolve(snapshot_id)


class JsonlSnapshotRepository(Generic[TPayload]):
    """Generic file-backed JSONL snapshot repository for one bucket.

    Structurally satisfies :class:`SnapshotRepository` so any stateless
    file-backed live service can adopt it without rewriting load/list/
    resolve/save. Storage layout is one JSONL file per bucket; callers
    inject the payload model class, the per-bucket storage-path resolver,
    and the not-found error factory so per-service exception class
    identities and CLI suggestion strings are preserved.

    The payload model must expose ``snapshot_id`` and ``bucket_id``
    attributes (every persisted live snapshot model in this codebase
    does); the repository validates the payload's ``bucket_id`` against
    the repository's bucket on save.
    """

    def __init__(
        self,
        *,
        bucket_id: str,
        payload_model: type[TPayload],
        storage_path: Callable[[str], Path],
        not_found_factory: Callable[[str], Exception],
        ambiguous_prefix_factory: Callable[[str, tuple[str, ...]], Exception],
        domain_label: str,
    ) -> None:
        trimmed = bucket_id.strip()
        if not trimmed:
            raise LiveApplicationInputError("bucket_id must not be blank")
        self._bucket_id = trimmed
        self._payload_model = payload_model
        self._storage_path = storage_path
        self._not_found_factory = not_found_factory
        self._ambiguous_prefix_factory = ambiguous_prefix_factory
        self._domain_label = domain_label

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def _read_all(self) -> list[TPayload]:
        path = self._storage_path(self._bucket_id)
        if not path.exists():
            return []
        return [
            self._payload_model.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _write_all(self, snapshots: list[TPayload]) -> None:
        path = self._storage_path(self._bucket_id)
        payload = "\n".join(s.model_dump_json() for s in snapshots)
        if payload:
            payload += "\n"
        path.write_text(payload, encoding="utf-8")

    def exists(self, snapshot_id: str) -> bool:
        return any(_snapshot_id_of(s) == snapshot_id for s in self._read_all())

    def load(self, snapshot_id: str) -> TPayload:
        for snapshot in self._read_all():
            if _snapshot_id_of(snapshot) == snapshot_id:
                return snapshot
        raise self._not_found_factory(snapshot_id)

    def list_snapshots(self) -> tuple[TPayload, ...]:
        return tuple(self._read_all())

    def resolve(self, snapshot_id: str) -> TPayload:
        matches = [
            s
            for s in self._read_all()
            if _snapshot_id_of(s) == snapshot_id or _snapshot_id_of(s).startswith(snapshot_id)
        ]
        if not matches:
            raise self._not_found_factory(snapshot_id)
        if len(matches) > 1:
            full_ids = tuple(sorted(_snapshot_id_of(s) for s in matches))
            raise self._ambiguous_prefix_factory(snapshot_id, full_ids)
        return matches[0]

    def save(self, snapshot: TPayload) -> None:
        snapshot_bucket = _bucket_id_of(snapshot)
        if snapshot_bucket != self._bucket_id:
            raise LiveApplicationInputError(
                f"{self._domain_label} snapshot bucket_id={snapshot_bucket!r} "
                f"does not match repository bucket {self._bucket_id!r}"
            )
        snapshot_id = _snapshot_id_of(snapshot)
        snapshots = self._read_all()
        for index, existing in enumerate(snapshots):
            if _snapshot_id_of(existing) == snapshot_id:
                snapshots[index] = snapshot
                self._write_all(snapshots)
                return
        snapshots.append(snapshot)
        self._write_all(snapshots)


def _snapshot_id_of(payload: BaseModel) -> str:
    snapshot_id = getattr(payload, "snapshot_id", None)
    if not isinstance(snapshot_id, str):
        raise LiveApplicationInputError(
            f"payload {type(payload).__name__} has no string snapshot_id attribute"
        )
    return snapshot_id


def _bucket_id_of(payload: BaseModel) -> str:
    bucket_id = getattr(payload, "bucket_id", None)
    if not isinstance(bucket_id, str):
        raise LiveApplicationInputError(
            f"payload {type(payload).__name__} has no string bucket_id attribute"
        )
    return bucket_id


__all__ = [
    "JsonlSnapshotRepository",
    "SnapshotLifecycleState",
    "SnapshotNotFoundError",
    "SnapshotRepository",
    "SnapshotService",
    "StatelessSnapshotService",
    "derive_snapshot_id_from_json",
    "enforce_snapshot_state_invariants",
]
