"""Contract tests for the strict, read-only Workspace V1 model family."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from ....core import OutputLanguage, Period
from .._work_addressing import ModeloVisibleFilingTarget
from .._workspace_models import (
    ModeloWorkspaceBoundedFacetV1,
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceFacetName,
    ModeloWorkspaceRefusedResultV1,
    ModeloWorkspaceRequestV1,
    ModeloWorkspaceResultV1,
    ModeloWorkspaceSchemaRecordV1,
    ModeloWorkspaceStaticInspectionAdmissionV1,
    ModeloWorkspaceVersionRefusalV1,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def test_workspace_request_preserves_the_canonical_visible_target_through_a_strict_round_trip() -> None:
    request = ModeloWorkspaceRequestV1.model_validate_json(
        """{
            "contract_version": 1,
            "target": {"modelo": "130", "filing_year": 2025, "period": "1T"},
            "admission": {"kind": "static_inspection"},
            "output_language": "es"
        }"""
    )

    assert isinstance(request.target, ModeloVisibleFilingTarget)
    assert request.target.period.filing_year == 2025
    assert request.target.period == Period.from_year_and_code(2025, "1T")
    assert request.output_language is OutputLanguage.ES
    assert ModeloWorkspaceRequestV1.model_validate_json(request.model_dump_json()) == request
    with pytest.raises(ValidationError):
        ModeloWorkspaceRequestV1.model_validate_json(
            """{
                "contract_version": 1,
                "target": {"modelo": "130", "filing_year": 2025, "period": "1T", "revision": "not-allowed"},
                "admission": {"kind": "static_inspection"},
                "output_language": "es"
            }"""
        )
    with pytest.raises(ValidationError):
        request.__setattr__("contract_version", 2)


def test_workspace_result_keeps_version_refusal_outside_the_v1_coordinate_arm() -> None:
    result = ModeloWorkspaceRefusedResultV1(
        refusal=ModeloWorkspaceVersionRefusalV1(requested_version=2),
    )

    decoded = TypeAdapter(ModeloWorkspaceResultV1).validate_json(result.model_dump_json())

    assert isinstance(decoded, ModeloWorkspaceRefusedResultV1)
    assert decoded.refusal.requested_version == 2
    assert decoded.refusal.supported_version == 1
    assert "contract_version" not in decoded.model_dump(mode="json")


def test_workspace_bounded_facet_refuses_records_or_cursors_when_not_available() -> None:
    unavailable = ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1](
        facet=ModeloWorkspaceFacetName.SCHEMA,
        disposition=ModeloWorkspaceCapabilityDisposition.UNMEASURED,
        page_size=1,
    )

    assert unavailable.records == ()
    with pytest.raises(ValidationError):
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1](
            facet=ModeloWorkspaceFacetName.SCHEMA,
            disposition=ModeloWorkspaceCapabilityDisposition.UNMEASURED,
            page_size=1,
            has_more=True,
            next_cursor="next",
        )
    assert ModeloWorkspaceStaticInspectionAdmissionV1().kind.value == "static_inspection"
