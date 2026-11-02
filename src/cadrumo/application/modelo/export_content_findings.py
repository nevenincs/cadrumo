"""Verification findings for an XML return the export would refuse for its content.

Which boxes a return lacks is decided only by rendering it and asking the export's
own required-content check, because the answer depends on the finished document:
zero-only branches are pruned by then and a choice in the schema has been taken. The
refusal is read rather than recomputed, so verification cannot grant what the export
refuses, and a layout of another format reaches no finding here.
"""

from __future__ import annotations

from ...core.export_layout_format import ExportLayoutFormat
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.export_shared_owner import canonical_export_layout
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.filing.errors import ModeloDraftError
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.modelos.work_unit import WorkUnit
from ..filing.export import refuse_xml_export_content
from ..filing.export_xml_value_limits import is_xml_required_content_refusal, is_xml_value_refusal, refused_xml_boxes
from ..filing.runtime import build_runtime_schema_provider
from .export_preparation import build_revision_export_draft, compose_export_dictionary_values
from .preconditions import ModeloPreconditionFailure
from .profile_export_binding import resolve_export_identity
from .verification_preconditions import build_verification_precondition_failure

_REQUIRED_CONTENT_MISSING = "application.modelo.findings.xml_required_content_missing"
_VALUE_REFUSED = "application.modelo.findings.xml_value_refused"
_NOT_RENDERED = "application.modelo.findings.xml_return_not_rendered"
_NOT_RENDERED_BOX = ""


def _refused_boxes(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    profile: TaxpayerProfile,
    operation: PinnedAuthorityOperation,
) -> tuple[str, tuple[str, ...]] | None:
    """Return the finding key and boxes of what the export would refuse, or ``None`` when it would pass."""
    provider = build_runtime_schema_provider(
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        modelos=(work_unit.modelo,),
        operation=operation,
    )
    try:
        draft = build_revision_export_draft(
            work_unit=work_unit,
            revision=target,
            workflow_profile=profile,
            period=work_unit.period,
            schema_provider=provider,
            operation=operation,
        )
        identity = resolve_export_identity(bucket_id=work_unit.bucket_id, operation=operation)
        if identity is None:
            return _NOT_RENDERED, (_NOT_RENDERED_BOX,)
        refuse_xml_export_content(
            draft,
            dictionary_values=compose_export_dictionary_values(
                draft=draft,
                taxpayer_identity=identity[1],
                bucket_id=work_unit.bucket_id,
                operation=operation,
                profile_export_bindings=provider.get_subview(str(work_unit.modelo)).profile_export_bindings,
            ),
            schema_provider=provider,
        )
    except (ModeloDraftError, ModeloError) as refused:
        if is_xml_required_content_refusal(refused):
            return _REQUIRED_CONTENT_MISSING, refused_xml_boxes(refused)
        if is_xml_value_refusal(refused):
            return _VALUE_REFUSED, refused_xml_boxes(refused)
        # Any other cause may quote a private value, so only the fact of it travels.
        return _NOT_RENDERED, (_NOT_RENDERED_BOX,)
    return None


def append_export_content_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    snapshot: RegistrySnapshot,
    profile: TaxpayerProfile,
    operation: PinnedAuthorityOperation,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    """Block one finding per box the export of an XML return would refuse."""
    layout = canonical_export_layout(snapshot.revision.export_layouts)
    if layout is None or layout.format is not ExportLayoutFormat.XML_DICTIONARY:
        return
    with validating_governed_facts(operation):
        refused = _refused_boxes(work_unit=work_unit, target=target, profile=profile, operation=operation)
    if refused is None:
        return
    message_locale_key, boxes = refused
    declared_casillas = {casilla.id for casilla in snapshot.revision.casillas}
    for box in boxes:
        finding = ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            casilla_id=box if box in declared_casillas else None,
            message_locale_key=message_locale_key,
            message_facts={"box": box} if box else {},
            legal_refs=tuple(layout.legal_refs),
            source_refs=tuple(layout.source_refs),
        )
        findings.append(finding)
        failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
            calculation_revision_id=target.calculation_revision_id,
            work_unit_id=target.work_unit_id,
            condition_id="modelo.work.verify.xml_return_content.accepted",
            scenario_id="modelo.work.verify.xml_return_content.refused",
            evidence_id="modelo.work.verify.xml_return_content",
            evidence_values={"box": box, "refusal": message_locale_key.rpartition(".")[2]},
            provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        )


__all__ = ["append_export_content_findings"]
