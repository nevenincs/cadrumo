from __future__ import annotations

import pytest

from .._command_spec import CommandSpecGraph
from .._config._repair_command_specs import CONFIG_REPAIR_COMMAND_SPECS
from .._root_command_specs import ROOT_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_prepared_exports_keeps_its_profile_bound_contract_under_config_repair() -> None:
    graph = CommandSpecGraph((*ROOT_COMMAND_SPECS, *CONFIG_REPAIR_COMMAND_SPECS))

    assert ("aeat", "config", "repair", "prepared-exports") in tuple(node.path for node in graph.nodes())
    assert not [node.path for node in graph.nodes() if "maintenance" in node.path]
    reconcile = graph.by_schema_identity()["config.repair.prepared_exports"]
    assert reconcile.policy.destructive is True
    assert reconcile.policy.write_route == "profile-bound"
    assert tuple(parameter.name for parameter in reconcile.parameters) == ("output_language",)
