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

import hashlib
import json
from collections.abc import Iterator, Mapping, ValuesView
from datetime import datetime
from enum import StrEnum
from typing import Annotated, override

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ..contribuyente import ProfileName as _ProfileName
from ._errors import BucketEventValidationError

_HEX_64_PATTERN = r"^[0-9a-f]{64}$"

_EventId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
BucketActorLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
"""Short label identifying the actor that emitted a bucket event.

A non-empty string of at most 64 characters; trailing and leading
whitespace is stripped at validation time. Typical values are the CLI
command path (``"aeat.app.modelo.calculate"``) or an automated-agent
slug (``"censo.sync"``).
"""
_ObjectId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
_PayloadKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
_PayloadValue = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=0, max_length=500),
]


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
    MODELO_RECONCILED = "modelo.reconciled"
    MODELO_EXPORTED = "modelo.exported"
    MODELO_IVA_WALLET_CORRECTED = "modelo.iva_wallet.corrected"
    # Work-unit lifecycle
    MODELO_WORK_UNIT_CREATED = "modelo.work_unit.created"
    MODELO_WORK_UNIT_DISCARDED = "modelo.work_unit.discarded"
    MODELO_WORK_UNIT_RENAMED = "modelo.work_unit.renamed"

    # profile lifecycle
    PROFILE_BUCKET_CREATED = "profile.bucket.created"
    PROFILE_SELECTED = "profile.selected"
    PROFILE_VALUES_UPDATED = "profile.values.updated"
    PROFILE_VALUES_CLEARED = "profile.values.cleared"
    PROFILE_TOMBSTONED = "profile.tombstoned"
    PROFILE_DUPLICATED = "profile.duplicated"
    PROFILE_RENAMED = "profile.renamed"
    PROFILE_EXPORTED = "profile.exported"
    PROFILE_IMPORTED = "profile.imported"
    PROFILE_ACTIVATED = "profile.activated"
    # 036 censo live-sync against the sede Mis Datos Censales endpoint
    CENSO_REFRESHED = "profile.censo.refreshed"
    CENSO_APPLIED = "profile.censo.applied"
    CENSO_DEPENDENT_STAMPED_STALE = "modelo.censo.dependent_stamped_stale"
    MODELO_LEDGER_DEPENDENT_STAMPED_STALE = "modelo.ledger.dependent_stamped_stale"

    # 036 declarative-recording verbs (operator declares an alta /
    # modificacion / baja was filed at sede). Per the 2026-05-16
    # ADR amendment to cli-workflow-redesign-modelo-036-037-foundation,
    # the local app never files a 036 — AEAT is the authority. These
    # events record the operator's declaration so downstream profile
    # state and stale-cascade logic can react. Distinct prefix
    # ``modelo.036.declaration.*`` separates them from the existing
    # mirror events (``profile.censo.refreshed/applied``) authored
    # for the live-read pipeline.
    CENSO_DECLARATION_ALTA = "modelo.036.declaration.alta"
    CENSO_DECLARATION_MODIFICACION = "modelo.036.declaration.modificacion"
    CENSO_DECLARATION_BAJA = "modelo.036.declaration.baja"

    # bucket maintenance lifecycle
    BUCKET_EXPORTED = "bucket.exported"
    BUCKET_IMPORTED = "bucket.imported"
    BUCKET_RENAMED = "bucket.renamed"
    BUCKET_DELETED = "bucket.deleted"

    # ledger usage-ratio mutations
    LEDGER_RATIOS_SET = "ledger.ratios.set"
    LEDGER_RATIOS_UNSET = "ledger.ratios.unset"
    LEDGER_RATIOS_CENSO_OVERRIDE_WARNING = "ledger.ratios.censo_override_warning"

    # operator authentication + workspace bootstrap
    AUTH_PROVIDER_CONFIGURED = "auth.provider.configured"
    CONFIG_ENV_UPDATED = "config.env.updated"
    SETUP_STATE_MIGRATED = "setup.state.migrated"

    # ledger transaction lifecycle
    LEDGER_TRANSACTION_CREATED = "ledger.transaction.created"
    LEDGER_TRANSACTION_IMPORTED = "ledger.transaction.imported"
    LEDGER_IMPORT_DIAGNOSTIC_RECORDED = "ledger.import.diagnostic_recorded"
    LEDGER_TRANSACTION_UPDATED = "ledger.transaction.updated"
    LEDGER_TRANSACTION_CLASSIFIED = "ledger.transaction.classified"
    LEDGER_TRANSACTION_ALLOCATED = "ledger.transaction.allocated"
    LEDGER_TRANSACTION_REMOVED = "ledger.transaction.removed"
    LEDGER_TRANSACTION_ARCHIVED = "ledger.transaction.archived"
    LEDGER_TRANSACTION_STASHED = "ledger.transaction.stashed"
    LEDGER_TRANSACTION_RESTORED = "ledger.transaction.restored"
    LEDGER_TRANSACTION_EXPORTED = "ledger.transaction.exported"
    LEDGER_TRANSACTION_SPLIT = "ledger.transaction.split"
    LEDGER_TRANSACTION_MERGED = "ledger.transaction.merged"
    LEDGER_CATALOGUE_RESET = "ledger.catalogue.reset"
    LEDGER_SANITIZATION_COMPLETED = "ledger.sanitization.completed"
    PURCHASE_INVOICE_EVIDENCE_ATTACHED = "purchase_invoice_evidence.attached"
    PURCHASE_INVOICE_EVIDENCE_REPLACED = "purchase_invoice_evidence.replaced"
    PURCHASE_INVOICE_EVIDENCE_DETACHED = "purchase_invoice_evidence.detached"
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
    MODELO_AUDIT_REPLAYED = "modelo.audit.replayed"
    # live AEAT read surface.
    # Every event below records a READ-ONLY capture; submission is
    # permanently forbidden per the live-AEAT charter.
    LIVE_NOTIFICATIONS_SNAPSHOT_CAPTURED = "live.notifications.snapshot_captured"
    LIVE_EXPEDIENTES_SNAPSHOT_CAPTURED = "live.expedientes.snapshot_captured"
    LIVE_VERIFY_NIF_IVA_CHECKED = "live.verify.nif_iva_checked"
    LIVE_VERIFY_TGVI_CHECKED = "live.verify.tgvi_checked"
    LIVE_BORRADOR100_SNAPSHOT_CAPTURED = "live.borrador100.snapshot_captured"
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


class BucketEventObjectType(StrEnum):
    """Closed catalogue of object types a bucket event can reference."""

    WORK_UNIT = "work_unit"
    CALCULATION_REVISION = "calculation_revision"
    VERIFICATION_REPORT = "verification_report"
    FILING_RECORD = "filing_record"
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
    """Return the deterministic SHA-256 id for a bucket event."""
    body = {
        "bucket_id": bucket_id.strip(),
        "event_type": event_type.value,
        "occurred_at": occurred_at.isoformat(),
        "actor": actor.strip(),
        "object_type": object_type.value,
        "object_id": object_id.strip(),
        "payload": _canonical_payload(payload),
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    event_id: _EventId
    bucket_id: _ProfileName
    event_type: BucketEventType
    occurred_at: datetime
    actor: BucketActorLabel
    object_type: BucketEventObjectType
    object_id: _ObjectId
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
            raise BucketEventValidationError(f"event_id {self.event_id!r} does not match the derived id {derived!r}")
        return self


class BucketEventHistoryCatalogue(BaseModel):
    """Immutable catalogue of every bucket event in storage."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    events: Mapping[str, BucketEvent] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_keys_match(self) -> BucketEventHistoryCatalogue:
        for key, event in self.events.items():
            if key != event.event_id:
                raise BucketEventValidationError(f"catalogue key {key!r} does not match event_id {event.event_id!r}")
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

        Events are sorted by ``occurred_at`` ascending and optionally filtered to one
        or more event types.
        """
        wanted = set(event_types) if event_types is not None else None
        matching = (
            e for e in self.events.values() if e.bucket_id == bucket_id and (wanted is None or e.event_type in wanted)
        )
        return tuple(sorted(matching, key=lambda e: e.occurred_at))

    def for_object(
        self,
        *,
        object_type: BucketEventObjectType,
        object_id: str,
    ) -> tuple[BucketEvent, ...]:
        """Return every event recorded against one object, ordered by ``occurred_at`` ascending.

        Returns:
            Tuple of :class:`BucketEvent` records in chronological order.
        """
        matching = (e for e in self.events.values() if e.object_type is object_type and e.object_id == object_id)
        return tuple(sorted(matching, key=lambda e: e.occurred_at))

    def values(self) -> ValuesView[BucketEvent]:
        """Return a live view over every :class:`BucketEvent` in the catalogue."""
        return self.events.values()

    @override
    # TYPE-IGNORE-RATIONALE-HARD-DEFERRED-PYDANTIC-METACLASS:
    # pydantic BaseModel.__iter__ override requires pydantic-v2 metaclass-aware
    # base class. Successor epic required.
    def __iter__(self) -> Iterator[BucketEvent]:  # type: ignore[override]  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]
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
    "derive_bucket_event_id",
]
