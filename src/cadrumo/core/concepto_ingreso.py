"""Closed value set for the income concept a receipt carries.

Some calculation bases are not "everything that came in". RD 439/2007 art. 110.1.c)
fixes the agrarian pago fraccionado at *el 2 por ciento del volumen de ingresos del
trimestre, excluidas las subvenciones de capital y las indemnizaciones*, and the AEAT
Modelo 131 instrucciones say the same thing from the other side, naming what stays in:

    Consignaremos en esta casilla el volumen de ingresos del trimestre por el que se
    realiza el pago fraccionado, incluidas las subvenciones corrientes y excluidas las
    subvenciones de capital y las indemnizaciones.

That sentence is the whole reason this typed axis exists. The distinction it draws is not
between subsidies and other income — it is *inside* subsidies: a subvención corriente
counts and a subvención de capital does not. No amount, category, counterparty or date
on a ledger row can tell those two apart, so the concept has to be declared, and
nothing else in the taxonomy carries it. The Modelo 347 operation catalogue has a
``subvenciones_y_ayudas`` kind, but that is a Modelo 347 clave describing an operation with a counterparty,
not a statement about whether a receipt belongs in a base.

Absence means ordinary income, deliberately. The overwhelming majority of receipts are
ordinary trading income, and a taxpayer who never touches the field must still have a
correct base; defaulting the other way would drop real income out of a declared volume,
which is the silent under-declaration this project treats as the worst failure mode.
The cost of that choice is stated rather than hidden: a subvención de capital that the
operator never marks is included and over-declares. That is the direction the error has
to point, because an unmarked receipt is far more likely to be ordinary than exceptional.

See Also:
    :func:`~domain.transactions.counts_toward_volumen_de_ingresos`
        The predicate consumers use; do not re-derive the membership test.
"""

from __future__ import annotations

from .registry_token import StrictRegistryToken

__all__ = ["ConceptoIngreso"]


class ConceptoIngreso(StrictRegistryToken):
    """Opaque receipt-concept token projected from the governed facts registry.

    The dated facts catalogue owns the income-concept vocabulary and the
    provision-specific exclusion sets. This core type carries only the typed
    wire token; callers must obtain instances through the registry projection.
    """

    __slots__ = ()
