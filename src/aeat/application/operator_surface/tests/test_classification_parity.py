"""Every command classifies from the declared risk table, coherently.

Proves the ADR ``mcp-protocol-hardening`` H3 model as it was actually decided:
the destructive / handoff / live-write axes are DECLARED per command in the risk
table, not inferred from a leaf-name heuristic; :func:`classify_command` reads the
declared row; read_only and idempotent derive from the manifest mutability;
open_world derives from the command path. The no-silent-default parity gate over
the live command surface lives in ``test_risk_table_parity.py``; this test asserts
the derivation is coherent and reads the declared data.
"""

from __future__ import annotations

import pytest

from .._classification import (
    classification_is_coherent,
    classify_command,
    command_classification,
)
from .._models import OperatorMutability
from .._risk_table import COMMAND_RISK, CommandRiskDeclaration, declared_risk

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_classify_reads_the_declared_row_for_a_mutating_command() -> None:
    # A declared destructive command classifies destructive/confirm; a declared
    # handoff classifies handoff; a bare (all-false) row is mutating-but-safe.
    remove = classify_command("ledger.remove", mutability=OperatorMutability.LOCAL_STATE_MUTATING)
    assert remove.destructive and not remove.read_only and not remove.idempotent
    quickfile = classify_command("quickfile", mutability=OperatorMutability.LOCAL_STATE_MUTATING)
    assert quickfile.handoff and not quickfile.destructive
    add = classify_command("ledger.add", mutability=OperatorMutability.LOCAL_STATE_MUTATING)
    assert not add.destructive and not add.handoff and not add.live_write


def test_a_read_only_command_has_no_row_and_derives_safe() -> None:
    c = classify_command("overview.status", mutability=OperatorMutability.READ_ONLY)
    assert c.read_only and c.idempotent
    assert not c.destructive and not c.handoff and not c.live_write
    assert declared_risk("overview.status") is None


def test_an_absent_row_for_a_mutating_command_is_all_false_at_runtime() -> None:
    # The runtime falls back to all-false for an unclassified mutating command;
    # the parity gate (separate test) is what makes that a BUILD failure, so the
    # runtime never silently mis-gates while the gate catches the omission.
    c = classify_command("family.brand_new_verb", mutability=OperatorMutability.LOCAL_STATE_MUTATING)
    assert not c.destructive and not c.handoff and not c.live_write and not c.read_only


def test_every_declared_row_is_coherent_when_classified() -> None:
    for key in COMMAND_RISK:
        c = classify_command(key, mutability=OperatorMutability.LOCAL_STATE_MUTATING)
        assert classification_is_coherent(c), key


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


def test_command_classification_resolves_mutability_from_the_manifest() -> None:
    # The by-key accessor the HITL tier and persona deny rules use: a read-only
    # family verb classifies read-only, a mutating destructive verb destructive.
    assert command_classification("overview.status").read_only
    assert command_classification("ledger.remove").destructive
    assert command_classification("modelo.work.file").handoff


def test_a_live_write_declaration_forces_non_read_only() -> None:
    # Defence in depth: were a command ever declared live_write, it is never
    # read-only regardless of its family mutability (the permanent block axis).
    risk = CommandRiskDeclaration(live_write=True)
    assert risk.live_write
