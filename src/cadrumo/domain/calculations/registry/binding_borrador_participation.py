"""How a binding admitted to a borrador snapshot takes part in a calculation.

``aeat_prefilled`` says only that a borrador snapshot may hold a value for the
binding. Whether that value may then supply the binding is a second, separate
fact, declared here: the AEAT borrador is informative, so on a casilla whose
value the taxpayer must evidence (a credit for withholding suffered) the
borrador may corroborate the evidenced value but never stand in for it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BeforeValidator

from .schema_base import coerce_enum_member

__all__ = ["BorradorParticipation", "BorradorParticipationField"]


class BorradorParticipation(StrEnum):
    """Whether a borrador value may supply a binding, or is only compared with it."""

    PRECEDENCE = "precedence"
    """The borrador tier may supply the value; the undeclared default of an admitted binding."""
    CROSS_CHECK_ONLY = "cross_check_only"
    """The borrador value is kept for comparison and never enters the precedence ladder."""


BorradorParticipationField = Annotated[
    BorradorParticipation,
    BeforeValidator(coerce_enum_member(BorradorParticipation)),
]
"""Registry token hydrated into a :class:`BorradorParticipation` member."""
