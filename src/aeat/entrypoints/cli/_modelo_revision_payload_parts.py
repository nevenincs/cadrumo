"""Shared :class:`OutputSchema` payload rows for modelo calculation revisions.

The rows in this module are nested JSON-envelope fragments reused by modelo
work-revision result schemas. They carry registry-grounded casilla, formula,
legal-reference, and source-reference identifiers while inheriting the strict
CLI payload contract from :class:`OutputSchema`.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from ...domain.calculations.registry import CasillaId, FormulaId, LegalRefId, SourceRefId
from ._schemas import OutputSchema


class ObservationPayload(OutputSchema):
    """One typed casilla observation with full provenance."""

    casilla_id: CasillaId
    value: str  # serialised Decimal
    formula_id: FormulaId | None = None
    operand_refs: tuple[str, ...] = ()
    operand_casilla_refs: tuple[CasillaId, ...] = ()
    operand_values: tuple[str, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _operand_casilla_refs_are_traced(self) -> ObservationPayload:
        missing = tuple(ref for ref in self.operand_casilla_refs if ref not in self.operand_refs)
        if missing:
            raise ValueError(
                f"observation payload for {self.casilla_id!r} declares operand_casilla_refs "
                f"that are absent from operand_refs: {missing!r}",
            )
        return self


class ResultSummaryRowPayload(OutputSchema):
    """One headline-result summary row (registry-declared lead figure)."""

    role: str
    casilla_id: CasillaId
    value: str  # serialised Decimal
    label: str


__all__ = ["ObservationPayload", "ResultSummaryRowPayload"]
