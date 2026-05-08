from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path
from typing import Any

import typer

from ...adapters.inbound.financial.providers import (
    CsvProvider,
    FinancialProvider,
    FinancialProviderError,
    OfxProvider,
    PdfN26Provider,
    ProviderValidation,
    XlsxProvider,
    detect_provider,
)
from ...application.review import EditParseError, FilterParseError, LedgerEditSpec, LedgerReviewFilterSpec
from ...application.user_cli import (
    LedgerSplit,
    UserCliState,
    state_repository,
    update_ledger_review,
)
from ...domain.transactions import (
    Transaction,
    TransactionDirection,
)
from ._common import (
    _bad,
    _canonical_period,
    _emit,
    _fmt_decimal,
    _load_transactions,
    _state,
    _tx_repo,
)
from ._i18n import tr

app = typer.Typer(
    name="ledger",
    help=tr("cli.ledger.app_help"),
    no_args_is_help=True,
)


def _direction_resolver(raw: Any) -> TransactionDirection:
    """Resolve a raw transaction's :class:`TransactionDirection` from amount sign."""
    return TransactionDirection.OUTGOING if raw.amount < 0 else TransactionDirection.INCOMING


@app.command("import", help=tr("cli.ledger.import.help"))
def ledger_import(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help=tr("cli.ledger.import.path_help")),
    provider: str = typer.Option(..., "--provider", help=tr("cli.ledger.import.provider_help")),
    dry_run: bool = typer.Option(False, "--dry-run", help=tr("cli.ledger.import.dry_run_help")),
    verify: bool = typer.Option(False, "--verify", help=tr("cli.ledger.import.verify_help")),
    source: Path | None = typer.Option(None, "--source", help=tr("cli.ledger.import.source_help")),
    verbose: bool = typer.Option(False, "--verbose", help=tr("cli.ledger.import.verbose_help")),
    period: str | None = typer.Option(None, "--period", help=tr("cli.ledger.import.period_help")),
) -> None:
    """Import a financial-statement file via the existing provider registry."""
    pid = provider.strip().lower()
    if pid == "auto":
        chosen = detect_provider(path)
        if chosen is None:
            raise _bad(tr("cli.ledger.errors.auto_detect_failed", path=str(path)))
    elif pid in {"csv"}:
        chosen = CsvProvider()
    elif pid in {"ofx", "qfx"}:
        chosen = OfxProvider()
    elif pid in {"xlsx", "excel"}:
        chosen = XlsxProvider()
    elif pid == "n26":
        chosen = detect_provider(path)
        if chosen is None:
            raise _bad(tr("cli.ledger.errors.n26_auto_detect_failed", path=str(path)))
    elif pid in {"pdf", "pdf-n26"}:
        chosen = PdfN26Provider()
    else:
        raise _bad(tr("cli.ledger.errors.unknown_provider", provider=provider))
    validation = _validate_import_source(chosen, path)
    source_verification = _build_source_verification(source=source, verify=verify)
    try:
        raws = list(chosen.ingest(path))
    except FinancialProviderError as exc:
        raise _bad(tr("cli.ledger.errors.invalid_source").format(reason=str(exc))) from exc
    if dry_run:
        payload = {
            "rows": len(raws),
            "imported": 0,
            "skipped": 0,
            "dry_run": True,
            "verify": verify,
            "validation": _validation_payload(validation),
            "source": source_verification,
        }
        lines = [
            f"{tr('cli.ledger.labels.rows')}\t{len(raws)}",
            f"{tr('cli.ledger.labels.dry_run')}\t{tr('cli.ledger.labels.yes')}",
        ]
        if verbose or verify:
            lines.extend(_validation_lines(validation, source_verification))
        _emit(ctx, payload, lines)
        return
    summary = _tx_repo().merge_raw_transactions(raws, direction_resolver=_direction_resolver)
    payload = {
        "rows": len(raws),
        "imported": summary.imported,
        "skipped": summary.skipped,
        "dry_run": False,
        "verify": verify,
        "period": _canonical_period(period) if period else None,
        "validation": _validation_payload(validation),
        "source": source_verification,
    }
    lines = [
        f"{tr('cli.ledger.labels.rows')}\t{len(raws)}",
        f"{tr('cli.ledger.labels.imported')}\t{summary.imported}",
        f"{tr('cli.ledger.labels.skipped')}\t{summary.skipped}",
    ]
    if verbose or verify:
        lines.extend(_validation_lines(validation, source_verification))
    _emit(
        ctx,
        payload,
        lines,
    )


def _validate_import_source(provider: FinancialProvider, path: Path) -> ProviderValidation:
    validation = provider.validate_source(path)
    if not validation.is_valid:
        reason = "; ".join(validation.warnings) or tr("cli.ledger.errors.invalid_source_unknown")
        raise _bad(tr("cli.ledger.errors.invalid_source").format(reason=reason))
    return validation


def _build_source_verification(*, source: Path | None, verify: bool) -> dict[str, Any]:
    if not verify:
        return {"requested": False, "path": None, "sha256": None}
    if source is None:
        return {"requested": True, "path": None, "sha256": None}
    resolved = source.resolve()
    if not resolved.exists() or not resolved.is_file():
        raise _bad(tr("cli.ledger.errors.source_not_found").format(source=source))
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return {"requested": True, "path": str(resolved), "sha256": digest}


def _validation_payload(validation: ProviderValidation) -> dict[str, Any]:
    return {
        "valid": validation.is_valid,
        "warnings": list(validation.warnings),
        "encoding": validation.detected_encoding,
        "dialect": validation.detected_dialect,
    }


def _validation_lines(validation: ProviderValidation, source_verification: dict[str, Any]) -> list[str]:
    valid_label = tr("cli.ledger.labels.yes") if validation.is_valid else tr("cli.ledger.labels.no")
    lines = [
        f"{tr('cli.ledger.labels.valid')}\t{valid_label}",
        f"{tr('cli.ledger.labels.dialect')}\t{validation.detected_dialect or '-'}",
    ]
    if validation.warnings:
        lines.append(f"{tr('cli.ledger.labels.warnings')}\t{'; '.join(validation.warnings)}")
    if source_verification["requested"]:
        lines.append(f"{tr('cli.ledger.labels.source')}\t{source_verification['path'] or '-'}")
    return lines


@app.command("review", help=tr("cli.ledger.review.help"))
def ledger_review(
    ctx: typer.Context,
    filters: list[str] = typer.Option([], "--filter", help=tr("cli.ledger.review.filter_help")),
    record_id: str | None = typer.Option(None, "--id", help=tr("cli.ledger.review.id_help")),
    verbose: bool = typer.Option(False, "--verbose", help=tr("cli.ledger.review.verbose_help")),
) -> None:
    """Render rows or a single row using the typed filter spec."""
    try:
        spec = LedgerReviewFilterSpec.from_strings(filters)
    except FilterParseError as exc:
        raise _bad(tr("cli.ledger.errors.filter_parse_error", reason=exc.reason, token=exc.raw_token)) from exc
    catalogue = _load_transactions()
    state = _state()
    rows: list[Transaction] = list(catalogue.transactions.values())
    if spec.period:
        canonical = _canonical_period(spec.period)
        rows = [tx for tx in rows if (tx.raw.value_date or tx.raw.booked_date).isoformat().startswith(canonical[:4])]
    if spec.status is not None:
        rows = [tx for tx in rows if _ledger_row_status(tx, state) == spec.status.value]
    if record_id is not None:
        for tx in rows:
            if tx.transaction_id == record_id:
                review = state.ledger_reviews.get(record_id)
                amount_val = tx.raw.amount
                if review and "amount" in review.fields:
                    amount_val = Decimal(review.fields["amount"])

                single_payload: dict[str, object] = {
                    "id": tx.transaction_id,
                    "date": (tx.raw.value_date or tx.raw.booked_date).isoformat(),
                    "amount": _fmt_decimal(amount_val),
                    "description": tx.raw.description,
                    "review": review,
                    "verbose": verbose,
                }
                _emit(
                    ctx,
                    single_payload,
                    [
                        f"{tr('cli.ledger.labels.id')}\t{tx.transaction_id}",
                        f"{tr('cli.ledger.labels.date')}\t{(tx.raw.value_date or tx.raw.booked_date).isoformat()}",
                        f"{tr('cli.ledger.labels.amount')}\t{_fmt_decimal(amount_val)}",
                        f"{tr('cli.ledger.labels.description')}\t{tx.raw.description}",
                    ],
                )
                return
        raise _bad(tr("cli.ledger.errors.row_not_found", id=record_id))
    list_payload: dict[str, object] = {
        "rows": [
            {
                "id": tx.transaction_id,
                "date": (tx.raw.value_date or tx.raw.booked_date).isoformat(),
                "amount": format(tx.raw.amount, "f"),
                "description": tx.raw.description,
                "status": _ledger_row_status(tx, state),
            }
            for tx in rows
        ],
        "filters": list(spec.clauses),
    }
    lines: list[str] = [tr("cli.ledger.review.header")]
    lines.extend(
        f"{tx.transaction_id[:8]}\t{(tx.raw.value_date or tx.raw.booked_date).isoformat()}\t"
        f"{format(tx.raw.amount, 'f')}\t{tx.raw.description}\t{_ledger_row_status(tx, state)}"
        for tx in rows
    )
    if not rows:
        lines.append(tr("cli.ledger.review.no_rows"))
    _emit(ctx, list_payload, lines)


def _ledger_row_status(tx: Transaction, state: UserCliState) -> str:
    review = state.ledger_reviews.get(tx.transaction_id)
    if review and review.skipped:
        return "skipped"
    if review and review.fields:
        return "reviewed"
    return "pending"


@app.command("edit", help=tr("cli.ledger.edit.help"))
def ledger_edit(
    ctx: typer.Context,
    record_id: str = typer.Option(..., "--id", help=tr("cli.ledger.edit.id_help")),
    sets: list[str] = typer.Option([], "--set", help=tr("cli.ledger.edit.set_help")),
    skip: str | None = typer.Option(None, "--skip", help=tr("cli.ledger.edit.skip_help")),
    splits: list[str] = typer.Option([], "--split", help=tr("cli.ledger.edit.split_help")),
    reason: str = typer.Option(..., "--reason", help=tr("cli.ledger.edit.reason_help")),
) -> None:
    """Apply a typed edit to one ledger row."""
    catalogue = _load_transactions()
    if record_id not in catalogue.transactions:
        raise _bad(tr("cli.ledger.errors.row_not_found", id=record_id))
    try:
        spec = LedgerEditSpec.from_strings(sets)
    except EditParseError as exc:
        raise _bad(tr("cli.ledger.errors.set_parse_error", reason=exc.reason, token=exc.raw_token)) from exc
    fields: dict[str, str] = {}
    if spec.category is not None:
        fields["category"] = spec.category
    if spec.business_share is not None:
        fields["business.share"] = format(spec.business_share, "f")
    if spec.reference is not None:
        fields["reference"] = spec.reference
    if spec.comments is not None:
        fields["comments"] = spec.comments
    if spec.document_path is not None:
        fields["document.path"] = str(spec.document_path)

    skip_flag: bool | None = None
    if skip is not None:
        skip_normalised = skip.strip().lower()
        if skip_normalised in {"true", "yes", "1"}:
            skip_flag = True
        elif skip_normalised in {"false", "no", "0"}:
            skip_flag = False
        else:
            raise _bad(tr("cli.ledger.errors.invalid_skip"))

    split_value: LedgerSplit | None = None
    clear_split = False
    if splits:
        if len(splits) == 1 and splits[0].strip().lower() == "clear":
            clear_split = True
        else:
            shares: dict[str, Decimal] = {}
            for raw in splits:
                if "=" not in raw:
                    raise _bad(tr("cli.ledger.errors.invalid_split_format", raw=raw))
                k, _, v = raw.partition("=")
                try:
                    shares[k.strip().lower()] = Decimal(v.strip())
                except Exception as exc:
                    raise _bad(tr("cli.ledger.errors.invalid_split_value", v=v)) from exc
            if "business" not in shares or "personal" not in shares:
                raise _bad(tr("cli.ledger.errors.match_both_required"))
            split_value = LedgerSplit(
                business_share=shares["business"], personal_share=shares["personal"], reason=reason
            )

    if not (fields or skip_flag is not None or split_value is not None or clear_split):
        raise _bad(tr("cli.ledger.errors.edit_requires_one"))

    updated = state_repository().update(
        lambda current: update_ledger_review(
            current,
            record_id,
            fields=fields or None,
            skipped=skip_flag,
            split=split_value,
            clear_split=clear_split,
            action="edit",
            reason=reason,
        )
    )
    review = updated.ledger_reviews.get(record_id)
    payload = {"id": record_id, "review": review}
    skipped_label = tr("cli.ledger.labels.yes") if review and review.skipped else tr("cli.ledger.labels.no")
    fields_label = ", ".join(sorted(review.fields)) if review else "-"
    _emit(
        ctx,
        payload,
        [
            f"{tr('cli.ledger.labels.id')}\t{record_id}",
            f"{tr('cli.ledger.labels.skipped')}\t{skipped_label}",
            f"{tr('cli.ledger.labels.fields')}\t{fields_label}",
        ],
    )
