"""Closed value set for the income concept a receipt carries.

Some calculation bases are not "everything that came in". RD 439/2007 art. 110.1.c)
fixes the agrarian pago fraccionado at *el 2 por ciento del volumen de ingresos del
trimestre, excluidas las subvenciones de capital y las indemnizaciones*, and the AEAT
Modelo 131 instrucciones say the same thing from the other side, naming what stays in:

    Consignaremos en esta casilla el volumen de ingresos del trimestre por el que se
    realiza el pago fraccionado, incluidas las subvenciones corrientes y excluidas las
    subvenciones de capital y las indemnizaciones.

That sentence is the whole reason this enum exists. The distinction it draws is not
between subsidies and other income — it is *inside* subsidies: a subvención corriente
counts and a subvención de capital does not. No amount, category, counterparty or date
on a ledger row can tell those two apart, so the concept has to be declared, and
nothing else in the taxonomy carries it. :class:`OperationKind347` has a ``SUBSIDY``
member, but that is a Modelo 347 clave describing an operation with a counterparty,
not a statement about whether a receipt belongs in a base.

Absence means ordinary income, deliberately. The overwhelming majority of receipts are
ordinary trading income, and a taxpayer who never touches the field must still have a
correct base; defaulting the other way would drop real income out of a declared volume,
which is the silent under-declaration this project treats as the worst failure mode.
The cost of that choice is stated rather than hidden: a subvención de capital that the
operator never marks is included and over-declares. That is the direction the error has
to point, because an unmarked receipt is far more likely to be ordinary than exceptional.

See Also:
    :data:`INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE`
        The excluded members, derived rather than re-listed.
    :func:`~domain.transactions.counts_toward_volumen_de_ingresos`
        The predicate consumers use; do not re-derive the membership test.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

__all__ = [
    "INGRESO_CONCEPTS_OUTSIDE_THE_ART_109_BASE",
    "INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE",
    "ConceptoIngreso",
]


class ConceptoIngreso(StrEnum):
    """What kind of receipt a ledger row records, for base-inclusion purposes.

    The value byte-equals the stored token, so a member compares, hashes, and
    JSON-serialises identically to its string.

    Attributes:
        ORDINARIO: Ordinary trading income — the contraprestación of the activity.
            Counts toward the volumen de ingresos.
        SUBVENCION_CORRIENTE: A current (operating) subsidy. Counts, and the Modelo
            131 instrucciones say so explicitly rather than by omission, which is why
            it is a member of its own instead of collapsing into ``ORDINARIO``: the
            operator who marks a receipt as a subsidy needs the answer to come out
            right, not to be told the field did not matter.
        SUBVENCION_CAPITAL: A capital subsidy. Excluded by art. 110.1.c).
        INDEMNIZACION: An indemnity. Excluded by art. 110.1.c).
    """

    ORDINARIO = "ordinario"
    SUBVENCION_CORRIENTE = "subvencion_corriente"
    SUBVENCION_CAPITAL = "subvencion_capital"
    INDEMNIZACION = "indemnizacion"


INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE: Final[frozenset[ConceptoIngreso]] = frozenset(
    {
        ConceptoIngreso.SUBVENCION_CAPITAL,
        ConceptoIngreso.INDEMNIZACION,
    },
)
"""The concepts art. 110.1.c) removes from the volumen de ingresos.

Listed rather than derived from a name prefix on purpose: ``SUBVENCION_CORRIENTE`` and
``SUBVENCION_CAPITAL`` share a prefix and land on opposite sides, so any rule keyed on
the word "subvención" gets one of them wrong.
"""

INGRESO_CONCEPTS_OUTSIDE_THE_ART_109_BASE: Final[frozenset[ConceptoIngreso]] = frozenset(
    {
        ConceptoIngreso.SUBVENCION_CORRIENTE,
        ConceptoIngreso.SUBVENCION_CAPITAL,
        ConceptoIngreso.INDEMNIZACION,
    },
)
"""The concepts art. 109.3 and 109.4 remove from the pago-fraccionado exemption base.

A SUPERSET of :data:`INGRESO_CONCEPTS_OUTSIDE_THE_VOLUME_BASE`, and the difference
is the whole reason both exist. Art. 110.1.c) fixes a quarterly payment on a volume
that KEEPS subvenciones corrientes in; art. 109.3 and 109.4 measure the 70 per cent
retention coverage over *los ingresos procedentes de la explotación, con excepción
de las subvenciones corrientes y de capital y de las indemnizaciones*, which takes
them out.

Sharing one set between the two provisions would therefore get exactly one of them
wrong, and the direction is not symmetric. Reusing art. 110's narrower set here
leaves subvenciones corrientes in the art. 109 denominator, where they never appear
in the numerator because subsidies carry no retención -- so the ratio is depressed,
the 70 per cent threshold is missed, and a filer the reglamento exempts is shown a
Modelo 130 obligation and pays a pago fraccionado they do not owe.
"""
