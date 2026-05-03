from __future__ import annotations

import contextlib
import json as _json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import typer

from ...application.review import EditParseError, FilterParseError, InvoiceEditSpec, InvoiceReviewFilterSpec
from ...application.user_cli import (
    UserCliState,
    state_repository,
    update_invoice_review,
)
from ...domain.invoices import Invoice, InvoiceCatalogue
from ._common import (
    _bad,
    _canonical_period,
    _emit,
    _fmt_decimal,
    _invoice_repo,
    _load_invoices,
    _load_transactions,
    _state,
)

app = typer.Typer(
    name="invoice",
    help="Invoice records: import, review, edit, match.",
    no_args_is_help=True,
)


@app.command("import", help="Import an invoice JSON / CSV file into the catalogue.")
def invoice_import(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Source invoice file."),
    kind: str = typer.Option(..., "--kind", help="issued | received."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse only; do not persist."),
) -> None:
    """Parse one or more invoice records and merge into the local catalogue."""
    if not path.exists():
        raise _bad(f"invoice file {path} does not exist")
    kind_normalised = kind.strip().upper()
    if kind_normalised not in {"ISSUED", "RECEIVED"}:
        raise _bad("--kind must be issued or received")
    raw = path.read_text(encoding="utf-8")
    rows = _parse_invoice_payload(raw, kind_normalised)
    if dry_run:
        _emit(ctx, {"rows": len(rows), "dry_run": True}, [f"rows\t{len(rows)}", "dry_run\tyes"])
        return
    repo = _invoice_repo()
    catalogue = repo.load() if repo.envelope_path.exists() else InvoiceCatalogue()
    existing = dict(catalogue.invoices)
    imported = 0
    skipped = 0
    for entry in rows:
        if entry.invoice_id in existing:
            skipped += 1
            continue
        existing[entry.invoice_id] = entry
        imported += 1
    repo.save(InvoiceCatalogue.model_validate({"invoices": existing}))
    payload = {"rows": len(rows), "imported": imported, "skipped": skipped}
    _emit(ctx, payload, [f"rows\t{len(rows)}", f"imported\t{imported}", f"skipped\t{skipped}"])


def _parse_invoice_payload(raw: str, kind: str) -> tuple[Any, ...]:
    candidates: list[dict[str, Any]] = []
    raw_stripped = raw.lstrip()
    if raw_stripped.startswith("[") or raw_stripped.startswith("{"):
        decoded = _json.loads(raw)
        candidates = decoded if isinstance(decoded, list) else [decoded]
    else:
        import csv

        reader = csv.DictReader(raw.splitlines())
        candidates = [dict(row) for row in reader]
    invoices: list[Invoice] = []
    for candidate in candidates:
        candidate.setdefault("kind", kind)
        if "kind" in candidate and isinstance(candidate["kind"], str):
            candidate["kind"] = candidate["kind"].upper()

        candidate.setdefault("currency", "EUR")
        candidate.setdefault("counterparty_country", "ES")
        candidate.setdefault("payment_status", "PAID")
        if "counterparty_name" not in candidate:
            candidate["counterparty_name"] = candidate.get("counterparty_tax_id", "Unknown")

        if "lines" not in candidate and "base_total" in candidate and "iva_rate" in candidate:
            base = Decimal(candidate["base_total"])
            rate_raw = str(candidate["iva_rate"])
            rate = {"21": "RATE_21", "10": "RATE_10", "4": "RATE_4", "0": "RATE_0"}.get(rate_raw, rate_raw)
            iva_amount = Decimal(candidate.get("iva_total", "0"))
            candidate["lines"] = [
                {
                    "description": "Imported invoice line",
                    "quantity": "1",
                    "unit_price": str(base),
                    "subtotal": str(base),
                    "iva_rate": rate,
                    "iva_amount": str(iva_amount),
                }
            ]
            candidate.pop("iva_rate", None)

        invoices.append(Invoice.model_validate(candidate))
    return tuple(invoices)


@app.command("review", help="List invoice records, optionally filtered.")
def invoice_review(
    ctx: typer.Context,
    filters: list[str] = typer.Option([], "--filter", help="--filter KEY=VALUE (status, kind)."),
    invoice_id: str | None = typer.Option(None, "--id", help="Show one invoice."),
    verbose: bool = typer.Option(False, "--verbose", help="Show invoice lines and review history."),
) -> None:
    try:
        spec = InvoiceReviewFilterSpec.from_strings(filters)
    except FilterParseError as exc:
        raise _bad(f"--filter parse error ({exc.reason}): {exc.raw_token}") from exc
    catalogue = _load_invoices()
    state = _state()
    invoices = list(catalogue.values())
    if spec.kind is not None:
        invoices = [inv for inv in invoices if inv.kind is spec.kind]
    if spec.status is not None:
        invoices = [inv for inv in invoices if _invoice_row_status(inv, state) == spec.status.value]

    if invoice_id is not None:
        for inv in invoices:
            if inv.invoice_id == invoice_id:
                review = state.invoice_reviews.get(invoice_id)
                base = inv.base_total
                iva = inv.iva_total
                rate_decimal = None
                if review:
                    if "base" in review.fields:
                        base = Decimal(review.fields["base"])
                    if "iva.rate" in review.fields:
                        rate_raw = review.fields["iva.rate"]
                        if rate_raw.startswith("RATE_"):
                            rate_decimal = Decimal(rate_raw[5:]) / Decimal("100")
                        else:
                            with contextlib.suppress(InvalidOperation):
                                rate_decimal = Decimal(rate_raw) / Decimal("100")
                    if "iva.amount" in review.fields:
                        iva = Decimal(review.fields["iva.amount"])
                    elif rate_decimal is not None and base is not None:
                        iva = (base * rate_decimal).quantize(Decimal("0.01"))

                payload = {
                    "id": inv.invoice_id,
                    "kind": inv.kind.value,
                    "issued_at": inv.issued_at.isoformat() if inv.issued_at else None,
                    "base_total": _fmt_decimal(base),
                    "iva_total": _fmt_decimal(iva),
                    "payment.id": review.fields.get("payment.id") if review else None,
                    "review": review,
                    "verbose": verbose,
                }
                _emit(
                    ctx,
                    payload,
                    [
                        f"id\t{inv.invoice_id}",
                        f"kind\t{inv.kind.value}",
                        f"base\t{_fmt_decimal(base)}",
                        f"iva\t{_fmt_decimal(iva)}",
                        f"payment\t{review.fields.get('payment.id', '-') if review else '-'}",
                    ],
                )
                return
        raise _bad(f"invoice {invoice_id!r} not found")
    payload = {"rows": []}
    for inv in invoices:
        review = state.invoice_reviews.get(inv.invoice_id)
        base = inv.base_total
        iva = inv.iva_total
        rate_decimal = None
        if review:
            if "base" in review.fields:
                base = Decimal(review.fields["base"])
            if "iva.rate" in review.fields:
                rate_raw = review.fields["iva.rate"]
                if rate_raw.startswith("RATE_"):
                    rate_decimal = Decimal(rate_raw[5:]) / Decimal("100")
                else:
                    with contextlib.suppress(InvalidOperation):
                        rate_decimal = Decimal(rate_raw) / Decimal("100")
            if "iva.amount" in review.fields:
                iva = Decimal(review.fields["iva.amount"])
            elif rate_decimal is not None and base is not None:
                iva = (base * rate_decimal).quantize(Decimal("0.01"))

        status = _invoice_row_status(inv, state)
        payload["rows"].append(
            {
                "id": inv.invoice_id,
                "kind": inv.kind.value,
                "base": _fmt_decimal(base),
                "iva": _fmt_decimal(iva),
                "status": status,
                "payment.id": review.fields.get("payment.id") if review else None,
            }
        )

    lines: list[str] = ["id\tkind\tbase\tiva\tstatus"]
    for row in payload["rows"]:
        lines.append(f"{row['id'][:12]}\t{row['kind']}\t{row['base']}\t{row['iva']}\t{row['status']}")

    if not invoices:
        lines.append("(no invoices)")
    _emit(ctx, payload, lines)


def _invoice_row_status(inv: Invoice, state: UserCliState) -> str:
    review = state.invoice_reviews.get(inv.invoice_id)
    if review and review.fields.get("payment.id"):
        return "paid"
    if review and review.fields:
        return "reviewed"
    return "pending"


@app.command("edit", help="Edit an invoice record via --set (base, iva.rate, iva.amount, payment.id, document.path).")
def invoice_edit(
    ctx: typer.Context,
    invoice_id: str = typer.Option(..., "--id", help="Invoice id."),
    sets: list[str] = typer.Option([], "--set", help="--set KEY=VALUE invoice metadata override."),
    reason: str = typer.Option(..., "--reason", help="Audit-trail reason for the edit."),
) -> None:
    catalogue = _load_invoices()
    if invoice_id not in catalogue.invoices:
        raise _bad(f"invoice {invoice_id!r} not found")
    try:
        spec = InvoiceEditSpec.from_strings(sets)
    except EditParseError as exc:
        raise _bad(f"--set parse error ({exc.reason}): {exc.raw_token}") from exc
    fields: dict[str, str] = {}
    for key, value in (
        ("base", spec.base),
        ("iva.rate", spec.iva_rate),
        ("iva.amount", spec.iva_amount),
        ("retention.rate", spec.retention_rate),
        ("retention.amount", spec.retention_amount),
    ):
        if value is not None:
            fields[key] = _fmt_decimal(value)
    if spec.iva_category is not None:
        fields["iva.category"] = spec.iva_category
    if spec.payment_id is not None:
        fields["payment.id"] = spec.payment_id
    if spec.reference is not None:
        fields["reference"] = spec.reference
    if spec.comments is not None:
        fields["comments"] = spec.comments
    if spec.document_path is not None:
        fields["document.path"] = str(spec.document_path)
    if not fields:
        raise _bad("invoice edit requires at least one --set KEY=VALUE")
    updated = state_repository().update(
        lambda current: update_invoice_review(current, invoice_id, fields=fields, action="edit", reason=reason)
    )
    review = updated.invoice_reviews.get(invoice_id)
    _emit(
        ctx,
        {"id": invoice_id, "review": review},
        [f"id\t{invoice_id}", f"fields\t{', '.join(sorted(review.fields)) if review else '-'}"],
    )


@app.command("match", help="Match invoices to ledger rows by stored payment.id for a period.")
def invoice_match(
    ctx: typer.Context,
    period: str = typer.Option(..., "--period", help="Period to scope the match."),
    invoice_id: str | None = typer.Option(None, "--invoice", help="Manual match: invoice id."),
    ledger_id: str | None = typer.Option(None, "--ledger", help="Manual match: ledger id."),
) -> None:
    """List invoices whose payment.id has a matching ledger row for ``period``.

    If both --invoice and --ledger are provided, records a manual match
    and persists it to the user state.
    """
    if (invoice_id is not None) != (ledger_id is not None):
        raise _bad("--invoice and --ledger must be provided together for manual matching")

    if invoice_id and ledger_id:
        state_repository().update(
            lambda state: update_invoice_review(
                state,
                invoice_id,
                fields={"payment.id": ledger_id},
                action="match",
                reason="manual match",
            )
        )
        _emit(ctx, {"invoice": invoice_id, "payment": ledger_id, "status": "matched"}, ["matched\tyes"])
        return

    canonical = _canonical_period(period)
    catalogue = _load_invoices()
    transactions = _load_transactions()
    state = _state()
    matched: list[dict[str, str]] = []
    unmatched: list[dict[str, str]] = []
    for inv in catalogue.values():
        review = state.invoice_reviews.get(inv.invoice_id)
        pid = (review.fields.get("payment.id") if review else None) or ""
        if pid and pid in transactions.transactions:
            matched.append({"invoice": inv.invoice_id, "payment": pid})
        else:
            unmatched.append({"invoice": inv.invoice_id})
    payload = {"period": canonical, "matched": matched, "unmatched": unmatched}
    lines: list[str] = [
        f"period\t{canonical}",
        f"matched\t{len(matched)}",
        f"unmatched\t{len(unmatched)}",
    ]
    _emit(ctx, payload, lines)
