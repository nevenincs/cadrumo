"""Typed projection of the governed income-concept vocabulary.

The Art. 110 fact owns both the agrarian exclusion declaration and the
complete receipt-concept vocabulary used by ledger rows. Keeping the
vocabulary as a selector-scoped variant of that fact prevents a second
canonical owner while allowing Art. 109 and Art. 110 to retain their distinct
exclusion sets.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ....core.concepto_ingreso import ConceptoIngreso
from .errors import RegistryValidationError
from .facts.resolution import EntitySetFactQuery, ResolvedEntitySetFact
from .facts.schema import FactSelector
from .governed_fact_scope import GovernedFactSource, cache_governed_projection, governed_facts_in_scope
from .schema_base import DateAxis

_FACT_ID = "rd-439-2007-art-110:conceptos-ingreso-excluidos-volumen-agrario"
_VOCABULARY_SELECTOR = FactSelector(name="scope", value="vocabulary")


@dataclass(frozen=True, slots=True)
class ConceptoIngresoCatalogue:
    """Registry-declared income-concept tokens for transaction boundaries."""

    tokens: tuple[ConceptoIngreso, ...]

    @property
    def all_tokens(self) -> frozenset[ConceptoIngreso]:
        """Return every token in the selected vocabulary."""
        return frozenset(self.tokens)

    def require(self, value: object) -> ConceptoIngreso:
        """Return one token only when the selected fact declares it."""
        if isinstance(value, ConceptoIngreso):
            token = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                raise RegistryValidationError("income-concept token must be non-empty")
            try:
                token = ConceptoIngreso.from_registry(raw)
            except (TypeError, ValueError) as exc:
                raise RegistryValidationError("income-concept token must be a non-empty string") from exc
        else:
            raise RegistryValidationError("income-concept token must be a string token")
        if token not in self.all_tokens:
            raise RegistryValidationError(
                f"income-concept token {str(token)!r} is not declared by fact {_FACT_ID!r}",
            )
        return token


def _resolve_catalogue(
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> ConceptoIngresoCatalogue:
    resolved = authority.resolve_governed_fact(
        EntitySetFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
            selectors=(_VOCABULARY_SELECTOR,),
        ),
    )
    if not isinstance(resolved, ResolvedEntitySetFact):
        raise RegistryValidationError("income-concept vocabulary must resolve as an entity-set fact")
    entities = tuple(sorted(str(entity).strip() for entity in resolved.payload.entities))
    if not entities or len(entities) != len(set(entities)) or any(not entity for entity in entities):
        raise RegistryValidationError("income-concept vocabulary must contain unique non-empty tokens")
    return ConceptoIngresoCatalogue(
        tokens=tuple(ConceptoIngreso.from_registry(entity) for entity in entities),
    )


@cache_governed_projection(maxsize=64)
def _bundled_catalogue(effective_date: date) -> ConceptoIngresoCatalogue:
    del effective_date
    raise RegistryValidationError("income-concept catalogue requires an explicit authority operation or scope")


def resolve_concepto_ingreso_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ConceptoIngresoCatalogue:
    """Resolve the selected dated income-concept vocabulary."""
    coordinate = effective_date or date.today()
    selected = authority or governed_facts_in_scope()
    if selected is None:
        return _bundled_catalogue(coordinate)
    return _resolve_catalogue(effective_date=coordinate, authority=selected)


def require_concepto_ingreso(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ConceptoIngreso:
    """Project one receipt-concept token from the selected facts authority."""
    return resolve_concepto_ingreso_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


def concepto_ingreso_tokens(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> tuple[ConceptoIngreso, ...]:
    """Return the selected income-concept tokens in stable order."""
    return resolve_concepto_ingreso_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).tokens


__all__ = [
    "ConceptoIngresoCatalogue",
    "concepto_ingreso_tokens",
    "require_concepto_ingreso",
    "resolve_concepto_ingreso_catalogue",
]
