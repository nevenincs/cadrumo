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

from ...application.auth import AuthProviderListing
from ...application.user_cli import UserCliState, state_repository
from ...domain.deadlines import AutonomoProfile, IVARegime
from ...domain.filing import FilingDraft, FilingDraftRepository
from ...domain.invoices import InvoiceCatalogue, InvoiceCatalogueRepository
from ...domain.profile import ProfileKey
from ...domain.transactions import TransactionCatalogue, TransactionCatalogueRepository

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
    return translatable


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
    """Normalise ``2026-Q1`` / ``2026Q1`` / ``2026-01`` / ``2026`` to canonical form."""
    if not raw:
        raise _bad("--period must not be empty")
    match = _PERIOD_RE.fullmatch(raw.strip())
    if match is None:
        raise _bad(f"unrecognised period {raw!r}; expected YYYY, YYYY-MM, YYYYQn, or YYYY-Qn")
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
        raise _bad(f"{label} must be ISO YYYY-MM-DD; got {raw!r}") from exc


def _profile_to_autonomo(state: UserCliState) -> AutonomoProfile:
    record = state.active_profile_record()
    tax_id = record.values.get("tax.id", "00000000T") if record else "00000000T"
    return AutonomoProfile(
        tax_id=tax_id or "00000000T",
        iva_regime=IVARegime.GENERAL,
    )


# ---------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------


def _tx_repo() -> TransactionCatalogueRepository:
    from ...core.config import load_settings

    return TransactionCatalogueRepository(store_dir=Path(load_settings().aeat_financial_txs_dir).resolve())


def _invoice_repo() -> InvoiceCatalogueRepository:
    from ...core.config import load_settings

    return InvoiceCatalogueRepository(store_dir=Path(load_settings().aeat_invoices_dir).resolve())


def _draft_repo() -> FilingDraftRepository:
    from ...core.config import load_settings

    return FilingDraftRepository(store_dir=Path(load_settings().aeat_drafts_dir).resolve())


def _load_transactions() -> TransactionCatalogue:
    repo = _tx_repo()
    if not repo.envelope_path.exists():
        return TransactionCatalogue()
    return repo.load()


def _load_invoices() -> InvoiceCatalogue:
    repo = _invoice_repo()
    if not repo.envelope_path.exists():
        return InvoiceCatalogue()
    return repo.load()


def _load_drafts() -> tuple[FilingDraft, ...]:
    repo = _draft_repo()
    if not repo.store_dir.exists():
        return ()
    return tuple(repo.iter_drafts())


def _draft_by_id(draft_id: str) -> FilingDraft:
    for draft in _load_drafts():
        if draft.draft_id == draft_id:
            return draft
    raise _bad(f"draft id {draft_id!r} not found")


def _aggregate_filing_inputs(modelo: str, period: str, state: UserCliState) -> dict[str, object]:
    """Return filing inputs aggregated from registry-approved sources."""
    del modelo, period, state
    return {}
