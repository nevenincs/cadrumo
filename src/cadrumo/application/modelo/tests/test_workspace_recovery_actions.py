"""The workspace offers recovery actions only from its one declared set.

The TUI names each offered action through a locale key built from its id, and
the locale registration enumerates the declared set, so an id offered from
outside it would render as a missing translation rather than a step.
"""

from __future__ import annotations

import pytest

from ....core.errors.hierarchy import InternalInvariantError
from ...operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from ..workspace import MODELO_WORKSPACE_RECOVERY_ACTION_IDS, modelo_workspace_recovery_action

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_every_declared_recovery_action_is_catalogued() -> None:
    for action_id in MODELO_WORKSPACE_RECOVERY_ACTION_IDS:
        assert OPERATOR_ACTION_CATALOGUE.lookup(action_id).action_id == action_id


def test_a_catalogued_action_outside_the_declared_set_is_refused() -> None:
    undeclared = next(
        entry.action_id
        for entry in OPERATOR_ACTION_CATALOGUE.entries
        if entry.action_id not in MODELO_WORKSPACE_RECOVERY_ACTION_IDS
    )

    with pytest.raises(InternalInvariantError, match="not a declared workspace recovery action"):
        modelo_workspace_recovery_action(undeclared, work_unit_id=None)


def test_a_declared_action_without_a_work_unit_argument_is_offered() -> None:
    reference = modelo_workspace_recovery_action("operator.modelo.work.create", work_unit_id=None)

    assert reference is not None
    assert reference.action_id == "operator.modelo.work.create"
