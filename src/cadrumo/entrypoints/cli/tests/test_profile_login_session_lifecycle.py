"""Opt-in OS-keychain lifecycle through installed runtime and real CLI processes.

Each invocation owns its runtime connection. Logout later clears only the
captured CLI default; the separately held receipt remains available to a
fresh, exact-profile login. These cases require an interactive Windows
credential store and clean up their isolated profile UUIDs on every exit.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)

from ....adapters.persistence.storage.tests.secure_sql import reap_profile_session_keys
from ....core.redaction.rules import CLI_PROFILE_ID_PLACEHOLDER
from ....tests.os_keychain_hook import require_os_credential_store
from ..config.tests.isolated_storage_fixture import native_profile_view_server
from .subprocess_cli import run_cadrumo_subprocess

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires installed Windows runtime"),
]

_CREDENTIAL_INPUT = "lifecycle-session-passphrase"

#: Storage-root directory name every test below provisions under ``tmp_path``.
_STORAGE_DIRNAME = "storage"


@pytest.fixture(autouse=True)
def _reap_session_keys(tmp_path: Path) -> Iterator[None]:
    """Return the OS keychain to its pre-test state after every test.

    These tests deliberately leave a logged-in profile behind (a login
    whose persistence is the assertion, a repeat login proving
    idempotence), and each run provisions a brand-new bucket uuid. Without
    this teardown every run deposits another permanent
    ``cadrumo:profile-session`` entry in the developer's real credential
    store. The reap runs in a fixture teardown rather than at the end of a
    test body so a FAILING test cleans up too.
    """
    try:
        yield
    finally:
        reap_profile_session_keys(tmp_path / _STORAGE_DIRNAME)


def _run(
    storage_root: Path,
    args: tuple[str, ...],
    *,
    with_passphrase: bool = False,
    as_json: bool = False,
    stdin_payload: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one real CLI invocation in a fresh interpreter.

    ``--format`` is a ROOT-level flag, so it is prepended ahead of the
    subcommand path rather than appended to it. ``with_passphrase`` decides
    whether separately governed substrate configuration is present: the login
    gate only engages when it is NOT, so the session assertions in this
    module run with it withheld by default.
    """
    root_flags = ("--format", "json") if as_json else ()
    settings: dict[str, object] = {
        "cadrumo_local_storage_root": storage_root,
        "cadrumo_output_language": "en",
    }
    if with_passphrase:
        settings["cadrumo_secret_passphrase"] = _CREDENTIAL_INPUT
    return run_cadrumo_subprocess(
        [*root_flags, *args],
        settings=settings,
        env_strip_prefixes=("AEAT_", "CADRUMO_", "PYTEST_"),
        stdin_payload=stdin_payload,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def _envelope(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """Parse the JSON envelope from a ``--format json`` invocation."""
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


def _create_profile(storage_root: Path) -> str:
    """Register one capsule through the current credential-only creation door."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
    from ....application.user_profile.registration import register_profile_with_credentials
    from ....core.config import override_settings

    with override_settings(cadrumo_local_storage_root=storage_root):
        outcome = register_profile_with_credentials(
            label="session-operator",
            passphrase=_CREDENTIAL_INPUT,
            profile_create_context=_profile_create_context_for_test,
            profile_decode_context=_profile_decode_context_for_test,
        )
        close_active_bucket_session()
    return outcome.bucket_id


def _session_record(storage_root: Path, bucket_id: str) -> Path:
    """Return the on-disk persisted-session path for ``bucket_id``."""
    from ....adapters.persistence.storage.custody.acceleration_receipt import profile_session_path

    return profile_session_path(storage_root=storage_root, profile_id=UUID(bucket_id))


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[tuple[Path, str]]:
    """Register before opening the exact native runtime for each CLI process."""
    require_os_credential_store()
    storage_root = tmp_path / _STORAGE_DIRNAME
    storage_root.mkdir()
    bucket_id = _create_profile(storage_root)
    with native_profile_view_server(storage_root):
        yield storage_root, bucket_id


@pytest.mark.os_keychain
class TestSessionLifecycle:
    """Actual OS-held receipt continuity across independently admitted commands."""

    def test_login_resume_and_logout_lifecycle(self, runtime_profile: tuple[Path, str]) -> None:
        """One full pass: gate, login, follow-on process, logout idempotence."""
        storage_root, bucket_id = runtime_profile

        # Logout clears the prior CLI default, so the login names its target.
        first_logout = _run(storage_root, ("config", "logout"), as_json=True)
        assert first_logout.returncode == 0, _output(first_logout)

        # 1. login over the bounded strict-JSON secrets channel; the
        #    passphrase is never an argv value.
        logged_in = _run(
            storage_root,
            ("config", "login", bucket_id, "--secrets-stdin"),
            as_json=True,
            stdin_payload=json.dumps({"passphrase": _CREDENTIAL_INPUT}),
        )
        assert logged_in.returncode == 0, _output(logged_in)
        envelope = _envelope(logged_in)
        assert envelope["command"] == "config.login"
        result = envelope["result"]
        assert result["already_authenticated"] is False
        assert result["closed_previous_profile"] is None
        # The new payload field rides the envelope redaction funnel like
        # every other profile identifier: the raw UUID must never reach
        # stdout, so the emitted value is the placeholder, not the id.
        assert result["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
        assert bucket_id not in logged_in.stdout

        # 2. THE COUPLING: the envelope's persistence claim must match the
        #    filesystem. A login that reports a saved session without
        #    writing one -- or writes one while reporting otherwise --
        #    fails here on any host.
        persisted = result["session_persisted"]
        assert persisted is True
        record = _session_record(storage_root, bucket_id)
        assert record.is_file()

        # 3. A later process admits through the existing receipt.
        follow_on = _run(storage_root, ("config", "profile", "view"))
        assert follow_on.returncode == 0, _output(follow_on)
        assert "aeat config login" not in _output(follow_on), _output(follow_on)

        # 4. Logout clears selection without revoking the receipt or another
        #    process's independently owned authority.
        original_receipt = record.read_bytes()
        logged_out = _run(storage_root, ("config", "logout"), as_json=True)
        assert logged_out.returncode == 0, _output(logged_out)
        logout_document = _envelope(logged_out)
        assert logout_document["result"]["scope"] == "cli_context"
        assert logout_document["result"]["human_receipt_revoked"] is False
        assert logout_document["result"]["automation_revoked"] is False
        assert "config.logout.remaining_access" in {notice["code"] for notice in logout_document["notices"]}
        assert record.read_bytes() == original_receipt

        again = _run(storage_root, ("config", "logout"), as_json=True)
        assert again.returncode == 0, _output(again)
        repeat = _envelope(again)["result"]
        assert repeat["already_logged_out"] is True
        assert repeat["logged_out_profile"] is None
        assert record.read_bytes() == original_receipt

        resumed = _run(storage_root, ("config", "login", bucket_id), as_json=True)
        assert resumed.returncode == 0, _output(resumed)
        assert _envelope(resumed)["result"]["already_authenticated"] is True

    def test_repeat_login_resumes_existing_receipt_without_new_secret(
        self,
        runtime_profile: tuple[Path, str],
    ) -> None:
        """A second CLI process resumes a persisted receipt without a password channel."""
        storage_root, bucket_id = runtime_profile
        _run(storage_root, ("config", "logout"))

        payload = json.dumps({"passphrase": _CREDENTIAL_INPUT})
        first = _run(
            storage_root,
            ("config", "login", bucket_id, "--secrets-stdin"),
            as_json=True,
            stdin_payload=payload,
        )
        assert first.returncode == 0, _output(first)
        first_result = _envelope(first)["result"]
        assert first_result["session_persisted"] is True
        record = _session_record(storage_root, bucket_id)
        original_receipt = record.read_bytes()

        second = _run(
            storage_root,
            ("config", "login", bucket_id),
            as_json=True,
        )
        assert second.returncode == 0, _output(second)
        second_result = _envelope(second)["result"]

        assert second_result["already_authenticated"] is True
        assert second_result["authenticated_at"] == first_result["authenticated_at"]
        assert record.read_bytes() == original_receipt
