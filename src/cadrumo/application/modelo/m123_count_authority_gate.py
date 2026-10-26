"""Refusal for a Modelo 123 window that holds captured withholding.

Modelo 123 reports how many rentas the retenedor settled in the quarter
("Número de rentas", split into participation income and other rentas). No
official AEAT, BOE or DGT text defines the unit of that count for the
2024-and-later form: whether two instalments of one income, or an income
recognised when exigible and paid later, count once or twice. Every Modelo 123
input casilla is a manual input, so the calculation never reads the captured
evidence either.

Captured capital-income withholding therefore lands in a window that cannot be
declared honestly. Calculating it from manual inputs would present a
complete-looking return beside evidence it ignored, and deriving the count from
the evidence would file an ungrounded rule. Both are refused here with one
typed reason until an official count authority exists. The refusal carries no
command action: recovering needs that authority, which is the operator's
decision rather than a step this application can offer.

The same check runs at every stage that can carry a revision towards filing.
A revision calculated from manual inputs before any evidence was captured is
not refused at calculation, so verification, local filing and export re-read
the window: evidence captured after the calculation must stop that revision
from being verified, filed or exported as if it were complete.

A window without captured evidence is not refused, because nothing is hidden
from its manual declaration.
"""

from __future__ import annotations

from enum import StrEnum

from ...core.modelo import Modelo
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.work_unit import WorkUnit
from ..aggregation.retencion_observations_repository import RetencionObservationPorts
from .action_errors import ModeloPreconditionErrorMixin
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario

_MODELO_123 = Modelo("123")


class Modelo123CountAuthorityStage(StrEnum):
    """Operator leaf whose action the unresolved count refuses."""

    CALCULATE = "modelo.work.calculate"
    VERIFY = "modelo.work.verify"
    FILE = "modelo.work.file"
    EXPORT = "modelo.export"


class Modelo123CountAuthorityUnresolvedError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when a Modelo 123 window holds evidence its unresolved count cannot declare."""


def require_modelo_123_count_authority(
    work_unit: WorkUnit,
    *,
    retencion_ports: RetencionObservationPorts,
    stage: Modelo123CountAuthorityStage,
) -> None:
    """Refuse a Modelo 123 period whose window holds captured withholding at ``stage``."""
    if work_unit.modelo != _MODELO_123:
        return
    captured = retencion_ports.repository.load_observations(str(_MODELO_123), work_unit.period)
    if not captured:
        return
    raise Modelo123CountAuthorityUnresolvedError(
        translated_message="errors.refused.canonical_modelo_123_count_authority_unresolved",
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "captured_retencion_observations": str(len(captured)),
            "stage": stage.value,
        },
        precondition_failure=modelo_123_count_authority_unresolved_failure(
            work_unit,
            captured_observation_count=len(captured),
            stage=stage,
        ),
    )


def modelo_123_count_authority_unresolved_failure(
    work_unit: WorkUnit,
    *,
    captured_observation_count: int,
    stage: Modelo123CountAuthorityStage,
) -> ModeloPreconditionFailure:
    """Build the declared no-action verdict for the unresolved Modelo 123 count at ``stage``."""
    leaf = stage.value
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=leaf,
        scenario_id=f"{leaf}.m123_count_authority.unresolved",
        evidence_id=f"{leaf}.m123_count_authority",
        evidence_values={
            "work_unit_id": work_unit.work_unit_id,
            "modelo": str(work_unit.modelo),
            "year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "captured_retencion_observations": captured_observation_count,
            "count_authority_resolved": False,
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )


__all__ = [
    "Modelo123CountAuthorityStage",
    "Modelo123CountAuthorityUnresolvedError",
    "modelo_123_count_authority_unresolved_failure",
    "require_modelo_123_count_authority",
]
