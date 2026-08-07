# INTENTIONAL: unit because "live" here names the assessed live_write flag,
# not a live AEAT contact -- this module unit-tests the risk_declared/
# live_write derivation without touching AEAT.
"""A command's safety assessment is distinguishable from its absence.

`aeat-safety-legal-gates` forbids live AEAT submission outright, so `live_write` is
False for every command in the tree and must stay that way. That correctness is
exactly what made the property untestable: an assertion holding for all 297 verbs
whether or not anyone assessed them is a tautology, and the project bans those.
`not live_write` cannot distinguish the verb someone judged safe from the verb
nobody has looked at, because a missing row is coerced to the same three Falses a
deliberate "mutating but safe" declaration produces.

`risk_declared` separates those two states, which is what makes a per-command
safety claim falsifiable: assert the value is False AND that it was declared, and
the pair fails for an unassessed command where the value alone never would.

Scope note. These are unit tests of the derivation. The surface-wide sweep - every
exposed command is assessed and none declares a live write - belongs beside
`test_risk_table_parity.py` in the MCP entrypoint tests, because the set of exposed
commands is materialised there and an application-layer test cannot enumerate it
without importing outward. The manifest's family/command rows do not compose to
full command keys (41 of 271 match), so they are not a substitute denominator.

What this does NOT change: the absent-row coercion in `classify_command` stays
permissive. Raising instead would turn the MCP identity gate's retired-key refusal
into a crash, which `_mutability_for` records as load-bearing. The coercion is now
VISIBLE rather than removed.
"""

from __future__ import annotations

import pytest

from .. import OperatorMutability, classify_command, command_classification
from .._risk_table import COMMAND_RISK

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: A real declared row in a mutating family, resolved from the table rather than
#: hardcoded so a rename cannot leave this test asserting against a dead key.
_DECLARED_MUTATING_KEY = "config.auth.certificate.remove"


def test_the_declared_fixture_key_is_real() -> None:
    """Guard the fixture.

    A key that stopped existing would make the positive control below assert
    against a defaulted classification and pass for the wrong reason.
    """
    assert _DECLARED_MUTATING_KEY in COMMAND_RISK


class TestAnAssessmentIsDistinguishableFromItsAbsence:
    """The distinction the safety claim rests on."""

    def test_an_unassessed_mutating_command_reports_undeclared(self) -> None:
        """The planted verb: mutating family, no declared row.

        Its ``live_write`` is False exactly like every assessed command's, which is
        precisely why the value alone proves nothing about it.
        """
        classification = classify_command(
            "ledger.unassessed_new_verb",
            mutability=OperatorMutability.LOCAL_STATE_MUTATING,
        )

        assert classification.risk_declared is False
        assert classification.live_write is False, "the default is safe-looking, which is the trap"

    def test_a_declared_mutating_command_reports_declared(self) -> None:
        """The positive control: a real declared row is assessed."""
        classification = command_classification(_DECLARED_MUTATING_KEY)

        assert classification.risk_declared is True
        assert classification.live_write is False

    def test_a_read_only_family_command_reports_declared(self) -> None:
        """Absence of a row is not automatically a gap.

        A read-only family carries no rows by design - the manifest declaring the
        whole family a read IS its assessment. Without this, the undeclared state
        would also flag the 26 row-less read-only commands, reporting false gaps
        and training a reader to ignore the signal.
        """
        classification = classify_command("app.registry.describe", mutability=OperatorMutability.READ_ONLY)

        assert classification.risk_declared is True
        assert classification.read_only is True

    def test_the_flag_is_not_merely_mirroring_read_only(self) -> None:
        """Anti-tautology: ``risk_declared`` is not a synonym for either neighbour.

        It is True for both a read-only command and a declared mutating one, and
        False only for the unassessed case - so it cannot be replaced by
        ``read_only`` or by ``not destructive``, and a reader cannot conclude the
        new field is redundant.
        """
        read_only = classify_command("app.registry.describe", mutability=OperatorMutability.READ_ONLY)
        declared_mutating = command_classification(_DECLARED_MUTATING_KEY)
        unassessed = classify_command("ledger.unassessed_new_verb", mutability=OperatorMutability.LOCAL_STATE_MUTATING)

        assert read_only.risk_declared == declared_mutating.risk_declared is True
        assert read_only.read_only != declared_mutating.read_only
        assert unassessed.read_only == declared_mutating.read_only
        assert unassessed.risk_declared != declared_mutating.risk_declared
