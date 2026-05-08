from __future__ import annotations

import json as _json
import re as _re
from collections.abc import Iterable
from datetime import date as _date
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import typer

from ...application.aggregation import aggregate_renta_ledger_expenses_from_repositories
from ...application.auth import AuthProviderListing
from ...application.user_cli import UserCliState, state_repository
from ...core.paths import PROJECT_ROOT
from ...domain.calculations.registry import (
    ModeloRevision,
    ValidatedRegistryAuthority,
    resolve_ledger_renta_expense_aggregation_binding_values,
)
from ...domain.deadlines import AutonomoProfile, autonomo_profile_from_mapping
from ...domain.filing import FilingDraft, FilingDraftRepository
from ...domain.invoices import InvoiceCatalogue, InvoiceCatalogueRepository
from ...domain.profile import ProfileKey
from ...domain.transactions import TransactionCatalogue, TransactionCatalogueRepository
from ._i18n import tr

# ---------------------------------------------------------------------
# Transport helpers
# ---------------------------------------------------------------------

_FORMAT_TEXT = "text"
_FORMAT_JSON = "json"
_FORMAT_TABLE = "table"


def _format_of(ctx: typer.Context) -> str:
    state = ctx.ensure_object(dict)
    return state.get("format", _FORMAT_TEXT)


def _emit(ctx: typer.Context, payload: Any, lines: Iterable[str]) -> None:
    """Render the result either as JSON or as line-formatted text."""
    if _format_of(ctx) == _FORMAT_JSON:
        typer.echo(_json.dumps(payload, default=_json_default, ensure_ascii=False))
        return
    for line in lines:
        typer.echo(line)


def _json_default(value: Any) -> Any:
    """Coerce non-JSON-native values from typed records."""
    from pydantic import BaseModel

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, _date | datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, set | frozenset):
        return sorted(value)
    raise TypeError(f"cannot JSON-encode {type(value).__name__}")


def _bad(message: str) -> typer.BadParameter:
    return typer.BadParameter(message)


def _exit(code: int) -> None:
    raise typer.Exit(code=code)


def _state() -> UserCliState:
    return state_repository().load()


def _active_profile_or_exit(ctx: typer.Context) -> tuple[UserCliState, str]:
    """Return (state, active_profile_name) or exit code 2 with a typed payload."""
    current = _state()
    if current.active_profile is None:
        _emit(
            ctx,
            {"error": "no-active-profile", "next": "aeat setup init --name NAME"},
            ["error\tno-active-profile", "next\taeat setup init --name NAME"],
        )
        _exit(2)
    assert current.active_profile is not None
    return current, current.active_profile


def _description_for(entry: AuthProviderListing | ProfileKey) -> str:
    return _translate(entry.description)


def _label_for(listing: AuthProviderListing) -> str:
    return _translate(listing.label)


def _translate(translatable: str) -> str:
    """Render a str in the operator's preferred locale (Spanish first)."""
    from ._i18n import tr

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


def _profile_to_autonomo(state: UserCliState) -> AutonomoProfile:
    record = state.active_profile_record()
    return autonomo_profile_from_mapping(record.values if record else {}, tax_id_default="00000000T")


# ---------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------


def _tx_repo() -> TransactionCatalogueRepository:
    return TransactionCatalogueRepository()


def _invoice_repo() -> InvoiceCatalogueRepository:
    return InvoiceCatalogueRepository()


def _draft_repo() -> FilingDraftRepository:
    return FilingDraftRepository()


def _load_transactions() -> TransactionCatalogue:
    return _tx_repo().load()


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


def _aggregate_filing_inputs(modelo: str, period: str, state: UserCliState) -> dict[str, object]:
    """Return filing inputs aggregated from registry-approved sources."""
    del state
    if modelo.strip() == "100" and _annual_filing_year(period) is not None:
        filing_year = _annual_filing_year(period)
        assert filing_year is not None
        return _aggregate_renta_filing_inputs(
            filing_year=filing_year,
            transaction_repository=_tx_repo(),
            invoice_repository=_invoice_repo(),
        )
    return {}


def _aggregate_renta_filing_inputs(
    *,
    filing_year: int,
    transaction_repository: TransactionCatalogueRepository,
    invoice_repository: InvoiceCatalogueRepository,
) -> dict[str, object]:
    aggregation = aggregate_renta_ledger_expenses_from_repositories(
        period=str(filing_year),
        transaction_repository=transaction_repository,
        invoice_repository=invoice_repository,
        profile_year=filing_year,
    )
    authority = ValidatedRegistryAuthority.load(PROJECT_ROOT / "registry" / "aeat", source_root=PROJECT_ROOT)
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
