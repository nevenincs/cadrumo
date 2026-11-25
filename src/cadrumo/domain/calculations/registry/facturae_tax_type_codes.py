"""The Facturae ``TaxTypeCodeType`` member that names IRPF, read from the dated governed fact."""

from __future__ import annotations

from datetime import date
from typing import Final

from .facts.resolution import reading_dated_facts_below_support
from .facts.string_mapping import MappingValueWhitespace, StringMappingFact, StringMappingPolicy
from .form_codes import FormCodes
from .governed_fact_scope import GovernedFactSource
from .schema_base import DateAxis

_TAX_TYPE_FACT: Final = "facturae-tax-type-codes"
_FACT: Final = StringMappingFact(
    fact_id=_TAX_TYPE_FACT,
    date_axis=DateAxis.INVOICE_DATE,
    policy=StringMappingPolicy(
        subject=f"fact {_TAX_TYPE_FACT!r}",
        value_whitespace=MappingValueWhitespace.STRIP,
    ),
)


def facturae_irpf_tax_type_code(*, issued_on: date | None, authority: GovernedFactSource | None = None) -> str:
    """Return the code an invoice issued on ``issued_on`` names IRPF with; no date reads today's.

    An invoice can be older than the years the product files for, and reading it files nothing.
    """
    with reading_dated_facts_below_support():
        entries = _FACT.resolve_scoped_entries(effective_date=issued_on, authority=authority)
    return FormCodes(fact_id=_TAX_TYPE_FACT, entries=entries).code("irpf")


__all__ = ["facturae_irpf_tax_type_code"]
