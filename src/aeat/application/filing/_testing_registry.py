"""Registry-backed draft builders for filing tests."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from ...domain.filing._schema import FilingDraft, ModeloDraftStatus, FilingScalar
from ...domain.transactions import TransactionCatalogue
from . import FilingBuilderError, approve_draft, build_draft, build_runtime_schema_provider


@dataclass(frozen=True, slots=True)
class RegistryTestProfile:
    """Minimal filing profile used by registry-backed filing tests."""

    tax_id: str
    display_name: str


def build_registry_filing_draft(
    *,
    modelo: str,
    period: str,
    profile_tax_id: str = "Y0000001S",
    casilla_values: Mapping[str, FilingScalar],
    status: ModeloDraftStatus = ModeloDraftStatus.APPROVED,
    filing_year: int = 2026,
) -> FilingDraft:
    """Build a filing draft through the validated registry runtime path."""

    runtime_period = _runtime_period(period, filing_year=filing_year)
    schema_provider = build_runtime_schema_provider(modelos=(modelo,), filing_year=filing_year, period=runtime_period)
    draft = build_draft(
        modelo=modelo,
        period=runtime_period,
        profile=RegistryTestProfile(
            tax_id=profile_tax_id,
            display_name="Registry filing test",
        ),
        inputs=casilla_values,
        schema_provider=schema_provider,
    )
    if status is ModeloDraftStatus.APPROVED:
        return approve_draft(
            draft,
            bucket_id="registry-test",
            approved_by="registry",
            schema_provider=schema_provider,
            transaction_catalogue=TransactionCatalogue(),
        )
    return draft.model_copy(
        update={
            "status": status,
            "approved_at": None,
            "approved_by": None,
            "review_checksum": None,
            "approval_basis": None,
        }
    )


def build_registry_filing_draft_from_decimals(
    *,
    modelo: str,
    period: str,
    profile_tax_id: str = "Y0000001S",
    casilla_decimals: Mapping[str, str | Decimal],
    status: ModeloDraftStatus = ModeloDraftStatus.APPROVED,
    filing_year: int = 2026,
) -> FilingDraft:
    """Coerce decimal strings before building through the registry runtime."""

    coerced: dict[str, FilingScalar] = {}
    for casilla_id, raw in casilla_decimals.items():
        coerced[casilla_id] = raw if isinstance(raw, Decimal) else Decimal(raw)
    return build_registry_filing_draft(
        modelo=modelo,
        period=period,
        profile_tax_id=profile_tax_id,
        casilla_values=coerced,
        status=status,
        filing_year=filing_year,
    )


_QUARTER_TOKEN_RE = re.compile(r"^(?P<quarter>[1-4])T$")
_ANNUAL_TOKEN_RE = re.compile(r"^0A$")
_RUNTIME_PERIOD_RE = re.compile(r"^\d{4}(?:Q[1-4]|A)$|^\d{4}-(?:0[1-9]|1[0-2])$")


def _runtime_period(period: str, *, filing_year: int) -> str:
    if _RUNTIME_PERIOD_RE.fullmatch(period):
        return period
    if match := _QUARTER_TOKEN_RE.fullmatch(period):
        return f"{filing_year}Q{match.group('quarter')}"
    if _ANNUAL_TOKEN_RE.fullmatch(period):
        return f"{filing_year}A"
    raise FilingBuilderError(f"cannot map filing period {period!r} to a registry period")


__all__ = [
    "RegistryTestProfile",
    "build_registry_filing_draft",
    "build_registry_filing_draft_from_decimals",
]
