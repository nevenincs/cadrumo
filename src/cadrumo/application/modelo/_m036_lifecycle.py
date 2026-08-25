"""Modelo 036 declarative-recording contracts, storage, and event emission.

Per the accepted Modelo 036/037 foundation decision, the local app never files a
036. AEAT is the authority; the operator files the declaration through AEAT Sede or in person at
a competent AEAT office, then records that fact locally through ``aeat app modelo m036
{alta,modificacion,baja}``. This module owns the typed application service behind
that surface: it persists encrypted
:data:`~cadrumo.adapters.persistence.storage.LIVE_M036_DECLARATION_NAMESPACE` rows,
emits the matching ``modelo.036.declaration.*`` bucket event, and exposes the
same :class:`~cadrumo.adapters.persistence.profile.snapshots.SecureSnapshotRepository` path for list/view
read-back.

The closed event-kind axis comes from
:class:`~cadrumo.domain.calculations.registry.CensoModeloEventKind`, whose values are
derived from the registry-owned censo foundation. Modelo 037 remains historical
metadata and is intentionally outside this recording surface.

See Also:
    :mod:`cadrumo.domain.calculations.registry.censo_modelos`
        Registry-owned Modelo 036 active-foundation and Modelo 037 historical
        routing.
    :mod:`cadrumo.entrypoints.cli._modelo_m036_cli`
        Thin Typer boundary that turns CLI verbs into these application commands.
    :class:`cadrumo.domain.buckets.BucketEventType`
        Declares the ``CENSO_DECLARATION_ALTA``,
        ``CENSO_DECLARATION_MODIFICACION``, and ``CENSO_DECLARATION_BAJA`` audit
        events emitted here.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.storage import LIVE_M036_DECLARATION_NAMESPACE
from ...core import STRICT_FROZEN_CONFIG
from ...core.hashing import sha256_hex
from ...core.identity import BucketId, ContentDigest, ProfileId
from ...core.time import now
from ...domain.buckets import (
    BucketEventObjectType,
    BucketEventType,
    bucket_event_history_write,
    build_bucket_event,
)
from ...domain.calculations.registry import CensoModeloEventKind
from ...domain.modelos import Modelo036PriorAltaRequiredError, Modelo036TerminalStateError

if TYPE_CHECKING:
    from ...adapters.persistence.profile.snapshots import SecureSnapshotRepository


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

    The ``event_kind`` member is a
    :class:`~cadrumo.domain.calculations.registry.CensoModeloEventKind`, so the
    digest can only describe one of the registry-backed ``alta``,
    ``modificacion``, or ``baja`` lifecycle events.
    """
    canonical = "\x1f".join(
        [
            str(profile_id),
            event_kind.value,
            declared_on.isoformat(),
            sede_justificante if sede_justificante is not None else "-",
        ],
    )
    return sha256_hex(canonical.encode("utf-8"))


class M036DeclarationCommand(BaseModel):
    """Operator request to record an M036 declaration already filed with AEAT.

    The operator files the 036 through AEAT Sede or in person at a competent
    AEAT office. This command records that declaration locally so the
    downstream stale-cascade + audit-trail logic can react. The optional
    ``sede_justificante`` records an electronic AEAT receipt when available;
    its absence does not prevent recording an office filing. The command MUST
    NOT trigger any local filing action.

    ``event_kind`` is typed as
    :class:`~cadrumo.domain.calculations.registry.CensoModeloEventKind`, preserving
    the registry foundation's closed event set at the application boundary.
    """

    model_config = STRICT_FROZEN_CONFIG

    profile_id: ProfileId
    event_kind: CensoModeloEventKind
    declared_on: date
    sede_justificante: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description=(
            "Optional electronic AEAT justificante identifier; omit it for an office filing or when unavailable."
        ),
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
    repository binding). Downstream consumers (stale-cascade engine, profile-state
    re-derivation) read these fields to decide what to recompute.

    The record is the payload model for
    :class:`~cadrumo.adapters.persistence.profile.snapshots.SecureSnapshotRepository` rows stored under
    :data:`~cadrumo.adapters.persistence.storage.LIVE_M036_DECLARATION_NAMESPACE`.
    """

    model_config = STRICT_FROZEN_CONFIG

    declaration_id: ContentDigest = Field(
        description=(
            "SHA-256 hex content-address derived from (profile_id, event_kind, declared_on, sede_justificante)."
        ),
    )
    bucket_id: BucketId
    profile_id: ProfileId
    event_kind: CensoModeloEventKind
    declared_on: date
    sede_justificante: str | None = None
    note: str | None = Field(default=None, max_length=512)
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


#: Payload version this declaration's audit event has always persisted. Held at
#: 1 deliberately: the modelo-wide builder supplies 2, and re-versioning a
#: persisted audit contract is a separate decision from co-committing the event.
_M036_BUCKET_EVENT_PAYLOAD_VERSION = 1

_EVENT_KIND_TO_BUCKET_EVENT: dict[CensoModeloEventKind, BucketEventType] = {
    CensoModeloEventKind.ALTA: BucketEventType.CENSO_DECLARATION_ALTA,
    CensoModeloEventKind.MODIFICACION: BucketEventType.CENSO_DECLARATION_MODIFICACION,
    CensoModeloEventKind.BAJA: BucketEventType.CENSO_DECLARATION_BAJA,
}


def m036_declaration_object_key(bucket_id: str, declaration_id: str) -> str:
    return f"m036-declaration:{bucket_id}:{declaration_id}"


def _m036_declaration_not_found(declaration_id: str) -> KeyError:
    return KeyError(f"M036 declaration {declaration_id!r} not found")


def _m036_declaration_ambiguous_prefix(declaration_id: str, full_ids: tuple[str, ...]) -> KeyError:
    return KeyError(f"M036 declaration prefix {declaration_id!r} is ambiguous; matches {list(full_ids)!r}")


def _m036_declaration_repository(bucket_id: BucketId) -> SecureSnapshotRepository[M036DeclarationResult]:
    """Build the single secure-object repository the write and read paths share.

    Both :func:`record_m036_declaration` (write) and the read-back surface
    (:func:`list_m036_declarations` / :func:`read_m036_declaration`) route
    through this one factory so there is no parallel read path: the
    :class:`SecureSnapshotRepository` it returns owns the encrypted
    :data:`LIVE_M036_DECLARATION_NAMESPACE` rows keyed by
    ``m036-declaration:<bucket_id>:<declaration_id>``.
    """
    # The repository class itself is adapter-side and imports nothing from
    # application, so it needs no deferral. The error class still does: it is
    # owned by application.live, which depends transitively on this package for
    # the work-unit aggregations.
    from ...adapters.persistence.profile.snapshots import SecureSnapshotRepository
    from ..live.errors import LiveApplicationInputError

    return SecureSnapshotRepository(
        bucket_id=bucket_id,
        payload_model=M036DeclarationResult,
        namespace_definition=LIVE_M036_DECLARATION_NAMESPACE,
        object_key=m036_declaration_object_key,
        not_found_factory=_m036_declaration_not_found,
        ambiguous_prefix_factory=_m036_declaration_ambiguous_prefix,
        domain_label="m036_declaration",
        input_error_cls=LiveApplicationInputError,
    )


def list_m036_declarations(*, bucket_id: BucketId) -> tuple[M036DeclarationResult, ...]:
    """Return every recorded M036 declaration in the active bucket.

    Reads through the same :class:`SecureSnapshotRepository` the write path
    persists into (no parallel read path), enumerating the encrypted
    :data:`LIVE_M036_DECLARATION_NAMESPACE` rows scoped to ``bucket_id`` and
    returning the typed :class:`M036DeclarationResult` records verbatim —
    every persisted field (``declaration_id``, ``event_kind``, ``declared_on``,
    ``recorded_at``, ``sede_justificante``, ``note``) is preserved, never
    collapsed to a flat mapping. An empty bucket returns an empty tuple, the
    clean "no declarations recorded yet" signal, not an error.

    See Also:
        :func:`read_m036_declaration`
        :func:`record_m036_declaration`
    """
    return _m036_declaration_repository(bucket_id).list_snapshots()


def read_m036_declaration(declaration_id: str, *, bucket_id: BucketId) -> M036DeclarationResult:
    """Return one recorded M036 declaration by id or unambiguous prefix.

    Reads through the owning :class:`SecureSnapshotRepository`, resolving the
    full content-addressed ``declaration_id`` or an unambiguous prefix of it
    to a single typed :class:`M036DeclarationResult`. Raises the repository's
    not-found error for an unknown id and the ambiguous-prefix error when a
    prefix matches more than one record, mirroring the established
    secure-object id-or-prefix resolution.

    See Also:
        :func:`list_m036_declarations`
        :class:`~cadrumo.adapters.persistence.profile.snapshots.SecureSnapshotRepository`
    """
    return _m036_declaration_repository(bucket_id).resolve(declaration_id)


def _require_profile_owns_bucket(*, profile_id: ProfileId, bucket_id: BucketId) -> None:
    """Refuse a declaration whose command profile does not name ``bucket_id``.

    A bucket identity is the profile UUID that owns the storage container, so
    the command's profile and the target bucket are two spellings of one
    identity. Without this gate the two diverge silently and each downstream
    consumer picks a different one: ``declaration_id`` and the event payload are
    derived from ``command.profile_id`` while the stored row and the event scope
    are keyed by ``bucket_id``. The repository cross-check only compares the
    result's own ``bucket_id`` against its binding, so it cannot see that the
    profile identity travelling inside the payload names someone else -- a
    profile-B declaration lands in bucket A and A's history claims B filed it.

    Both values are compared in their canonical stripped form, matching the
    :data:`~cadrumo.core.identity.BucketId` and
    :data:`~cadrumo.core.identity.ProfileId` boundary constraints, so
    surrounding whitespace cannot manufacture a mismatch or hide one.
    """
    from ..live.errors import LiveApplicationInputError

    canonical_profile = str(profile_id).strip()
    canonical_bucket = str(bucket_id).strip()
    if canonical_profile != canonical_bucket:
        raise LiveApplicationInputError(
            translated_message="application.modelo.errors.m036_declaration_profile_bucket_mismatch",
            context={
                "profile_id": canonical_profile,
                "bucket_id": canonical_bucket,
                "owns_bucket": False,
            },
        )


def _latest_m036_declaration(
    declarations: tuple[M036DeclarationResult, ...],
) -> M036DeclarationResult | None:
    """Return the chronologically latest declaration, or ``None`` when there are none.

    Ordered by ``declared_on`` (the AEAT-facing filing date) with
    ``recorded_at`` as the tiebreak for two declarations filed the same day,
    matching the read order an operator reviewing their own filing history
    would use.
    """
    if not declarations:
        return None
    return max(declarations, key=lambda d: (d.declared_on, d.recorded_at))


def _require_m036_sequence_valid(
    *,
    command: M036DeclarationCommand,
    declaration_id: str,
    existing: tuple[M036DeclarationResult, ...],
) -> None:
    """Refuse a declaration that violates the alta / modificación / baja ordering.

    AEAT's Modelo 036 is event-triggered: ``modificacion`` and ``baja`` amend
    or close a registration that has to already exist, and ``baja`` is
    terminal — nothing more is recorded against a deregistered taxpayer
    until a fresh ``alta`` opens a new registration, which is exactly what a
    record already in a terminal state refuses (:class:`Modelo036TerminalStateError`
    covers every event kind, ``alta`` included, once the latest declaration is
    a ``baja``).

    An exact repeat of an already-recorded declaration (same content-address)
    is exempted rather than refused: :func:`record_m036_declaration` derives
    ``declaration_id`` so a retry of the identical tuple is idempotent, and a
    retry is not a new transition to validate against the sequence.
    """
    if any(existing_declaration.declaration_id == declaration_id for existing_declaration in existing):
        return
    latest = _latest_m036_declaration(existing)
    if latest is not None and latest.event_kind is CensoModeloEventKind.BAJA:
        raise Modelo036TerminalStateError(
            f"m036 declaration_id={declaration_id!r} refused: prior declaration "
            f"{latest.declaration_id!r} is a terminal baja",
            context={
                "declaration_id": declaration_id,
                "prior_declaration_id": latest.declaration_id,
                "requested_event_kind": command.event_kind.value,
            },
        )
    if latest is None and command.event_kind is not CensoModeloEventKind.ALTA:
        raise Modelo036PriorAltaRequiredError(
            f"m036 declaration_id={declaration_id!r} refused: no prior alta on record for {command.event_kind.value!r}",
            context={
                "declaration_id": declaration_id,
                "requested_event_kind": command.event_kind.value,
            },
        )


def record_m036_declaration(
    command: M036DeclarationCommand,
    *,
    bucket_id: BucketId,
) -> M036DeclarationResult:
    """Persist an M036 declaration record and emit its BucketEvent.

    Records an M036 declaration already filed through AEAT Sede or in person
    at a competent AEAT office. The local app NEVER files; this verb only
    records the operator's declaration so downstream profile-state
    re-derivation and stale-cascade reasoning can react. An optional
    ``sede_justificante`` records electronic receipt evidence, so its absence
    does not prevent recording an office filing. The content-addressed
    ``declaration_id`` keeps a re-declaration with the identical tuple
    idempotent; the parallel ``BucketEvent`` (one of
    :attr:`BucketEventType.CENSO_DECLARATION_ALTA` /
    :attr:`~.CENSO_DECLARATION_MODIFICACION` /
    :attr:`~.CENSO_DECLARATION_BAJA`) carries the audit-trail entry the
    composition-service rule requires alongside the data write, saved via the
    :class:`BucketEventHistoryRepository`.

    The persisted :class:`M036DeclarationResult` is encrypted into the
    bucket-local :data:`LIVE_M036_DECLARATION_NAMESPACE` row keyed by
    ``m036-declaration:<bucket_id>:<declaration_id>`` via the standard
    :class:`SecureSnapshotRepository` machinery (shared with the
    :func:`list_m036_declarations` / :func:`read_m036_declaration` read-back
    surface through :func:`_m036_declaration_repository`).  ``bucket_id`` is
    checked against the repository binding at save time, so a cross-bucket
    payload cannot land silently.

    Args:
        command: The declaration command naming the profile, event kind,
            declared-on date, and optional electronic justificante.
        bucket_id: The bucket to persist into; checked against
            ``command.profile_id`` before anything is derived or stored.

    Raises:
        LiveApplicationInputError: If ``command.profile_id`` names a different
            profile than ``bucket_id``. A bucket identity IS the profile UUID
            that owns it, so the two must agree before anything is derived,
            stored, or emitted.
        Modelo036PriorAltaRequiredError: If ``modificacion`` or ``baja`` is
            requested with no declaration on record yet. Checked, and
            refused, before anything is derived, stored or emitted.
        Modelo036TerminalStateError: If the latest recorded declaration is
            already a ``baja`` — a terminal state no further declaration
            (``alta`` included) may follow. Checked, and refused, before
            anything is derived, stored or emitted.

    See Also:
        :class:`~cadrumo.domain.calculations.registry.CensoModeloEventKind`
        :class:`cadrumo.domain.buckets.BucketEventType`
        :data:`~cadrumo.adapters.persistence.storage.LIVE_M036_DECLARATION_NAMESPACE`
    """
    _require_profile_owns_bucket(profile_id=command.profile_id, bucket_id=bucket_id)
    declaration_id = derive_m036_declaration_id(
        profile_id=command.profile_id,
        event_kind=command.event_kind,
        declared_on=command.declared_on,
        sede_justificante=command.sede_justificante,
    )
    _require_m036_sequence_valid(
        command=command,
        declaration_id=declaration_id,
        existing=list_m036_declarations(bucket_id=bucket_id),
    )
    occurred_at = now()
    result = M036DeclarationResult(
        declaration_id=declaration_id,
        bucket_id=bucket_id,
        profile_id=command.profile_id,
        event_kind=command.event_kind,
        declared_on=command.declared_on,
        sede_justificante=command.sede_justificante,
        note=command.note,
        recorded_at=occurred_at,
    )

    event_type = _EVENT_KIND_TO_BUCKET_EVENT[command.event_kind]
    payload: dict[str, str] = {
        "profile_id": str(command.profile_id),
        "declared_on": command.declared_on.isoformat(),
    }
    if command.sede_justificante is not None:
        payload["sede_justificante"] = command.sede_justificante
    if command.note is not None:
        payload["note"] = command.note
    # Built through the shared derive helper rather than a local
    # derive_bucket_event_id + BucketEvent construction, which was a fourth copy
    # of that shape. The domain-level builder is used rather than the modelo
    # wrapper because this event persists payload_version=1: the wrapper
    # supplies the modelo-wide version 2, and silently re-versioning a persisted
    # audit contract is not part of closing this finding.
    declaration_event = build_bucket_event(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor="operator",
        object_type=BucketEventObjectType.PROFILE,
        object_id=declaration_id,
        payload=payload,
        payload_version=_M036_BUCKET_EVENT_PAYLOAD_VERSION,
    )
    # One unit of work: the declaration snapshot and its audit event. Saved
    # first and emitted afterwards, an event-storage failure left the M036
    # declaration durable with nothing in the history accounting for it.
    _m036_declaration_repository(bucket_id).save_with_secure_object_writes(
        result,
        (bucket_event_history_write(BucketEventHistoryRepository(), (declaration_event,)),),
    )

    return result


__all__ = [
    "M036DeclarationCommand",
    "M036DeclarationResult",
    "derive_m036_declaration_id",
    "list_m036_declarations",
    "read_m036_declaration",
    "record_m036_declaration",
]
