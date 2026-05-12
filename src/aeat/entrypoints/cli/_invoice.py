from __future__ import annotations

from pathlib import Path

import typer

from ...application.invoices import (
    apply_manual_invoice_match,
    import_invoices_from_path,
    project_invoice_payment_matches,
    project_invoice_reviews,
)
from ...application.review import (
    EditParseError,
    FilterParseError,
    InvoiceEditSpec,
    InvoiceReviewFilterSpec,
    update_invoice_review,
)
from ...application.workflow import workflow_state_repository
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
    result = import_invoices_from_path(path, kind=kind_normalised, dry_run=dry_run, repository=_invoice_repo())
    if dry_run:
        _emit(
            ctx,
            {"rows": result.rows, "dry_run": True},
            [
                f"{tr('cli.invoice.labels.rows')}\t{result.rows}",
                f"{tr('cli.invoice.labels.dry_run')}\t{tr('cli.invoice.labels.yes')}",
            ],
        )
        return
    payload = {
        "rows": result.rows,
        "imported": result.imported,
        "skipped": result.skipped,
    }
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.invoice.labels.rows')}\t{result.rows}",
            f"{tr('cli.invoice.labels.imported')}\t{result.imported}",
            f"{tr('cli.invoice.labels.skipped')}\t{result.skipped}",
        ],
    )


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
    rows = project_invoice_reviews(catalogue, state, spec=spec, invoice_id=invoice_id)

    if invoice_id is not None:
        if rows:
            row = rows[0]
            payload = row.model_dump(mode="python") | {"verbose": verbose}
            _emit(
                ctx,
                payload,
                [
                    f"{tr('cli.invoice.labels.id')}\t{row.id}",
                    f"{tr('cli.invoice.labels.kind')}\t{row.kind}",
                    f"{tr('cli.invoice.labels.base')}\t{row.base}",
                    f"{tr('cli.invoice.labels.iva')}\t{row.iva}",
                    f"{tr('cli.invoice.labels.payment')}\t{row.payment or '-'}",
                ],
            )
            return
        raise _bad(tr("cli.invoice.errors.invoice_not_found", id=invoice_id))
    payload = {"rows": []}
    for row in rows:
        payload["rows"].append(
            {
                "id": row.id,
                "kind": row.kind,
                "base": row.base,
                "iva": row.iva,
                "status": row.status,
                "payment": row.payment,
                "payment.id": row.payment_id,
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

    if not rows:
        lines.append(tr("cli.invoice.review.no_invoices"))
    _emit(ctx, payload, lines)


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
    updated = workflow_state_repository().update(
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
        workflow_state_repository().update(lambda state: apply_manual_invoice_match(state, invoice_id, ledger_id))
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
    projection = project_invoice_payment_matches(
        period=canonical,
        catalogue=catalogue,
        transactions=transactions,
        state=state,
    )
    payload = projection.model_dump(mode="python")
    lines: list[str] = [
        f"{tr('cli.invoice.labels.period')}\t{canonical}",
        f"{tr('cli.invoice.labels.matched')}\t{len(projection.matched)}",
        f"{tr('cli.invoice.labels.unmatched')}\t{len(projection.unmatched)}",
    ]
    _emit(ctx, payload, lines)
