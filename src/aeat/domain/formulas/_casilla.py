"""Casilla-definition model used inside a :class:`Ruleset`.

A :class:`CasillaDefinition` is the engine-side description of a single
casilla (tax-form box): its identifier, multilingual label, data type,
whether it is user-entered or computed, and the legal citations that
govern it.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core.errors import RulesetValidationError
from ...core.i18n import Translatable, require_authoritative
from ..casillas import CasillaDataType
from ..modelos import LegalCitation

_CASILLA_ID_RE = re.compile(r"^\d{2,5}$")
"""Permitted casilla-identifier shape: 2 to 5 ASCII digits."""


class CasillaDefinition(BaseModel):
    """One casilla inside a ruleset.

    Attributes:
        casilla_id: The 2-4 digit casilla identifier (e.g. ``"01"``).
        label: Multilingual label (Spanish authoritative).
        computed: ``True`` when the engine derives this casilla from
            a :class:`FormulaDefinition`; ``False`` when the caller
            supplies the value.
        data_type: The casilla's value kind (EUR / integer / ...).
        legal_basis: Tuple of legal citations grounding the casilla.
        notes_es: Optional Spanish free-form engine-author note.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    casilla_id: Annotated[str, Field(min_length=2, max_length=5)]
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

    @model_validator(mode="after")
    def _require_legal_basis_for_computed(self) -> CasillaDefinition:
        """Refuse construction of a computed casilla without a legal citation.

        ``CasillaDefinition.legal_basis`` is required for ``computed=True``
        rows because tax math without legal citations is unverifiable for
        an AEAT-inspector scenario, and the ``KnownBadCitation`` blocklist
        only fires when a citation is present.

        The companion ``aeat audit rulesets citations`` CLI (under
        :mod:`aeat.entrypoints.cli.audit`) reports per-modelo coverage and
        fails non-zero on any gap, so future drift surfaces both at import
        time and in the dedicated audit surface.
        """
        if self.computed and not self.legal_basis:
            raise RulesetValidationError(
                f"casilla {self.casilla_id!r}: computed casillas require at least "
                f"one LegalCitation in legal_basis. Cite the BOE / RD / Orden / "
                f"Ley / Reglamento / Manual práctico primary source that grounds "
                f"this calculation."
            )
        return self
