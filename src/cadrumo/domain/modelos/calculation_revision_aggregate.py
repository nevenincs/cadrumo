"""Context-bound validation for persisted calculation-revision amendments."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.identity import SubjectTaxId
from ..calculations.registry.schema import RegistrySnapshot
from ..calculations.registry.schema_references import SourceReference
from ..justificante import Justificante
from .calculation_revision import CalculationRevision
from .calculation_revision_amendment import (
    CalculationRevisionAmendmentIdentity,
    CalculationRevisionAmendmentKind,
    M303RectificativaMotive,
    m303_rectificativa_motive_is_applicable,
)
from .calculation_revision_m303_handoff import M303FilingInstanceEvidence
from .errors import ModeloValidationError
from .filing_record import ModeloRecordCatalogue, is_justificante_backed_external_evidence
from .work_unit import WorkUnit, WorkUnitCatalogue

CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY = "calculation_revision_aggregate_context"


class CalculationRevisionAggregateContext(BaseModel):
    """Authorities required to validate a revision outside isolated model shape."""

    model_config = STRICT_FROZEN_CONFIG

    work_units: WorkUnitCatalogue
    filing_records: ModeloRecordCatalogue
    justificantes: tuple[Justificante, ...]
    registry_snapshots: Mapping[str, RegistrySnapshot]
    expected_taxpayer_tax_id: SubjectTaxId | None


class ValidatedM303RectificativaEvidence(BaseModel):
    """The persisted amendment evidence exposed after the complete authority join."""

    model_config = STRICT_FROZEN_CONFIG

    motive: M303RectificativaMotive
    original_aeat_receipt: str


def validate_calculation_revision_aggregate(
    revision: CalculationRevision,
    *,
    context: CalculationRevisionAggregateContext,
) -> ValidatedM303RectificativaEvidence | None:
    """Validate one amendment :class:`~CalculationRevision` against its parent and evidence chain."""
    identity = _rectificativa_identity(revision)
    if identity is None:
        return None
    work_unit = _require_parent_work_unit(revision, context)
    if work_unit.modelo != Modelo.M303.value:
        if identity.m303_rectificativa_motive is not None:
            raise ModeloValidationError("an M303 rectificativa motive is forbidden for another modelo")
        return None

    m303 = _require_m303_filing_evidence(revision)
    record_design = _validate_m303_evidence_coordinate(m303, work_unit)
    snapshot = _require_registry_snapshot(context, work_unit)
    _validate_record_design_authority(snapshot, record_design)
    motive = _require_rectificativa_motive(identity, work_unit, record_design)
    receipt = _require_target_receipt(identity, context, work_unit)
    if context.expected_taxpayer_tax_id is None:
        raise ModeloValidationError("M303 rectificativa aggregate requires the authoritative taxpayer tax id")
    if not receipt.matches_filing_target(
        modelo=Modelo.M303.value,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        tax_id=context.expected_taxpayer_tax_id,
    ):
        raise ModeloValidationError("M303 rectificativa justificante disagrees with the taxpayer or filing coordinate")
    if receipt.presentation_id is None:
        raise ModeloValidationError("M303 rectificativa justificante requires the original AEAT receipt number")
    return ValidatedM303RectificativaEvidence(
        motive=motive,
        original_aeat_receipt=receipt.presentation_id,
    )


def _rectificativa_identity(revision: CalculationRevision) -> CalculationRevisionAmendmentIdentity | None:
    """Return the revision identity when this revision is rectificativa."""
    identity = revision.amendment_identity
    if identity is None or identity.kind is not CalculationRevisionAmendmentKind.RECTIFICATIVA:
        return None
    return identity


def _require_parent_work_unit(
    revision: CalculationRevision,
    context: CalculationRevisionAggregateContext,
) -> WorkUnit:
    """Resolve and identity-check the authoritative parent work unit."""
    work_unit = context.work_units.get(revision.work_unit_id)
    if work_unit is None:
        raise ModeloValidationError("rectificativa calculation revision has no authoritative parent WorkUnit")
    if work_unit.work_unit_id != revision.work_unit_id:
        raise ModeloValidationError("rectificativa calculation revision and parent WorkUnit identities disagree")
    return work_unit


def _require_m303_filing_evidence(revision: CalculationRevision) -> M303FilingInstanceEvidence:
    """Resolve the immutable M303 evidence envelope from a revision."""
    filing_evidence = revision.filing_instance_evidence
    if filing_evidence is None:
        raise ModeloValidationError("M303 rectificativa revision requires immutable filing-instance evidence")
    return filing_evidence.m303


def _validate_m303_evidence_coordinate(
    evidence: M303FilingInstanceEvidence,
    work_unit: WorkUnit,
) -> SourceReference:
    """Validate the M303 evidence coordinates and return its record design."""
    regimen_snapshot = evidence.regimen_simplificado.regimen_snapshot
    calculation_result = evidence.regimen_simplificado.calculation_result
    if evidence.period != work_unit.period:
        raise ModeloValidationError("M303 rectificativa evidence period disagrees with its parent WorkUnit")
    if regimen_snapshot.filing_year != work_unit.filing_year:
        raise ModeloValidationError("M303 rectificativa evidence filing year disagrees with its parent WorkUnit")
    if regimen_snapshot.registry_revision_id != work_unit.revision_id:
        raise ModeloValidationError("M303 rectificativa evidence registry revision disagrees with its parent WorkUnit")
    if calculation_result.period != work_unit.period:
        raise ModeloValidationError("M303 rectificativa result period disagrees with its parent WorkUnit")
    return regimen_snapshot.record_design


def _require_registry_snapshot(
    context: CalculationRevisionAggregateContext,
    work_unit: WorkUnit,
) -> RegistrySnapshot:
    """Resolve the exact law-selected registry snapshot for a work unit.

    A filing snapshot rather than a static revision inspection. Amending and
    exporting a rectificativa IS a filing operation, so it reads through the
    gate that certifies the revision can produce a filing artifact instead of
    the projection that exists to skip it -- and every M303 coordinate these
    paths reach resolves the identical revision under either.
    """
    snapshot = context.registry_snapshots.get(work_unit.work_unit_id)
    if snapshot is None:
        raise ModeloValidationError("M303 rectificativa revision lacks exact registry snapshot context")
    if snapshot.modelo.id != Modelo.M303 or snapshot.revision.id != work_unit.revision_id:
        raise ModeloValidationError("M303 rectificativa registry snapshot disagrees with its parent WorkUnit")
    return snapshot


def _validate_record_design_authority(
    snapshot: RegistrySnapshot,
    record_design: SourceReference,
) -> None:
    """Require the embedded M303 record design to be owned by the snapshot."""
    inspected_source = snapshot.sources.get(record_design.id)
    if inspected_source is None or inspected_source.id not in snapshot.revision.source_refs:
        raise ModeloValidationError("M303 rectificativa record-design source is not owned by the selected revision")
    if inspected_source != record_design:
        raise ModeloValidationError(
            "M303 rectificativa embedded record-design evidence diverges from registry authority",
        )


def _require_rectificativa_motive(
    identity: CalculationRevisionAmendmentIdentity,
    work_unit: WorkUnit,
    record_design: SourceReference,
) -> M303RectificativaMotive:
    """Validate and return the persisted motive for the exact M303 design."""
    applicable = m303_rectificativa_motive_is_applicable(
        registry_revision_id=work_unit.revision_id,
        record_design=record_design,
    )
    motive = identity.m303_rectificativa_motive
    if not applicable:
        if motive is not None:
            raise ModeloValidationError(
                "M303 rectificativa motive is forbidden outside the exact reviewed capability set",
            )
        raise ModeloValidationError("M303 rectificativa amendment is unsupported by this exact record-design source")
    if motive is None:
        raise ModeloValidationError("M303 rectificativa amendment requires exactly one persisted motive")
    return motive


def _require_target_receipt(
    identity: CalculationRevisionAmendmentIdentity,
    context: CalculationRevisionAggregateContext,
    work_unit: WorkUnit,
) -> Justificante:
    """Resolve the one AEAT-accepted target receipt for a rectificativa."""
    target = context.filing_records.get(identity.amends_filing_record_id)
    if target is None:
        raise ModeloValidationError("M303 rectificativa amended filing target does not resolve")
    target_coordinate = (
        target.work_unit_id,
        target.bucket_id,
        target.modelo,
        target.filing_year,
        target.period,
    )
    work_coordinate = (
        work_unit.work_unit_id,
        work_unit.bucket_id,
        work_unit.modelo,
        work_unit.filing_year,
        work_unit.period,
    )
    if target_coordinate != work_coordinate:
        raise ModeloValidationError("M303 rectificativa amended filing target crosses its WorkUnit filing coordinate")
    if not target.aeat_accepted or target.external_evidence is None:
        raise ModeloValidationError("M303 rectificativa target must be an AEAT-accepted filing with external evidence")
    if not is_justificante_backed_external_evidence(target.external_evidence.kind):
        raise ModeloValidationError(
            "M303 rectificativa target evidence is not backed by persisted justificante metadata",
        )
    target_reference_id = target.external_evidence.reference_id
    matches = tuple(receipt for receipt in context.justificantes if receipt.csv == target_reference_id)
    if len(matches) != 1:
        raise ModeloValidationError("M303 rectificativa target evidence must resolve to exactly one justificante")
    return matches[0]


__all__ = [
    "CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY",
    "CalculationRevisionAggregateContext",
    "ValidatedM303RectificativaEvidence",
    "validate_calculation_revision_aggregate",
]
