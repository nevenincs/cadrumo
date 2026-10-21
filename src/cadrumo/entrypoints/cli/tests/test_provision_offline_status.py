"""``config provision status``, ``probe`` and ``report`` declare the network they can reach.

Each submits an operation that can read the local AI program at its endpoint
setting, which may name another host, or reach the download hosts, so each
declares ``network``. ``probe`` runs the full check, which loads a model and
refreshes the Google sign-in, so it alone declares the network side effect;
``status`` stays side-effect-free. How each check answers offline is proved by
the setup registry's own suites, since the command no longer reads anything
in its own process.
"""

from __future__ import annotations

import pytest

from ..command_specs import COMMAND_GRAPH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("key", ["config_provision_status", "config_provision_probe", "config_provision_report"])
def test_a_runtime_reading_provision_command_declares_network(key: str) -> None:
    assert "network" in COMMAND_GRAPH.spec(key).policy.expanded_capabilities


def test_only_probe_declares_the_model_load_it_causes() -> None:
    status = COMMAND_GRAPH.spec("config_provision_status")
    probe = COMMAND_GRAPH.spec("config_provision_probe")

    assert status.policy.side_effects == frozenset({"none"})
    assert status.parameters == ()
    assert "network" in probe.policy.side_effects
