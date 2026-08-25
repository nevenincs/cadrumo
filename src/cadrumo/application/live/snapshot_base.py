"""Shared lifecycle base classes and helpers for live snapshot services.

This module factors the duplicated state-machine, supersession, and content-
addressed-id derivation logic shared across the bucket-scoped live snapshot
services (Borrador100, Censo, Expedientes, and Notifications). Each concrete
service writes and reads snapshot payloads through a ``SnapshotRepository``
scoped to the active profile bucket.

This module declares the PORT and the lifecycle bases only. The encrypted
secure-object backend that satisfies the port lives in the persistence adapter,
as ``adapters.persistence.profile.snapshots.SecureSnapshotRepository``, so the
storage coupling is an adapter-internal edge rather than an application-layer
reach outward.

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

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from ...core.errors import CadrumoError
from .errors import LiveApplicationInputError


class SnapshotNotFoundError(CadrumoError, KeyError):
    """Shared base for per-service snapshot-lookup-miss errors.

    Inherits from both :class:`cadrumo.core.errors.CadrumoError` and
    :class:`KeyError` so the class is enrolled in the ``ERROR_REGISTRY``
    via the ``CadrumoError.__init_subclass__`` hook while preserving the
    mapping-style lookup-miss type. ``CadrumoError`` is listed first so MRO
    routes ``__init__`` through
    ``CadrumoError.__init__`` (which accepts the structured
    ``context=`` / ``translated_message=`` kwargs) rather than ``KeyError``'s
    C-level constructor.

    Per-service subclasses (BorradorSnapshotNotFoundError,
    ExpedientesSnapshotNotFoundError, NotificationsSnapshotNotFoundError,
    and future siblings) inherit from this base alongside
    :class:`cadrumo.core.errors.CadrumoError` so callers can either catch the
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


class SnapshotStateFilter(StrEnum):
    """Operator-facing filter over :class:`SnapshotLifecycleState`, plus ``ALL``.

    ``ALL`` is deliberately NOT a member of :class:`SnapshotLifecycleState`. No
    persisted snapshot is ever *in* an "all" state, so adding it there would give
    every exhaustive match over the lifecycle a branch that cannot occur and would
    let a stored record claim a state that means "no filter". The filter is its own
    closed axis that maps onto the lifecycle, mirroring
    :class:`~application.review.ReviewState`.

    Every lifecycle state has a member here, so a filter exists for each; the
    correspondence is enforced by a gate rather than left to the next author.
    """

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DISCARDED = "discarded"
    ALL = "all"

    def as_lifecycle_state(self) -> SnapshotLifecycleState | None:
        """Return the lifecycle state to filter on, or ``None`` for no filter."""
        if self is SnapshotStateFilter.ALL:
            return None
        return SnapshotLifecycleState(self.value)


@runtime_checkable
class SnapshotRepository[TPayload: BaseModel](Protocol):
    """Structural contract for bucket-scoped snapshot persistence backends.

    Implementations may be SecureObjectRepository-backed (Borrador100, Censo)
    or file-system-backed (stateless services).
    """

    @property
    def bucket_id(self) -> str:
        """Execute this public contract operation."""
        ...

    def exists(self, snapshot_id: str) -> bool:
        """Execute this public contract operation."""
        ...

    def load(self, snapshot_id: str) -> TPayload:
        """Execute this public contract operation."""
        ...

    def list_snapshots(self) -> tuple[TPayload, ...]:
        """Execute this public contract operation."""
        ...

    def resolve(self, snapshot_id: str) -> TPayload:
        """Execute this public contract operation."""
        ...

    def save(self, snapshot: TPayload) -> None:
        """Execute this public contract operation."""
        ...


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
            raise LiveApplicationInputError(
                translated_message="application.live.snapshot_base.errors.state_active_supersession_pointer",
                context={"state": state.value, "has_supersession_pointer": True},
            )
        if discard_metadata_present:
            raise LiveApplicationInputError(
                translated_message="application.live.snapshot_base.errors.state_discard_metadata_forbidden",
                context={"state": state.value, "discard_metadata_present": True},
            )
        return
    if state is SnapshotLifecycleState.SUPERSEDED:
        if not has_supersession_pointer:
            raise LiveApplicationInputError(
                translated_message="application.live.snapshot_base.errors.state_supersession_pointer_required",
                context={"state": state.value, "has_supersession_pointer": False},
            )
        if discard_metadata_present:
            raise LiveApplicationInputError(
                translated_message="application.live.snapshot_base.errors.state_discard_metadata_forbidden",
                context={"state": state.value, "discard_metadata_present": True},
            )
        return
    # DISCARDED
    if has_supersession_pointer:
        raise LiveApplicationInputError(
            translated_message="application.live.snapshot_base.errors.state_discarded_supersession_pointer",
            context={"state": state.value, "has_supersession_pointer": True},
        )
    if discarded_at is None or not discarded_by.strip():
        raise LiveApplicationInputError(
            translated_message="application.live.snapshot_base.errors.state_discard_audit_required",
            context={
                "state": state.value,
                "has_discarded_at": discarded_at is not None,
                "has_discarded_by": bool(discarded_by.strip()),
            },
        )


class SnapshotService[TPayload: BaseModel, TCapture: BaseModel](ABC):
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
        """Initialize this public contract."""
        if repository.bucket_id != bucket_id.strip():
            raise LiveApplicationInputError(
                translated_message="application.live.snapshot_base.errors.service_bucket_mismatch",
                context={
                    "requested_bucket_id": bucket_id.strip(),
                    "repository_bucket_id": repository.bucket_id,
                },
            )
        self._repository: SnapshotRepository[TPayload] = repository

    # ---- subclass hooks ----------------------------------------------------

    @abstractmethod
    def _derive_snapshot_id(self, capture: TCapture) -> str:
        """Derive a content-addressed id from a typed capture request."""

    @abstractmethod
    def _build_active_payload(self, *, snapshot_id: str, capture: TCapture) -> TPayload:
        """Construct an ACTIVE snapshot payload for fresh captures."""

    @abstractmethod
    def _payload_axis_key(self, payload: TPayload) -> tuple[object, ...]:
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

    def _capture_with_lifecycle(self, capture: TCapture) -> TPayload:
        """Template method: subclasses expose a typed ``capture`` wrapper.

        The base intentionally does not place ``capture`` on itself with
        ``**kwargs``. That would force every concrete subclass to either
        accept ``**kwargs`` (losing type safety on operator-visible
        signatures) or override ``capture`` with a narrower signature
        (LSP-violating). Renaming the base hook resolves the Liskov
        conflict while preserving the operator-facing keyword-only
        signatures on each service.
        """
        snapshot_id = self._derive_snapshot_id(capture)
        if self._repository.exists(snapshot_id):
            return self._repository.load(snapshot_id)
        candidate = self._build_active_payload(snapshot_id=snapshot_id, capture=capture)
        active_snapshot = self._latest_active_for_axis(candidate)
        if active_snapshot is not None and self._payload_captured_at(active_snapshot) > self._payload_captured_at(
            candidate,
        ):
            # Late-arriving capture: demote the incoming snapshot to SUPERSEDED.
            demoted = self._demote_to_superseded(candidate, superseded_by=self._payload_snapshot_id(active_snapshot))
            self._repository.save(demoted)
            return demoted
        self._supersede_current_for_axis(candidate)
        self._repository.save(candidate)
        return candidate

    def list_snapshots(self) -> tuple[TPayload, ...]:
        """Execute this public contract operation."""
        return self._repository.list_snapshots()

    def resolve_snapshot(self, snapshot_id: str) -> TPayload:
        """Execute this public contract operation."""
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


class StatelessSnapshotService[TPayload: BaseModel, TCapture: BaseModel](ABC):
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
        """Initialize this public contract."""
        self._repository_factory = repository_factory

    def _repository_for(self, bucket_id: str) -> SnapshotRepository[TPayload]:
        repository = self._repository_factory(bucket_id)
        if repository.bucket_id != bucket_id.strip():
            raise LiveApplicationInputError(
                translated_message="application.live.snapshot_base.errors.repository_bucket_mismatch",
                context={
                    "requested_bucket_id": bucket_id.strip(),
                    "repository_bucket_id": repository.bucket_id,
                },
            )
        return repository

    @abstractmethod
    def _derive_snapshot_id(self, capture: TCapture) -> str: ...

    @abstractmethod
    def _build_payload(self, *, snapshot_id: str, bucket_id: str, capture: TCapture) -> TPayload: ...

    def _capture_stateless(self, *, bucket_id: str, capture: TCapture) -> TPayload:
        repository = self._repository_for(bucket_id)
        snapshot_id = self._derive_snapshot_id(capture)
        if repository.exists(snapshot_id):
            return repository.load(snapshot_id)
        payload = self._build_payload(snapshot_id=snapshot_id, bucket_id=repository.bucket_id, capture=capture)
        repository.save(payload)
        return payload

    def list_snapshots(self, *, bucket_id: str) -> tuple[TPayload, ...]:
        """Execute this public contract operation."""
        return self._repository_for(bucket_id).list_snapshots()

    def resolve_snapshot(self, *, bucket_id: str, snapshot_id: str) -> TPayload:
        """Execute this public contract operation."""
        return self._repository_for(bucket_id).resolve(snapshot_id)


__all__ = [
    "SnapshotLifecycleState",
    "SnapshotNotFoundError",
    "SnapshotRepository",
    "SnapshotService",
    "SnapshotStateFilter",
    "StatelessSnapshotService",
    "enforce_snapshot_state_invariants",
]
