"""Shared payload rows for modelo calculation-revision envelopes.

The rows in this module are nested JSON-envelope fragments reused by modelo
work-revision result schemas. They project
:class:`~aeat.domain.calculations.registry.CasillaObservation` rows emitted by
:class:`~aeat.domain.calculations.registry.RegistryCalculationResult` and
:class:`~aeat.application.modelo.ResultSummaryRow` headline-result rows into
strict :class:`~aeat.entrypoints.cli._schemas.OutputSchema` fragments.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from ...domain.calculations.registry import CasillaId, FormulaId, LegalRefId, SourceRefId
from ._schemas import OutputSchema


class ObservationPayload(OutputSchema):
    """One JSON-safe casilla observation with registry provenance.

    Mirrors :class:`~aeat.domain.calculations.registry.CasillaObservation` after
    :func:`~aeat.entrypoints.cli._modelo_rendering.calculation_revision_payload`
    converts Decimal values to strings. Formula observations carry
    :class:`~aeat.domain.calculations.registry.FormulaId`, operand lineage,
    :class:`~aeat.domain.calculations.registry.LegalRefId`, and
    :class:`~aeat.domain.calculations.registry.SourceRefId`; non-formula
    observations still require legal and source refs so the CLI cannot emit an
    ungrounded casilla row.
    """

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
        """Require every casilla operand ref to remain present in the full operand trace."""
        missing = tuple(ref for ref in self.operand_casilla_refs if ref not in self.operand_refs)
        if missing:
            raise ValueError(
                f"observation payload for {self.casilla_id!r} declares operand_casilla_refs "
                f"that are absent from operand_refs: {missing!r}",
            )
        return self


class ResultSummaryRowPayload(OutputSchema):
    """One headline-result summary row selected from a calculation revision.

    Mirrors :class:`~aeat.application.modelo.ResultSummaryRow`, whose rows come
    from :func:`~aeat.application.modelo.calculation_result_summary`.  ``role``
    names the registry-declared total or key-figure purpose, while
    ``casilla_id`` keeps the summary row joinable to the underlying
    :class:`ObservationPayload` provenance.
    """

    role: str
    casilla_id: CasillaId
    value: str  # serialised Decimal
    label: str


__all__ = ["ObservationPayload", "ResultSummaryRowPayload"]
