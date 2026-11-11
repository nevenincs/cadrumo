"""Replay an inventory book's purchases, each claiming the ledger row that books it, and the stock sold in the year.

A persona states its purchases by the ledger rows that book them. Each becomes a
purchase whose cost is the row's base, IVA and recargo, claiming that row, so the
Modelo 100 declares the purchase once, through the book. The persona states no
units, so a purchase counts one unit per euro of cost; under FIFO the stock sold
on the last day of the year is what leaves the book at its stated closing.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from ...application.inventory.registered_evidence_operation import (
    INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
    InventoryEvidenceAddProjection,
    InventoryEvidenceAddRequest,
)
from ...application.inventory.registered_projections import InventoryMovementAddProjection
from ...application.inventory.registered_requests import (
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
    InventoryAcquisitionCostRequest,
    InventoryMovementAddRequest,
)
from ...application.operations.public_scalar import PublicDecimal
from ...core.decimal.constants import MONEY_ZERO
from ...domain.contribuyente.inventory.records import (
    InventoryAcquisitionCompleteness,
    InventoryAcquisitionEvidence,
    InventoryAcquisitionEvidenceKind,
    MovementKind,
    PurchaseLedgerRow,
    ValuationMethod,
    derive_inventory_acquisition_totals,
)
from ...domain.filing_evidence import FilingEvidenceReference
from ...tests.personas import InventoryBook, LedgerRow, Persona

type SettleOperation = Callable[[str, BaseModel], BaseModel | None]
"""Settles one registered operation against the persona's profile and returns its public result."""

_ATTRIBUTABLE_COST_REVIEW = (
    "Las compras de existencias de este ejercicio no llevan costes añadidos al precio de la factura: "
    "ni transporte, ni seguros, ni aranceles."
)
_IVA_RECOVERABILITY_REVIEW = (
    "La actividad tributa en el recargo de equivalencia, así que el IVA y el recargo soportados en estas "
    "compras no se deducen (artículo 154.Dos de la Ley del IVA) y forman parte de su precio de adquisición."
)


class PersonaInventoryPurchaseError(RuntimeError):
    """A persona's inventory purchases cannot be replayed as the book states them."""


def _evidence(
    settle: SettleOperation, profile_id: UUID, source: Path, kind: InventoryAcquisitionEvidenceKind
) -> InventoryAcquisitionEvidence:
    stored = settle(
        INVENTORY_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
        InventoryEvidenceAddRequest(
            profile_id=profile_id, source_path=str(source), source_directory=str(source.parent)
        ),
    )
    if (
        not isinstance(stored, InventoryEvidenceAddProjection)
        or stored.reference is None
        or stored.content_digest is None
    ):
        raise PersonaInventoryPurchaseError(f"{source.name}: the evidence was not kept")
    return InventoryAcquisitionEvidence(
        reference=FilingEvidenceReference(reference=stored.reference),
        evidence_kind=kind,
        content_digest=stored.content_digest,
    )


def _review(workdir: Path, name: str, text: str) -> Path:
    target = workdir / "inventory" / f"{name}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(f"%PDF-1.4\n% {text}\n%%EOF\n".encode())
    return target


def _purchase_row(persona: Persona, book: InventoryBook, ref: str, *, where: str) -> LedgerRow:
    rows = [row for row in persona.ledger if row.ref == ref]
    if len(rows) != 1 or rows[0].year != book.year:
        raise PersonaInventoryPurchaseError(f"{where}: purchase {ref} names no single ledger row of the book's year")
    return rows[0]


def _cost(
    row: LedgerRow, evidence: tuple[InventoryAcquisitionEvidence, ...], *, where: str
) -> tuple[InventoryAcquisitionCostRequest, Decimal]:
    if row.taxable_base is None or row.iva_amount is None:
        raise PersonaInventoryPurchaseError(f"{where}: purchase {row.ref} states no base or IVA")
    recargo = row.recargo_amount or MONEY_ZERO
    ratio = MONEY_ZERO if recargo != MONEY_ZERO else Decimal(1)
    totals = derive_inventory_acquisition_totals(
        consideration_excluding_iva=row.taxable_base,
        consideration_iva_amount=row.iva_amount,
        consideration_recargo_amount=recargo,
        consideration_deductible_iva_ratio=ratio,
        attributable_cost_components=(),
    )
    invoice, cost_review, iva_review = evidence
    request = InventoryAcquisitionCostRequest(
        consideration_excluding_iva=PublicDecimal(decimal=str(row.taxable_base)),
        consideration_iva_amount=PublicDecimal(decimal=str(row.iva_amount)),
        consideration_deductible_iva_ratio=PublicDecimal(decimal=str(ratio)),
        attributable_cost_components=(),
        evidence=evidence,
        completeness=InventoryAcquisitionCompleteness(
            consideration_evidence=invoice.reference,
            attributable_cost_review_evidence=cost_review.reference,
            iva_recoverability_review_evidence=iva_review.reference,
        ),
        consideration_recargo_amount=None if recargo == MONEY_ZERO else PublicDecimal(decimal=str(recargo)),
        directly_attributable_cost_total=PublicDecimal(decimal=str(totals.directly_attributable_cost_total)),
        nonrecoverable_iva_included=PublicDecimal(decimal=str(totals.nonrecoverable_iva_included)),
        recoverable_iva_excluded=PublicDecimal(decimal=str(totals.recoverable_iva_excluded)),
        total_acquisition_cost=PublicDecimal(decimal=str(totals.total_acquisition_cost)),
    )
    return request, totals.total_acquisition_cost


def _add(settle: SettleOperation, request: InventoryMovementAddRequest, *, where: str) -> None:
    added = settle(INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID, request)
    if not isinstance(added, InventoryMovementAddProjection) or added.outcome != "added":
        detail = added.model_dump_json() if added is not None else "no result"
        raise PersonaInventoryPurchaseError(f"{where}: movement {request.movement_id} refused: {detail}")


def replay_inventory_purchases(
    persona: Persona,
    book: InventoryBook,
    *,
    year: int,
    profile_id: UUID,
    workdir: Path,
    transactions: Mapping[str, str],
    invoice_source: Callable[[str], Path],
    settle: SettleOperation,
) -> None:
    """Add each purchase the book names, claiming its ledger row, then the stock sold so the book closes as stated.

    ``invoice_source`` returns the file of the invoice a ledger row's purchase
    rests on; ``transactions`` maps each ledger ref to its transaction id.
    """
    if not book.purchases:
        return
    where = f"{persona.id} inventory {book.activity} {year}"
    if book.valuation_method != ValuationMethod.FIFO.value:
        raise PersonaInventoryPurchaseError(f"{where}: purchases at one unit per euro are replayed under FIFO only")
    stem = f"{persona.id}-{book.activity}-{year}"
    cost_review = _evidence(
        settle,
        profile_id,
        _review(workdir, f"{stem}-coste", f"{_ATTRIBUTABLE_COST_REVIEW} ({year})"),
        InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW,
    )
    iva_review = _evidence(
        settle,
        profile_id,
        _review(workdir, f"{stem}-iva", f"{_IVA_RECOVERABILITY_REVIEW} ({year})"),
        InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW,
    )
    purchased = MONEY_ZERO
    for ref in book.purchases:
        row = _purchase_row(persona, book, ref, where=where)
        invoice = _evidence(settle, profile_id, invoice_source(ref), InventoryAcquisitionEvidenceKind.PURCHASE_INVOICE)
        cost, total = _cost(row, (invoice, cost_review, iva_review), where=where)
        purchased += total
        _add(
            settle,
            InventoryMovementAddRequest(
                profile_id=profile_id,
                actividad_id=book.activity,
                year=year,
                movement_id=ref,
                movement_date=date(year, row.month, row.day),
                kind=MovementKind.PURCHASE,
                quantity=PublicDecimal(decimal=str(total)),
                acquisition_cost=cost,
                ledger_row=PurchaseLedgerRow.CLAIMED,
                claimed_transaction_id=transactions[ref],
            ),
            where=where,
        )
    if book.closing_stock > purchased:
        raise PersonaInventoryPurchaseError(f"{where}: the closing exceeds the year's purchases")
    opening_units = Decimal(1) if book.opening_stock != MONEY_ZERO else MONEY_ZERO
    sold = opening_units + purchased - book.closing_stock
    if sold != MONEY_ZERO:
        _add(
            settle,
            InventoryMovementAddRequest(
                profile_id=profile_id,
                actividad_id=book.activity,
                year=year,
                movement_id=f"{book.activity}-{year}-vendido",
                movement_date=date(year, 12, 31),
                kind=MovementKind.COGS,
                quantity=PublicDecimal(decimal=str(sold)),
            ),
            where=where,
        )


__all__ = ["PersonaInventoryPurchaseError", "SettleOperation", "replay_inventory_purchases"]
