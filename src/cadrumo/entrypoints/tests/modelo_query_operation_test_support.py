"""Canonical expectations for actual supervised modelo query reads."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel

from ...adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from ...application.modelo.data_inventory import data_inventory_checklist
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
                profile_id, checklist, language=OutputLanguage.ES
            ),
        )
    if definition_id != "modelo.readiness":
        raise ValueError(f"unknown modelo query operation: {definition_id}")
    ports = build_modelo_query_read_ports(bucket_id=str(profile_id))
    readiness = build_modelo_readiness_reports(
        (ModeloReadinessRequest(modelo="303", revision_id=report.revision, filing_year=2025, period=period),),
        active_profile_id=str(profile_id),
        read_ports=ports.read_ports,
        operation=operation,
    )
    assert len(readiness) == 1
    return ModeloQueryConformanceCase(
        request=ModeloReadinessOperationRequest(
            profile_id=profile_id, modelo="303", filing_year=2025, period=public_period
        ),
        expected_projection=ModeloReadinessProjection.from_report(profile_id, readiness[0], language=OutputLanguage.ES),
    )


__all__ = ["ModeloQueryConformanceCase", "prepare_modelo_query_conformance_case"]
