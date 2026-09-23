"""A refused authenticated command still names its profile and its sandbox state.

The success envelope carries the active-profile label and, for a sandbox, the
sandbox-active notice. A refusal from the same profile must carry both too:
without them a failure inside a discardable sandbox renders exactly like the
same failure against the operator's real profile. The refusal here comes from
a real command after a real login, in a child process, so the error is
rendered by the same boundary an operator's terminal sees.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile

from ....core.config import load_settings, override_settings
from ....core.external_constants import SANDBOX_LABEL_PREFIX
from .subprocess_cli import run_cadrumo_subprocess

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SANDBOX_NOTICE = "config.profile.sandbox.active_indicator"


def _register_active_profile(storage_root: Path, label: str) -> None:
    with override_settings(
        cadrumo_local_storage_root=storage_root,
        cadrumo_secret_passphrase=load_settings().cadrumo_dev_test_database_password,
        cadrumo_active_profile=None,
    ):
        profile_id = register_cli_profile(label=label, facts={})
        # Release the parent's engine and session so the child observes a
        # completed create, as an operator's next command would.
        from ....adapters.persistence.storage.sql.engine import dispose_engine
        from ....application.user_profile.lifecycle import ProfileCapsuleLifecycle
        from ....application.user_profile.login_session import logout_active_profile

        logout_active_profile()
        dispose_engine()
        ProfileCapsuleLifecycle().select(profile_id)


def _refused_lookup(storage_root: Path, *, as_json: bool) -> subprocess.CompletedProcess[str]:
    passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    return run_cadrumo_subprocess(
        (
            *(("--format", "json") if as_json else ()),
            "--profile-secrets-stdin",
            "app",
            "ledger",
            "view",
            "no-such-transaction",
        ),
        settings={
            "cadrumo_local_storage_root": storage_root,
            "cadrumo_secret_passphrase": passphrase,
            "cadrumo_output_language": "en",
        },
        env_strip_prefixes=("AEAT_", "PYTEST_"),
        stdin_payload=json.dumps({"profile_passphrase": passphrase}),
        timeout=120.0,
    )


@pytest.mark.parametrize("label", ["refusal-spine", f"{SANDBOX_LABEL_PREFIX}refusal-spine"])
def test_a_refused_command_carries_the_profile_label_and_sandbox_notice(tmp_path: Path, label: str) -> None:
    _register_active_profile(tmp_path, label)

    refused = _refused_lookup(tmp_path, as_json=True)

    assert refused.returncode != 0, refused.stdout + refused.stderr
    envelope = json.loads(refused.stderr)
    assert envelope["status"] == "error"
    assert envelope["active_profile"] == label
    codes = [notice["code"] for notice in envelope["notices"]]
    assert (_SANDBOX_NOTICE in codes) is label.startswith(SANDBOX_LABEL_PREFIX), codes


def test_a_refused_sandbox_command_prints_the_sandbox_banner_in_text_mode(tmp_path: Path) -> None:
    label = f"{SANDBOX_LABEL_PREFIX}refusal-banner"
    _register_active_profile(tmp_path, label)

    refused = _refused_lookup(tmp_path, as_json=False)

    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert label in refused.stderr, refused.stderr
