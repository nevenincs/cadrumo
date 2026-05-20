"""Application service for importing invoice records."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ...domain.invoices import Invoice, InvoiceCatalogue, InvoiceCatalogueRepository, InvoiceKind
from ...domain.invoices._errors import InvoiceValidationError

_IVA_RATE_ALIASES = {
    "0": "RATE_0",
    "4": "RATE_4",
    "10": "RATE_10",
    "21": "RATE_21",
}


class InvoiceImportResult(BaseModel):
    """Result DTO returned by invoice import application services."""

    model_config = ConfigDict(frozen=True)

    rows: int
    imported: int = 0
    skipped: int = 0
    dry_run: bool = False
    catalogue: InvoiceCatalogue | None = None


def parse_invoice_payload(raw: str, *, default_kind: InvoiceKind | str) -> tuple[Invoice, ...]:
    """Parse JSON or CSV invoice payloads into validated invoice models."""

    kind = _coerce_kind(default_kind)
    candidates = _decode_invoice_payload(raw)
    invoices: list[Invoice] = []
    for candidate in candidates:
        payload = dict(candidate)
        payload.setdefault("kind", kind.value)
        raw_kind = payload.get("kind")
        if isinstance(raw_kind, str):
            payload["kind"] = raw_kind.lower()

        payload.setdefault("currency", "EUR")
        payload.setdefault("counterparty_country", "ES")
        payload.setdefault("payment_status", "PAID")
        payload.setdefault("counterparty_name", payload.get("counterparty_tax_id", "Unknown"))
        _synthesise_single_line_if_needed(payload)
        invoices.append(Invoice.model_validate(payload))
    return tuple(invoices)


def merge_invoice_import(catalogue: InvoiceCatalogue, invoices: Sequence[Invoice]) -> InvoiceImportResult:
    """Merge imported invoices into ``catalogue`` without duplicating IDs."""

    existing = dict(catalogue.invoices)
    imported = 0
    skipped = 0
    for invoice in invoices:
        if invoice.invoice_id in existing:
            skipped += 1
            continue
        existing[invoice.invoice_id] = invoice
        imported += 1
    return InvoiceImportResult(
        rows=len(invoices),
        imported=imported,
        skipped=skipped,
        catalogue=InvoiceCatalogue.model_validate({"invoices": existing}),
    )


def import_invoices_from_path(
    path: Path,
    *,
    kind: InvoiceKind | str,
    dry_run: bool = False,
    repository: InvoiceCatalogueRepository | None = None,
) -> InvoiceImportResult:
    """Import invoices from ``path`` through the secure invoice repository."""

    invoices = parse_invoice_payload(path.read_text(encoding="utf-8"), default_kind=kind)
    if dry_run:
        return InvoiceImportResult(rows=len(invoices), dry_run=True)

    repo = repository or InvoiceCatalogueRepository()
    result = merge_invoice_import(repo.load(), invoices)
    if result.catalogue is not None:
        repo.save(result.catalogue)
    return result


def _decode_invoice_payload(raw: str) -> tuple[Mapping[str, object], ...]:
    raw_stripped = raw.lstrip()
    if raw_stripped.startswith("[") or raw_stripped.startswith("{"):
        decoded = json.loads(raw)
        if isinstance(decoded, Mapping):
            return (decoded,)
        if isinstance(decoded, list) and all(isinstance(item, Mapping) for item in decoded):
            return tuple(decoded)
        raise InvoiceValidationError("invoice JSON payload must be an object or a list of objects")

    reader = csv.DictReader(raw.splitlines())
    return tuple(dict(row) for row in reader)


def _synthesise_single_line_if_needed(payload: dict[str, object]) -> None:
    if "lines" in payload or "base_total" not in payload or "iva_rate" not in payload:
        return
    base = Decimal(str(payload["base_total"]))
    rate_raw = str(payload["iva_rate"])
    rate = _IVA_RATE_ALIASES.get(rate_raw, rate_raw)
    iva_amount = Decimal(str(payload.get("iva_total", "0")))
    payload["lines"] = [
        {
            "description": "Imported invoice line",
            "quantity": "1",
            "unit_price": str(base),
            "subtotal": str(base),
            "iva_rate": rate,
            "iva_amount": str(iva_amount),
        }
    ]
    payload.pop("iva_rate", None)


def _coerce_kind(kind: InvoiceKind | str) -> InvoiceKind:
    if isinstance(kind, InvoiceKind):
        return kind
    return InvoiceKind(kind.strip().lower())


__all__ = [
    "InvoiceImportResult",
    "import_invoices_from_path",
    "merge_invoice_import",
    "parse_invoice_payload",
]
