"""No mutating command escapes the declared risk table (the H3 no-silent-default gate).

The safety guarantee of the declared risk model (ADR ``mcp-protocol-hardening``
H3): every command whose family mutates local state carries EXACTLY ONE declared
risk row, so a new mutating verb cannot slip in unclassified and auto-approve -
the failure mode the leaf-name frozensets had. This gate fails the build the
moment a mutating-family command has no row, and it fails if a row references a
command key that no longer exists (a stale declaration). Driven over the real
exposed command surface - no mocks.
"""

from __future__ import annotations

import pytest

from ....application.operator_surface import (
    COMMAND_RISK,
    OperatorMutability,
    classify_command,
    command_classification,
    declared_risk,
)
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _exposed_keys() -> set[str]:
    return {descriptor.command_key for descriptor in build_tool_descriptors()}


def test_every_mutating_family_command_carries_a_declared_row() -> None:
    # A command is "mutating" iff its family is not read-only; such a command MUST
    # carry a declared row, else it silently classifies all-false and auto-approves.
    missing = sorted(
        key for key in _exposed_keys() if not command_classification(key).read_only and declared_risk(key) is None
    )
    assert missing == [], f"mutating commands with no declared risk row (H3 no-silent-default): {missing}"


def test_no_declared_row_references_a_dead_command_key() -> None:
    exposed = _exposed_keys()
    stale = sorted(key for key in COMMAND_RISK if key not in exposed)
    assert stale == [], f"risk rows referencing command keys that no longer exist: {stale}"


def test_a_new_unclassified_mutating_verb_would_be_caught() -> None:
    # Anti-tautology: a synthetic new mutating verb with no row classifies
    # all-false at runtime (not read-only) and has no declared row, so the
    # no-silent-default gate above would list it - the exact hole the frozensets left.
    key = "ledger.brand_new_wipe_verb"
    classification = classify_command(key, mutability=OperatorMutability.LOCAL_STATE_MUTATING)
    assert not classification.read_only
    assert not classification.destructive  # all-false at runtime...
    assert declared_risk(key) is None  # ...but undeclared, so the gate refuses it
