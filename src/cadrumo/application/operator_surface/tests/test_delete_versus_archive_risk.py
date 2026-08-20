"""A repair verb that DELETES is destructive; one that ARCHIVES is not.

The two sit side by side in the repair family and read alike from their names,
which is exactly why the distinction needs pinning rather than describing.

`config.repair.quarantine` copies every undecryptable secure-object row --
ciphertext intact -- into the `secure_objects_quarantine` archive table before
removing it from the active one. Nothing is discarded, and an operator who
later recovers the key can re-import. Non-destructive is the correct reading.

`config.repair.reset_progress` deletes the saved workflow-state envelope. A
fingerprint survives for audit; the state does not, and there is no re-import
path. It was declared non-destructive, which contradicted the same table's own
precedent for `app.maintenance.reconcile`: an unrecoverable local delete is
declared destructive regardless of the recovery intent behind it.

WHY THE `--yes` FLAG IS NOT THE ANSWER. Both verbs already demand `--yes` for
their live path, and that gates a human at a terminal. This table gates
something else: the MCP console reads it to decide whether an autonomous caller
is asked at all, and a required flag is something such a caller supplies
itself. A command whose only protection is a flag has no protection from the
operator this CLI was built for.

Asserted as a PAIR on purpose. Pinning only the destructive half would be
satisfied by declaring every repair verb destructive, which would bury the real
one in noise and train operators to approve without reading.
"""

from __future__ import annotations

import pytest

from .._risk_table import COMMAND_RISK

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DELETES = "config.repair.reset_progress"
_ARCHIVES = "config.repair.quarantine"


def test_the_verb_that_deletes_saved_state_is_destructive() -> None:
    """DISCRIMINATING: the row that was wrong, and why it mattered."""
    declaration = COMMAND_RISK.get(_DELETES)

    assert declaration is not None, f"{_DELETES} carries no risk row at all"
    assert declaration.destructive is True, (
        f"{_DELETES} deletes the saved workflow state with no re-import path. An unrecoverable "
        "local delete is destructive regardless of the recovery intent behind it, which is the "
        "same reading app.maintenance.reconcile carries."
    )


def test_the_verb_that_archives_recoverable_rows_is_not_destructive() -> None:
    """ANTI-TAUTOLOGY: the distinction collapses if everything is destructive.

    Quarantine preserves the operator's ciphertext in an archive table it can
    be restored from. Declaring it destructive too would satisfy any
    "repair verbs are dangerous" rule while erasing the difference this pair
    exists to hold.
    """
    declaration = COMMAND_RISK.get(_ARCHIVES)

    assert declaration is not None, f"{_ARCHIVES} carries no risk row at all"
    assert declaration.destructive is False, (
        f"{_ARCHIVES} copies undecryptable rows into an archive table with their ciphertext "
        "intact and nothing discarded; declaring it destructive erases the delete/archive "
        "distinction that makes the flag on its neighbour meaningful."
    )


def test_both_verbs_are_still_exposed_under_these_keys() -> None:
    """Anchor: a rename must red this pair rather than silently empty it.

    Both assertions above read the table by KEY. If either verb is renamed and
    the keys are not, `COMMAND_RISK.get` returns None and the assertions would
    be checking a command that no longer exists -- the exact failure a sibling
    gate in this tree suffered when all four of its pinned symbols were
    removed.
    """
    missing = sorted(key for key in (_DELETES, _ARCHIVES) if key not in COMMAND_RISK)

    assert not missing, f"these command keys are no longer in the risk table: {missing}"
