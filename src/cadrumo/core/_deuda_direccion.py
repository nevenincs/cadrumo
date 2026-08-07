"""Whether an AEAT-reported liability is owed by or refundable to the taxpayer.

A *Consultar deudas* row carries an amount whose flow direction is not
inferable from the amount itself: AEAT's recaudación surface reports both
outstanding debts and amounts it owes back (a devolución acordada, an ingreso
indebido being returned). :class:`DeudaDireccion` carries that direction as its
own typed axis, declared in ``core`` per the core-authority discipline.

Direction is a FIELD, never the sign of an amount. This mirrors the ledger
contract's amount-is-magnitude convention, where a transaction stores a
non-negative amount and flow lives solely on its direction enum. Encoding flow
twice — once in a sign and once in a field — creates a state where the two can
disagree, and nothing establishes which one a downstream reader should trust;
a debt silently read as a refund is the failure that convention exists to make
unrepresentable.

The axis is deliberately not
:class:`~core.AmendmentLiabilityDirection`, which is a different concept
despite the similar name: that enum classifies whether *correcting a
declaration* raises or lowers the declared liability, and it selects between
the complementaria and rectificación procedures. This axis classifies which
way an already-assessed amount flows between AEAT and the taxpayer.

See Also:
    :class:`~core.ObjetoTributario`
        Which LGT object the reported liability is.
"""

from __future__ import annotations

from enum import StrEnum


class DeudaDireccion(StrEnum):
    """Which way an AEAT-reported amount flows between AEAT and the taxpayer.

    Attributes:
        DEUDOR: The taxpayer owes the amount to AEAT. The ordinary debts-list
            case, and the direction under which a recargo de apremio can
            accrue.
        ACREEDOR: AEAT owes the amount to the taxpayer — a devolución acordada
            or an ingreso indebido being returned.
    """

    DEUDOR = "deudor"
    ACREEDOR = "acreedor"


__all__ = ["DeudaDireccion"]
