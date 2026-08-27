"""CLI projection of calculation-registry failure facts into an operator refusal."""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.errors import (
    RegistryFailureClassification,
    RegistryFailureCondition,
    RegistryValidationError,
)
from .._common import cli_policy_refusal_projection
from ..errors import _project_cadrumo_error

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_shared_cli_boundary_projects_the_domain_facts_through_application_policy() -> None:
    """The CLI consumes the application verdict instead of translating domain prose."""
    error = RegistryValidationError(
        translated_message="errors.calc.empty_expression",
        registry_failure=RegistryFailureClassification(
            condition=RegistryFailureCondition.QUERY_FILING_YEAR_SCOPED,
            facts={"modelo": "100", "as_of_supplied": True, "filing_year_supplied": False},
        ),
    )

    projected = _project_cadrumo_error(error, callback=lambda: None)
    refusal = cli_policy_refusal_projection(projected)

    assert refusal is not None
    assert refusal.precondition_action.failed_condition_id == RegistryFailureCondition.QUERY_FILING_YEAR_SCOPED.value
    assert refusal.precondition_action.action is not None
    assert refusal.precondition_action.action.action_id == "operator.modelo.describe"
