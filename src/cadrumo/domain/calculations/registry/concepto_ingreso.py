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
from .facts.envelope_editions import resolve_support_envelope_editions
from .facts.resolution import EntitySetFactQuery, ResolvedEntitySetFact, ResolvedGovernedFact
from .facts.variants import FactSelector
from .governed_fact_scope import GovernedFactSource, require_governed_fact_authority
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


def _vocabulary_query(effective_date: date) -> EntitySetFactQuery:
    return EntitySetFactQuery(
        fact_id=_FACT_ID,
        date_axis=DateAxis.FILING_PERIOD,
        effective_date=effective_date,
        selectors=(_VOCABULARY_SELECTOR,),
    )


def _vocabulary_entities(resolved: ResolvedGovernedFact) -> frozenset[str]:
    if not isinstance(resolved, ResolvedEntitySetFact):
        raise RegistryValidationError("income-concept vocabulary must resolve as an entity-set fact")
    entities = tuple(entity.strip() for entity in resolved.payload.entities)
    if not entities or len(entities) != len(set(entities)) or any(not entity for entity in entities):
        raise RegistryValidationError("income-concept vocabulary must contain unique non-empty tokens")
    return frozenset(entities)


def _catalogue(entities: frozenset[str]) -> ConceptoIngresoCatalogue:
    return ConceptoIngresoCatalogue(
        tokens=tuple(ConceptoIngreso.from_registry(entity) for entity in sorted(entities)),
    )


def resolve_concepto_ingreso_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> ConceptoIngresoCatalogue:
    """Resolve the income-concept vocabulary.

    A dated read takes the vocabulary in force on ``effective_date``. Without a
    date the run date is never substituted: the vocabulary admits every token
    an edition inside the supported filing years declares, which admits a
    token but cannot decide a tax fact; a caller deciding one supplies the
    date.
    """
    selected = require_governed_fact_authority(authority, subject="income-concept catalogue")
    if effective_date is not None:
        return _catalogue(_vocabulary_entities(selected.resolve_governed_fact(_vocabulary_query(effective_date))))
    editions = resolve_support_envelope_editions(selected, _vocabulary_query)
    if not editions:
        raise RegistryValidationError("income-concept vocabulary authors no edition inside the supported filing years")
    entities = frozenset[str]()
    for resolved in editions:
        entities |= _vocabulary_entities(resolved)
    return _catalogue(entities)


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


__all__ = [
    "ConceptoIngresoCatalogue",
    "require_concepto_ingreso",
    "resolve_concepto_ingreso_catalogue",
]
