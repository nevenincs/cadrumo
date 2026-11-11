"""Give each perceptor a withholding record names the filing name the person declared for it.

A record naming a perceptor (a Modelo 180, 190 or 193 type-2 record) files the
name the person declared for that perceptor, composed by the slot's design rule.
The name a retention source printed is display only. A perceptor with no
declared name, with one the design does not compose, or with one wider than its
slot leaves the slot without content; each such perceptor is named here once,
with a row to recognise it by, and the export refuses until the name is stated.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final, NamedTuple

from ...domain.calculations.registry.withholding_bindings import DeclaredWithholdingParty
from ...domain.filing.errors import FilingExportDeclaredPartyNameError
from ..invoices.source_party_names import RefusedParty, refused_party_diagnostics
from ..invoices.source_resolver_ports import CounterpartyFilingNameReader
from ..ledger.counterparty_establishment import confirmed_counterparty_facts_key
from .source_mesh import CalculationSourceContext, CalculationSourceDiagnostic

#: How many characters of a party's stated-facts key name it in a refusal.
_PARTY_HANDLE_LENGTH: Final = 12


class PerceptorReference(NamedTuple):
    """One perceptor as a withholding row names it, with a row and a printed name to recognise it by."""

    country_code: str
    """The country the source stated, or empty when it stated none."""
    tax_id: str
    row_ref: str
    """An opaque reference to a row naming the perceptor, or empty when the source offers none."""
    printed_name: str


@dataclass(frozen=True, slots=True)
class DeclaredPerceptors:
    """The perceptors of one calculation, each with the filing name declared for it."""

    parties: tuple[DeclaredWithholdingParty, ...]
    shown_as: dict[str, RefusedParty]
    """How a refusal names each perceptor, by the handle the refusal carries."""


def declare_perceptors(
    references: Iterable[PerceptorReference],
    filing_names: CounterpartyFilingNameReader,
) -> DeclaredPerceptors:
    """Look up the filing name declared for each distinct perceptor.

    Only a stated name is used; a perceptor with none keeps no name. The party
    handle is a prefix of the stated-facts key, never the identifier.

    Raises:
        InvoiceSourcePersistenceError: The stated facts cannot be read.
    """
    parties: dict[tuple[str, str], DeclaredWithholdingParty] = {}
    shown_as: dict[str, RefusedParty] = {}
    for reference in sorted(references):
        party = (reference.country_code, reference.tax_id)
        if party in parties:
            continue
        country = reference.country_code or None
        key = confirmed_counterparty_facts_key(reference.tax_id, country_code=country)
        name = None if key is None else filing_names.filing_name_of(reference.tax_id, country_code=country)
        handle = None if key is None else key[:_PARTY_HANDLE_LENGTH]
        parties[party] = DeclaredWithholdingParty(
            country_code=reference.country_code,
            party_tax_id=reference.tax_id,
            party_handle=handle,
            party_filing_name=name,
        )
        if handle is not None:
            shown_as.setdefault(
                handle, RefusedParty(_perceptor_named(reference), (reference.row_ref,) if reference.row_ref else ())
            )
    return DeclaredPerceptors(parties=tuple(parties.values()), shown_as=shown_as)


def perceptor_name_refusal_diagnostics(
    refusals: Sequence[FilingExportDeclaredPartyNameError],
    perceptors: DeclaredPerceptors,
    *,
    context: CalculationSourceContext,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Name each perceptor whose filing name a slot could not file, once per perceptor and refusal."""
    return refused_party_diagnostics(refusals, perceptors.shown_as, context=context, resolver_id=resolver_id)


def _perceptor_named(reference: PerceptorReference) -> str:
    return reference.tax_id if not reference.printed_name else f"{reference.printed_name} ({reference.tax_id})"


__all__ = [
    "DeclaredPerceptors",
    "PerceptorReference",
    "declare_perceptors",
    "perceptor_name_refusal_diagnostics",
]
