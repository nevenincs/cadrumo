"""Verification findings for values the export would write into cells of unconfirmed meaning.

The export refuses these values itself. Verification reports them too, because a
granted verification tells the operator the declaration is ready: it must not
pass a revision whose every export is already known to refuse;
:class:`RegistrySnapshot`, the pinned registry snapshot;
:class:`CalculationRevision`, the saved calculation revision.
"""

from __future__ import annotations

from ...core.casilla_id import CasillaId
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.calculations.registry.export_shared_owner import (
    canonical_export_layout,
    written_unadjudicated_shared_owners,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .preconditions import ModeloPreconditionFailure
from .verification_preconditions import build_verification_precondition_failure


def append_shared_casilla_cells_findings(
    *,
    target: CalculationRevision,
    snapshot: RegistrySnapshot,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    """Block one finding per casilla whose held value the export would refuse to write.

    ``target`` is the :class:`CalculationRevision`, the saved calculation revision.

    ``snapshot`` is the :class:`RegistrySnapshot`, the pinned registry snapshot.
    """
    layout = canonical_export_layout(snapshot.revision.export_layouts)
    if layout is None:
        return
    values: dict[CasillaId, object] = {**target.input_values_by_casilla_id, **target.casilla_values}
    for owner in written_unadjudicated_shared_owners(layout, snapshot.revision.casillas, values):
        target_cells = ",".join(owner.target_cell_ids)
        finding = ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            casilla_id=owner.casilla_id,
            message_locale_key="application.modelo.findings.shared_casilla_cells_unadjudicated",
            message_facts={"casilla_id": str(owner.casilla_id), "target_cells": target_cells},
            legal_refs=tuple(layout.legal_refs),
            source_refs=tuple(layout.source_refs),
        )
        findings.append(finding)
        failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
            calculation_revision_id=target.calculation_revision_id,
            work_unit_id=target.work_unit_id,
            condition_id="modelo.work.verify.shared_casilla_cells.adjudicated",
            scenario_id="modelo.work.verify.shared_casilla_cells.unadjudicated",
            evidence_id="modelo.work.verify.shared_casilla_cells",
            evidence_values={"casilla_id": str(owner.casilla_id), "target_cells": target_cells},
            provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        )


__all__ = ["append_shared_casilla_cells_findings"]
