from __future__ import annotations

import re as _re
from collections.abc import Iterable
from datetime import date as _date
from decimal import Decimal

import typer

from ...application.aggregation import aggregate_renta_ledger_expenses_from_repositories
from ...application.auth import AuthProviderListing
from ...application.workflow import (
    NoActiveProfileError,
    WorkflowState,
    active_bucket_id_or_raise,
    active_transaction_catalogue_repository,
    workflow_state_repository,
)
from ...core.output_rendering import render_command_output
from ...core.resources import resources
from ...domain.calculations.registry import (
    ModeloRevision,
    resolve_ledger_renta_expense_aggregation_binding_values,
)
from ...domain.deadlines import AutonomoProfile, autonomo_profile_from_mapping
from ...domain.filing import FilingDraft, FilingDraftRepository
from ...domain.invoices import InvoiceCatalogue, InvoiceCatalogueRepository
from ...domain.profile import ProfileKey
from ...domain.transactions import LedgerNoActiveBucketError, TransactionCatalogue, TransactionCatalogueRepository
from ...core.i18n import tr

# ---------------------------------------------------------------------
# Transport helpers
# ---------------------------------------------------------------------

_FORMAT_TEXT = "text"
_FORMAT_JSON = "json"
_FORMAT_TABLE = "table"


def _format_of(ctx: typer.Context) -> str:
    state = ctx.ensure_object(dict)
    return state.get("format", _FORMAT_TEXT)


def _emit(ctx: typer.Context, payload: object, lines: Iterable[str]) -> None:
    """Render the result either as JSON or as line-formatted text."""
    rendered = render_command_output(format_name=_format_of(ctx), payload=payload, lines=lines)
    if rendered.text:
        typer.echo(rendered.text)


def _bad(message: str) -> typer.BadParameter:
    return typer.BadParameter(message)


def _exit(code: int) -> None:
    raise typer.Exit(code=code)


def _state() -> WorkflowState:
    return workflow_state_repository().load()


def _active_profile_or_exit(ctx: typer.Context) -> tuple[WorkflowState, str]:
    """Return (state, active_profile_name) or exit code 2 with a typed payload."""
    from ...application.workflow._models import resolve_active_bucket_id

    current = _state()
    active = resolve_active_bucket_id()
    if active is None:
        _emit(
            ctx,
            {"error": "no-active-profile", "next": "aeat config init --profile NAME"},
            ["error\tno-active-profile", "next\taeat config init --profile NAME"],
        )
        _exit(2)
    return current, active


def _description_for(entry: AuthProviderListing | ProfileKey) -> str:
    return _translate(entry.description)


def _label_for(listing: AuthProviderListing) -> str:
    return _translate(listing.label)


def _translate(translatable: str) -> str:
    """Render a str in the operator's preferred locale (Spanish first)."""
    from ...core.i18n import tr

    return tr(translatable)


def _fmt_decimal(value: Decimal | None) -> str:
    if value is None:
        return "0"
    normalized = value.normalize()
    return format(normalized, "f")


# ---------------------------------------------------------------------
# Period normaliser
# ---------------------------------------------------------------------

_PERIOD_RE = _re.compile(r"^(?P<year>\d{4})(?:[-]?Q(?P<quarter>[1-4])|-(?P<month>0[1-9]|1[0-2]))?$", _re.IGNORECASE)


def _canonical_period(raw: str) -> str:
    """Return the upper-case, un-hyphenated period ID or raise _bad."""
    if not raw.strip():
        raise _bad(tr("cli.common.errors.period_empty"))
    match = _PERIOD_RE.fullmatch(raw.strip())
    if match is None:
        raise _bad(tr("cli.common.errors.period_unrecognised", raw=raw))
    year = match.group("year")
    quarter = match.group("quarter")
    month = match.group("month")
    if quarter is not None:
        return f"{year}Q{quarter}"
    if month is not None:
        return f"{year}-{month}"
    return year


def _parse_iso_date(raw: str, *, label: str) -> _date:
    try:
        return _date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise _bad(tr("cli.common.errors.invalid_iso_date", label=label, raw=raw)) from exc


def _profile_to_autonomo(state: WorkflowState) -> AutonomoProfile:
    from ...application.user_profile._projections import record_to_values

    record = state.active_profile_record()
    raw = record_to_values(record) if record is not None else {}
    return autonomo_profile_from_mapping(raw, tax_id_default="00000000T")


# ---------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------


def _active_bucket_id_or_bad(state: WorkflowState) -> str:
    """Return the active profile bucket id or raise the CLI 'bad' error."""

    try:
        return active_bucket_id_or_raise()
    except NoActiveProfileError as exc:
        raise _bad(tr("cli.common.errors.no_active_profile")) from exc


def _tx_repo(state: WorkflowState) -> TransactionCatalogueRepository:
    try:
        return active_transaction_catalogue_repository(state)
    except LedgerNoActiveBucketError as exc:
        raise _bad(tr("cli.common.errors.no_active_profile")) from exc


def _invoice_repo() -> InvoiceCatalogueRepository:
    return InvoiceCatalogueRepository()


def _draft_repo() -> FilingDraftRepository:
    return FilingDraftRepository()


def _load_transactions(state: WorkflowState) -> TransactionCatalogue:
    return _tx_repo(state).load()


def _load_invoices() -> InvoiceCatalogue:
    return _invoice_repo().load()


def _load_drafts() -> tuple[FilingDraft, ...]:
    repo = _draft_repo()
    return tuple(repo.iter_drafts())


def _draft_by_id(draft_id: str) -> FilingDraft:
    for draft in _load_drafts():
        if draft.draft_id == draft_id:
            return draft
    raise _bad(f"draft id {draft_id!r} not found")


def _aggregate_filing_inputs(modelo: str, period: str, state: WorkflowState) -> dict[str, object]:
    """Return filing inputs aggregated from registry-approved sources."""
    if modelo.strip() == "100" and _annual_filing_year(period) is not None:
        filing_year = _annual_filing_year(period)
        assert filing_year is not None
        return _aggregate_renta_filing_inputs(
            bucket_id=_active_bucket_id_or_bad(state),
            filing_year=filing_year,
            transaction_repository=_tx_repo(state),
            invoice_repository=_invoice_repo(),
        )
    return {}


def _aggregate_renta_filing_inputs(
    *,
    bucket_id: str,
    filing_year: int,
    transaction_repository: TransactionCatalogueRepository,
    invoice_repository: InvoiceCatalogueRepository,
) -> dict[str, object]:
    aggregation = aggregate_renta_ledger_expenses_from_repositories(
        bucket_id=bucket_id,
        period=str(filing_year),
        transaction_repository=transaction_repository,
        invoice_repository=invoice_repository,
        profile_year=filing_year,
    )
    authority = resources().modelos.authority
    snapshot = authority.snapshot("100", filing_year=filing_year, period="0A")
    binding_values = resolve_ledger_renta_expense_aggregation_binding_values(
        snapshot.revision,
        aggregation.observations,
    )
    return _bound_inputs_from_available_bindings(snapshot.revision, binding_values)


def _bound_inputs_from_available_bindings(
    revision: ModeloRevision,
    binding_values: dict[str, Decimal],
) -> dict[str, object]:
    return {
        casilla.id: binding_values[casilla.binding]
        for casilla in revision.casillas
        if casilla.input_kind == "bound" and casilla.binding is not None and casilla.binding in binding_values
    }


def _annual_filing_year(period: str) -> int | None:
    text = period.strip().upper()
    if _re.fullmatch(r"\d{4}", text):
        return int(text)
    if _re.fullmatch(r"\d{4}A", text):
        return int(text[:4])
    return None
