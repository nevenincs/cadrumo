"""A stopped operation records the registry's failed condition for every frontend that reads its detail."""

from __future__ import annotations

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.calculations.registry.snapshot import build_validated_snapshot
from ....domain.calculations.registry.tests.registry_tree import bundled_modelo_components
from ..error_detail import OperationErrorDetailKind, build_operation_error_detail

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _filing_grade_refusal(operation: PinnedAuthorityOperation) -> RegistryValidationError:
    """Ask the published Modelo 200 revision for filing authority it does not declare."""
    modelo, catalogues = bundled_modelo_components("200")
    with validating_governed_facts(operation), pytest.raises(RegistryValidationError) as refused:
        build_validated_snapshot(modelo, catalogues, filing_year=2024, period="0A", grade=RegistryAuthorityGrade.FILING)
    return refused.value


def test_a_registry_authority_refusal_records_its_failed_condition_and_facts(
    operation: PinnedAuthorityOperation,
) -> None:
    error = _filing_grade_refusal(operation)

    detail = build_operation_error_detail(error)

    assert detail is not None
    assert detail.kind is OperationErrorDetailKind.REGISTERED_ERROR
    assert detail.error_code == "ERROR_CALCULATIONS_REGISTRY_VALIDATION"
    verdict = detail.precondition_verdict()
    assert verdict is not None
    assert verdict.failed_condition_id == "registry.snapshot.authority_grade.sufficient"
    (evidence,) = verdict.evidence
    assert dict(evidence.values) == {
        "authority_grade_declared": True,
        "declared_authority_grade": "calculation",
        "modelo": "200",
        "requested_authority_grade": "filing",
        "revision_id": "2024",
    }


def test_a_registry_error_without_a_classification_records_no_verdict() -> None:
    detail = build_operation_error_detail(RegistryValidationError("unclassified registry contradiction"))

    assert detail is not None
    assert detail.error_code == "ERROR_CALCULATIONS_REGISTRY_VALIDATION"
    assert detail.precondition_verdict() is None
