"""The boxes and bindings a modelo calculation or projection left without a value.

Shared by the annual projection and the calculation: both name a source gap
and a formula target the engine could not work out the same way, from the
source resolution's diagnostics and the engine's unresolved outcomes.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping

from pydantic import BaseModel, Field

from ...core.casilla_id import CasillaId
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.binding_targets import revision_bindings_by_id, sole_bound_casilla
from ...domain.calculations.registry.formula_runtime import RegistryCalculationResult
from ...domain.calculations.registry.ids import BindingId, FormulaId, LegalRefId, SourceRefId
from ...domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from .printed_boxes import PrintedBoxes


class ModeloProjectionUnresolvedBinding(BaseModel):
    """One source-owned binding the projection's sources left without a value.

    ``reason`` is the source diagnostic's reason token and ``note`` its closed
    calculation-note sentence when the resolver named one (for a credit: no
    payer evidence, or evidence contradicted by an absence attestation).
    ``fact`` is that sentence with the values it names, kept so the words of the
    note can be served; it is not a public field.
    """

    model_config = STRICT_FROZEN_CONFIG

    binding_id: BindingId
    casilla_id: CasillaId | None
    #: The number the form prints for that box; ``None`` for a working figure or when no box is named.
    box: str | None = None
    source_kind: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    note: CalculationNoteSentence | None = None
    fact: CalculationNoteFact | None = None


UNRESOLVED_OPERAND_REASON = "unresolved_operand"
"""The reason of a computed box omitted because an operand it reads is unresolved."""


class ModeloProjectionUnresolvedCasilla(BaseModel):
    """One computed box the projection could not give a value, with its formula's grounding.

    ``reason`` is :data:`UNRESOLVED_OPERAND_REASON` when the box reads an
    unresolved operand, or the engine's typed outcome reason otherwise.
    """

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    #: The number the form prints for the box; ``None`` for a working figure the form does not print.
    box: str | None = None
    reason: str = Field(min_length=1)
    formula_id: FormulaId
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


def unresolved_binding_rows(
    unresolved_binding_ids: Iterable[BindingId],
    diagnostics: Iterable[CalculationSourceDiagnostic],
    revision: ModeloRevision,
    boxes: PrintedBoxes,
    *,
    typed_casilla_ids: Collection[CasillaId] = (),
) -> tuple[ModeloProjectionUnresolvedBinding, ...]:
    """Report each unresolved binding once, by the diagnostic that names its box.

    Shared by the projection and the calculation: both name a source gap the
    same way, from the ids a source resolution left unresolved and the
    diagnostics it raised for them.

    A binding that feeds a box the filer typed is no gap: the filer's figure
    is that box's value, so a row naming the box would call a valued box empty.
    A binding that names no box, or another box, is still reported.

    Args:
        unresolved_binding_ids: The bindings the source resolution left unresolved.
        diagnostics: The diagnostics that resolution raised.
        revision: The pinned :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
            whose bindings name the box each unresolved binding feeds.
        boxes: The boxes that revision's form prints, which name each box by its printed number.
        typed_casilla_ids: The boxes the filer typed for this run; the projection has none.
    """
    bindings_by_id = revision_bindings_by_id(revision)
    by_binding = {
        diagnostic.binding_id: diagnostic
        for diagnostic in diagnostics
        if diagnostic.reason == "unresolved_binding" and diagnostic.binding_id is not None
    }
    rows = (
        _unresolved_binding_row(binding_id, by_binding.get(binding_id), revision, bindings_by_id, boxes)
        for binding_id in unresolved_binding_ids
    )
    return tuple(row for row in rows if row.casilla_id is None or row.casilla_id not in typed_casilla_ids)


def _unresolved_binding_row(
    binding_id: BindingId,
    diagnostic: CalculationSourceDiagnostic | None,
    revision: ModeloRevision,
    bindings_by_id: Mapping[BindingId, BindingDefinition],
    boxes: PrintedBoxes,
) -> ModeloProjectionUnresolvedBinding:
    """One unresolved binding, named by its diagnostic's box or else the sole box it feeds."""
    if diagnostic is None:
        casilla_id = sole_bound_casilla(revision, binding_id)
        return ModeloProjectionUnresolvedBinding(
            binding_id=binding_id,
            casilla_id=casilla_id,
            box=boxes.number(casilla_id),
            source_kind=str(bindings_by_id[binding_id].source),
            reason="unresolved_binding",
        )
    casilla_id = diagnostic.casilla_id or sole_bound_casilla(revision, binding_id)
    return ModeloProjectionUnresolvedBinding(
        binding_id=binding_id,
        casilla_id=casilla_id,
        box=boxes.number(casilla_id),
        source_kind=diagnostic.source_kind,
        reason=diagnostic.reason,
        note=diagnostic.fact.sentence if diagnostic.fact is not None else None,
        fact=diagnostic.fact,
    )


def unresolved_casilla_rows(
    engine_result: RegistryCalculationResult,
    revision: ModeloRevision,
    boxes: PrintedBoxes,
) -> tuple[ModeloProjectionUnresolvedCasilla, ...]:
    """Report every formula target the engine left without a value.

    The engine omits a formula target that reads an unresolved operand and
    reports a typed outcome for one it could not evaluate; every other formula
    target carries an observation. A target in neither is therefore omitted for
    an unresolved operand.

    Args:
        engine_result: The engine's observations and unresolved outcomes.
        revision: The pinned :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
            whose formulas name every target.
        boxes: The boxes that revision's form prints, which name each box by its printed number.
    """
    observed = {observation.casilla_id for observation in engine_result.observations}
    outcomes = {outcome.casilla_id: outcome for outcome in engine_result.unresolved_outcomes}
    rows = [
        ModeloProjectionUnresolvedCasilla(
            casilla_id=formula.target_casilla_id,
            box=boxes.number(formula.target_casilla_id),
            reason=(
                str(outcomes[formula.target_casilla_id].reason)
                if formula.target_casilla_id in outcomes
                else UNRESOLVED_OPERAND_REASON
            ),
            formula_id=formula.id,
            legal_refs=tuple(formula.legal_refs),
            source_refs=tuple(formula.source_refs),
        )
        for formula in revision.formulas
        if formula.target_casilla_id not in observed
    ]
    return tuple(sorted(rows, key=lambda row: row.casilla_id))


__all__ = [
    "UNRESOLVED_OPERAND_REASON",
    "ModeloProjectionUnresolvedBinding",
    "ModeloProjectionUnresolvedCasilla",
    "unresolved_binding_rows",
    "unresolved_casilla_rows",
]
