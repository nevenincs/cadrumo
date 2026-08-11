"""Action-spine coverage for modelo verification findings."""

from __future__ import annotations

import pytest

from ....core import OperatorActionAxis
from .. import (
    OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND,
    ModeloVerificationFindingKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_verification_finding_action_projection_is_total_and_preserves_distinct_remedies() -> None:
    assert set(OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND) == set(ModeloVerificationFindingKind)
    assert set(OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND.values()) <= set(OperatorActionAxis)
    assert (
        OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND[ModeloVerificationFindingKind.RECONCILIATION_MISMATCH]
        is OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE
    )
    assert (
        OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND[
            ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN
        ]
        is OperatorActionAxis.FILE_PRIOR_PERIOD
    )
    assert (
        OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND[ModeloVerificationFindingKind.ADVISORY]
        is OperatorActionAxis.REVIEW_ADVISORY
    )
