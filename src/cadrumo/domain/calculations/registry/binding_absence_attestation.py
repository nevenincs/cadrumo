"""The statement a filer may make that a figure only they can state holds nothing.

Two kinds of figure take it. An earlier-filing carry, and an income box that no
record of the declaration supplies and only the filer can state.

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
fails registry load. A scalar family's binding must read a decimal, from an
earlier filing or from the filer's own entry. A row family's binding is a
column of a repeating group whose carry the application reads from no earlier
filing it holds, so each statement names the row it speaks of and may state an
amount as well as an absence: the interest and repair expenses a let property
still carries from the four previous ejercicios (Ley 35/2006 art. 23.1.a;
RIRPF art. 13.a) are one.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final

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
    #: The work income no payer certificate states: the employer contributions and the protected-estate contribution.
    RENTA_TRABAJO_INCOME_NOT_STATED = "renta_trabajo_income_not_stated"
    #: The interest and repair expenses a let property carries from the four previous ejercicios
    #: (Ley 35/2006 art. 23.1.a), stated per property row.
    RENTA_CAPITAL_INMOBILIARIO_GASTOS_PENDIENTES = "renta_capital_inmobiliario_gastos_pendientes"

    @property
    def row_grain(self) -> bool:
        """Whether each statement of this family names one row of a repeating group."""
        return self in ROW_GRAIN_FAMILIES


ROW_GRAIN_FAMILIES: Final = frozenset({AbsenceAttestationFamily.RENTA_CAPITAL_INMOBILIARIO_GASTOS_PENDIENTES})
"""The families stated per row, each statement naming the row's source identity."""


AbsenceAttestationFamilyField = Annotated[
    AbsenceAttestationFamily, BeforeValidator(coerce_enum_member(AbsenceAttestationFamily))
]
"""Registry token hydrated into an :class:`AbsenceAttestationFamily` member."""

PRIOR_CARRY_FAMILIES: Final[frozenset[AbsenceAttestationFamily]] = frozenset(
    {
        AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING,
        AbsenceAttestationFamily.RENTA_NEGATIVE_SAVINGS_CAPITAL_INCOME_PENDING,
        AbsenceAttestationFamily.RENTA_NEGATIVE_SAVINGS_GAINS_LOSSES_PENDING,
    }
)
"""The families whose bindings carry an amount pending from an earlier ejercicio's return.

A family of another kind states figures of the year itself that no source
holds, and a row family is stated on its own row; neither is stated as a
declaration-wide carry.
"""


__all__ = ["PRIOR_CARRY_FAMILIES", "ROW_GRAIN_FAMILIES", "AbsenceAttestationFamily", "AbsenceAttestationFamilyField"]
