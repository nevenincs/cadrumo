"""Regression for the shared agent-evaluation lifecycle-order authority."""

from __future__ import annotations

import pytest

from .. import _live_scoring, _runner
from .._models import LIFECYCLE_STAGE_ORDER

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_declared_and_observed_evaluators_share_one_lifecycle_order() -> None:
    """Both evaluator paths must consume the same immutable stage-order object."""
    assert _runner.LIFECYCLE_STAGE_ORDER is LIFECYCLE_STAGE_ORDER
    assert _live_scoring.LIFECYCLE_STAGE_ORDER is LIFECYCLE_STAGE_ORDER
