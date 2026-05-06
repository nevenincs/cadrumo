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
from ._i18n import tr

app = typer.Typer(
    name="invoice",
    help=tr("cli.invoice.app_help"),
    no_args_is_help=True,
)


@app.command("import", help=tr("cli.invoice.import.help"))
def invoice_import(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help=tr("cli.invoice.import.path_help")),
    kind: str = typer.Option(..., "--kind", help=tr("cli.invoice.import.kind_help")),
    dry_run: bool = typer.Option(False, "--dry-run", help=tr("cli.invoice.import.dry_run_help")),
) -> None:
    """Parse one or more invoice records and merge into the local catalogue."""
    if not path.exists():
        raise _bad(tr("cli.invoice.errors.file_not_found", path=str(path)))
    kind_normalised = kind.strip().upper()
    if kind_normalised not in {"ISSUED", "RECEIVED"}:
        raise _bad(tr("cli.invoice.errors.invalid_kind"))
    raw = path.read_text(encoding="utf-8")
    rows = _parse_invoice_payload(raw, kind_normalised)
    if dry_run:
        _emit(
            ctx,
            {"rows": len(rows), "dry_run": True},
            [
                f"{tr('cli.invoice.labels.rows')}\t{len(rows)}",
                f"{tr('cli.invoice.labels.dry_run')}\t{tr('cli.invoice.labels.yes')}",
            ],
        )
        return
    repo = _invoice_repo()
    catalogue = repo.load()
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
    payload = {
        "rows": len(rows),
        "imported": imported,
        "skipped": skipped,
    }
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.invoice.labels.rows')}\t{len(rows)}",
            f"{tr('cli.invoice.labels.imported')}\t{imported}",
            f"{tr('cli.invoice.labels.skipped')}\t{skipped}",
        ],
    )


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


@app.command("review", help=tr("cli.invoice.review.help"))
def invoice_review(
    ctx: typer.Context,
    filters: list[str] = typer.Option([], "--filter", help=tr("cli.invoice.review.filter_help")),
    invoice_id: str | None = typer.Option(None, "--id", help=tr("cli.invoice.review.id_help")),
    verbose: bool = typer.Option(False, "--verbose", help=tr("cli.invoice.review.verbose_help")),
) -> None:
    try:
        spec = InvoiceReviewFilterSpec.from_strings(filters)
    except FilterParseError as exc:
        raise _bad(tr("cli.invoice.errors.filter_parse_error", reason=exc.reason, token=exc.raw_token)) from exc
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
                    "base": _fmt_decimal(base),
                    "iva": _fmt_decimal(iva),
                    "payment": review.fields.get("payment.id") if review else None,
                    "review": review,
                    "verbose": verbose,
                }
                payment_id = review.fields.get("payment.id", "-") if review else "-"
                _emit(
                    ctx,
                    payload,
                    [
                        f"{tr('cli.invoice.labels.id')}\t{inv.invoice_id}",
                        f"{tr('cli.invoice.labels.kind')}\t{inv.kind.value}",
                        f"{tr('cli.invoice.labels.base')}\t{_fmt_decimal(base)}",
                        f"{tr('cli.invoice.labels.iva')}\t{_fmt_decimal(iva)}",
                        f"{tr('cli.invoice.labels.payment')}\t{payment_id}",
                    ],
                )
                return
        raise _bad(tr("cli.invoice.errors.invoice_not_found", id=invoice_id))
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
                "payment": review.fields.get("payment.id") if review else None,
                "payment.id": review.fields.get("payment.id") if review else None,
            }
        )

    lines: list[str] = [
        f"{tr('cli.invoice.labels.id')}\t"
        f"{tr('cli.invoice.labels.kind')}\t"
        f"{tr('cli.invoice.labels.base')}\t"
        f"{tr('cli.invoice.labels.iva')}\t"
        f"{tr('cli.invoice.labels.status')}"
    ]
    for row in payload["rows"]:
        lines.append(f"{row['id'][:12]}\t{row['kind']}\t{row['base']}\t{row['iva']}\t{row['status']}")

    if not invoices:
        lines.append(tr("cli.invoice.review.no_invoices"))
    _emit(ctx, payload, lines)


def _invoice_row_status(inv: Invoice, state: UserCliState) -> str:
    review = state.invoice_reviews.get(inv.invoice_id)
    if review and review.fields.get("payment.id"):
        return "paid"
    if review and review.fields:
        return "reviewed"
    return "pending"


@app.command("edit", help=tr("cli.invoice.edit.help"))
def invoice_edit(
    ctx: typer.Context,
    invoice_id: str = typer.Option(..., "--id", help=tr("cli.invoice.edit.id_help")),
    sets: list[str] = typer.Option([], "--set", help=tr("cli.invoice.edit.set_help")),
    reason: str = typer.Option(..., "--reason", help=tr("cli.invoice.edit.reason_help")),
) -> None:
    catalogue = _load_invoices()
    if invoice_id not in catalogue.invoices:
        raise _bad(tr("cli.invoice.errors.invoice_not_found", id=invoice_id))
    try:
        spec = InvoiceEditSpec.from_strings(sets)
    except EditParseError as exc:
        raise _bad(tr("cli.invoice.errors.set_parse_error", reason=exc.reason, token=exc.raw_token)) from exc
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
        raise _bad(tr("cli.invoice.errors.at_least_one_edit"))
    updated = state_repository().update(
        lambda current: update_invoice_review(current, invoice_id, fields=fields, action="edit", reason=reason)
    )
    review = updated.invoice_reviews.get(invoice_id)
    _emit(
        ctx,
        {"id": invoice_id, "review": review},
        [
            f"{tr('cli.invoice.labels.id')}\t{invoice_id}",
            f"{tr('cli.invoice.labels.fields')}\t{', '.join(sorted(review.fields)) if review else '-'}",
        ],
    )


@app.command("match", help=tr("cli.invoice.match.help"))
def invoice_match(
    ctx: typer.Context,
    period: str = typer.Option(..., "--period", help=tr("cli.invoice.match.period_help")),
    invoice_id: str | None = typer.Option(None, "--invoice", help=tr("cli.invoice.match.invoice_help")),
    ledger_id: str | None = typer.Option(None, "--ledger", help=tr("cli.invoice.match.ledger_help")),
) -> None:
    """List invoices whose payment.id has a matching ledger row for ``period``.

    If both --invoice and --ledger are provided, records a manual match
    and persists it to the user state.
    """
    if (invoice_id is not None) != (ledger_id is not None):
        raise _bad(tr("cli.invoice.errors.match_both_required"))

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
        _emit(
            ctx,
            {"invoice": invoice_id, "payment": ledger_id, "status": "matched"},
            [f"{tr('cli.invoice.labels.matched')}\t{tr('cli.invoice.labels.yes')}"],
        )
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
    payload = {
        "period": canonical,
        "matched": matched,
        "unmatched": unmatched,
    }
    lines: list[str] = [
        f"{tr('cli.invoice.labels.period')}\t{canonical}",
        f"{tr('cli.invoice.labels.matched')}\t{len(matched)}",
        f"{tr('cli.invoice.labels.unmatched')}\t{len(unmatched)}",
    ]
    _emit(ctx, payload, lines)
