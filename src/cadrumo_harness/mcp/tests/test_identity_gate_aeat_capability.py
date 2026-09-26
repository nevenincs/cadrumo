"""The identity gate follows the ``aeat`` capability, and only local-runtime probes left it.

The gate once treated every ``network`` command as a taxpayer read. Keying it on
``aeat`` must not release any command that reads AEAT or anything tied to a
taxpayer: the only commands allowed to change gating are the read-only probes of
this host's own model runtime, which leave the process but read nothing of a
taxpayer's.
"""

from __future__ import annotations

from typing import Final

import pytest

from cadrumo.application.operator_surface.command_ports import CommandExecutionPolicy

from ..command_surface import command_surface
from ..identity_gate import (
    ACTIVE_IDENTITY_CHANGING_COMMANDS,
    IDENTITY_READ_COMMANDS,
    SessionIdentityState,
    identity_gate_refusal,
)
from ..tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: Read-only commands that reach only this host's model runtime.
_LOCAL_RUNTIME_PROBES: Final = frozenset({"config.provision.report", "config.provision.status"})


def _gated_by_the_retired_network_rule(command_key: str, policy: CommandExecutionPolicy) -> bool:
    """The gate's former predicate: any ``network`` command counted as a taxpayer read."""
    if command_key in ACTIVE_IDENTITY_CHANGING_COMMANDS or command_key in IDENTITY_READ_COMMANDS:
        return False
    classification = policy.classification
    read_only = classification.side_effects == frozenset({"none"})
    return not (read_only and "network" not in classification.expanded_capabilities)


def _gating() -> dict[str, tuple[bool, bool, CommandExecutionPolicy]]:
    surface = command_surface()
    gating: dict[str, tuple[bool, bool, CommandExecutionPolicy]] = {}
    for descriptor in build_tool_descriptors():
        policy = surface.command_execution_policy_for_cli_path(descriptor.verb_schema.cli_path)
        refused = identity_gate_refusal(
            descriptor.command_key,
            execution_policy=descriptor.execution_policy,
            state=SessionIdentityState(),
        )
        gating[descriptor.command_key] = (
            _gated_by_the_retired_network_rule(descriptor.command_key, policy),
            refused is not None,
            policy,
        )
    return gating


def test_only_the_local_runtime_probes_changed_gating() -> None:
    gating = _gating()
    changed = {key for key, (before, after, _) in gating.items() if before != after}

    assert changed == _LOCAL_RUNTIME_PROBES
    for key in changed:
        before, after, policy = gating[key]
        assert (before, after) == (True, False), key
        assert "network" in policy.classification.expanded_capabilities, key
        assert "aeat" not in policy.classification.expanded_capabilities, key


def test_every_aeat_command_is_gated_for_an_unidentified_session() -> None:
    gating = _gating()
    aeat = {key for key, (_, _, policy) in gating.items() if "aeat" in policy.classification.expanded_capabilities}

    assert len(aeat) > 10, f"expected the live AEAT surface, found {len(aeat)}"
    assert sorted(key for key in aeat if not gating[key][1]) == []
