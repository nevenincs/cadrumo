"""Every command carries a coherent declared classification.

Proves the ADR ``mcp-protocol-hardening`` H3 parity gate at the application
layer: :func:`classify_command` is coherent for every manifest family mutability
across a representative leaf matrix (never both read-only and destructive,
read-only implies idempotent, live-write never read-only), the open-world axis
covers exactly the AEAT-sede surface (``app.live.*`` and ``pull*`` leaves) and no
local verb, and a mutating verb whose leaf is in the declared destructive set is
classified destructive rather than failing open (research finding F3). The
full-real-key coverage - that every exposed MCP command classifies coherently and
carries the right open-world hint - is asserted in the entrypoints annotation
test where the live command surface is in scope.
"""

from __future__ import annotations

import pytest

from .._classification import (
    DESTRUCTIVE_LEAVES,
    HANDOFF_LEAVES,
    IDEMPOTENT_LEAVES,
    LIVE_WRITE_LEAVES,
    classification_is_coherent,
    classify_command,
)
from .._models import OperatorMutability

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REPRESENTATIVE_LEAVES = tuple(
    sorted(DESTRUCTIVE_LEAVES | IDEMPOTENT_LEAVES | HANDOFF_LEAVES | LIVE_WRITE_LEAVES | {"calculate", "add", "update"})
)


def test_classification_is_coherent_across_every_mutability_and_leaf() -> None:
    for mutability in OperatorMutability:
        for leaf in _REPRESENTATIVE_LEAVES:
            classification = classify_command(f"family.sub.{leaf}", mutability=mutability)
            assert classification_is_coherent(classification), (mutability, leaf)


def test_open_world_covers_the_sede_family_and_no_local_verb() -> None:
    for key in (
        "app.live.expedientes.pull",
        "app.live.notifications.list",
        "app.live.iva_wallet.pull_history",
        "modelo.reconcile.pull",
    ):
        assert classify_command(key, mutability=OperatorMutability.READ_ONLY).open_world, key
    for key in ("ledger.add", "modelo.work.calculate", "overview.status", "contract"):
        assert not classify_command(key, mutability=OperatorMutability.LOCAL_STATE_MUTATING).open_world, key


def test_a_destructive_leaf_under_a_mutating_family_is_classified_destructive() -> None:
    # The fail-open closure: a verb whose leaf is in the declared destructive set
    # is destructive when its family mutates state, never silently safe.
    for leaf in DESTRUCTIVE_LEAVES:
        classification = classify_command(f"ledger.{leaf}", mutability=OperatorMutability.LOCAL_STATE_MUTATING)
        assert classification.destructive, leaf
        assert not classification.read_only


def test_a_read_only_family_never_yields_a_destructive_verb() -> None:
    for leaf in DESTRUCTIVE_LEAVES:
        classification = classify_command(f"overview.{leaf}", mutability=OperatorMutability.READ_ONLY)
        assert classification.read_only
        assert not classification.destructive
        assert classification.idempotent


def test_handoff_and_live_write_axes_track_their_declared_leaves() -> None:
    assert classify_command("modelo.export", mutability=OperatorMutability.LOCAL_STATE_MUTATING).handoff
    assert classify_command("modelo.work.file", mutability=OperatorMutability.LOCAL_STATE_MUTATING).handoff
    assert not classify_command("ledger.add", mutability=OperatorMutability.LOCAL_STATE_MUTATING).handoff
    for leaf in LIVE_WRITE_LEAVES:
        assert classify_command(f"live.{leaf}", mutability=OperatorMutability.LOCAL_STATE_MUTATING).live_write
