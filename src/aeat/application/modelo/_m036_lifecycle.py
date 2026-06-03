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

from ...core.identity import BucketId, ProfileId
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
            "SHA-256 hex content-address derived from "
            "(profile_id, event_kind, declared_on, sede_justificante)."
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


__all__ = [
    "M036DeclarationCommand",
    "M036DeclarationResult",
    "derive_m036_declaration_id",
]
