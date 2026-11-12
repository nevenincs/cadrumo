"""Refusal for a Modelo 390 whose prorrata apartado the registry does not render.

The annual summary prints the prorrata of each activity in its apartado 12
(boxes 114 to 118, five activity rows). The Modelo 303 already reads those
rows from the profile's prorrata register, but an edition whose registry
declares no casilla for those boxes leaves the record positions blank in the
exported file, so a taxpayer whose register applies for the ejercicio would
export an incomplete summary without being told.

Verification reports that gap as a blocking finding and local filing and
export refuse with one typed reason, until the revision's registry renders
the apartado. The detection reads two things only: whether the register
records a prorrata that makes the rows applicable (or activity rows) for the
work unit's ejercicio, and whether the pinned revision registers casillas for
the apartado's boxes. No year or flag decides it, so an edition that registers
the boxes lifts the finding and the refusal without a change here. A taxpayer
with no register for the ejercicio is not affected: nothing is hidden from a
summary that has no prorrata to print.

The door points at the prorrata register listing, where the operator sees the
rows the summary lacks; recovering needs the registry edition, which is not a
step this application can offer.

See Also:
    :class:`~cadrumo.domain.prorrata_register.register.ProrrataRegister`
        The register whose rows the apartado prints.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ..prorrata_register.service import require_prorrata_register_coordinates_current
from .action_errors import ModeloPreconditionErrorMixin
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema import ModeloRevision
    from ...domain.modelos.work_unit import WorkUnit
    from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
    from ...domain.prorrata_register.register import ProrrataRegister

_ANNUAL_SUMMARY_ROLE: Final = "iva.annual_summary"

_APARTADO_BOXES: Final[tuple[str, ...]] = ("114", "115", "116", "117", "118")
"""The record-design boxes of apartado 12, one per fact each activity row prints."""

_PRORRATA_APARTADO_LEGAL_REFS: Final[tuple[str, ...]] = (
    "ley-37-1992:art-101",
    "orden-eha-3111-2009:art-1",
)


class Modelo390ProrrataApartadoStage(StrEnum):
    """Operator leaf whose action the unrendered apartado refuses."""

    VERIFY = "modelo.work.verify"
    FILE = "modelo.work.file"
    EXPORT = "modelo.export"


class Modelo390ProrrataApartadoUnrenderedError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when a Modelo 390 must print a prorrata apartado its registry edition does not render."""


def registry_renders_prorrata_apartado(revision: ModeloRevision) -> bool:
    """Whether ``revision`` registers a casilla for every box of apartado 12.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    registered = {casilla.number for casilla in revision.casillas}
    return all(box in registered for box in _APARTADO_BOXES)


def register_applies_to_ejercicio(register: ProrrataRegister, ejercicio: int) -> bool:
    """Whether the register holds a prorrata the summary of ``ejercicio`` must print.

    Core types:
    :class:`~cadrumo.domain.prorrata_register.register.ProrrataRegister`.
    """
    return register.requires_activity_rows_for(ejercicio) or bool(register.activity_rows_for_ejercicio(ejercicio))


def _unrendered_activity_rows(
    work_unit: WorkUnit,
    *,
    registry_revision_id: str,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> int | None:
    """The activity rows the apartado would print, or ``None`` where this gate does not apply."""
    if work_unit.modelo != form_for_role(_ANNUAL_SUMMARY_ROLE):
        return None
    if registry_renders_prorrata_apartado(operation.revision(work_unit.modelo, registry_revision_id)):
        return None
    register = require_prorrata_register_coordinates_current(prorrata_register_repository.load(), operation=operation)
    if not register_applies_to_ejercicio(register, work_unit.filing_year):
        return None
    return len(register.activity_rows_for_ejercicio(work_unit.filing_year))


def require_modelo_390_prorrata_apartado_rendered(
    work_unit: WorkUnit,
    *,
    registry_revision_id: str,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    operation: PinnedAuthorityOperation,
    stage: Modelo390ProrrataApartadoStage,
) -> None:
    """Refuse a Modelo 390 whose register applies but whose registry edition does not render apartado 12."""
    rows = _unrendered_activity_rows(
        work_unit,
        registry_revision_id=registry_revision_id,
        prorrata_register_repository=prorrata_register_repository,
        operation=operation,
    )
    if rows is None:
        return
    raise Modelo390ProrrataApartadoUnrenderedError(
        translated_message="errors.refused.refused_modelo_390_prorrata_apartado_unrendered",
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": str(work_unit.filing_year),
            "registered_activity_rows": str(rows),
            "stage": stage.value,
        },
        precondition_failure=modelo_390_prorrata_apartado_unrendered_failure(
            work_unit, activity_row_count=rows, stage=stage
        ),
    )


def modelo_390_prorrata_apartado_unrendered_failure(
    work_unit: WorkUnit,
    *,
    activity_row_count: int,
    stage: Modelo390ProrrataApartadoStage,
) -> ModeloPreconditionFailure:
    """Build the declared verdict that sends the filer to the prorrata register at ``stage``."""
    leaf = stage.value
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=leaf,
        scenario_id=f"{leaf}.m390_prorrata_apartado.unrendered",
        evidence_id=f"{leaf}.m390_prorrata_apartado",
        evidence_values={
            "work_unit_id": work_unit.work_unit_id,
            "modelo": str(work_unit.modelo),
            "year": work_unit.filing_year,
            "registered_activity_rows": activity_row_count,
            "apartado_rendered": False,
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )


def modelo_390_prorrata_apartado_verification_finding(
    work_unit: WorkUnit,
    *,
    registry_revision_id: str,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> tuple[ModeloVerificationFinding, ModeloPreconditionFailure] | None:
    """Return the blocking finding and its verify verdict, or ``None`` where the apartado is not owed or is rendered."""
    rows = _unrendered_activity_rows(
        work_unit,
        registry_revision_id=registry_revision_id,
        prorrata_register_repository=prorrata_register_repository,
        operation=operation,
    )
    if rows is None:
        return None
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.m390_prorrata_apartado_unrendered",
        message_facts={
            "filing_year": work_unit.filing_year,
            "registered_activity_rows": rows,
        },
        legal_refs=_PRORRATA_APARTADO_LEGAL_REFS,
    )
    failure = modelo_390_prorrata_apartado_unrendered_failure(
        work_unit, activity_row_count=rows, stage=Modelo390ProrrataApartadoStage.VERIFY
    )
    return finding, failure


__all__ = [
    "Modelo390ProrrataApartadoStage",
    "Modelo390ProrrataApartadoUnrenderedError",
    "modelo_390_prorrata_apartado_unrendered_failure",
    "modelo_390_prorrata_apartado_verification_finding",
    "register_applies_to_ejercicio",
    "registry_renders_prorrata_apartado",
    "require_modelo_390_prorrata_apartado_rendered",
]
