"""Shared payload rows for modelo calculation-revision envelopes.

The rows in this module are nested JSON-envelope fragments reused by modelo
work-revision result schemas. They project
:class:`CasillaObservation` rows emitted by
:class:`RegistryCalculationResult` and
:class:`ResultSummaryRow` headline-result rows into
strict :class:`OutputSchema` fragments.
They are not direct CommandSpec result targets on their own; graph-declared
:class:`WorkRevisionResult`,
:class:`WorkObservationsResult`,
and :class:`WorkCalculateResult` models
carry them into :class:`SchemaEnvelope` through
:func:`emit_envelope`.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from ...application.modelo._result_summary import ResultSummaryRole
from ...core import BindingSourceKind, CalculationSourceLineageRole, CasillaId
from ...core.identity import CalculationRevisionId, WorkUnitId
from ...core.json_contract import OutputSchema
from ...core.text_bounds import NonEmptyStr, PositiveCount
from ...domain.calculations.registry.ids import BindingId, FormulaId, RelationId
from ...domain.calculations.registry.schema_base import LegalRefs, SourceRefs


class DetailRowPayload(OutputSchema):
    """One JSON-safe modelo detail row.

    Detail rows are heterogeneous by modelo and row type, so the public payload
    keeps the row discriminator and the row's own field map instead of forcing
    each command schema to duplicate every domain row shape.
    """

    index: PositiveCount
    row_type: NonEmptyStr
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
    legal_refs: LegalRefs
    source_refs: SourceRefs
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


class SourceProvenancePayload(OutputSchema):
    """One JSON-safe resolver-level source-mesh trace row.

    Mirrors :class:`CalculationSourceRef`: the resolver -> source-object ->
    fingerprint trace the calculation source mesh recorded when it produced
    the revision, projected from :class:`CalculationRevision.source_provenance`.

    ``dependency_treatment`` carries the registry's declared carry
    classification (``direct_annual_settlement`` / ``factual_evidence``)
    through to the operator, so a ``factual_evidence`` carry — a fact to
    reconcile against a taxpayer's own document, rather than a figure that
    settles the return — stays distinguishable at the JSON boundary. Empty
    means the revision declared no treatment, which is not the same as either
    declared value and must never be read as one. This field is carried, not
    gated: its presence never withholds or zeroes the casilla value it
    accompanies.
    """

    resolver_id: str
    resolved_binding_source: BindingSourceKind
    contributor_source_kind: str
    contributor_binding_source: BindingSourceKind | None
    lineage_role: CalculationSourceLineageRole
    source_ref: str
    parent_source_ref: str | None
    fingerprint: str | None = None
    dependency_treatment: str = ""


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


class CalculationRevisionProjectionFields(OutputSchema):
    """Shared JSON projection of a persisted :class:`CalculationRevision`.

    ``aeat app modelo work calculate``, ``... work revision``, and
    ``... work wizard`` each emit the same calculation-revision snapshot
    fields, plus their own command-specific extras (``saved``/
    ``saved_confirmation``, Modelo 202 modality, the wizard's
    ``prompted_casillas``, …). Not itself a CommandSpec schema authority target: each
    concrete result subclasses this mixin and is referenced by its own command
    path, so the shared fields stay declared once while each command keeps
    its own strict, independently declared schema target.
    """

    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    state: str
    casilla_values: dict[CasillaId, str]
    observations: tuple[ObservationPayload, ...]
    result_summary: tuple[ResultSummaryRowPayload, ...] = ()
    detail_rows: tuple[DetailRowPayload, ...] = ()
    source_provenance: tuple[SourceProvenancePayload, ...] = ()
    binding_overrides: dict[BindingId, str]
    relation_overrides: dict[RelationId, str] = Field(default_factory=dict)
    input_values_by_casilla_id: dict[CasillaId, str]
    created_at: str
    updated_at: str
    verified_at: str | None = None
    verified_by: str | None = None
    filed_at: str | None = None
    filed_by: str | None = None
    superseded_at: str | None = None


class CalculationRevisionCommandProjectionFields(OutputSchema):
    """Compact persisted-revision projection for create-style command results.

    Calculate and wizard return the new revision's actionable values and stable
    identity. Resolver-level ``source_provenance`` remains available from the
    singular ``modelo work revision`` read instead of being duplicated in every
    create response and advertised schema.
    """

    calculation_revision_id: CalculationRevisionId
    work_unit_id: WorkUnitId
    state: str
    casilla_values: dict[CasillaId, str]
    observations: tuple[ObservationPayload, ...]
    result_summary: tuple[ResultSummaryRowPayload, ...] = ()
    detail_rows: tuple[DetailRowPayload, ...] = ()
    binding_overrides: dict[BindingId, str]
    relation_overrides: dict[RelationId, str] = Field(default_factory=dict)
    input_values_by_casilla_id: dict[CasillaId, str]
    created_at: str
    updated_at: str
    verified_at: str | None = None
    verified_by: str | None = None
    filed_at: str | None = None
    filed_by: str | None = None
    superseded_at: str | None = None


__all__ = [
    "CalculationRevisionCommandProjectionFields",
    "CalculationRevisionProjectionFields",
    "DetailRowPayload",
    "ObservationPayload",
    "ResultSummaryRowPayload",
    "SourceProvenancePayload",
]
