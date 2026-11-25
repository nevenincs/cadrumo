"""Ordinary Modelo 303 evidence refused for its profile names the door of its cause."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.work_unit import WorkUnit
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ..action_errors import ModeloProfileReadinessError
from ..m303_ordinary_filing_evidence_authoring import _require_current_profile
from ..work_profile import ModeloWorkProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _stub(**attributes: object) -> object:
    """A record exposing only the attributes the refusal reads."""
    return SimpleNamespace(**attributes)


def test_a_profile_of_another_bucket_is_a_safety_stop() -> None:
    work_unit = cast("WorkUnit", _stub(bucket_id="bucket-a"))
    operation = cast("PinnedAuthorityOperation", _stub())
    profile = cast("ModeloWorkProfile", _stub(record=SimpleNamespace(profile_id="bucket-b")))

    with pytest.raises(ModeloProfileReadinessError) as refused:
        _require_current_profile(work_unit=work_unit, operation=operation, profile=profile)

    verdict = nested_terminal_precondition_verdict(refused.value)
    assert verdict is not None
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.SAFETY
