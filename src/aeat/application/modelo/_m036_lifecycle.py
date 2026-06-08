"""Typed contracts for the Modelo 036 declarative-recording verbs.

Per the 2026-05-16 amendment to
``cli-workflow-redesign-modelo-036-037-foundation-adr`` the local
app never files a 036. AEAT is the authority; the operator files
at sede. The verbs surfaced by ``aeat app modelo m036
{alta,modificacion,baja}`` are declarative recording — they
record that the operator filed at sede so downstream profile
state and stale-cascade logic can react.

This module defines the Pydantic command + result contracts the
verb handlers and downstream service implementations consume.
The service implementation lands in a follow-up commit per the
3-commit landing plan in
``2026-06-03-m036-lifecycle-verbs-research``.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage import LIVE_M036_DECLARATION_NAMESPACE
from ...core.identity import BucketId, ProfileId
from ...core.time import now
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
)
from ...domain.calculations.registry import CensoModeloEventKind


def derive_m036_declaration_id(
    *,
    profile_id: ProfileId,
    event_kind: CensoModeloEventKind,
    declared_on: date,
    sede_justificante: str | None,
) -> str:
    """Content-address the declaration tuple as 64-char lowercase SHA-256 hex.

    The address makes a replay of the same operator-declared filing
    idempotent: a second invocation with identical inputs hashes to
    the same ``declaration_id`` and the secure-object write becomes a
    no-op overwrite of the same row. ``sede_justificante`` is folded
    in unmangled (``"-"`` when omitted) so a same-day same-kind
    re-declaration that acquires the acuse is recorded as a distinct
    record, not silently coalesced with the pre-acuse draft.
    """
    canonical = "\x1f".join(
        [
            str(profile_id),
            event_kind.value,
            declared_on.isoformat(),
            sede_justificante if sede_justificante is not None else "-",
        ],
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class M036DeclarationCommand(BaseModel):
    """Operator request to record an M036 declaration filed at sede.

    The operator files the 036 with AEAT through the sede portal
    (or in person at an oficina). This command records that the
    declaration happened locally so the downstream stale-cascade
    + audit-trail logic can react. The command MUST NOT trigger
    any local filing action.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    profile_id: ProfileId
    event_kind: CensoModeloEventKind
    declared_on: date
    sede_justificante: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Optional AEAT acuse de recibo identifier emitted by sede for the filing.",
    )
    note: str | None = Field(default=None, max_length=512)


class M036DeclarationResult(BaseModel):
    """Outcome of a successful declaration-recording call.

    Carries the content-addressed declaration id (SHA-256 over the
    derived tuple), the canonical event-kind, the declared date, the
    bucket scope of the record, and the timestamp at which the local
    record was written. The ``bucket_id`` field bridges the storage
    cross-check `SecureSnapshotRepository` performs when loading and
    saving records (it refuses payloads whose bucket disagrees with the
    repository binding), per the M036-declaration-service Path A ADR
    decision. Downstream consumers (stale-cascade engine, profile-state
    re-derivation) read these fields to decide what to recompute.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    declaration_id: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
        description=(
            "SHA-256 hex content-address derived from (profile_id, event_kind, declared_on, sede_justificante)."
        ),
    )
    bucket_id: BucketId
    profile_id: ProfileId
    event_kind: CensoModeloEventKind
    declared_on: date
    sede_justificante: str | None = None
    recorded_at: datetime

    # SNAPSHOT-ID-ALIAS: ``SecureSnapshotRepository`` locates payloads by a
    # ``snapshot_id`` attribute. The M036 record's natural id is the typed
    # content-address ``declaration_id``; the runtime property exposes it
    # under the generic name without duplicating storage and without
    # round-tripping through the strict JSON envelope (computed-field
    # serialisation would emit a duplicate key the strict + extra="forbid"
    # load contract refuses on the symmetric model_validate_json).
    @property
    def snapshot_id(self) -> str:
        return self.declaration_id


_EVENT_KIND_TO_BUCKET_EVENT: dict[CensoModeloEventKind, BucketEventType] = {
    CensoModeloEventKind.ALTA: BucketEventType.CENSO_DECLARATION_ALTA,
    CensoModeloEventKind.MODIFICACION: BucketEventType.CENSO_DECLARATION_MODIFICACION,
    CensoModeloEventKind.BAJA: BucketEventType.CENSO_DECLARATION_BAJA,
}


def _m036_declaration_object_key(bucket_id: str, declaration_id: str) -> str:
    return f"m036-declaration:{bucket_id}:{declaration_id}"


def _m036_declaration_not_found(declaration_id: str) -> KeyError:
    return KeyError(f"M036 declaration {declaration_id!r} not found")


def _m036_declaration_ambiguous_prefix(declaration_id: str, full_ids: tuple[str, ...]) -> KeyError:
    return KeyError(f"M036 declaration prefix {declaration_id!r} is ambiguous; matches {list(full_ids)!r}")


def record_m036_declaration(
    command: M036DeclarationCommand,
    *,
    bucket_id: BucketId,
) -> M036DeclarationResult:
    """Persist an M036 declaration record + emit its BucketEvent atomically.

    Records that the operator filed an M036 declaration at sede.  The local
    app NEVER files; this verb only records the operator's declaration so
    downstream profile-state re-derivation and stale-cascade reasoning can
    react.  The content-addressed ``declaration_id`` keeps a re-declaration
    with the identical tuple idempotent; the parallel ``BucketEvent`` (one
    of :attr:`BucketEventType.CENSO_DECLARATION_ALTA` /
    :attr:`~.CENSO_DECLARATION_MODIFICACION` /
    :attr:`~.CENSO_DECLARATION_BAJA`) carries the audit-trail entry the
    composition-service rule requires alongside the data write, saved via the
    :class:`BucketEventHistoryRepository`.

    The persisted :class:`M036DeclarationResult` is encrypted into the
    bucket-local :data:`LIVE_M036_DECLARATION_NAMESPACE` row keyed by
    ``m036-declaration:<bucket_id>:<declaration_id>`` via the standard
    :class:`SecureSnapshotRepository` machinery.  ``bucket_id`` is checked
    against the repository binding at save time, so a cross-bucket payload
    cannot land silently.
    """
    # Local imports avoid the import cycle between this module (in
    # application.modelo) and SecureSnapshotRepository (in
    # application.live, which depends transitively on application.modelo
    # for the work-unit aggregations).
    from ..live import SecureSnapshotRepository

    declaration_id = derive_m036_declaration_id(
        profile_id=command.profile_id,
        event_kind=command.event_kind,
        declared_on=command.declared_on,
        sede_justificante=command.sede_justificante,
    )
    occurred_at = now()
    result = M036DeclarationResult(
        declaration_id=declaration_id,
        bucket_id=bucket_id,
        profile_id=command.profile_id,
        event_kind=command.event_kind,
        declared_on=command.declared_on,
        sede_justificante=command.sede_justificante,
        recorded_at=occurred_at,
    )

    repository = SecureSnapshotRepository(
        bucket_id=bucket_id,
        payload_model=M036DeclarationResult,
        namespace_definition=LIVE_M036_DECLARATION_NAMESPACE,
        object_key=_m036_declaration_object_key,
        not_found_factory=_m036_declaration_not_found,
        ambiguous_prefix_factory=_m036_declaration_ambiguous_prefix,
        domain_label="m036_declaration",
    )
    repository.save(result)

    event_type = _EVENT_KIND_TO_BUCKET_EVENT[command.event_kind]
    payload: dict[str, str] = {
        "profile_id": str(command.profile_id),
        "declared_on": command.declared_on.isoformat(),
    }
    if command.sede_justificante is not None:
        payload["sede_justificante"] = command.sede_justificante
    if command.note is not None:
        payload["note"] = command.note
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor="operator",
        object_type=BucketEventObjectType.PROFILE,
        object_id=declaration_id,
        payload=payload,
    )
    catalogue_repo = BucketEventHistoryRepository()
    next_catalogue = append_bucket_event(
        catalogue_repo.load(),
        BucketEvent(
            event_id=event_id,
            bucket_id=bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor="operator",
            object_type=BucketEventObjectType.PROFILE,
            object_id=declaration_id,
            payload_version=1,
            payload=payload,
        ),
    )
    catalogue_repo.save(next_catalogue)

    return result


__all__ = [
    "M036DeclarationCommand",
    "M036DeclarationResult",
    "derive_m036_declaration_id",
    "record_m036_declaration",
]
