"""The official codes an export writes where the calculation keys a box on a registry concept.

The calculation keys the IRNR rate on the conceptual tipo de renta token, while
the design's field holds the official code the filer declared. Several codes
share one concept, so the export writes the code the calculation revision
retained, checked against the one registry projection from code to concept,
and refuses a revision that retained none rather than guess one.
"""

from __future__ import annotations

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.irnr_tipo_renta import m210_tipo_renta_code_projection
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.filing.schema import ModeloDraft, ModeloValue
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.errors import ModeloError
from .export_field_refusal import export_design_fault_refusal, export_operator_decision_refusal
from .semantic_role_resolution import casilla_id_for_unique_semantic_role

_IRNR_TIPO_RENTA_ROLE = "irnr_tipo_renta"
_CODE_MISSING = "application.modelo.errors.export_m210_tipo_renta_code_missing"
_CODE_MISSING_REASON = "official tipo de renta code not retained by the calculation revision"
_CODE_CONCEPT_MISMATCH = "retained official tipo de renta code projects to another concept than the draft's"


def draft_with_official_codes(
    draft: ModeloDraft,
    *,
    revision: CalculationRevision,
    snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
) -> ModeloDraft:
    """Return ``draft`` with its tipo de renta box holding the official code ``revision`` retained.

    A revision without a tipo de renta box, or whose box is empty, is returned unchanged.
    """
    casilla_id = casilla_id_for_unique_semantic_role(snapshot, _IRNR_TIPO_RENTA_ROLE)
    if casilla_id is None:
        return draft
    values = list(draft.values)
    position = next(
        (index for index, value in enumerate(values) if value.casilla_id == casilla_id and value.value is not None),
        None,
    )
    if position is None:
        return draft
    values[position] = _official_code_value(values[position], revision=revision, operation=operation)
    return draft.model_copy(update={"values": tuple(values)})


def _official_code_value(
    value: ModeloValue, *, revision: CalculationRevision, operation: PinnedAuthorityOperation
) -> ModeloValue:
    projection = m210_tipo_renta_code_projection(authority=operation)
    code = revision.m210_official_tipo_renta_code
    if code is None:
        raise _code_missing_refusal(revision, casilla_id=value.casilla_id, accepted=sorted(projection))
    concept = projection.get(code)
    if concept is None or concept.value != str(value.value):
        raise export_design_fault_refusal(
            cause=_CODE_CONCEPT_MISMATCH, calculation_revision_id=revision.calculation_revision_id
        )
    return value.model_copy(update={"value": code})


def _code_missing_refusal(revision: CalculationRevision, *, casilla_id: str, accepted: list[str]) -> ModeloError:
    return export_operator_decision_refusal(
        translated_message=_CODE_MISSING,
        reason=_CODE_MISSING_REASON,
        context={
            "calculation_revision_id": revision.calculation_revision_id,
            "casilla_id": casilla_id,
            "accepted": ", ".join(accepted),
        },
    )


__all__ = ["draft_with_official_codes"]
