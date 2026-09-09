"""CI boundary gates for the production-owned command authority."""

from __future__ import annotations

import pytest

from cadrumo.entrypoints.cli.command_api import command_spec_nodes

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

def test_ci_observes_every_production_node_through_the_public_api() -> None:
    nodes = command_spec_nodes()
    assert nodes
    assert len(nodes) == len({node.spec.key for node in nodes})
    assert len(nodes) == len({node.path for node in nodes})
    assert all(node.path[-1] == node.spec.token for node in nodes)
