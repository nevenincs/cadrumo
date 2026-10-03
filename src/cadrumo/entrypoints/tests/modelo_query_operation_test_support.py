"""Canonical expectations for actual supervised modelo query reads."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel

from ...adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from ...application.modelo.data_inventory import data_inventory_checklist
from ...application.modelo.mcp_query_operation import (
    ModeloBindingsResolveTypedProjection,
    ModeloReadinessSafeLedgerIssue,
    ModeloReadinessSafeMissingRequirement,
    ModeloReadinessSafeRecovery,
    ModeloReadinessSummaryProjection,
    ModeloTypedBindingValue,
)
from ...application.modelo.query_read_operation import (
    ModeloBindingOverride,
    ModeloBindingRowV1,
    ModeloBindingsListProjection,
    ModeloBindingsListRequest,
    ModeloBindingsResolveProjection,
    ModeloBindingsResolveRequest,
    ModeloReadinessOperationRequest,
    ModeloReadinessProjection,
    ModeloRequiresProjection,
    ModeloRequiresRequest,
)
from ...application.modelo.registry_discovery import registry_bindings_for_scope, registry_modelo_codes
from ...application.operations.public_period import PublicPeriod
from ...application.state_projection import ModeloReadinessRequest, build_modelo_readiness_reports
from ...core.external_constants import OutputLanguage
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.user_profile.values import UserProfileFact
from ..modelo_query_read_operation_composition import build_modelo_query_read_ports


@dataclass(frozen=True, slots=True)
class ModeloQueryConformanceCase:
    """Actual request and a complete independently requested canonical answer."""

    request: BaseModel
    expected_projection: BaseModel


def prepare_modelo_query_conformance_case(
    definition_id: str, *, profile_id: UUID, operation: PinnedAuthorityOperation
) -> ModeloQueryConformanceCase:
    """Use the real indexed authority and the admitted encrypted profile."""
    period = Period.from_year_and_code(2025, "1T")
    public_period = PublicPeriod.from_period(period)
    report = registry_bindings_for_scope("303", period=period, operation=operation)
    if definition_id == "modelo.bindings.list":
        rows = tuple(ModeloBindingRowV1.from_report_row(report, row) for row in report.rows)
        return ModeloQueryConformanceCase(
            request=ModeloBindingsListRequest(profile_id=profile_id, modelo="303", year=2025, period_code="1T"),
            expected_projection=ModeloBindingsListProjection(
                authority_generation=operation.generation.logical_generation,
                profile_id=profile_id,
                modelo_filter="303",
                year_filter=2025,
                period_filter="1T",
                missing_filter=False,
                catalogue_only=False,
                known_modelos=registry_modelo_codes(operation=operation),
                binding_count=len(rows),
                bindings=rows,
            ),
        )
    if definition_id == "modelo.bindings.resolve":
        assert report.rows, "the real modelo must provide a grounded binding preview"
        override = ModeloBindingOverride(binding_id=report.rows[0].binding_id, value="0.75")
        rows = tuple(
            ModeloBindingRowV1.from_report_row(
                report, row, override=override.value if row.binding_id == override.binding_id else None
            )
            for row in report.rows
        )
        return ModeloQueryConformanceCase(
            request=ModeloBindingsResolveRequest(
                profile_id=profile_id, modelo="303", period=public_period, overrides=(override,)
            ),
            expected_projection=ModeloBindingsResolveProjection(
                authority_generation=operation.generation.logical_generation,
                profile_id=profile_id,
                modelo=report.code,
                revision=report.revision,
                filing_year=report.filing_year,
                period=report.period,
                override_count=1,
                binding_count=len(rows),
                bindings=rows,
            ),
        )
    if definition_id == "modelo.bindings.resolve.typed":
        assert report.rows, "the real modelo must provide a grounded binding preview"
        first = report.rows[0]
        snapshot = operation.snapshot("303", filing_year=2025, period="1T")
        declaration = next(binding for binding in snapshot.revision.bindings if binding.id == first.binding_id)
        assert declaration.value.channel.value == "decimal"
        override = ModeloBindingOverride(binding_id=first.binding_id, value="0.75")
        rows = tuple(
            ModeloBindingRowV1.from_report_row(
                report, row, override=override.value if row.binding_id == override.binding_id else None
            )
            for row in report.rows
        )
        return ModeloQueryConformanceCase(
            request=ModeloBindingsResolveRequest(
                profile_id=profile_id, modelo="303", period=public_period, overrides=(override,)
            ),
            expected_projection=ModeloBindingsResolveTypedProjection(
                authority_generation=operation.generation.logical_generation,
                profile_id=profile_id,
                modelo=report.code,
                revision=report.revision,
                filing_year=report.filing_year,
                period=report.period,
                override_count=1,
                binding_count=len(rows),
                bindings=rows,
                validated_overrides=(
                    ModeloTypedBindingValue(
                        binding_id=declaration.id,
                        data_type=declaration.value.data_type,
                        channel=declaration.value.channel,
                        value=override.value,
                    ),
                ),
            ),
        )
    if definition_id == "modelo.requires":
        upsert_test_profile_facts(
            profile_id, (UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),)
        )
        checklist = data_inventory_checklist(
            modelo="303", filing_year=2025, period=period, bucket_id=str(profile_id), operation=operation
        )
        return ModeloQueryConformanceCase(
            request=ModeloRequiresRequest(profile_id=profile_id, modelo="303", period=public_period),
            expected_projection=ModeloRequiresProjection.from_checklist(
                profile_id,
                checklist,
                language=OutputLanguage.ES,
                authority_generation=operation.generation.logical_generation,
            ),
        )
    if definition_id not in {"modelo.readiness", "modelo.readiness.summary"}:
        raise ValueError(f"unknown modelo query operation: {definition_id}")
    ports = build_modelo_query_read_ports(bucket_id=str(profile_id))
    readiness = build_modelo_readiness_reports(
        (ModeloReadinessRequest(modelo="303", revision_id=report.revision, filing_year=2025, period=period),),
        active_profile_id=str(profile_id),
        read_ports=ports.read_ports,
        operation=operation,
    )
    assert len(readiness) == 1
    request = ModeloReadinessOperationRequest(
        profile_id=profile_id, modelo="303", filing_year=2025, period=public_period
    )
    human = ModeloReadinessProjection.from_report(
        profile_id,
        readiness[0],
        language=OutputLanguage.ES,
        authority_generation=operation.generation.logical_generation,
    )
    if definition_id == "modelo.readiness":
        return ModeloQueryConformanceCase(request=request, expected_projection=human)
    verdict = human.profile_precondition_verdict
    return ModeloQueryConformanceCase(
        request=request,
        expected_projection=ModeloReadinessSummaryProjection(
            authority_generation=operation.generation.logical_generation,
            profile_id=human.profile_id,
            language=human.language,
            modelo=human.modelo,
            revision_id=human.revision_id,
            filing_year=human.filing_year,
            period=human.period,
            ready=human.ready,
            profile_ready=human.profile_ready,
            per_operation_requirements_assessed=human.per_operation_requirements_assessed,
            profile_refusal_cause=readiness[0].profile_refusal_cause,
            profile_recovery=(
                ModeloReadinessSafeRecovery(
                    failed_condition_id="profile.setup.declared_complete",
                    action_id="operator.profile.complete_setup",
                    missing_argument_names=(),
                )
                if verdict is not None
                else None
            ),
            registry_ready=human.registry_ready,
            registry_refusal_cause=readiness[0].registry_refusal_cause,
            binding_ready=human.binding_ready,
            missing=tuple(
                ModeloReadinessSafeMissingRequirement(
                    section_key=row.section_key,
                    field_key=row.field_key,
                    legal_refs=row.legal_refs,
                    modelos=row.modelos,
                )
                for row in readiness[0].missing
            ),
            missing_bindings=human.missing_bindings,
            ledger_preflight_required=human.ledger_preflight_required,
            ledger_ready=human.ledger_ready,
            ledger_period=human.ledger_period,
            ledger_checked_transaction_count=human.ledger_checked_transaction_count,
            ledger_issues=tuple(
                ModeloReadinessSafeLedgerIssue(transaction_id=row.transaction_id, reason=row.reason)
                for row in readiness[0].ledger_issues
            ),
        ),
    )


__all__ = ["ModeloQueryConformanceCase", "prepare_modelo_query_conformance_case"]
