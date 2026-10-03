"""Shared strict base, exact design identity, and parser-owned render-profile anchors."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from cadrumo.domain.calculations.registry.ids import (
    ModeloId,
    SourceRefId,
)


class _StrictModel(BaseModel):
    """Frozen authored boundary with unknown keys forbidden."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RenderProfileDesignIdentity(_StrictModel):
    """Identity of the exact official design to which rules apply."""

    modelo: ModeloId
    design_epoch: str = Field(min_length=1)
    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _coerce_ordinal(value: object) -> object:
    """Accept a legacy authored int literal alongside the parser's printed str label.

    Committed render-profile authoring data predates the parser's widened
    ``str | None`` ordinal and still writes bare integers (``ordinal = 14``).
    Coercing here lets that authored data hydrate unchanged.
    """
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    raise ValueError("ordinal must be a printed str label, a legacy int literal, or None")


type _AnchorOrdinal = Annotated[str | None, BeforeValidator(_coerce_ordinal)]


class RenderProfileAnchor(_StrictModel):
    """Complete parser-owned field identity; no selector or wildcard exists."""

    sheet: str = Field(min_length=1)
    source_row: int = Field(gt=0)
    #: Defaulted to ``None`` so a PDF anchor is authorable at all, mirroring
    #: :class:`SemanticMapAnchor`, which carries the same field for the same
    #: reason: a workbook design has a stable parser-column cell and a PDF design
    #: has none. The type already permitted ``None``; without a default the key
    #: was still required, and TOML has no way to author an explicit null, so
    #: every PDF anchor refused at load.
    source_cell: str | None = Field(default=None, pattern=r"^[A-Z]+[1-9][0-9]*$")
    #: The ordinal AEAT printed, verbatim -- a str because it is a printed LABEL,
    #: never an arithmetic value. Mirrors
    #: :attr:`domain.calculations.registry.RecordDesignField.ordinal`.
    ordinal: _AnchorOrdinal | None = Field(default=None, min_length=1)
    #: Declares that AEAT printed this row with NO ordinal, mirroring
    #: :attr:`SemanticMapAnchor.ordinal_absent` for the same reason: a row whose
    #: naturaleza AEAT omitted is admitted by a gap fill that cannot invent the
    #: ordinal AEAT never printed, and such a row is exactly the one this profile
    #: must be able to anchor. Kept an EXPLICIT opt-in so omitting both keys
    #: still refuses rather than defaulting into an anchor nothing can match.
    ordinal_absent: bool = False
    record_identity: str = Field(min_length=1)

    @model_validator(mode="after")
    def _require_ordinal_or_declared_absence(self) -> RenderProfileAnchor:
        if self.ordinal_absent and self.ordinal is not None:
            raise ValueError("anchor declares ordinal_absent but also names an ordinal")
        if not self.ordinal_absent and self.ordinal is None:
            raise ValueError(
                "anchor names no ordinal; author the ordinal AEAT printed, or declare "
                "ordinal_absent = true when the design printed the row without one",
            )
        return self
