"""A profile written in one process is found by NAME in another.

The regression the named-profile resolution split owes, and which could not be
written when that split was fixed: the scenario needs cross-process session
resumption, which needs the operating-system credential store, and that store
was saturated on the executing host -- every credential write failed, so the
defect could be neither reproduced nor its fix verified. The record of that
Step says so explicitly and declines to author the test blind, on the grounds
that a test which can never be watched to fail asserts only that its author
believed the fix correct. This module is that owed test, written now that the
store has been cleared.

The defect was a RESOLUTION split, not durability and not the key digest,
which is why two earlier investigations framed around those found nothing.
The CLI root callback deliberately returns early for a verb naming an explicit
profile target, on the stated ground that such a verb resolves and unlocks its
OWN target. Resolving happened; unlocking never did. So the active-profile
path was resumed by the root callback and reported the record present, while
the named-profile path skipped that resume, found no session serving its
bucket, and reported the SAME record on the SAME disk as missing.

Both halves are asserted here, and the pairing is the point. Asserting only
that a named lookup succeeds would pass against a build where the root
callback happened to resume the target anyway; asserting only that the two
agree would pass if both were broken. The claim is that a fresh process,
given a name and no active-profile pointer, reaches the record -- and reaches
the same one the active path does.

A fresh interpreter is not a stylistic choice: the fix binds a session
resumed from persisted material, and an in-process runner would find a session
already bound by an earlier test in the same session, so it cannot observe the
regression at all.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from .test_cold_start_wizard_registration import _register_profile_for_cold_run, _run_cli_cold

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LABEL = "cross-process-subject"
_FACTS = {
    "identity.tax_id": "45678912S",
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Cross",
    "identity.surnames": "Process",
    "activities.description": "Servicios",
}


def _envelope_result(stdout: str) -> dict[str, object]:
    """Return the success envelope's result payload from a cold-run stdout."""
    document = json.loads(stdout)
    result = document["result"]
    assert isinstance(result, dict)
    return result


@pytest.mark.os_keychain  # cross-process resumption needs a minted acceleration receipt
def test_a_named_profile_resolves_in_a_process_that_did_not_write_it(tmp_path: Path) -> None:
    """``config profile view NAME`` finds a record another process persisted.

    The failing observation this closes: the record is present on disk with
    its keys, and the named-profile path reported ``missing_profile_record``
    because nothing had bound a custody session serving that bucket.
    """
    _register_profile_for_cold_run(tmp_path, _LABEL, **_FACTS)

    shown = _run_cli_cold(tmp_path, ["--format", "json", "config", "profile", "view", _LABEL])

    assert shown.returncode == 0, f"named-profile show failed in a cold process: {shown.stdout}\n{shown.stderr}"
    result = _envelope_result(shown.stdout)

    # The failure branch is asserted by name rather than inferred from a zero
    # exit: the missing-record branch also exits zero, because "your record is
    # not there" is a successful report of a bad state.
    assert result.get("profile_record_present") is not False, (
        f"a record written by another process was reported absent by name: {result}"
    )

    # These two are the assertions that actually bite, and that is measured
    # rather than assumed. Disabling the session binding at runtime -- from
    # outside the repository, so nothing tracked was mutated -- reproduces the
    # pre-fix behaviour, and the resulting payload carries
    # ``profile_record_present = False``, ``valid = None`` and NO facts, while
    # still carrying ``display_name``. So a check on the label would pass
    # against the broken build, and a check on ``status`` would too: it stays
    # ``None`` on both sides. Facts and ``valid`` are what separate them.
    #
    # The distinction is the defect itself. Resolution located the capsule in
    # both cases; only the fixed build BOUND a session able to open it, and
    # facts exist only when something did.
    facts = result.get("facts")
    assert isinstance(facts, list)
    assert facts, f"the record resolved but yielded no facts, so nothing opened it: {result}"
    assert result.get("valid") is True
    assert result.get("display_name") == _LABEL


@pytest.mark.os_keychain  # cross-process resumption needs a minted acceleration receipt
def test_the_named_and_active_paths_agree_about_the_same_record(tmp_path: Path) -> None:
    """The two resolution paths report the same record, not two answers.

    The defect was never that one path was wrong in isolation -- each was
    self-consistent. It was that the two disagreed about one record on one
    disk, so which answer an operator got depended on whether they named the
    profile or relied on the active pointer.
    """
    profile_id = _register_profile_for_cold_run(tmp_path, _LABEL, **_FACTS)

    by_name = _run_cli_cold(tmp_path, ["--format", "json", "config", "profile", "view", _LABEL])
    by_active = _run_cli_cold(tmp_path, ["--format", "json", "config", "profile", "view"])

    assert by_name.returncode == 0, f"{by_name.stdout}\n{by_name.stderr}"
    assert by_active.returncode == 0, f"{by_active.stdout}\n{by_active.stderr}"

    named_result = _envelope_result(by_name.stdout)
    active_result = _envelope_result(by_active.stdout)

    # Compared on the decrypted CONTENT, not on a presence flag: the defect
    # produced two different answers about one record, so agreement is the
    # claim. Facts are asserted non-empty first, because two empty lists would
    # otherwise satisfy the equality while proving neither path opened
    # anything -- which is precisely the broken state.
    named_facts = named_result.get("facts")
    active_facts = active_result.get("facts")
    assert isinstance(named_facts, list)
    assert named_facts, f"the named path opened nothing: {named_result}"
    assert named_facts == active_facts
    assert named_result.get("display_name") == active_result.get("display_name") == _LABEL
    assert profile_id
