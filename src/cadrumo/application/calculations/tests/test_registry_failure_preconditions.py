"""Application resolution of calculation-registry domain failure facts."""

from __future__ import annotations

import pytest

from ....core import ActionConditionality, NoRecoveryOutcome
from ....domain.calculations.registry.errors import RegistryFailureClassification, RegistryFailureCondition
from .._registry_preconditions import calculation_registry_failure_verdict

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("condition", "facts", "action_id", "outcome"),
    (
        (
            RegistryFailureCondition.TAXPAYER_MODEL_DECLARED,
            {"modelo": "100", "taxpayer_model_declared": False},
            "operator.profile.edit",
            None,
        ),
        (
            RegistryFailureCondition.MODELO_202_INCN_DECLARED,
            {"modelo": "202", "incn_prior_12_months_declared": False},
            "operator.profile.edit",
            None,
        ),
        (
            RegistryFailureCondition.QUERY_FILING_YEAR_SCOPED,
            {"modelo": "100", "as_of_supplied": True, "filing_year_supplied": False},
            "operator.modelo.describe",
            None,
        ),
        (
            RegistryFailureCondition.QUERY_CASILLA_DECLARED,
            {"modelo": "100", "casilla": "001", "casilla_declared": False},
            None,
            NoRecoveryOutcome.SAFETY,
        ),
        (
            RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT,
            {"modelo": "036", "authority_grade_declared": False},
            None,
            NoRecoveryOutcome.SAFETY,
        ),
        (
            RegistryFailureCondition.SNAPSHOT_EXPORT_LAYOUT_DECLARED,
            {"modelo": "036", "export_layout_declared": False},
            None,
            NoRecoveryOutcome.SAFETY,
        ),
        (
            RegistryFailureCondition.TREE_QUIESCENT,
            {"path": "registry/aeat", "registry_tree_quiescent": False},
            None,
            NoRecoveryOutcome.SAFETY,
        ),
    ),
)
def test_registry_failure_facts_resolve_through_existing_action_or_terminal_authority(
    condition: RegistryFailureCondition,
    facts: dict[str, str | bool],
    action_id: str | None,
    outcome: NoRecoveryOutcome | None,
) -> None:
    """Only application policy chooses the live catalogue action or terminal outcome."""
    verdict = calculation_registry_failure_verdict(RegistryFailureClassification(condition=condition, facts=facts))

    assert verdict.failed_condition_id == condition.value
    assert dict(verdict.evidence[0].values) == facts
    actual_action_id = None if verdict.action is None else verdict.action.action_id
    assert actual_action_id == action_id
    assert verdict.no_recovery_outcome is outcome
    if action_id is None:
        assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    elif condition in {
        RegistryFailureCondition.TAXPAYER_MODEL_DECLARED,
        RegistryFailureCondition.MODELO_202_INCN_DECLARED,
    }:
        assert verdict.conditionality is ActionConditionality.REQUIRES_ARGUMENTS
        assert verdict.missing_argument_names == ("profile_name",)
    else:
        assert verdict.conditionality is ActionConditionality.IMMEDIATE


def test_registry_failure_resolution_rejects_an_undeclared_domain_condition() -> None:
    """Mutation proof: a new domain condition cannot silently receive a guessed action."""
    with pytest.raises(AssertionError, match="unclassified calculation-registry failure condition"):
        calculation_registry_failure_verdict(
            RegistryFailureClassification(  # type: ignore[arg-type]
                condition="registry.test.unclassified", facts={"observed": False}
            )
        )
