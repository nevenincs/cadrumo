"""The statement a filer may make that one earlier-filing carry holds nothing.

A carry read from an earlier filing is unknown, never zero, while no earlier
return supplies it. For some carries the law leaves a filer who has nothing
pending only that statement to make: the negative general bases still pending
from the four previous ejercicios a Modelo 100 compensates (Ley 35/2006 art.
50.3) are one, and the negative savings balances of either kind it compensates
(art. 49.1) are two more. The registry declares on the binding which statement it takes,
as one member of a closed family, so a carry that is not declared never takes
it: a statement that a prior-year income or a prior instalment was zero would
assert a figure, not an absence.

The family is authored on the binding row::

    absence_attestation = "renta_negative_general_bases_pending"

It is a closed vocabulary hydrated at the loader boundary, so an unknown token
fails registry load, and the binding must read a decimal from an earlier filing.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BeforeValidator

from .schema_base import coerce_enum_member


class AbsenceAttestationFamily(StrEnum):
    """The closed families of earlier-filing carries a filer may state hold nothing."""

    #: The negative general bases pending from the four previous ejercicios (Ley 35/2006 art. 50.3).
    RENTA_NEGATIVE_GENERAL_BASES_PENDING = "renta_negative_general_bases_pending"
    #: The negative net capital-mobiliario balances of the savings base pending from the four
    #: previous ejercicios (Ley 35/2006 art. 49.1.a).
    RENTA_NEGATIVE_SAVINGS_CAPITAL_INCOME_PENDING = "renta_negative_savings_capital_income_pending"
    #: The negative savings-base balances of gains and losses pending from the four previous
    #: ejercicios (Ley 35/2006 art. 49.1.b).
    RENTA_NEGATIVE_SAVINGS_GAINS_LOSSES_PENDING = "renta_negative_savings_gains_losses_pending"


AbsenceAttestationFamilyField = Annotated[
    AbsenceAttestationFamily, BeforeValidator(coerce_enum_member(AbsenceAttestationFamily))
]
"""Registry token hydrated into an :class:`AbsenceAttestationFamily` member."""


__all__ = ["AbsenceAttestationFamily", "AbsenceAttestationFamilyField"]
