"""Contract tests for registry-projected Modelo 303 simplified scope tokens."""

from __future__ import annotations

import pytest

from ....core.errors.hierarchy import CoreValidationError
from ...calculations.registry.errors import RegistryValidationError
from ...calculations.registry.iva_schema_vocabulary import (
    m303_regime_composition_simplified_scope,
)
from ...calculations.registry.tests.published_authority import PublishedGovernedFactSource
from ..regimen_simplificado_rows import (
    M303RegimenSimplificadoScope,
    M303RegimenSimplificadoScopeDecision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_AUTHORITY = PublishedGovernedFactSource()


@pytest.mark.parametrize(
    ("composition", "expected_scope", "is_not_claimed"),
    (
        ("general", "not_claimed", True),
        ("simplified", "evidence_required", False),
        ("mixed", "evidence_required", False),
    ),
)
def test_scope_decision_accepts_only_registry_projected_current_states(
    composition: str,
    expected_scope: str,
    is_not_claimed: bool,
) -> None:
    scope = m303_regime_composition_simplified_scope(composition, authority=_AUTHORITY)
    decision = M303RegimenSimplificadoScopeDecision(scope=scope)

    assert scope.value == expected_scope
    assert decision.is_not_claimed is is_not_claimed
    assert decision.model_dump(mode="json") == {"scope": expected_scope}


def test_scope_decision_rejects_an_unprojected_serialized_token() -> None:
    with pytest.raises(CoreValidationError, match="registry-projected token"):
        M303RegimenSimplificadoScopeDecision.model_validate({"scope": "not_claimed"})


def test_scope_token_refuses_direct_construction() -> None:
    with pytest.raises(TypeError, match="must be projected from the registry"):
        M303RegimenSimplificadoScope("not_claimed")


def test_scope_projection_refuses_an_unknown_composition() -> None:
    with pytest.raises(RegistryValidationError):
        m303_regime_composition_simplified_scope("unknown", authority=_AUTHORITY)
