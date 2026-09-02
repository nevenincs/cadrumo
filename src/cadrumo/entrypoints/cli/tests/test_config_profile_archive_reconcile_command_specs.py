from __future__ import annotations

import pytest

from .._root_command_specs import ROOT_COMMAND_SPECS
from ..command_spec import CommandSpecGraph
from ..config.profile_command_specs import PROFILE_COMMAND_SPECS

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_prepared_exports_keeps_its_profile_bound_contract_under_config_repair() -> None:
    graph = CommandSpecGraph((*ROOT_COMMAND_SPECS, *PROFILE_COMMAND_SPECS))

    assert ("aeat", "config", "profile", "archive", "reconcile") in tuple(node.path for node in graph.nodes())
    assert not [node.path for node in graph.nodes() if "maintenance" in node.path]
    reconcile = graph.by_schema_identity()["config.profile.archive.reconcile"]
    assert reconcile.policy.destructive is True
    assert reconcile.policy.write_route == "profile-bound"
    assert tuple(parameter.name for parameter in reconcile.parameters) == ("output_language",)
