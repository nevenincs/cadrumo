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
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.core.config import load_settings
from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo.tests.installed_process_ports import InstalledProcessWorld
from cadrumo.tests.os_keychain_hook import require_os_credential_store

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LABEL = "cross-process-subject"
_FACTS = {
    "identity.tax_id": "45678912S",
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Cross",
    "identity.surnames": "Process",
    "activities.description": "Servicios",
}


_DOCUMENT_ADAPTER: TypeAdapter[dict[str, object]] = TypeAdapter(dict[str, object])


def _run_cli_cold(
    storage_root: Path,
    argv: list[str],
    *,
    stdin_payload: str | None = None,
    installed_process_world: InstalledProcessWorld,
) -> subprocess.CompletedProcess[str]:
    """Run the real runtime frontend in a new interpreter without ambient custody."""
    environment = installed_process_world.environment(
        storage_root=storage_root, authority_root=bundled_authority_descriptor_path().parent
    )
    return subprocess.run(  # noqa: S603 -- Exact interpreter and test-authored CLI arguments; no shell.
        [
            sys.executable,
            "-c",
            "from cadrumo_runtime.host.frontend.cli.bootstrap import main; main()",
            *argv,
        ],
        input=stdin_payload,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )


@pytest.fixture
def cold_profile(tmp_path: Path, *, installed_process_world: InstalledProcessWorld) -> Generator[tuple[Path, str]]:
    """Keep a real runtime and native credential-store receipt across CLI processes."""
    require_os_credential_store()
    scripts = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")
    executable = scripts / ("aeat.exe" if sys.platform == "win32" else "aeat")
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        environment = installed_process_world.environment(
            storage_root=root, authority_root=bundled_authority_descriptor_path().parent
        )
        with installed_process_world.runtime(executable, environment, tmp_path / "caller-owned-runtime.log"):
            profile_id = register_cli_profile(label=_LABEL, facts=_FACTS, log_in=False)
            close_active_bucket_session()
            login = _run_cli_cold(
                root,
                ["--format", "json", "config", "login", _LABEL, "--secrets-stdin"],
                stdin_payload=json.dumps(
                    {"passphrase": load_settings().cadrumo_dev_test_database_password.get_secret_value()}
                ),
                installed_process_world=installed_process_world,
            )
            try:
                assert login.returncode == 0, login.stderr
                assert _envelope_result(login.stdout)["session_persisted"] is True
                yield root, profile_id
            finally:
                logout = _run_cli_cold(
                    root, ["--format", "json", "config", "logout"], installed_process_world=installed_process_world
                )
                assert logout.returncode == 0, logout.stderr


def _envelope_result(stdout: str) -> dict[str, object]:
    """Return the success envelope's result payload from a cold-run stdout."""
    document = _DOCUMENT_ADAPTER.validate_python(json.loads(stdout))
    return _DOCUMENT_ADAPTER.validate_python(document["result"])


@pytest.mark.os_keychain  # cross-process resumption needs a minted acceleration receipt
def test_a_named_profile_resolves_in_a_process_that_did_not_write_it(
    cold_profile: tuple[Path, str], *, installed_process_world: InstalledProcessWorld
) -> None:
    """``config profile view NAME`` finds a record another process persisted.

    The failing observation this closes: the record is present on disk with
    its keys, and the named-profile path reported ``missing_profile_record``
    because nothing had bound a custody session serving that bucket.
    """
    storage_root, _profile_id = cold_profile

    shown = _run_cli_cold(
        storage_root,
        ["--format", "json", "config", "profile", "view", _LABEL],
        installed_process_world=installed_process_world,
    )

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
def test_the_named_and_active_paths_agree_about_the_same_record(
    cold_profile: tuple[Path, str], *, installed_process_world: InstalledProcessWorld
) -> None:
    """The two resolution paths report the same record, not two answers.

    The defect was never that one path was wrong in isolation -- each was
    self-consistent. It was that the two disagreed about one record on one
    disk, so which answer an operator got depended on whether they named the
    profile or relied on the active pointer.
    """
    storage_root, profile_id = cold_profile

    by_name = _run_cli_cold(
        storage_root,
        ["--format", "json", "config", "profile", "view", _LABEL],
        installed_process_world=installed_process_world,
    )
    by_active = _run_cli_cold(
        storage_root, ["--format", "json", "config", "profile", "view"], installed_process_world=installed_process_world
    )

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
