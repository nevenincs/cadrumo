"""Join every declared operator-action path to the live command surface.

The catalogue declares the command path an operator types to reach each
action, because the target command keys are not uniformly shaped -- some
carry the root segment and some do not, and both forms resolve -- so a
transformation that satisfies one action fabricates a command for another.
Declaring the path moves the risk from a wrong derivation to a stale
declaration, and this is what refuses a stale one.

The proof lives here rather than beside the catalogue because the live
operator surface is only reachable from the entrypoint that mounts it; an
application-level test reaching for it would invert the layer direction.
"""

from __future__ import annotations

import pytest

from ....application.operator_actions import OPERATOR_ACTION_CATALOGUE
from .._operator_surface_reconciliation import current_operator_surface_reconciliation

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _live_paths_by_subject_key() -> dict[str, tuple[str, ...]]:
    """Index the live command surface by the key the catalogue targets."""
    return {
        leaf.live_leaf.subject_leaf_key: leaf.live_leaf.canonical_cli_path
        for leaf in current_operator_surface_reconciliation().leaves
    }


def test_every_declared_action_path_matches_the_live_command_surface() -> None:
    """A renamed verb must red this gate rather than reach an operator."""
    live_paths = _live_paths_by_subject_key()

    divergent: list[str] = []
    for entry in OPERATOR_ACTION_CATALOGUE.entries:
        live_path = live_paths.get(entry.target_command_key)
        if live_path is None:
            divergent.append(f"{entry.action_id}: target {entry.target_command_key} is not a live command")
            continue
        if entry.canonical_cli_path != live_path:
            divergent.append(
                f"{entry.action_id}: declared {' '.join(entry.canonical_cli_path)!r} "
                f"but the live surface reaches it at {' '.join(live_path)!r}"
            )

    assert not divergent, "operator action paths diverge from the live command surface:\n" + "\n".join(divergent)


def test_the_gate_reads_a_populated_catalogue_and_a_populated_surface() -> None:
    """Both sides must be non-empty, or the comparison above passes vacuously."""
    assert OPERATOR_ACTION_CATALOGUE.entries
    assert _live_paths_by_subject_key()


def test_a_resolved_next_action_carries_the_path_an_operator_can_type() -> None:
    """The notice channel's own producer must emit a live, resolvable command."""
    from ....application.operator_actions import next_action

    live_paths = _live_paths_by_subject_key()
    zero_argument_entries = [entry for entry in OPERATOR_ACTION_CATALOGUE.entries if not entry.argument_specifications]
    assert zero_argument_entries, "no zero-argument action remains to resolve"

    for entry in zero_argument_entries:
        resolved = next_action(entry.action_id)
        assert resolved.action.cli_path == live_paths[entry.target_command_key], entry.action_id
