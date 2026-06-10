"""Shared lifecycle base classes and helpers for live snapshot services.

This module factors the duplicated state-machine, supersession, and content-
addressed-id derivation logic shared across the bucket-scoped live snapshot
services (Borrador100, Censo, Expedientes, and Notifications). Each concrete
service writes and reads snapshot payloads through a :class:`SecureObjectRepository`
scoped to the active profile bucket.

Design notes:

* ``SnapshotLifecycleState`` carries the three operator-visible states all
  stateful snapshot services share. Every stateful service binds payload
  ``state`` directly to this enum.
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
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from ...adapters.persistence.storage import Envelope, SecureObjectNamespaceDefinition
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...adapters.persistence.storage.sql import SecureObjectRecord, SecureObjectRepository
from ...core.errors import AeatError
from ...core.time import now
from ._errors import LiveApplicationInputError


class SnapshotNotFoundError(AeatError, KeyError):
    """Shared base for per-service snapshot-lookup-miss errors.

    Inherits from both :class:`aeat.core.errors.AeatError` and
    :class:`KeyError` so the class is enrolled in the ``ERROR_REGISTRY``
    via the ``AeatError.__init_subclass__`` hook, and callers that catch
    the broad ``KeyError`` family remain unaffected. ``AeatError`` is
    listed first so MRO routes ``__init__`` through
    ``AeatError.__init__`` (which accepts the structured
    ``suggestion=`` / ``context=`` kwargs) rather than ``KeyError``'s
    C-level constructor.

    Per-service subclasses (BorradorSnapshotNotFoundError,
    ExpedientesSnapshotNotFoundError, NotificationsSnapshotNotFoundError,
    and future siblings) inherit from this base alongside
    :class:`aeat.core.errors.AeatError` so callers can either catch the
    domain-specific class name or the shared parent.
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


@runtime_checkable
class SnapshotRepository[TPayload: BaseModel](Protocol):
    """Structural contract for bucket-scoped snapshot persistence backends.

    Implementations may be SecureObjectRepository-backed (Borrador100, Censo)
    or file-system-backed (legacy stateless services).
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
    rules apply across Borrador100, Censo, and future stateful services.
    """
    discard_metadata_present = discarded_at is not None or bool(discarded_by) or bool(discard_reason)
    if state is SnapshotLifecycleState.ACTIVE:
        if has_supersession_pointer:
            raise LiveApplicationInputError("active snapshots cannot carry supersession pointers")
        if discard_metadata_present:
            raise LiveApplicationInputError("only discarded snapshots can carry discard metadata")
        return
    if state is SnapshotLifecycleState.SUPERSEDED:
        if not has_supersession_pointer:
            raise LiveApplicationInputError("superseded snapshots must carry superseded_by_snapshot_id")
        if discard_metadata_present:
            raise LiveApplicationInputError("only discarded snapshots can carry discard metadata")
        return
    # DISCARDED
    if has_supersession_pointer:
        raise LiveApplicationInputError("discarded snapshots cannot carry supersession pointers")
    if discarded_at is None or not discarded_by.strip():
        raise LiveApplicationInputError("discarded snapshots require discarded_at and discarded_by")


class SnapshotService[TPayload: BaseModel](ABC):
    """Abstract lifecycle service base for stateful bucket-scoped snapshots.

    Subclasses bind ``TPayload`` to their concrete Pydantic snapshot model and
    implement two hooks:

    * ``_payload_axis_key`` — returns a tuple identifying the domain axis on
      which prior ACTIVE snapshots are superseded (e.g. ``(modelo, year,
      period)`` for Borrador100, ``(profile_id,)`` for Censo).
    * ``_build_active_payload`` — constructs an ACTIVE snapshot from
      keyword-only capture arguments and a derived snapshot id.

    The ``capture`` template orchestrates dedup, auto-supersession of prior
    ACTIVE snapshots, and late-arrival demotion when a freshly-captured
    snapshot arrives older than the current ACTIVE on the same axis.
    """

    def __init__(self, *, bucket_id: str, repository: SnapshotRepository[TPayload]) -> None:
        if repository.bucket_id != bucket_id.strip():
            raise LiveApplicationInputError(
                f"snapshot service bucket_id={bucket_id!r} does not match repository bucket {repository.bucket_id!r}"
            )
        self._repository: SnapshotRepository[TPayload] = repository

    # ---- subclass hooks ----------------------------------------------------

    # KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH: abstract hook accepts **kwargs to
    # let concrete subclasses pass caller-specific arguments without a shared set.
    @abstractmethod
    def _derive_snapshot_id(self, **kwargs: Any) -> str:
        """Derive a content-addressed id from capture kwargs."""

    # KWARGS-ANY-RATIONALE-SNAPSHOT-PAYLOAD: abstract hook accepts **kwargs to
    # let concrete subclasses pass caller-specific arguments without a shared set.
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

    # KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH: template method threads
    # subclass-specific keyword arguments through the abstract hook contract;
    # concrete subclasses expose a typed wrapper that calls into this base.
    def _capture_with_lifecycle(self, **kwargs: Any) -> TPayload:
        """Template method: subclasses expose a typed ``capture`` wrapper.

        The base intentionally does not place ``capture`` on itself with
        ``**kwargs``. That would force every concrete subclass to either
        accept ``**kwargs`` (losing type safety on operator-visible
        signatures) or override ``capture`` with a narrower signature
        (LSP-violating). Renaming the base hook resolves the Liskov
        conflict while preserving the operator-facing keyword-only
        signatures on each service.
        """
        snapshot_id = self._derive_snapshot_id(**kwargs)
        if self._repository.exists(snapshot_id):
            return self._repository.load(snapshot_id)
        candidate = self._build_active_payload(snapshot_id=snapshot_id, **kwargs)
        active_snapshot = self._latest_active_for_axis(candidate)
        if active_snapshot is not None and self._payload_captured_at(active_snapshot) > self._payload_captured_at(
            candidate
        ):
            # Late-arriving capture: demote the incoming snapshot to SUPERSEDED.
            demoted = self._demote_to_superseded(candidate, superseded_by=self._payload_snapshot_id(active_snapshot))
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
                self._repository.save(self._demote_to_superseded(snapshot, superseded_by=replacement_id))

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


class StatelessSnapshotService[TPayload: BaseModel](ABC):
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
                f"snapshot repository for bucket_id={bucket_id!r} reported bucket {repository.bucket_id!r}"
            )
        return repository

    # KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH: abstract hook accepts **kwargs to
    # let concrete subclasses pass caller-specific arguments without a shared set.
    @abstractmethod
    def _derive_snapshot_id(self, **kwargs: Any) -> str: ...

    # KWARGS-ANY-RATIONALE-SNAPSHOT-PAYLOAD: abstract hook accepts **kwargs to
    # let concrete subclasses pass caller-specific arguments without a shared set.
    @abstractmethod
    def _build_payload(self, *, snapshot_id: str, bucket_id: str, **kwargs: Any) -> TPayload: ...

    # KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH: template method threads
    # subclass-specific keyword arguments through the abstract hook contract.
    def _capture_stateless(self, *, bucket_id: str, **kwargs: Any) -> TPayload:
        repository = self._repository_for(bucket_id)
        snapshot_id = self._derive_snapshot_id(**kwargs)
        if repository.exists(snapshot_id):
            return repository.load(snapshot_id)
        payload = self._build_payload(snapshot_id=snapshot_id, bucket_id=repository.bucket_id, **kwargs)
        repository.save(payload)
        return payload

    def list_snapshots(self, *, bucket_id: str) -> tuple[TPayload, ...]:
        return self._repository_for(bucket_id).list_snapshots()

    def resolve_snapshot(self, *, bucket_id: str, snapshot_id: str) -> TPayload:
        return self._repository_for(bucket_id).resolve(snapshot_id)


class SecureSnapshotRepository[TPayload: BaseModel]:
    """Generic secure-object snapshot repository for one runtime bucket.

    The repository preserves the :class:`SnapshotRepository` structural
    contract used by stateless live services while replacing one-file-per-
    bucket JSONL stores with encrypted secure-object rows. Each row is a
    typed :class:`Envelope` whose object key carries the bucket id and
    content-addressed snapshot id.
    """

    def __init__(
        self,
        *,
        bucket_id: str,
        payload_model: type[TPayload],
        namespace_definition: SecureObjectNamespaceDefinition,
        object_key: Callable[[str, str], str],
        not_found_factory: Callable[[str], Exception],
        ambiguous_prefix_factory: Callable[[str, tuple[str, ...]], Exception],
        domain_label: str,
        objects: SecureObjectRepository | None = None,
    ) -> None:
        trimmed = bucket_id.strip()
        if not trimmed:
            raise LiveApplicationInputError("bucket_id must not be blank")
        self._bucket_id = trimmed
        self._payload_model = payload_model
        self._namespace_definition = namespace_definition
        self._object_key = object_key
        self._not_found_factory = not_found_factory
        self._ambiguous_prefix_factory = ambiguous_prefix_factory
        self._domain_label = domain_label
        self._objects = objects if objects is not None else secure_object_repository_for_bucket(trimmed)

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self, snapshot_id: str) -> bool:
        return self._objects.exists(
            self._namespace_definition.namespace,
            self._object_key(self._bucket_id, snapshot_id),
        )

    def load(self, snapshot_id: str) -> TPayload:
        record = self._objects.load(
            self._namespace_definition.namespace,
            self._object_key(self._bucket_id, snapshot_id),
            expected_class=self._namespace_definition.sensitivity,
            max_supported_version=self._namespace_definition.schema_version,
        )
        if record is None:
            raise self._not_found_factory(snapshot_id)
        snapshot = self._snapshot_from_record(record, requested_snapshot_id=snapshot_id)
        if _bucket_id_of(snapshot) != self._bucket_id:
            raise LiveApplicationInputError(
                f"{self._domain_label} snapshot bucket_id={_bucket_id_of(snapshot)!r} "
                f"does not match repository bucket {self._bucket_id!r}"
            )
        if _snapshot_id_of(snapshot) != snapshot_id:
            raise LiveApplicationInputError(
                f"{self._domain_label} snapshot id={_snapshot_id_of(snapshot)!r} "
                f"does not match requested snapshot {snapshot_id!r}"
            )
        return snapshot

    def list_snapshots(self) -> tuple[TPayload, ...]:
        snapshots: list[TPayload] = []
        for record in self._objects.list_records(
            self._namespace_definition.namespace,
            expected_class=self._namespace_definition.sensitivity,
            max_supported_version=self._namespace_definition.schema_version,
        ):
            snapshot = self._snapshot_from_record(record)
            snapshot_bucket = _bucket_id_of(snapshot)
            if snapshot_bucket != self._bucket_id:
                raise LiveApplicationInputError(
                    f"{self._domain_label} snapshot bucket_id={snapshot_bucket!r} "
                    f"does not match repository bucket {self._bucket_id!r}",
                    translated_message="application.live.snapshot_base.errors.snapshot_bucket_mismatch",
                    context={
                        "domain_label": self._domain_label,
                        "snapshot_bucket": snapshot_bucket,
                        "repository_bucket": self._bucket_id,
                    },
                )
            snapshots.append(snapshot)
        return tuple(sorted(snapshots, key=lambda item: _snapshot_id_of(item)))

    def resolve(self, snapshot_id: str) -> TPayload:
        trimmed_snapshot_id = snapshot_id.strip()
        if not trimmed_snapshot_id:
            raise LiveApplicationInputError("snapshot_id must not be blank")
        matches = [
            snapshot
            for snapshot in self.list_snapshots()
            if _snapshot_id_of(snapshot) == trimmed_snapshot_id
            or _snapshot_id_of(snapshot).startswith(trimmed_snapshot_id)
        ]
        if not matches:
            raise self._not_found_factory(snapshot_id)
        if len(matches) > 1:
            full_ids = tuple(sorted(_snapshot_id_of(snapshot) for snapshot in matches))
            raise self._ambiguous_prefix_factory(snapshot_id, full_ids)
        return matches[0]

    def save(self, snapshot: TPayload) -> None:
        snapshot_bucket = _bucket_id_of(snapshot)
        if snapshot_bucket != self._bucket_id:
            raise LiveApplicationInputError(
                f"{self._domain_label} snapshot bucket_id={snapshot_bucket!r} "
                f"does not match repository bucket {self._bucket_id!r}"
            )
        envelope = self._envelope_cls()(
            schema_version=self._namespace_definition.schema_version,
            written_at=now(),
            classification=self._namespace_definition.sensitivity,
            payload=snapshot,
        )
        self._objects.save(
            namespace=self._namespace_definition.namespace,
            object_key=self._object_key(self._bucket_id, _snapshot_id_of(snapshot)),
            classification=self._namespace_definition.sensitivity,
            schema_version=self._namespace_definition.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

    def _snapshot_from_record(
        self,
        record: SecureObjectRecord,
        requested_snapshot_id: str | None = None,
    ) -> TPayload:
        envelope = self._envelope_cls().model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not self._namespace_definition.sensitivity:
            snapshot_label = requested_snapshot_id or _snapshot_id_of(envelope.payload)
            raise ClassificationError(
                f"{self._domain_label} snapshot {snapshot_label!r} has classification "
                f"{envelope.classification}; consumer expected {self._namespace_definition.sensitivity}",
            )
        if envelope.schema_version > self._namespace_definition.schema_version:
            snapshot_label = requested_snapshot_id or _snapshot_id_of(envelope.payload)
            raise EnvelopeVersionError(
                f"{self._domain_label} snapshot {snapshot_label!r} is at version "
                f"{envelope.schema_version}; consumer supports up to "
                f"{self._namespace_definition.schema_version}",
            )
        return envelope.payload

    def _envelope_cls(self) -> type[Envelope[TPayload]]:
        return Envelope.for_payload_type(self._payload_model)


def _snapshot_id_of(payload: BaseModel) -> str:
    snapshot_id = getattr(payload, "snapshot_id", None)
    if not isinstance(snapshot_id, str):
        raise LiveApplicationInputError(f"payload {type(payload).__name__} has no string snapshot_id attribute")
    return snapshot_id


def _bucket_id_of(payload: BaseModel) -> str:
    bucket_id = getattr(payload, "bucket_id", None)
    if not isinstance(bucket_id, str):
        raise LiveApplicationInputError(f"payload {type(payload).__name__} has no string bucket_id attribute")
    return bucket_id


__all__ = [
    "SecureSnapshotRepository",
    "SnapshotLifecycleState",
    "SnapshotNotFoundError",
    "SnapshotRepository",
    "SnapshotService",
    "StatelessSnapshotService",
    "derive_snapshot_id_from_json",
    "enforce_snapshot_state_invariants",
]
