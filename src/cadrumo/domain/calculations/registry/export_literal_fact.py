"""Export literals whose value is a governed fact, resolved when the registry is built.

A literal export field normally carries its value inline. Some constants are not
the design's to state: the entidad-desarrolladora identity AEAT reserves in
every ``<AUX>`` envelope belongs to the product, and the same value fills that
slot in every modelo. Writing it inline in each layout would scatter one
identity across dozens of declarations. A field instead names the governed
mapping fact and entry that holds it, and the value is materialised into the
literal while the registry is validated -- so the compiled authority carries an
ordinary literal plus the reference it came from, and no render path ever looks
a fact up.

Static means static: the entry must resolve to ONE value across the whole
filing-year support envelope. A fact that varies by period has no single
literal to give, and is refused rather than sampled.
"""

from __future__ import annotations

from datetime import date

from pydantic import Field

from .errors import RegistryError, RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .facts.schema import FactId
from .governed_fact_scope import GovernedFactSource
from .schema_base import DateAxis, RegistryModel

__all__ = ["ExportLiteralFact", "resolve_export_literal_fact"]


class ExportLiteralFact(RegistryModel):
    """Name the governed mapping fact, and the entry within it, that supplies a literal."""

    fact_id: FactId
    key: str = Field(min_length=1)


def resolve_export_literal_fact(reference: ExportLiteralFact, *, authority: GovernedFactSource) -> str:
    """Return the one value ``reference`` resolves to across the support envelope.

    Every authored filing year is consulted, not just one, because a value that
    changes between years would otherwise be frozen at whichever year happened
    to be asked.

    Raises:
        RegistryValidationError: When the fact is absent or not a mapping, the
            entry is missing or blank, or the entry differs between years.
    """
    values = {
        _entry_value(reference, authority=authority, effective_date=date(year, 1, 1))
        for year in authority.supported_filing_years().years
    }
    if len(values) != 1:
        raise RegistryValidationError(
            f"export literal fact {reference.fact_id!r} entry {reference.key!r} resolves to "
            f"{sorted(values)!r} across the support envelope; a static literal needs exactly one value",
        )
    return values.pop()


def _entry_value(reference: ExportLiteralFact, *, authority: GovernedFactSource, effective_date: date) -> str:
    try:
        resolved = authority.resolve_governed_fact(
            MappingFactQuery(
                fact_id=reference.fact_id,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
            ),
        )
    except RegistryError as error:
        raise RegistryValidationError(
            f"export literal fact {reference.fact_id!r} does not resolve on {effective_date.isoformat()}: {error}",
        ) from error
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError(f"export literal fact {reference.fact_id!r} is not a mapping fact")
    entries = {str(entry.key): entry.value for entry in resolved.payload.entries}
    value = entries.get(reference.key)
    if not isinstance(value, str) or not value.strip():
        raise RegistryValidationError(
            f"export literal fact {reference.fact_id!r} has no text entry {reference.key!r}",
        )
    return value
