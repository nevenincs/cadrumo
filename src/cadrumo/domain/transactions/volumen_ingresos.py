"""Whether a receipt belongs in the volumen de ingresos a pago fraccionado is fixed on.

One predicate, so the art. 110.1.c) exclusion is applied identically everywhere and a
consumer never re-derives it from the concept's name. That last part is the trap this
module exists to remove: ``SUBVENCION_CORRIENTE`` and ``SUBVENCION_CAPITAL`` share a
prefix and land on opposite sides of the rule, so anything keyed on the word "subvención"
gets exactly one of them wrong, and it is the *inclusion* that breaks — a filer's
operating subsidy silently dropped out of the declared volume.

See Also:
    :class:`~core.ConceptoIngreso`
        The closed set this reads.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Final

from ...core.concepto_ingreso import ConceptoIngreso
from ..calculations.registry.facts.resolution import EntitySetFactQuery, ResolvedEntitySetFact
from ..calculations.registry.schema_base import DateAxis
from .errors import TransactionValidationError

__all__ = ["counts_toward_art_109_activity_income", "counts_toward_volumen_de_ingresos"]

if TYPE_CHECKING:
    from ..calculations.registry.authority import ValidatedRegistryAuthority

_ART_110_EXCLUDED_CONCEPTS_FACT_ID: Final[str] = "rd-439-2007-art-110:conceptos-ingreso-excluidos-volumen-agrario"
_ART_109_EXCLUDED_CONCEPTS_FACT_ID: Final[str] = "rd-439-2007-art-109:conceptos-ingreso-excluidos-base-agraria"


def _excluded_concepts(
    fact_id: str,
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> frozenset[ConceptoIngreso]:
    if authority is None:
        from ..calculations.registry.authority import bundled_authority

        authority = bundled_authority()
    try:
        resolved = authority.resolve_governed_fact(
            EntitySetFactQuery(fact_id=fact_id, date_axis=DateAxis.FILING_PERIOD, effective_date=effective_date)
        )
    except Exception as exc:
        from ..calculations.registry.errors import RegistryError

        if isinstance(exc, RegistryError):
            raise TransactionValidationError(f"failed to resolve income-concept fact {fact_id!r}: {exc}") from exc
        raise
    if not isinstance(resolved, ResolvedEntitySetFact):
        raise TransactionValidationError(f"income-concept fact {fact_id!r} did not resolve to an entity set")
    try:
        return frozenset(ConceptoIngreso(token) for token in resolved.payload.entities)
    except ValueError as exc:
        raise TransactionValidationError(f"income-concept fact {fact_id!r} contains an unknown concept") from exc


def counts_toward_volumen_de_ingresos(
    concepto: ConceptoIngreso | None,
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> bool:
    """Return whether a receipt of this concept belongs in the volumen de ingresos.

    Grounded in RD 439/2007 art. 110.1.c) — *el 2 por ciento del volumen de ingresos
    del trimestre, excluidas las subvenciones de capital y las indemnizaciones* — and
    in the AEAT Modelo 131 instrucciones for casilla 05, which state the inclusion side
    explicitly: *incluidas las subvenciones corrientes y excluidas las subvenciones de
    capital y las indemnizaciones*.

    Args:
        concepto: The declared concept, or ``None`` when the operator declared none.
        effective_date: Filing-period coordinate for the governed exclusion fact.
        authority: Optional validated authority used to resolve that fact.

    Returns:
        ``True`` for ordinary income, for a subvención corriente, and for an undeclared
        concept; ``False`` for a subvención de capital or an indemnización.

        ``None`` counting as included is a deliberate direction for the error to point.
        An unmarked receipt is far more likely to be ordinary than exceptional, and the
        alternative — treating silence as exclusion — would drop real income out of a
        declared volume. The cost is that an unmarked capital subsidy over-declares,
        which is the tolerable side of a rule that cannot be inferred from the row.
    """
    if concepto is None:
        return True
    return concepto not in _excluded_concepts(
        _ART_110_EXCLUDED_CONCEPTS_FACT_ID, effective_date=effective_date, authority=authority
    )


def counts_toward_art_109_activity_income(
    concepto: ConceptoIngreso | None,
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> bool:
    """Return whether a receipt belongs in the Art. 109 retention-coverage base.

    Grounded in RD 439/2007 art. 109.3 and 109.4 -- *al menos el 70 por ciento de
    los ingresos procedentes de la explotación, con excepción de las subvenciones
    corrientes y de capital y de las indemnizaciones, fueron objeto de retención o
    ingreso a cuenta*.

    Distinct from :func:`counts_toward_volumen_de_ingresos` on purpose. That
    predicate serves art. 110.1.c), which keeps subvenciones corrientes IN the
    base; this one takes them out. The two provisions genuinely disagree, so they
    get two predicates rather than one with a flag -- a flag would put the choice
    at the call site, which is where it would eventually be got wrong.

    Args:
        concepto: The declared concept, or ``None`` when the operator declared none.
        effective_date: Filing-period coordinate for the governed exclusion fact.
        authority: Optional validated authority used to resolve that fact.

    Returns:
        ``True`` for ordinary income and for an undeclared concept; ``False`` for a
        subvención of either kind and for an indemnización.
    """
    if concepto is None:
        return True
    return concepto not in _excluded_concepts(
        _ART_109_EXCLUDED_CONCEPTS_FACT_ID, effective_date=effective_date, authority=authority
    )
