"""Which side of an account a contabilidad amount falls on.

A PGC amount carries its economic direction in this enum and its size as a
non-negative magnitude, never as a numeric sign. That is the same separation
the ledger already keeps for bank movements
(:class:`~cadrumo.domain.transactions.enums.TransactionDirection`) and the same
one the fixed-width export codec keeps on the wire, where a signed money field
renders an explicit sign character beside a zero-padded magnitude rather than a
negative number.

Consumers that need arithmetic ask for :attr:`ContabilidadDireccion.sign` and
multiply, exactly as
:attr:`~cadrumo.domain.renta.ledger_expenses.RentaExpenseFact.sign` does for
IRPF expenses. Nothing in this module decides whether a balance is *normal* for
a given account: a debit balance on a passive account is unusual, not invalid,
and judging it belongs to the account's own contract rather than to its
direction.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal


class ContabilidadDireccion(StrEnum):
    """The side of a PGC account an amount is recorded on.

    Attributes:
        DEBE: Debit — the left side. Increases assets and expenses.
        HABER: Credit — the right side. Increases liabilities, equity and
            income.
    """

    DEBE = "debe"
    HABER = "haber"

    @property
    def sign(self) -> Literal[-1, 1]:
        """Return +1 for ``DEBE`` and -1 for ``HABER``.

        The convention is arithmetic, not evaluative: it makes a debit-natured
        total add and a credit-natured total subtract when both are summed into
        one figure. It says nothing about whether either is expected.
        """
        return 1 if self is ContabilidadDireccion.DEBE else -1

    @property
    def opposite(self) -> ContabilidadDireccion:
        """Return the contra side, for reversals and closing entries."""
        return (
            ContabilidadDireccion.HABER
            if self is ContabilidadDireccion.DEBE
            else ContabilidadDireccion.DEBE
        )
