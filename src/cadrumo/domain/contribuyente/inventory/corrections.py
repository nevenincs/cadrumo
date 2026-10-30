"""Append-only edits, rectifications, retirement and restoration of an inventory ledger.

``InventoryLedger.period_movements`` stays the effective movement set, so every
valuation and projection reads rectified facts without filtering. A rectification
takes the displaced fact out of that set and keeps it in ``history``: registers are
corrected by a further annotation and never erased (Orden HAC/773/2019 art. 11,
Código de Comercio art. 29.1), and the evidence is kept through the prescription
period (RIRPF art. 68.1).

Each function is a pure function of the document it is handed, because the
repository re-applies it to the newly current document on a revision conflict. Each
returns the ledger it was given, unchanged, for an exact replay.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, TypeIs, get_args

from ....core.hashing import content_hash_hex as _content_hash_hex
from ....core.identity.digest import ContentDigest
from .closing_foundations import InventoryLedgerError
from .records import (
    InventoryCorrectionReason,
    InventoryHistoryKind,
    InventoryLedger,
    InventoryLedgerDescriptor,
    InventoryLedgerDocument,
    InventoryLedgerHistoryEntry,
    InventoryRetirementReason,
    MovementRecord,
    ValuationMethod,
)
from .valuation import compute_inventory_valuation

InventoryCorrectionRefusalReason = Literal[
    "closing_authority_recorded",
    "later_closing_authority_recorded",
    "inventory_retired",
    "inventory_already_retired",
    "inventory_not_retired",
    "movement_not_found",
    "movement_already_superseded",
    "movement_outside_year",
    "stock_would_go_negative",
    "count_would_raise_stock",
    "correction_id_conflict",
    "correction_changes_nothing",
]
"""Every typed reason this module and the valuation engine refuse a change for."""

INVENTORY_CORRECTION_REFUSAL_REASONS: tuple[str, ...] = tuple(
    str(reason) for reason in get_args(InventoryCorrectionRefusalReason)
)


def is_inventory_correction_refusal_reason(value: str) -> TypeIs[InventoryCorrectionRefusalReason]:
    """Whether one token is a typed refusal reason of this module."""
    return value in INVENTORY_CORRECTION_REFUSAL_REASONS


def inventory_refusal_key(reason: str) -> str:
    """Name the catalogue key of one typed inventory refusal."""
    return f"application.inventory.service.errors.{reason}"


def _refused(reason: InventoryCorrectionRefusalReason, ledger: InventoryLedger, **facts: str) -> InventoryLedgerError:
    return InventoryLedgerError(
        f"inventory change refused: {reason}",
        context={"actividad_id": ledger.actividad_id, "year": str(ledger.year), **facts},
        translated_message=inventory_refusal_key(reason),
    )


@dataclass(frozen=True, slots=True)
class InventoryChangeStamp:
    """Identity and attribution recorded on one history entry."""

    correction_id: str
    recorded_at: datetime
    actor: str


def _is_replay(ledger: InventoryLedger, correction_id: str, fingerprint: ContentDigest) -> bool:
    """Whether this exact request already applied; the same identity on another request refuses."""
    for entry in ledger.history:
        if entry.correction_id == correction_id:
            if entry.request_fingerprint != fingerprint:
                raise _refused("correction_id_conflict", ledger, correction_id=correction_id)
            return True
    return False


def require_ledger_active(ledger: InventoryLedger) -> None:
    """Refuse a change to a ledger that left the active register."""
    if ledger.is_retired:
        raise _refused("inventory_retired", ledger)


def _require_no_consumer(document: InventoryLedgerDocument, ledger: InventoryLedger) -> None:
    """Refuse once this year's stock facts have become, or feed, a recorded closing authority.

    The Anexo D projection requires a closing authority, so a ledger without one
    has reached no calculated period. The next year's authority states its opening
    from this year's closing, and that link is evidence nothing re-reads.
    """
    if ledger.closing_authority_record is not None:
        raise _refused("closing_authority_recorded", ledger)
    if any(
        other.actividad_id == ledger.actividad_id
        and other.year == ledger.year + 1
        and other.closing_authority_record is not None
        for other in document.ledgers
    ):
        raise _refused("later_closing_authority_recorded", ledger, later_year=str(ledger.year + 1))


def require_ledger_open_for_stock_change(document: InventoryLedgerDocument, ledger: InventoryLedger) -> None:
    """Refuse any change to the facts valuation reads unless they are still unconsumed."""
    require_ledger_active(ledger)
    _require_no_consumer(document, ledger)


def _validated(candidate: InventoryLedger) -> InventoryLedger:
    """Rehydrate and revalue the candidate so a refusal precedes the guarded write."""
    validated = InventoryLedger.model_validate(candidate.model_dump())
    compute_inventory_valuation(validated)
    return validated


def _decimal_identity(value: Decimal) -> str:
    """Keep one number one identity however its exponent was written."""
    return format(value.normalize(), "f")


def describe_ledger(
    ledger: InventoryLedger,
    *,
    stamp: InventoryChangeStamp,
    descriptor: InventoryLedgerDescriptor,
) -> InventoryLedger:
    """Replace the descriptive facts; no valuation input moves, so no consumer guard applies."""
    fingerprint = _content_hash_hex(
        {"kind": InventoryHistoryKind.DESCRIBED.value, **descriptor.model_dump(mode="json")},
    )
    if _is_replay(ledger, stamp.correction_id, fingerprint) or ledger.descriptor == descriptor:
        return ledger
    entry = _entry(stamp, InventoryHistoryKind.DESCRIBED, fingerprint, prior_descriptor=ledger.descriptor)
    return ledger.model_copy(update={"descriptor": descriptor, "history": (*ledger.history, entry)})


def correct_opening(
    document: InventoryLedgerDocument,
    ledger: InventoryLedger,
    *,
    stamp: InventoryChangeStamp,
    reason: InventoryCorrectionReason,
    opening_stock: Decimal | None,
    valuation_method: ValuationMethod | None,
) -> InventoryLedger:
    """Rectify the opening value or valuation method, keeping the values they displace."""
    fingerprint = _content_hash_hex(
        {
            "kind": InventoryHistoryKind.OPENING_CORRECTED.value,
            "reason": reason.value,
            "opening_stock": None if opening_stock is None else _decimal_identity(opening_stock),
            "valuation_method": None if valuation_method is None else valuation_method.value,
        }
    )
    if _is_replay(ledger, stamp.correction_id, fingerprint):
        return ledger
    require_ledger_open_for_stock_change(document, ledger)
    next_opening = ledger.opening_stock if opening_stock is None else opening_stock
    next_method = ledger.valuation_method if valuation_method is None else valuation_method
    if next_opening == ledger.opening_stock and next_method is ledger.valuation_method:
        raise _refused("correction_changes_nothing", ledger)
    entry = _entry(
        stamp,
        InventoryHistoryKind.OPENING_CORRECTED,
        fingerprint,
        correction_reason=reason,
        prior_opening_stock=ledger.opening_stock,
        prior_valuation_method=ledger.valuation_method,
    )
    return _validated(
        ledger.model_copy(
            update={
                "opening_stock": next_opening,
                "valuation_method": next_method,
                "history": (*ledger.history, entry),
            }
        )
    )


def _require_effective_movement(ledger: InventoryLedger, movement_id: str) -> MovementRecord:
    for movement in ledger.period_movements:
        if movement.movement_id == movement_id:
            return movement
    if movement_id in ledger.known_movement_ids:
        raise _refused("movement_already_superseded", ledger, movement_id=movement_id)
    raise _refused("movement_not_found", ledger, movement_id=movement_id)


def correct_movement(
    document: InventoryLedgerDocument,
    ledger: InventoryLedger,
    *,
    stamp: InventoryChangeStamp,
    target_movement_id: str,
    replacement: MovementRecord,
    reason: InventoryCorrectionReason,
) -> InventoryLedger:
    """Supersede one movement with a replacement under a new identity."""
    fingerprint = _content_hash_hex(
        {
            "kind": InventoryHistoryKind.MOVEMENT_CORRECTED.value,
            "reason": reason.value,
            "target_movement_id": target_movement_id,
            "replacement": replacement.model_dump(mode="json"),
        }
    )
    if _is_replay(ledger, stamp.correction_id, fingerprint):
        return ledger
    require_ledger_open_for_stock_change(document, ledger)
    target = _require_effective_movement(ledger, target_movement_id)
    if replacement.movement_id in ledger.known_movement_ids:
        raise InventoryLedgerError(
            f"movement {replacement.movement_id!r} already exists",
            context={"movement_id": replacement.movement_id},
            translated_message=inventory_refusal_key("duplicate_movement_id"),
        )
    if replacement.movement_date.year != ledger.year:
        raise _refused("movement_outside_year", ledger, movement_id=replacement.movement_id)
    entry = _entry(
        stamp,
        InventoryHistoryKind.MOVEMENT_CORRECTED,
        fingerprint,
        correction_reason=reason,
        superseded_movement=target,
        replacement_movement_id=replacement.movement_id,
    )
    effective = tuple(item for item in ledger.period_movements if item.movement_id != target_movement_id)
    return _validated(
        ledger.model_copy(update={"period_movements": (*effective, replacement), "history": (*ledger.history, entry)})
    )


def reverse_movement(
    document: InventoryLedgerDocument,
    ledger: InventoryLedger,
    *,
    stamp: InventoryChangeStamp,
    target_movement_id: str,
    reason: InventoryCorrectionReason,
) -> InventoryLedger:
    """Take one movement out of the effective set, retaining it as the reversal's evidence."""
    fingerprint = _content_hash_hex(
        {
            "kind": InventoryHistoryKind.MOVEMENT_REVERSED.value,
            "reason": reason.value,
            "target_movement_id": target_movement_id,
        }
    )
    if _is_replay(ledger, stamp.correction_id, fingerprint):
        return ledger
    require_ledger_open_for_stock_change(document, ledger)
    target = _require_effective_movement(ledger, target_movement_id)
    entry = _entry(
        stamp,
        InventoryHistoryKind.MOVEMENT_REVERSED,
        fingerprint,
        correction_reason=reason,
        superseded_movement=target,
    )
    effective = tuple(item for item in ledger.period_movements if item.movement_id != target_movement_id)
    return _validated(ledger.model_copy(update={"period_movements": effective, "history": (*ledger.history, entry)}))


def retire_ledger(
    document: InventoryLedgerDocument,
    ledger: InventoryLedger,
    *,
    stamp: InventoryChangeStamp,
    reason: InventoryRetirementReason,
) -> InventoryLedger:
    """Take the inventory out of the active register with every fact retained."""
    fingerprint = _content_hash_hex({"kind": InventoryHistoryKind.RETIRED.value, "reason": reason.value})
    if _is_replay(ledger, stamp.correction_id, fingerprint):
        return ledger
    if ledger.is_retired:
        raise _refused("inventory_already_retired", ledger)
    _require_no_consumer(document, ledger)
    entry = _entry(stamp, InventoryHistoryKind.RETIRED, fingerprint, retirement_reason=reason)
    return ledger.model_copy(update={"history": (*ledger.history, entry)})


def restore_ledger(ledger: InventoryLedger, *, stamp: InventoryChangeStamp) -> InventoryLedger:
    """Bring a retired inventory back to the active register."""
    fingerprint = _content_hash_hex({"kind": InventoryHistoryKind.RESTORED.value})
    if _is_replay(ledger, stamp.correction_id, fingerprint):
        return ledger
    if not ledger.is_retired:
        raise _refused("inventory_not_retired", ledger)
    entry = _entry(stamp, InventoryHistoryKind.RESTORED, fingerprint)
    return ledger.model_copy(update={"history": (*ledger.history, entry)})


def _entry(
    stamp: InventoryChangeStamp,
    kind: InventoryHistoryKind,
    fingerprint: ContentDigest,
    *,
    correction_reason: InventoryCorrectionReason | None = None,
    retirement_reason: InventoryRetirementReason | None = None,
    superseded_movement: MovementRecord | None = None,
    replacement_movement_id: str | None = None,
    prior_opening_stock: Decimal | None = None,
    prior_valuation_method: ValuationMethod | None = None,
    prior_descriptor: InventoryLedgerDescriptor | None = None,
) -> InventoryLedgerHistoryEntry:
    return InventoryLedgerHistoryEntry(
        correction_id=stamp.correction_id,
        kind=kind,
        recorded_at=stamp.recorded_at,
        actor=stamp.actor,
        request_fingerprint=fingerprint,
        correction_reason=correction_reason,
        retirement_reason=retirement_reason,
        superseded_movement=superseded_movement,
        replacement_movement_id=replacement_movement_id,
        prior_opening_stock=prior_opening_stock,
        prior_valuation_method=prior_valuation_method,
        prior_descriptor=prior_descriptor,
    )


__all__ = [
    "INVENTORY_CORRECTION_REFUSAL_REASONS",
    "InventoryChangeStamp",
    "InventoryCorrectionRefusalReason",
    "correct_movement",
    "correct_opening",
    "describe_ledger",
    "inventory_refusal_key",
    "is_inventory_correction_refusal_reason",
    "require_ledger_active",
    "require_ledger_open_for_stock_change",
    "restore_ledger",
    "retire_ledger",
    "reverse_movement",
]
