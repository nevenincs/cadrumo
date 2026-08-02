"""Shared payload rows for modelo calculation-revision envelopes.

The rows in this module are nested JSON-envelope fragments reused by modelo
work-revision result schemas. They project
:class:`CasillaObservation` rows emitted by
:class:`RegistryCalculationResult` and
:class:`ResultSummaryRow` headline-result rows into
strict :class:`OutputSchema` fragments.
They are not registered command results on their own; registered
:class:`WorkRevisionResult`,
:class:`WorkObservationsResult`,
and :class:`WorkCalculateResult` models
carry them into :class:`SchemaEnvelope` through
:func:`_emit_envelope`.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from ...application.modelo import ResultSummaryRole
from ...domain.calculations.registry import CasillaId, FormulaId, LegalRefId, SourceRefId
from ._schemas import OutputSchema


class DetailRowPayload(OutputSchema):
    """One JSON-safe modelo detail row.

    Detail rows are heterogeneous by modelo and row type, so the public payload
    keeps the row discriminator and the row's own field map instead of forcing
    each command schema to duplicate every domain row shape.
    """

    index: int = Field(ge=1)
    row_type: str = Field(min_length=1)
    fields: dict[str, str | None]


class ObservationPayload(OutputSchema):
    """One JSON-safe casilla observation with registry provenance.

    Mirrors :class:`CasillaObservation` after
    :func:`calculation_revision_payload`
    converts Decimal values to strings. Formula observations carry
    :obj:`FormulaId`, operand lineage,
    :obj:`LegalRefId`, and
    :obj:`SourceRefId`; non-formula
    observations still require legal and source refs so the CLI cannot emit an
    ungrounded casilla row.
    """

    casilla_id: CasillaId
    value: str  # serialised Decimal
    formula_id: FormulaId | None = None
    # Top-level formula operator label (``subtract``, ``add``, ``percent`` …)
    # carried from :class:`CasillaObservation`
    # so the operand trace can be rendered inline as ``op(refs) = op(values) =
    # value`` at the draft-review surface. ``None`` for input / bound casillas.
    op: str | None = None
    operand_refs: tuple[str, ...] = ()
    operand_casilla_refs: tuple[CasillaId, ...] = ()
    operand_values: tuple[str, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)
    # Carried from :class:`CasillaObservation` so an intentional zero (a
    # binding whose selector produced no source anchor for the target period)
    # stays distinguishable from a value-bearing zero at the operator surface.
    absent_by_design: bool = False

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

    Mirrors :class:`ResultSummaryRow`, whose rows come
    from :func:`calculation_result_summary`.  ``role``
    names the registry-declared total or key-figure purpose, while
    ``casilla_id`` keeps the summary row joinable to the underlying
    :class:`ObservationPayload` provenance.
    """

    role: ResultSummaryRole
    casilla_id: CasillaId
    value: str  # serialised Decimal
    label: str
    localized_labels: dict[str, str] = Field(default_factory=dict)


__all__ = ["DetailRowPayload", "ObservationPayload", "ResultSummaryRowPayload"]
