"""Casilla-definition model used inside a :class:`Ruleset`.

A :class:`CasillaDefinition` is the engine-side description of a
single casilla (tax-form box): its identifier, trilingual label,
data type, whether it is user-entered or computed, and the
legal citations that govern it.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..casillas import CasillaDataType
from ..i18n import Translatable, require_authoritative
from ..models import LegalCitation

_CASILLA_ID_RE = re.compile(r"^\d{2,4}$")


class CasillaDefinition(BaseModel):
    """One casilla inside a ruleset.

    Attributes:
        casilla_id: The 2-4 digit casilla identifier (e.g. ``"01"``).
        label: Trilingual label (Spanish authoritative).
        computed: ``True`` when the engine derives this casilla from
            a :class:`FormulaDefinition`; ``False`` when the caller
            supplies the value.
        data_type: The casilla's value kind (EUR / integer / ...).
        legal_basis: Tuple of legal citations grounding the casilla.
        notes_es: Optional Spanish free-form engine-author note.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    casilla_id: Annotated[str, Field(min_length=2, max_length=4)]
    label: Translatable
    computed: bool
    data_type: CasillaDataType
    legal_basis: tuple[LegalCitation, ...] = ()
    notes_es: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def _validate_shape(self) -> CasillaDefinition:
        if not _CASILLA_ID_RE.fullmatch(self.casilla_id):
            raise ValueError(f"invalid casilla id: {self.casilla_id!r}")
        try:
            require_authoritative(self.label, domain="aeat")
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        return self
