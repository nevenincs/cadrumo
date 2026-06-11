"""Application service for importing invoice records.

:func:`import_invoices_from_path` loads the persisted :class:`InvoiceCatalogue`
from the :class:`InvoiceCatalogueRepository`, merges the parsed invoices, and
writes the updated catalogue back.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, NotRequired, TypedDict, cast

from pydantic import BaseModel, ConfigDict

from ...core.decimal import coerce_decimal
from ...core.external_constants import DEFAULT_CURRENCY, UTF_8_ENCODING
from ...core.logging import get_logger
from ...domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceCatalogueRepositoryProtocol,
    InvoiceValidationError,
)
from ...domain.iva import InvoiceKind

_log = get_logger(__name__)


class InvoiceRowPayload(TypedDict, total=False):
    """Typed shape for a single decoded invoice row from JSON or CSV input.

    All fields are optional at the decode boundary because CSV and JSON
    sources may omit fields that are defaulted downstream in
    :func:`parse_invoice_payload`. The downstream coercion stage
    (``setdefault`` calls + :func:`_synthesise_single_line_if_needed`)
    fills in required gaps before :class:`Invoice` validation runs.
    """

    invoice_id: NotRequired[str]
    kind: NotRequired[str]
    currency: NotRequired[str]
    counterparty_name: NotRequired[str]
    counterparty_tax_id: NotRequired[str]
    counterparty_country: NotRequired[str]
    payment_status: NotRequired[str]
    lines: NotRequired[list[Any]]
    base_total: NotRequired[str]
    iva_rate: NotRequired[str]
    iva_total: NotRequired[str]


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
    """Parse JSON or CSV invoice payloads into validated :class:`Invoice` models."""
    kind = _coerce_kind(default_kind)
    candidates = _decode_invoice_payload(raw)
    invoices: list[Invoice] = []
    for candidate in candidates:
        payload = dict(candidate)
        payload.setdefault("kind", kind.value)
        raw_kind = payload.get("kind")
        if isinstance(raw_kind, str):
            payload["kind"] = raw_kind.lower()

        payload.setdefault("currency", DEFAULT_CURRENCY)
        payload.setdefault("counterparty_country", "ES")
        payload.setdefault("payment_status", "PAID")
        payload.setdefault("counterparty_name", payload.get("counterparty_tax_id", "Unknown"))
        _synthesise_single_line_if_needed(payload)
        invoices.append(Invoice.model_validate(payload))
    return tuple(invoices)


def merge_invoice_import(catalogue: InvoiceCatalogue, invoices: Sequence[Invoice]) -> InvoiceImportResult:
    """Merge imported invoices into ``catalogue`` without duplicating IDs.

    Args:
        catalogue: The :class:`InvoiceCatalogue` to merge the imported invoices into.
        invoices: Sequence of :class:`Invoice` rows produced by an importer;
            rows whose ``invoice_id`` already exists in ``catalogue`` are
            skipped to preserve catalogue identity.

    Returns an :class:`InvoiceImportResult` with the updated catalogue
    and counts of imported and skipped invoices.
    """
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
    repository: InvoiceCatalogueRepositoryProtocol | None = None,
) -> InvoiceImportResult:
    """Import invoices from ``path`` through the secure invoice repository.

    Returns an :class:`InvoiceImportResult`.
    """
    try:
        raw = path.read_text(encoding=UTF_8_ENCODING)
    except OSError as exc:
        _log.debug("invoice import file read failed", extra={"path_name": path.name, "error_type": type(exc).__name__})
        raise InvoiceValidationError(
            "invoice import file could not be read",
            translated_message="application.invoices.importing.errors.import_file_read_failed",
            context={"path_name": path.name, "error_type": type(exc).__name__},
        ) from exc
    invoices = parse_invoice_payload(raw, default_kind=kind)
    if dry_run:
        return InvoiceImportResult(rows=len(invoices), dry_run=True)

    repo = repository or InvoiceCatalogueRepository()
    result = merge_invoice_import(repo.load(), invoices)
    if result.catalogue is not None:
        repo.save(result.catalogue)
    return result


def _decode_invoice_payload(raw: str) -> tuple[InvoiceRowPayload, ...]:
    raw_stripped = raw.lstrip()
    if raw_stripped.startswith("[") or raw_stripped.startswith("{"):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvoiceValidationError(
                "invoice JSON payload is not valid JSON",
                translated_message="application.invoices.importing.errors.invalid_json",
                context={"line": str(exc.lineno), "column": str(exc.colno)},
            ) from exc
        if isinstance(decoded, Mapping):
            # CAST-RATIONALE-WIRE-PAYLOAD-JSON-OBJECT:
            # json.loads returns Mapping[str, Any]; cast to TypedDict at the
            # decode boundary before downstream coercion.
            return (cast(InvoiceRowPayload, dict(decoded)),)
        if isinstance(decoded, list) and all(isinstance(item, Mapping) for item in decoded):
            # CAST-RATIONALE-WIRE-PAYLOAD-JSON-ARRAY:
            # Same JSON-array decode boundary; each item is cast to TypedDict
            # before coercion.
            return tuple(cast(InvoiceRowPayload, dict(item)) for item in decoded)
        raise InvoiceValidationError(
            "invoice JSON payload must be an object or a list of objects",
            translated_message="application.invoices.importing.errors.invalid_json_shape",
            context={"payload_type": type(decoded).__name__},
        )

    reader = csv.DictReader(raw.splitlines())
    # CAST-RATIONALE-WIRE-PAYLOAD-CSV-ROW:
    # csv.DictReader yields dict[str, str]; cast to TypedDict at the CSV
    # decode boundary before downstream coercion.
    return tuple(cast(InvoiceRowPayload, dict(row)) for row in reader)


# ANY-RETURN-RATIONALE-INVOICE-PARSE-STAGING:
# Parse-stage slot assembled from CSV/JSON decode before
# Invoice.model_validate; typed InvoiceRowPayload TypedDict governs field
# names but dict mutation is required for the line-synthesis back-fill.
# ANY-RETURN-RATIONALE-INVOICE-PARSE-STAGING: payload is a parse-stage dict
# assembled from CSV/JSON decode before Invoice.model_validate; in-place mutation
# is required for the line-synthesis back-fill before the typed boundary.
def _synthesise_single_line_if_needed(payload: dict[str, Any]) -> None:
    if "lines" in payload or "base_total" not in payload or "iva_rate" not in payload:
        return
    base = coerce_decimal(payload["base_total"])
    if base is None:
        raise InvoiceValidationError(
            "invoice base_total is not a decimal",
            translated_message="application.invoices.importing.errors.invalid_base_total",
            context={"base_total": str(payload["base_total"])},
        )
    rate_raw = str(payload["iva_rate"])
    rate = _IVA_RATE_ALIASES.get(rate_raw, rate_raw)
    iva_amount = coerce_decimal(payload.get("iva_total"), default=Decimal("0")) or Decimal("0")
    payload["lines"] = [
        {
            "description": "Imported invoice line",
            "quantity": "1",
            "unit_price": str(base),
            "subtotal": str(base),
            "iva_rate": rate,
            "iva_amount": str(iva_amount),
        },
    ]
    payload.pop("iva_rate", None)


def _coerce_kind(kind: InvoiceKind | str) -> InvoiceKind:
    if isinstance(kind, InvoiceKind):
        return kind
    normalized = kind.strip().lower()
    try:
        return InvoiceKind(normalized)
    except ValueError as exc:
        raise InvoiceValidationError(
            "invoice kind is not supported",
            translated_message="application.invoices.importing.errors.invalid_kind",
            context={"kind": normalized},
        ) from exc


__all__ = [
    "InvoiceImportResult",
    "import_invoices_from_path",
    "merge_invoice_import",
    "parse_invoice_payload",
]
