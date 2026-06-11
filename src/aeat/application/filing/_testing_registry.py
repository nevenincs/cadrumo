"""Registry-backed draft builders for filing tests.

:func:`build_registry_filing_draft` constructs a :class:`ModeloDraft`
through the production registry runtime. It calls
:func:`aeat.application.filing.approve_draft` with an empty
:class:`TransactionCatalogue` so the approval basis is deterministic
in tests that have no ledger state.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from ...domain.filing._protocols import ModeloInputs
from ...domain.filing._schema import ModeloDraft
from ...domain.period import PeriodValidationError, parse_canonical_period
from ...domain.submission import ModeloDraftStatus
from ...domain.transactions import TransactionCatalogue
from . import ModeloBuilderError, approve_draft, build_draft, build_runtime_schema_provider

_REGISTRY_TEST_BUCKET_ID = "registry-test"


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
    casilla_values: ModeloInputs,
    binding_values: ModeloInputs | None = None,
    status: ModeloDraftStatus = ModeloDraftStatus.APROBADO,
    filing_year: int = 2026,
) -> ModeloDraft:
    """Build and return a :class:`ModeloDraft` through the validated registry runtime path."""
    runtime_period = _runtime_period(period, filing_year=filing_year)
    snapshot_year, registry_period_token = _snapshot_year_and_token(runtime_period)
    schema_provider = build_runtime_schema_provider(
        modelos=(modelo,),
        filing_year=snapshot_year,
        period=registry_period_token,
    )
    duplicate_input_ids = sorted(set(casilla_values).intersection(binding_values or {}))
    if duplicate_input_ids:
        raise ModeloBuilderError(
            f"registry filing test helper received duplicate casilla/binding input ids: {duplicate_input_ids!r}",
        )
    draft = build_draft(
        modelo=modelo,
        period=runtime_period,
        profile=RegistryTestProfile(
            tax_id=profile_tax_id,
            display_name="Registry filing test",
        ),
        inputs={**(binding_values or {}), **casilla_values},
        schema_provider=schema_provider,
    )
    if status is ModeloDraftStatus.APROBADO:
        return approve_draft(
            draft,
            bucket_id=_REGISTRY_TEST_BUCKET_ID,
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
        },
    )


def build_registry_filing_draft_from_decimals(
    *,
    modelo: str,
    period: str,
    profile_tax_id: str = "Y0000001S",
    casilla_decimals: Mapping[str, str | Decimal],
    binding_decimals: Mapping[str, str | Decimal] | None = None,
    status: ModeloDraftStatus = ModeloDraftStatus.APROBADO,
    filing_year: int = 2026,
) -> ModeloDraft:
    """Coerce decimal strings before building through the registry runtime.

    Returns a :class:`ModeloDraft`.
    """
    coerced: dict[str, Decimal] = {}
    for casilla_id, raw in casilla_decimals.items():
        coerced[casilla_id] = raw if isinstance(raw, Decimal) else Decimal(raw)
    coerced_bindings: dict[str, Decimal] = {}
    for binding_id, raw in (binding_decimals or {}).items():
        coerced_bindings[binding_id] = raw if isinstance(raw, Decimal) else Decimal(raw)
    return build_registry_filing_draft(
        modelo=modelo,
        period=period,
        profile_tax_id=profile_tax_id,
        casilla_values=coerced,
        binding_values=coerced_bindings,
        status=status,
        filing_year=filing_year,
    )


_QUARTER_TOKEN_RE = re.compile(r"^(?P<quarter>[1-4])T$")
_ANNUAL_TOKEN_RE = re.compile(r"^0A$")
_RUNTIME_PERIOD_RE = re.compile(r"^\d{4}(?:Q[1-4]|A)$|^\d{4}-(?:0[1-9]|1[0-2])$")


def _snapshot_year_and_token(runtime_period: str) -> tuple[int, str]:
    """Return ``(filing_year, registry_period_token)`` for a canonical runtime period.

    Translates the canonical ``{year}Q{n}`` / ``{year}A`` / ``{year}-{mm}``
    format produced by :func:`_runtime_period` back to the registry-native
    token (``"1T"``…``"4T"``, ``"0A"``, ``"01"``…``"12"``) and the year
    encoded in the period string.  The registry's ``period_selector.periods``
    stores native tokens, so snapshot lookups must use the native form.
    """
    try:
        return parse_canonical_period(runtime_period)
    except PeriodValidationError as exc:
        raise ModeloBuilderError(f"cannot resolve snapshot period for {runtime_period!r}: {exc}") from exc


def _runtime_period(period: str, *, filing_year: int) -> str:
    if _RUNTIME_PERIOD_RE.fullmatch(period):
        return period
    if match := _QUARTER_TOKEN_RE.fullmatch(period):
        return f"{filing_year}Q{match.group('quarter')}"
    if _ANNUAL_TOKEN_RE.fullmatch(period):
        return f"{filing_year}A"
    raise ModeloBuilderError(f"cannot map filing period {period!r} to a registry period")


__all__ = [
    "RegistryTestProfile",
    "build_registry_filing_draft",
    "build_registry_filing_draft_from_decimals",
]
