"""A profile is unlocked only in the process that created it.

Registration publishes the new profile's session in the creating process, so
the operator is not asked for the passphrase they just chose, and it mints no
acceleration receipt. The security property that leaves behind is the one
proven here: any other process, holding no credential, is refused before it
reads a record. The reader is a fresh interpreter with every product setting
stripped from its environment, so nothing but the storage root reaches it.

The decisive case gives that reader a working, empty keychain, so the only
thing it lacks is authentication and the refusal must say so. Two keychain-
less hosts are kept as well: there the reader is refused for want of a
keychain, which alone would not prove the lock on a host that has one.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile

from ....core.config import load_settings, override_settings
from ....core.i18n.render import tr
from ....tests.call_time_refusing_keyring import CALL_TIME_REFUSING_KEYRING
from ....tests.in_memory_keyring import IN_MEMORY_KEYRING
from .subprocess_cli import run_cadrumo_subprocess

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LABEL = "locked-to-other-processes"


def _create_profile(storage_root: Path) -> None:
    with override_settings(
        cadrumo_local_storage_root=storage_root,
        cadrumo_secret_passphrase=load_settings().cadrumo_dev_test_database_password,
        cadrumo_active_profile=None,
    ):
        register_cli_profile(label=_LABEL, facts={})


def _list_in_a_fresh_process(
    storage_root: Path, *, keychain_backend: str, credential: str | None
) -> subprocess.CompletedProcess[str]:
    root_options = ("--profile-secrets-stdin",) if credential is not None else ()
    return run_cadrumo_subprocess(
        ("--format", "json", *root_options, "app", "ledger", "list"),
        settings={"cadrumo_local_storage_root": storage_root, "cadrumo_output_language": "en"},
        env_strip_prefixes=("AEAT_", "PYTEST_", "CADRUMO_"),
        extra_env={"PYTHON_KEYRING_BACKEND": keychain_backend},
        stdin_payload="" if credential is None else json.dumps({"profile_passphrase": credential}),
        timeout=180.0,
    )


def _english(key: str) -> str:
    with override_settings(cadrumo_output_language="en"):
        return tr(key)


def _refused_as_unauthenticated(listed: subprocess.CompletedProcess[str]) -> bool:
    """Whether a fresh process was refused for holding no credential, and read nothing."""
    if listed.returncode != 2 or listed.stdout != "":
        return False
    envelope: object = json.loads(listed.stderr)
    if not isinstance(envelope, dict) or envelope.get("status") != "error":
        return False
    error: object = envelope.get("error")
    if not isinstance(error, dict) or error.get("code") != "REFUSED_CLI_BOUNDARY":
        return False
    context: object = error.get("context")
    return isinstance(context, dict) and bool(context.get("reason") == "absent")


def test_another_process_with_a_working_keychain_and_no_credential_is_refused_as_unauthenticated(
    tmp_path: Path,
) -> None:
    _create_profile(tmp_path)

    listed = _list_in_a_fresh_process(tmp_path, keychain_backend=IN_MEMORY_KEYRING, credential=None)

    assert _refused_as_unauthenticated(listed), listed.stdout + listed.stderr
    envelope = json.loads(listed.stderr)
    assert envelope["active_profile"] == _LABEL
    assert envelope["error"]["action"]["action"]["action_id"] == "operator.profile.login"


def test_the_unauthenticated_check_fails_when_a_fresh_process_does_read_the_profile(tmp_path: Path) -> None:
    """Detector teeth: a fresh process that gets in must fail the property check.

    Supplying the credential is the isolated stand-in for the regression the
    check exists to catch, a fresh process reading a just-created profile; it
    produces exactly that observable without touching the product.
    """
    _create_profile(tmp_path)
    credential = load_settings().cadrumo_dev_test_database_password.get_secret_value()

    listed = _list_in_a_fresh_process(tmp_path, keychain_backend=IN_MEMORY_KEYRING, credential=credential)

    assert listed.returncode == 0, listed.stdout + listed.stderr
    assert not _refused_as_unauthenticated(listed)
    # The keychain here works; the process-scoped notice must say why the
    # session is not kept without claiming the keychain is missing.
    notices = json.loads(listed.stdout)["notices"]
    assert [(notice["code"], notice["message"]) for notice in notices] == [
        ("config.login.session_not_persisted", _english("cli.config.login.notices.session_invocation_scoped")),
    ]


@pytest.mark.parametrize(
    "keychain_backend",
    ["keyring.backends.fail.Keyring", CALL_TIME_REFUSING_KEYRING],
    ids=["no-usable-backend", "call-time-logon-session-refusal"],
)
def test_another_process_on_a_keychain_less_host_is_refused_before_it_reads(
    tmp_path: Path, keychain_backend: str
) -> None:
    _create_profile(tmp_path)

    listed = _list_in_a_fresh_process(tmp_path, keychain_backend=keychain_backend, credential=None)

    assert listed.returncode == 3, listed.stdout + listed.stderr
    assert listed.stdout == ""
    envelope = json.loads(listed.stderr)
    assert envelope["status"] == "error"
    assert envelope["error"]["code"] == "AUTH_STORAGE_KEYRING_UNAVAILABLE"
    assert envelope["active_profile"] == _LABEL
