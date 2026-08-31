"""Total operator-action projection for cross-period clean-state blockers."""

from __future__ import annotations

import pytest

from ....core.operator_action_enums import OperatorActionAxis
from ..cross_period_clean_state import CrossPeriodCleanStateBlocker
from ..cross_period_models import OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_cross_period_blocker_projection_is_total_and_action_typed() -> None:
    assert set(OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER) == set(CrossPeriodCleanStateBlocker)
    assert set(OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER.values()) <= set(OperatorActionAxis)


def test_cross_period_blocker_projection_preserves_distinct_operator_actions() -> None:
    assert (
        OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER[CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD]
        is OperatorActionAxis.FILE_PRIOR_PERIOD
    )
    assert (
        OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER[
            CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD
        ]
        is OperatorActionAxis.CAPTURE_EXTERNAL_EVIDENCE
    )
    assert (
        OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER[
            CrossPeriodCleanStateBlocker.MISSING_COMPLETE_VERIFICATION_REPORT
        ]
        is OperatorActionAxis.RE_VERIFY
    )
    assert (
        OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER[CrossPeriodCleanStateBlocker.UNRESOLVED_TAXPAYER_IDENTITY]
        is OperatorActionAxis.RESOLVE_IDENTITY
    )
    assert (
        OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER[
            CrossPeriodCleanStateBlocker.OBSERVATION_REVISION_VALUE_DIVERGENCE
        ]
        is OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE
    )
    assert (
        OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER[
            CrossPeriodCleanStateBlocker.INCOMPLETE_GROUP_MEMBER_COVERAGE
        ]
        is OperatorActionAxis.CONFIRM_GROUP_MEMBERSHIP
    )
    assert (
        OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER[CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE]
        is OperatorActionAxis.RESOLVE_REVISION_MISMATCH
    )
