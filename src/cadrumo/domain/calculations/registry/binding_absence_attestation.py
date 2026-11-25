"""The registry's hydration of the absence-attestation family authored on a binding row.

The family is authored on the binding row::

    absence_attestation = "renta_negative_general_bases_pending"

It is a closed vocabulary (:class:`~cadrumo.core.absence_attestation_family.AbsenceAttestationFamily`)
hydrated at the loader boundary, so an unknown token fails registry load.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator

from ....core.absence_attestation_family import AbsenceAttestationFamily
from .schema_base import coerce_enum_member

AbsenceAttestationFamilyField = Annotated[
    AbsenceAttestationFamily, BeforeValidator(coerce_enum_member(AbsenceAttestationFamily))
]
"""Registry token hydrated into an :class:`AbsenceAttestationFamily` member."""


__all__ = ["AbsenceAttestationFamilyField"]
