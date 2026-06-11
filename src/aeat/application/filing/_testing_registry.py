"""Registry-backed draft builders for filing tests.

:func:`build_registry_filing_draft` constructs a :class:`ModeloDraft`
through the production registry runtime. It calls
:func:`aeat.application.filing.approve_draft` with an empty
:class:`TransactionCatalogue` so the approval basis is deterministic
in tests that have no ledger state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from ...core import Period
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
    period: str | Period,
    profile_tax_id: str = "Y0000001S",
    casilla_values: ModeloInputs,
    binding_values: ModeloInputs | None = None,
    status: ModeloDraftStatus = ModeloDraftStatus.APROBADO,
    filing_year: int = 2026,
) -> ModeloDraft:
    """Build and return a :class:`ModeloDraft` through the validated registry runtime path."""
    typed_period = _resolve_test_period(period, filing_year=filing_year)
    schema_provider = build_runtime_schema_provider(
        modelos=(modelo,),
        filing_year=typed_period.year,
        period=typed_period.registry_token,
    )
    duplicate_input_ids = sorted(set(casilla_values).intersection(binding_values or {}))
    if duplicate_input_ids:
        raise ModeloBuilderError(
            f"registry filing test helper received duplicate casilla/binding input ids: {duplicate_input_ids!r}",
        )
    draft = build_draft(
        modelo=modelo,
        period=typed_period,
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
    period: str | Period,
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


def _resolve_test_period(period: str | Period, *, filing_year: int) -> Period:
    """Resolve test helper period input without constructing combined runtime strings."""
    if isinstance(period, Period):
        return period
    try:
        return Period.from_year_and_code(filing_year, period)
    except ValueError:
        pass
    try:
        parsed_year, registry_period_token = parse_canonical_period(period)
        return Period.from_year_and_code(parsed_year, registry_period_token)
    except (PeriodValidationError, ValueError) as exc:
        raise ModeloBuilderError(f"cannot map filing period {period!r} to a registry period") from exc


__all__ = [
    "RegistryTestProfile",
    "build_registry_filing_draft",
    "build_registry_filing_draft_from_decimals",
]
