"""Every registered operation has recorded access facts, so a narrowed MCP surface can decide it."""

from __future__ import annotations

import pytest

from cadrumo.application.operations.access_facts import OPERATION_ACCESS_FACTS
from cadrumo.entrypoints.operation_composition import build_production_operation_registry

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_the_recorded_facts_name_exactly_the_registered_operations() -> None:
    """An operation with no facts is refused by every narrowed surface, and a stale entry hides a removal."""
    registered = {definition.definition_id for definition in build_production_operation_registry().definitions}
    recorded = {facts.definition_id for facts in OPERATION_ACCESS_FACTS}

    assert sorted(registered - recorded) == []
    assert sorted(recorded - registered) == []
