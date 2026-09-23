"""A profile is unlocked only in the process that created it.

Registration publishes the new profile's session in the creating process, so
the operator is not asked for the passphrase they just chose, and it mints no
acceleration receipt. The security property that leaves behind is the one
proven here: any other process, holding no credential, is refused before it
reads a record. The reader is a fresh interpreter with every product setting
stripped from its environment, so nothing but the storage root reaches it.

The keychain is pinned to the two ways a host can fail to hold a session key,
so the refusal is the same on every host: with no receipt to resume and no
credential supplied, the reader is refused for want of authentication.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile

from ....core.config import load_settings, override_settings
from ....tests.call_time_refusing_keyring import CALL_TIME_REFUSING_KEYRING
from .subprocess_cli import run_cadrumo_subprocess

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LABEL = "locked-to-other-processes"


@pytest.mark.parametrize(
    "keychain_backend",
    ["keyring.backends.fail.Keyring", CALL_TIME_REFUSING_KEYRING],
    ids=["no-usable-backend", "call-time-logon-session-refusal"],
)
def test_another_process_without_a_credential_is_refused_by_a_just_created_profile(
    tmp_path: Path, keychain_backend: str
) -> None:
    with override_settings(
        cadrumo_local_storage_root=tmp_path,
        cadrumo_secret_passphrase=load_settings().cadrumo_dev_test_database_password,
        cadrumo_active_profile=None,
    ):
        register_cli_profile(label=_LABEL, facts={})

    listed = run_cadrumo_subprocess(
        ("--format", "json", "app", "ledger", "list"),
        settings={"cadrumo_local_storage_root": tmp_path, "cadrumo_output_language": "en"},
        env_strip_prefixes=("AEAT_", "PYTEST_", "CADRUMO_"),
        extra_env={"PYTHON_KEYRING_BACKEND": keychain_backend},
        stdin_payload="",
        timeout=120.0,
    )

    assert listed.returncode == 3, listed.stdout + listed.stderr
    assert listed.stdout == ""
    envelope = json.loads(listed.stderr)
    assert envelope["status"] == "error"
    assert envelope["error"]["code"] == "AUTH_STORAGE_KEYRING_UNAVAILABLE"
    assert envelope["active_profile"] == _LABEL
