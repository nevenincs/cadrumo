"""The statement a filer may make that one earlier-filing carry holds nothing.

A carry read from an earlier filing is unknown, never zero, while no earlier
return supplies it. For some carries the law leaves a filer who has nothing
pending only that statement to make: the negative general bases still pending
from the four previous ejercicios a Modelo 100 compensates (Ley 35/2006 art.
50.3) are one. The registry declares on the binding which statement it takes,
as one member of a closed family, so a carry that is not declared never takes
it: a statement that a prior-year income or a prior instalment was zero would
assert a figure, not an absence.

The family is authored on the binding row::

    absence_attestation = "renta_negative_general_bases_pending"

It is a closed vocabulary hydrated at the loader boundary, so an unknown token
fails registry load. A scalar family's binding must read a decimal from an
earlier filing. A row family's binding is a column of a repeating group whose
carry the application reads from no earlier filing it holds, so each statement
names the row it speaks of and may state an amount as well as an absence: the
interest and repair expenses a let property still carries from the four
previous ejercicios (Ley 35/2006 art. 23.1.a; RIRPF art. 13.a) are one.
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


__all__ = ["ROW_GRAIN_FAMILIES", "AbsenceAttestationFamily", "AbsenceAttestationFamilyField"]
