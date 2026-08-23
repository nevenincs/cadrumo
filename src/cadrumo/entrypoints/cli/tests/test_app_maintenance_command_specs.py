from __future__ import annotations

import pytest

from .._app_maintenance_command_specs import MAINTENANCE_COMMAND_SPECS
from .._command_spec import CommandSpecGraph
from .._root_command_specs import ROOT_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_maintenance_specs_replace_typer_structure_and_own_exact_contract() -> None:
    graph = CommandSpecGraph((*ROOT_COMMAND_SPECS, *MAINTENANCE_COMMAND_SPECS))

    assert tuple(node.path for node in graph.nodes() if "maintenance" in node.path) == (
        ("aeat", "app", "maintenance"),
        ("aeat", "app", "maintenance", "reconcile"),
    )
    reconcile = graph.by_schema_identity()["app.maintenance.reconcile"]
    assert reconcile.policy.destructive is True
    assert reconcile.policy.write_route == "profile-bound"
    assert tuple(parameter.name for parameter in reconcile.parameters) == ("output_language",)
