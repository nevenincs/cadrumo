"""How a casilla row stands toward its predecessor edition.

A successor edition's casilla either continues a row of the edition before it
or it does not, and each answer comes in kinds that must not be confused:

- a continuation may be GROUNDED -- established from cited evidence such as an
  official record design -- or SEEDED, inferred mechanically from agreeing
  identifier, semantic role and data type. Inference written down is not a
  statement, so the two are kept apart;
- an absence may mean the box did not exist on the predecessor form
  (NEW_ON_FORM), that it existed but the corpus's predecessor edition does not
  declare it (PREDECESSOR_EDITION_SILENT), or that the row is a product concept
  no official form prints at all (NOT_ON_FORM). Writing a declaration gap as
  "new" is true of the corpus and false of the law.

The TOML token is hydrated into the closed :class:`CasillaLineageOrigin`
vocabulary at the registry boundary, so an unknown token is refused at load
with the accepted set named.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BeforeValidator

from .errors import RegistryValidationError

__all__ = ["CasillaLineageOrigin", "CasillaLineageOriginField"]


class CasillaLineageOrigin(StrEnum):
    """The relationship a casilla row declares toward its predecessor edition."""

    GROUNDED = "grounded"
    SEEDED = "seeded"
    NEW_ON_FORM = "new_on_form"
    PREDECESSOR_EDITION_SILENT = "predecessor_edition_silent"
    NOT_ON_FORM = "not_on_form"

    @property
    def continues_a_chain(self) -> bool:
        """Whether this origin asserts the row continues a predecessor-edition row."""
        return self in {CasillaLineageOrigin.GROUNDED, CasillaLineageOrigin.SEEDED}

    @property
    def requires_evidence(self) -> bool:
        """Whether this origin must name the evidence it rests on.

        A seeded chain is justified by the mechanical predicate its value
        names; every other origin is a claim about the form or the corpus that
        a reader must be able to check.
        """
        return self is not CasillaLineageOrigin.SEEDED


def _coerce_casilla_lineage_origin(value: object) -> object:
    """Coerce a TOML string literal to the canonical CasillaLineageOrigin member."""
    if isinstance(value, CasillaLineageOrigin):
        return value
    if isinstance(value, str):
        try:
            return CasillaLineageOrigin(value)
        except ValueError:
            raise RegistryValidationError(
                f"continuidad_origin {value!r} is not a recognised CasillaLineageOrigin "
                f"member; expected one of {[member.value for member in CasillaLineageOrigin]}",
            ) from None
    raise RegistryValidationError(
        f"continuidad_origin must be a string, got {type(value).__name__!r}",
    )


CasillaLineageOriginField = Annotated[
    CasillaLineageOrigin,
    BeforeValidator(_coerce_casilla_lineage_origin),
]
"""Annotated CasillaLineageOrigin that coerces TOML string literals to enum members."""
