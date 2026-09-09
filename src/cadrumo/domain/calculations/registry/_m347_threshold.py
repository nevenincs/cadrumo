"""The Modelo 347 per-counterparty declaration floor, in one place.

Two binding families reach the same declarable set: the counterpart aggregation
and the invoice resolver. They differ only in which observation type they sum
and how they read an amount off it, so the summation stays with each family and
only the regulatory comparison lives here.

This is a leaf module on purpose. ``counterpart_bindings`` already imports from
``_invoice_bindings``, so putting the shared predicate in either one would make
the dependency circular. Neither family owns the threshold; the regulation does.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, cast

from .facts.modelo_projections import ModeloParameterFact
from .facts.resolution import ResolvedScalarFact, ScalarFactQuery
from .facts.schema import FactSelector
from .errors import RegistryValidationError
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .authority import ValidatedRegistryAuthority

__all__ = [
    "m347_clave_c_declarable_party_ids",
    "m347_declarable_party_ids",
    "m347_threshold_decimal",
    "resolve_m347_clave_c_declaration_threshold",
    "resolve_m347_counterparty_annual_threshold",
]


_M347_THRESHOLD_PARAMETER_ID = "modelo-347-tercero-anual-threshold-eur"
_M347_CLAVE_C_THRESHOLD_FACT_ID = "m347-clave-c-beneficiary-declaration-threshold"


def resolve_m347_counterparty_annual_threshold(
    *,
    effective_date: date,
    authority: "ValidatedRegistryAuthority | None" = None,
) -> ResolvedScalarFact:
    """Resolve the Modelo-projected annual counterparty threshold with provenance."""
    if authority is None:
        from .authority import bundled_authority

        authority = bundled_authority()
    resolved = authority.resolve_governed_fact(
        ScalarFactQuery(
            fact_id=ModeloParameterFact.M347_COUNTERPARTY_ANNUAL_THRESHOLD,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
            selectors=(
                FactSelector(name="modelo", value="347"),
                FactSelector(name="parameter_id", value=_M347_THRESHOLD_PARAMETER_ID),
            ),
        ),
    )
    return cast("ResolvedScalarFact", resolved)


def resolve_m347_clave_c_declaration_threshold(
    *,
    effective_date: date,
    authority: "ValidatedRegistryAuthority | None" = None,
) -> ResolvedScalarFact:
    """Resolve the distinct clave-C threshold with its statutory provenance."""
    if authority is None:
        from .authority import bundled_authority

        authority = bundled_authority()
    resolved = authority.resolve_governed_fact(
        ScalarFactQuery(
            fact_id=_M347_CLAVE_C_THRESHOLD_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    return cast("ResolvedScalarFact", resolved)


def _declarable_party_ids(totals: Mapping[str, Decimal], *, floor: Decimal) -> frozenset[str]:
    """The one comparison every M347 declaration-floor caller shares.

    The floor is *exceeded*, never merely reached: a party landing exactly
    on the figure is not declarable (RD 1065/2007 art. 31). The operator is
    therefore ``>``, and a ``>=`` here would over-declare every party sitting
    on the threshold -- which is the mutation this function's single home
    exists to make visible.

    Before this module the comparison was written out separately in each
    family, byte-identical in two of them, so mutating one left the other's
    tests green and the duplication invisible to any test that did not know
    to look for it. Every public entry point in this module delegates here
    rather than re-writing the comparison at a different cutoff.
    """
    return frozenset(party_tax_id for party_tax_id, total in totals.items() if total > floor)


def m347_threshold_decimal(threshold: ResolvedScalarFact) -> Decimal:
    """Return a resolved M347 monetary threshold only when it is a Decimal."""
    value = threshold.payload.value
    if not isinstance(value, Decimal):
        raise RegistryValidationError(
            f"M347 threshold fact {threshold.fact_id!r} resolved non-decimal payload {value!r}",
        )
    return value


def m347_declarable_party_ids(
    totals: Mapping[str, Decimal],
    *,
    effective_date: date | None = None,
    authority: "ValidatedRegistryAuthority | None" = None,
) -> frozenset[str]:
    """Return the party ids whose summed Modelo 347 total passes the GENERAL declaration floor.

    Args:
        totals: Summed Modelo 347 amount per party tax id, across every
            clave (RD 1065/2007 art. 33.1 aggregates the party's TOTAL
            operations, not a single clave's).

    Returns:
        The party tax ids that must be declared.
    """
    resolved = resolve_m347_counterparty_annual_threshold(
        effective_date=effective_date or date.today(),
        authority=authority,
    )
    return _declarable_party_ids(totals, floor=m347_threshold_decimal(resolved))


def m347_clave_c_declarable_party_ids(
    totals: Mapping[str, Decimal],
    *,
    effective_date: date | None = None,
    authority: "ValidatedRegistryAuthority | None" = None,
) -> frozenset[str]:
    """Return the beneficiary ids whose summed clave-C total passes ITS OWN, lower floor.

    RD 1065/2007 arts. 32.c and 33.4 set a separate 300,51 EUR floor for
    amounts collected on behalf of a third party (Modelo 347 clave C),
    applied per BENEFICIARY (the "persona imputada" art. 33.4 names) and
    ALONGSIDE the general floor above, never instead of it: the same
    counterparty can carry both ordinary operations and clave-C collections
    in the same year, and each is judged against its own floor.

    Args:
        totals: Summed clave-C ``invoice_total_amount`` per beneficiary tax id.

    Returns:
        The beneficiary tax ids whose clave-C total must be declared.
    """
    resolved = resolve_m347_clave_c_declaration_threshold(
        effective_date=effective_date or date.today(),
        authority=authority,
    )
    return _declarable_party_ids(totals, floor=m347_threshold_decimal(resolved))
