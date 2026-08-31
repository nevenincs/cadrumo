"""Bucket-scoped append-only event records.

A :class:`BucketEvent` captures one material workflow transition
inside a bucket. Events are immutable, content-addressed by their
(bucket_id, event_type, occurred_at, actor, object_type, object_id,
payload) tuple, and grouped into a frozen catalogue.

The closed :class:`BucketEventType` enum fixes the emission scope
mandated by the bucket event history specification. New event kinds enter the
codebase as enum additions, never as ad-hoc strings.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, ValuesView
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Final, override

from pydantic import BaseModel, Field, StringConstraints, model_validator

from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.hashing import content_hash_hex
from ...core.identity import BucketId
from ...core.time import UtcInstant, validate_utc_aware
from .errors import BucketEventValidationError

BucketEventId = Hex64Str
"""Lowercase 64-character SHA-256 identifier of a bucket event.

Content-addressed from the full event body, so structurally identical
emissions collapse to one id. Public because every CLI history transport
projects this identity and must not re-declare its shape.
"""
BUCKET_ACTOR_LABEL_MAX_LENGTH: Final[int] = 64
"""Maximum length of a bucket-event actor label.

Named rather than inlined because a CLI surface accepting an operator-supplied
actor has to refuse an over-long value at the boundary, quoting the accepted
bound. Reaching the bound only when the event is constructed makes the refusal
arrive after the work it records has already been done, and leaves the operator
with no accepted-value set to correct against.
"""

BucketActorLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=BUCKET_ACTOR_LABEL_MAX_LENGTH),
]
"""Short label identifying the actor that emitted a bucket event.

A non-empty string of at most
:data:`BUCKET_ACTOR_LABEL_MAX_LENGTH` characters; trailing and leading
whitespace is stripped at validation time. Typical values are the CLI
command path (``"cadrumo.app.modelo.calculate"``) or an automated-agent
slug (``"censo.sync"``).
"""
BucketObjectId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
_PayloadKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]

BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH: Final[int] = 500
"""Maximum length of a single bucket-event payload value.

The bound keeps the append-only event log bounded per event: the log is a
substrate every service in the application writes to, so one unbounded
producer degrades a shared surface rather than only its own.

**A payload value is a fixed-width fact, never a variable-length join.** The
bound is enforced by refusal, not truncation — a silently shortened audit
value is worse than a refused write — so a producer that joins a collection
into one value stops being able to record its own event once the collection
grows. Six occurrences of that shape have been found, each independently:
joined attachment ids on transaction removal, joined child ids on ledger
split and on merge, an unbounded evidence path, an unbounded export row set,
and the reconcile diff detail. Identifiers are commonly 64-char SHA-256
digests, so the ceiling is reached at eight joined ids (519 characters) —
low enough to be reachable by ordinary use.

A producer holding a collection has exactly three sanctioned options:

- emit a **count** (``*_count``) when the members are recoverable from their
  own catalogue or from sibling events in the same batch;
- emit a **digest** (``sha256_hex`` over the joined members) when the set
  must stay verifiable but need not be enumerable from the log;
- give the detail a **durable home of its own** when the event log is its
  only copy, and leave the event carrying verdict plus count.

:func:`~cadrumo.domain.buckets.payload_value_fits` answers the bound without
constructing an event. The static gate
``domain/buckets/tests/test_payload_value_bounding.py`` refuses a new join
into a payload value at authoring time, which is where every one of the six
occurrences should have been caught.
"""

_PayloadValue = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=0,
        max_length=BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH,
    ),
]


def payload_value_fits(value: str) -> bool:
    """Return whether ``value`` fits a bucket-event payload slot.

    Lets a producer check the bound before it builds an event, rather than
    discovering it as a :class:`pydantic.ValidationError` raised after the
    surrounding work has already been done. Whitespace is stripped first, to
    match how :class:`BucketEvent` validates.

    Args:
        value: Candidate payload value.

    Returns:
        ``True`` when the stripped value is within
        :data:`BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH`.
    """
    return len(value.strip()) <= BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH


class BucketEventType(StrEnum):
    """Closed catalogue of bucket-event kinds.

    The enum mirrors the per-service emission scope declared by the
    bucket event history specification. Emitters land incrementally with their
    owning implementations; new kinds are added here only when a corresponding
    specification sanctions the emission.
    """

    # modelo lifecycle
    MODELO_CALCULATION_CREATED = "modelo.calculation.created"
    MODELO_VERIFICATION_PASSED = "modelo.verification.passed"
    MODELO_VERIFICATION_REFUSED = "modelo.verification.refused"
    MODELO_FILED = "modelo.filed"
    MODELO_FILED_SUPERSEDED = "modelo.filed_superseded"
    MODELO_AMENDED = "modelo.amended"
    MODELO_FILING_IMPORTED = "modelo.filing.imported"
    MODELO_LIVE_EVIDENCE_STAMPED = "modelo.live_evidence.stamped"
    MODELO_RECONCILED = "modelo.reconciled"
    MODELO_EXPORTED = "modelo.exported"
    MODELO_IVA_WALLET_CORRECTED = "modelo.iva_wallet.corrected"
    MODELO_IVA_WALLET_OVERRIDE_RECORDED = "modelo.iva_wallet.override_recorded"
    # Modelo 145 local payer-communication lifecycle
    MODELO_145_COMMUNICATION_CREATED = "modelo.145.communication.created"
    MODELO_145_COMMUNICATION_EXPORTED = "modelo.145.communication.exported"
    MODELO_145_COMMUNICATION_DELIVERED_TO_PAYER = "modelo.145.communication.delivered_to_payer"
    MODELO_145_COMMUNICATION_LOCALLY_COMPLETED = "modelo.145.communication.locally_completed"
    # Work-unit lifecycle
    MODELO_WORK_UNIT_CREATED = "modelo.work_unit.created"
    MODELO_WORK_UNIT_DISCARDED = "modelo.work_unit.discarded"
    MODELO_WORK_UNIT_RENAMED = "modelo.work_unit.renamed"

    # profile lifecycle
    PROFILE_BUCKET_CREATED = "profile.bucket.created"
    PROFILE_SELECTED = "profile.selected"
    PROFILE_VALUES_UPDATED = "profile.values.updated"
    PROFILE_VALUES_CLEARED = "profile.values.cleared"
    PROFILE_DUPLICATED = "profile.duplicated"
    PROFILE_RENAMED = "profile.renamed"
    PROFILE_EXPORTED = "profile.exported"
    PROFILE_IMPORTED = "profile.imported"
    PROFILE_ACTIVATED = "profile.activated"
    PROFILE_SETUP_COMPLETED = "profile.setup.completed"
    # The profile's password wrapper was re-minted over the SAME data key.
    # A lifecycle fact, not an operator verb: it records that the custody
    # generation advanced, which is what makes an earlier record row's
    # provenance witness legitimately stale rather than evidence of tampering.
    PROFILE_PASSPHRASE_ROTATED = "profile.passphrase.rotated"  # noqa: S105 - event-type token, not a credential
    # 036 censo cotejo: emitted once per artefact-apply reconciliation
    # commit (``apply_cotejo``). The live-refresh scrape against the sede
    # Mis Datos Censales endpoint was retired and its snapshot substrate
    # deleted, so no refresh event remains.
    CENSO_APPLIED = "profile.censo.applied"

    # 036 declarative-recording verbs (operator declares an alta /
    # modificacion / baja was filed at sede). The local app never
    # files a 036 — AEAT is the authority. These
    # events record the operator's declaration so downstream profile
    # state and stale-cascade logic can react. Distinct prefix
    # ``modelo.036.declaration.*`` separates them from the
    # ``profile.censo.applied`` cotejo mirror event.
    CENSO_DECLARATION_ALTA = "modelo.036.declaration.alta"
    CENSO_DECLARATION_MODIFICACION = "modelo.036.declaration.modificacion"
    CENSO_DECLARATION_BAJA = "modelo.036.declaration.baja"

    # bucket maintenance lifecycle
    BUCKET_EXPORTED = "bucket.exported"
    BUCKET_IMPORTED = "bucket.imported"
    BUCKET_RENAMED = "bucket.renamed"
    BUCKET_DELETED = "bucket.deleted"
    BUCKET_ARCHIVED = "bucket.archived"
    BUCKET_RESTORED = "bucket.restored"
    BUCKET_MERGED = "bucket.merged"

    # ledger usage-ratio mutations
    LEDGER_RATIOS_SET = "ledger.ratios.set"
    LEDGER_RATIOS_UNSET = "ledger.ratios.unset"
    LEDGER_RATIOS_CENSO_OVERRIDE_WARNING = "ledger.ratios.censo_override_warning"

    # operator authentication + workspace bootstrap
    AUTH_PROVIDER_CONFIGURED = "auth.provider.configured"
    AUTH_PROVIDER_CLEARED = "auth.provider.cleared"
    AUTH_SESSION_VERIFIED = "auth.session.verified"
    AUTH_SESSION_CLEARED = "auth.session.cleared"
    AUTH_LOCK_CLEARED = "auth.lock.cleared"
    CONFIG_ENV_UPDATED = "config.env.updated"

    # named multi-certificate source registry (personal + apoderado certs)
    AUTH_CERTIFICATE_SOURCE_REGISTERED = "auth.certificate_source.registered"
    AUTH_CERTIFICATE_SOURCE_SELECTED = "auth.certificate_source.selected"
    AUTH_CERTIFICATE_SOURCE_REMOVED = "auth.certificate_source.removed"
    AUTH_CERTIFICATE_SOURCE_SECRET_SET = "auth.certificate_source.secret_set"  # noqa: S105 - event-type label, not a secret
    AUTH_CERTIFICATE_SOURCE_SECRET_ROTATED = "auth.certificate_source.secret_rotated"  # noqa: S105 - event-type label
    AUTH_CERTIFICATE_SOURCE_SECRET_REMOVED = "auth.certificate_source.secret_removed"  # noqa: S105 - event-type label

    # secret-store custody: passphrase rotation and the recovery-code lifecycle.
    # Generic custody vocabulary with no AEAT surface, so the stems stay English.
    # Payloads carry only non-secret witnesses (the recovery fingerprint, the
    # store location); no passphrase, mnemonic, or key material is ever recorded.
    CUSTODY_PASSPHRASE_CHANGED = "custody.passphrase.changed"  # noqa: S105 - event-type label, not a secret
    CUSTODY_RECOVERY_CODE_CREATED = "custody.recovery_code.created"
    CUSTODY_RECOVERY_CODE_ROTATED = "custody.recovery_code.rotated"
    CUSTODY_SECRET_STORE_RECOVERED = "custody.secret_store.recovered"  # noqa: S105 - event-type label, not a secret

    # ledger transaction lifecycle
    LEDGER_TRANSACTION_CREATED = "ledger.transaction.created"
    LEDGER_TRANSACTION_IMPORTED = "ledger.transaction.imported"
    LEDGER_IMPORT_DIAGNOSTIC_RECORDED = "ledger.import.diagnostic_recorded"
    LEDGER_TRANSACTION_UPDATED = "ledger.transaction.updated"
    LEDGER_TRANSACTION_CLASSIFIED = "ledger.transaction.classified"
    LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED = "ledger.transaction.llm_suggestion.rejected"
    LEDGER_TRANSACTION_ALLOCATED = "ledger.transaction.allocated"
    LEDGER_TRANSACTION_REMOVED = "ledger.transaction.removed"
    LEDGER_TRANSACTION_ARCHIVED = "ledger.transaction.archived"
    LEDGER_TRANSACTION_STASHED = "ledger.transaction.stashed"
    LEDGER_TRANSACTION_RESTORED = "ledger.transaction.restored"
    LEDGER_TRANSACTION_REVIEWED_EXCLUDED = "ledger.transaction.reviewed_excluded"
    LEDGER_TRANSACTION_EXPORTED = "ledger.transaction.exported"
    LEDGER_TRANSACTION_SPLIT = "ledger.transaction.split"
    LEDGER_TRANSACTION_MERGED = "ledger.transaction.merged"
    LEDGER_TRANSACTION_INVOICE_LINKED = "ledger.transaction.invoice.linked"
    LEDGER_CATALOGUE_RESET = "ledger.catalogue.reset"
    LEDGER_SANITIZATION_COMPLETED = "ledger.sanitization.completed"
    PURCHASE_INVOICE_EVIDENCE_ATTACHED = "purchase_invoice_evidence.attached"
    PURCHASE_INVOICE_EVIDENCE_REPLACED = "purchase_invoice_evidence.replaced"
    PURCHASE_INVOICE_EVIDENCE_DETACHED = "purchase_invoice_evidence.detached"
    # An operator declined a read draft. Its own member rather than a reuse of
    # the three above, because a decline changes no stored evidence at all: it
    # records that a human looked and said no, which is the only trace the
    # decision leaves. Without it a declined read and a read never reviewed are
    # the same absence.
    PURCHASE_INVOICE_EVIDENCE_DRAFT_DECLINED = "purchase_invoice_evidence.draft.declined"
    # business-operation invoice noun-groups (invoice-domain-decoupling)
    PAYABLE_INVOICE_CREATED = "payable_invoice.created"
    PAYABLE_INVOICE_UPDATED = "payable_invoice.updated"
    PAYABLE_INVOICE_REMOVED = "payable_invoice.removed"
    COLLECTIBLE_INVOICE_CREATED = "collectible_invoice.created"
    COLLECTIBLE_INVOICE_UPDATED = "collectible_invoice.updated"
    COLLECTIBLE_INVOICE_REMOVED = "collectible_invoice.removed"
    # inventory noun-group (inventory placement)
    LEDGER_INVENTORY_CREATED = "ledger.inventory.created"
    LEDGER_INVENTORY_MOVEMENT_ADDED = "ledger.inventory.movement_added"
    LEDGER_INVENTORY_VALUATION_PREVIEWED = "ledger.inventory.valuation_previewed"
    LEDGER_INVENTORY_REMOVED = "ledger.inventory.removed"
    # audit verb-group (evidence bundle)
    MODELO_AUDIT_VERIFIED = "modelo.audit.verified"
    MODELO_AUDIT_EXPORTED = "modelo.audit.exported"
    # live AEAT read surface.
    # Every event below records a READ-ONLY capture; submission is
    # permanently forbidden per the live-AEAT charter.
    LIVE_NOTIFICATIONS_SNAPSHOT_CAPTURED = "live.notifications.snapshot_captured"
    LIVE_EXPEDIENTES_SNAPSHOT_CAPTURED = "live.expedientes.snapshot_captured"
    LIVE_VERIFY_NIF_IVA_CHECKED = "live.verify.nif_iva_checked"
    LIVE_VERIFY_TGVI_CHECKED = "live.verify.tgvi_checked"
    LIVE_BORRADOR100_SNAPSHOT_CAPTURED = "live.borrador100.snapshot_captured"
    # Synchronisation-run completion, one member per surface. Distinct from the
    # capture events above: those record that a snapshot was taken, these record
    # that a whole run over a surface finished and how much of it was covered.
    # A run that ends in partial failure still emits its member -- a run record
    # written only on success makes every truncated sweep invisible.
    SYNC_RUN_FILED_DECLARATIONS_COMPLETED = "sync_run.filed_declarations.completed"
    SYNC_RUN_CALC_SHEETS_EXPORT_COMPLETED = "sync_run.calc_sheets_export.completed"
    ATTACHMENT_LINKED = "attachment.linked"
    ATTACHMENT_REMOVED = "attachment.removed"

    # workflow-state recovery
    WORKFLOW_STATE_RESET = "workflow_state.reset"

    # reverse-merge corrections
    LEDGER_TRANSACTION_CORRECTION_APPLIED = "ledger.transaction.correction.applied"
    LEDGER_PURCHASE_INVOICE_EVIDENCE_CORRECTION_APPLIED = "ledger.purchase_invoice_evidence.correction.applied"
    LEDGER_PAYABLE_INVOICE_CORRECTION_APPLIED = "ledger.payable_invoice.correction.applied"
    LEDGER_COLLECTIBLE_INVOICE_CORRECTION_APPLIED = "ledger.collectible_invoice.correction.applied"
    LEDGER_RENTAL_INCOME_CORRECTION_APPLIED = "ledger.rental_income.correction.applied"
    LEDGER_RENTAL_EXPENSE_CORRECTION_APPLIED = "ledger.rental_expense.correction.applied"

    # accountant/gestor review-package collaboration surface (recipient
    # fingerprint registry, encrypt-for-recipient transport, review-only
    # workspace mode). ``collab_event`` naming distinguishes the trust/
    # transport-boundary crossing from ``privacy_event`` below, which marks
    # a distinct disclosure-relevant read of decrypted material.
    COLLAB_RECIPIENT_REGISTERED = "collab_event.recipient.registered"
    COLLAB_RECIPIENT_REMOVED = "collab_event.recipient.removed"
    COLLAB_PACKAGE_ENCRYPTED_FOR_RECIPIENT = "collab_event.package.encrypted_for_recipient"
    COLLAB_PACKAGE_DECRYPTED = "privacy_event.package.decrypted"
    COLLAB_REVIEW_ONLY_WORKSPACE_OPENED = "privacy_event.review_only_workspace.opened"
    COLLAB_PACKAGE_COUNTER_SIGNED = "collab_event.package.counter_signed"


class BucketEventObjectType(StrEnum):
    """Closed catalogue of object types a bucket event can reference."""

    WORK_UNIT = "work_unit"
    CALCULATION_REVISION = "calculation_revision"
    VERIFICATION_REPORT = "verification_report"
    FILING_RECORD = "filing_record"
    COMMUNICATION_RECORD = "communication_record"
    PROFILE = "profile"
    BUCKET = "bucket"
    LEDGER_TRANSACTION = "ledger_transaction"
    LEDGER_IMPORT_BATCH = "ledger_import_batch"
    LEDGER_CATALOGUE = "ledger_catalogue"
    LEDGER_EXPORT = "ledger_export"
    PURCHASE_INVOICE_EVIDENCE = "purchase_invoice_evidence"
    PAYABLE_INVOICE = "payable_invoice"
    COLLECTIBLE_INVOICE = "collectible_invoice"
    ATTACHMENT = "attachment"
    WORKFLOW_STATE = "workflow_state"
    RECIPIENT = "recipient"


def _canonical_payload(payload: Mapping[str, str]) -> dict[str, str]:
    return dict(sorted((k.strip(), v.strip()) for k, v in payload.items()))


def derive_bucket_event_id(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
    object_type: BucketEventObjectType,
    object_id: str,
    payload: Mapping[str, str],
) -> str:
    """Return the deterministic SHA-256 id for a bucket event.

    ``occurred_at`` is held to the canonical UTC contract before it reaches
    the digest. The instant is hashed as text, so each spelling of one
    moment -- naive, ``+01:00``, UTC -- produced a different id, and the
    append path assigns by id: the same event submitted twice under two
    spellings became two immutable history rows rather than collapsing, and
    the content-addressing the catalogue documents held only for callers who
    happened to agree on a timezone.
    """
    validate_utc_aware(occurred_at)
    body = {
        "bucket_id": bucket_id.strip(),
        "event_type": event_type.value,
        "occurred_at": occurred_at.isoformat(),
        "actor": actor.strip(),
        "object_type": object_type.value,
        "object_id": object_id.strip(),
        "payload": _canonical_payload(payload),
    }
    return content_hash_hex(body)


class BucketEvent(BaseModel):
    """One append-only bucket event.

    Attributes:
        event_id: Lowercase 64-char SHA-256 derived from the full
            event body. Content-addressed: structurally identical
            emissions collapse to the same id, making append
            naturally idempotent.
        bucket_id: Owning bucket identifier.
        event_type: One of :class:`BucketEventType`.
        occurred_at: UTC timestamp when the event was emitted.
        actor: Actor label (free text up to 64 chars).
        object_type: Type of the affected domain object.
        object_id: Stable identifier of the affected object (e.g.
            a 64-char SHA-256 work-unit / revision / filing-record id).
        payload_version: Integer schema version of the payload
            mapping. Bumped when the payload contract changes.
        payload: Free-form structured details. Keys and values are
            short strings; secrets / credentials must not appear.
    """

    model_config = STRICT_FROZEN_CONFIG

    event_id: BucketEventId
    bucket_id: BucketId
    event_type: BucketEventType
    occurred_at: UtcInstant
    actor: BucketActorLabel
    object_type: BucketEventObjectType
    object_id: BucketObjectId
    payload_version: int = Field(ge=1)
    payload: Mapping[_PayloadKey, _PayloadValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_derived_id(self) -> BucketEvent:
        derived = derive_bucket_event_id(
            bucket_id=self.bucket_id,
            event_type=self.event_type,
            occurred_at=self.occurred_at,
            actor=self.actor,
            object_type=self.object_type,
            object_id=self.object_id,
            payload=self.payload,
        )
        if derived != self.event_id:
            raise BucketEventValidationError(
                translated_message="errors.error.error_storage_bucket",
                context={
                    "declared_event_id": str(self.event_id),
                    "derived_event_id": str(derived),
                    "event_id_matches_derivation": False,
                },
            )
        return self


def bucket_event_order_key(event: BucketEvent) -> tuple[datetime, str]:
    """Return the canonical chronological sort key for one bucket event.

    Ordering by ``occurred_at`` alone is not a total order: emissions inside
    one operation share an instant by design (a rename emits the lifecycle
    event and the maintenance event at the same ``now()``), so ties fell
    through to whatever order the catalogue mapping happened to hold. Two
    processes reading the same persisted events could therefore render the
    operator different timelines, and the same reader could change its mind
    after a reload -- with no validation error anywhere, because nothing was
    wrong with the data.

    ``event_id`` breaks the tie because it is content-addressed: it is
    derived from the event body, so the tie-break is a property of the events
    themselves rather than of how they were stored or merged. The
    reconciliation history already ordered on this pair; this is the same
    rule, declared once for every projection that reads bucket events.
    """
    return (event.occurred_at, event.event_id)


class BucketEventHistoryCatalogue(BaseModel):
    """Immutable catalogue of every bucket event in storage."""

    model_config = STRICT_FROZEN_CONFIG

    events: Mapping[str, BucketEvent] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_keys_match(self) -> BucketEventHistoryCatalogue:
        for key, event in self.events.items():
            if key != event.event_id:
                raise BucketEventValidationError(
                    translated_message="errors.error.error_storage_bucket",
                    context={
                        "catalogue_key": str(key),
                        "event_id": str(event.event_id),
                        "catalogue_key_matches_event_id": False,
                    },
                )
        return self

    def get(self, event_id: str) -> BucketEvent | None:
        """Return the :class:`BucketEvent` for ``event_id``, or ``None`` if absent."""
        return self.events.get(event_id)

    def for_bucket(
        self,
        bucket_id: str,
        *,
        event_types: tuple[BucketEventType, ...] | None = None,
    ) -> tuple[BucketEvent, ...]:
        """Return every :class:`BucketEvent` recorded against ``bucket_id`` in chronological order.

        Events are ordered by :func:`bucket_event_order_key` and optionally
        filtered to one or more event types.
        """
        wanted = set(event_types) if event_types is not None else None
        matching = (
            e for e in self.events.values() if e.bucket_id == bucket_id and (wanted is None or e.event_type in wanted)
        )
        return tuple(sorted(matching, key=bucket_event_order_key))

    def for_object(
        self,
        *,
        object_type: BucketEventObjectType,
        object_id: str,
    ) -> tuple[BucketEvent, ...]:
        """Return every event recorded against one object, in canonical chronological order.

        Returns:
            Tuple of :class:`BucketEvent` records ordered by
            :func:`bucket_event_order_key`.
        """
        matching = (e for e in self.events.values() if e.object_type is object_type and e.object_id == object_id)
        return tuple(sorted(matching, key=bucket_event_order_key))

    def values(self) -> ValuesView[BucketEvent]:
        """Return a live view over every :class:`BucketEvent` in the catalogue."""
        return self.events.values()

    @override
    # TYPE-IGNORE-RATIONALE-HARD-DEFERRED-PYDANTIC-METACLASS:
    # pydantic BaseModel.__iter__ override requires a pydantic-v2
    # metaclass-aware base class, which is not yet available.
    def __iter__(self) -> Iterator[BucketEvent]:  # type: ignore[override]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: TYPE-IGNORE-RATIONALE-HARD-DEFERRED-PYDANTIC-METACLASS: pydantic BaseModel.__iter__ override requires a pydantic-v2 metaclass-aware base class, whi...
        """Iterate over every :class:`BucketEvent` in insertion order."""
        return iter(self.events.values())

    def __len__(self) -> int:
        """Return the total number of events in the catalogue."""
        return len(self.events)


__all__ = [
    "BucketEvent",
    "BucketEventHistoryCatalogue",
    "BucketEventObjectType",
    "BucketEventType",
    "bucket_event_order_key",
    "derive_bucket_event_id",
]
