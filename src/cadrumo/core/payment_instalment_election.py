"""The operator's election to pay a positive annual IRPF result in two instalments.

Ley 35/2006 art. 97.2 and RD 439/2007 art. 62.2 let the taxpayer split the
amount a Modelo 100 declaration leaves to pay, with no interest or surcharge,
into a first instalment of 60 per cent paid on filing and a second of the
remaining 40 per cent. The bundled Manual práctico de Renta 2025, Parte 1
("Pago en dos plazos: Fraccionamiento especial 60/40 por 100") states its
conditions: the declaration is filed within its period, it is not a
complementaria, and the 60 per cent is paid when it is filed. The second
instalment may be direct-debited, in the same account as the first when the
first is; otherwise the taxpayer pays it with Modelo 102.

The axis is separate from :class:`~core.payment_election.PaymentElection`,
which says how the whole amount, or the first instalment, is paid. The two
answers together fill the official record's ``PAGONOFRACC`` or ``PAGOFRACC``
block.

Which modelos admit the split, and the first instalment's share, are
registry data (:mod:`cadrumo.domain.calculations.registry.payment_instalment_split`).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Final


class PaymentInstalmentElection(StrEnum):
    """Whether a positive result is paid at once or in two instalments, and how the second is paid."""

    SINGLE = "single"
    """"Pago no fraccionado": the whole amount is paid at once."""
    TWO_INSTALMENTS_SECOND_DEBITED = "two_instalments_second_debited"
    """60 per cent on filing and the second instalment direct-debited (``ING_DOMICILIA_PF2`` SI)."""
    TWO_INSTALMENTS_SECOND_PAID = "two_instalments_second_paid"
    """60 per cent on filing and the second instalment paid by the taxpayer (``ING_DOMICILIA_PF2`` NO)."""

    @property
    def splits(self) -> bool:
        """Whether the amount is paid in two instalments."""
        return self is not PaymentInstalmentElection.SINGLE

    @property
    def debits_second(self) -> bool:
        """Whether the second instalment is direct-debited."""
        return self is PaymentInstalmentElection.TWO_INSTALMENTS_SECOND_DEBITED


_CENT: Final = Decimal("0.01")


def instalment_amounts(amount: Decimal, *, first_share: Decimal) -> tuple[Decimal, Decimal]:
    """Split a positive amount to pay into its first instalment, ``first_share`` of it, and the second.

    The share is the one the registry declares for the modelo. The first is
    rounded half up to the cent and the second is the remainder, so the two
    always add up to the amount declared. No official source states that
    rounding, so the split is advisory wherever it is shown.

    Raises:
        ValueError: When ``amount`` is not positive.
    """
    if amount <= 0:
        raise ValueError("only a positive amount to pay is split into instalments")
    first = (amount * first_share).quantize(_CENT, rounding=ROUND_HALF_UP)
    return first, amount - first


__all__ = [
    "PaymentInstalmentElection",
    "instalment_amounts",
]
