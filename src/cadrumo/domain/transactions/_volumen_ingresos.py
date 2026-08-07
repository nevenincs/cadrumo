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

from ...core import INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE, ConceptoIngreso

__all__ = ["counts_toward_volumen_de_ingresos"]


def counts_toward_volumen_de_ingresos(concepto: ConceptoIngreso | None) -> bool:
    """Return whether a receipt of this concept belongs in the volumen de ingresos.

    Grounded in RD 439/2007 art. 110.1.c) — *el 2 por ciento del volumen de ingresos
    del trimestre, excluidas las subvenciones de capital y las indemnizaciones* — and
    in the AEAT Modelo 131 instrucciones for casilla 05, which state the inclusion side
    explicitly: *incluidas las subvenciones corrientes y excluidas las subvenciones de
    capital y las indemnizaciones*.

    Args:
        concepto: The declared concept, or ``None`` when the operator declared none.

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
    return concepto not in INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE
