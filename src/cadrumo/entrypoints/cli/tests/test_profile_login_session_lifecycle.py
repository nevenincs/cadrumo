"""End-to-end profile session lifecycle over the real CLI entrypoint.

Real subprocesses, real storage, real custody: every invocation below
spawns a fresh interpreter running the production ``main()`` against a
per-test storage root, so "a later process resumes without prompting" is
observed rather than simulated. No mocks, stubs, or monkeypatching, and no
verb is driven through an in-process shortcut.

The suite deliberately does NOT assume the host can custody a session
key. ``aeat config login`` reports ``session_persisted`` per the
documented degradation rule: a host with no usable OS keychain mints no
persisted artefact and logs in for that process only. Both branches are real
product behaviour, so the load-bearing assertion here is the COUPLING —
the envelope's ``session_persisted`` claim must match what is actually on
disk, and the follow-on process must behave the way that claim implies
(silent resume when persisted, a typed keychain-unavailable refusal when
the current receipt cannot be accelerated). That coupling fails loudly if
either half drifts, on a healthy host and a degraded one alike.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from ....core.redaction import CLI_PROFILE_ID_PLACEHOLDER
from ....tests.secure_sql import reap_profile_session_keys
from ....tests.subprocess_cli import run_cadrumo_subprocess

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "lifecycle-session-passphrase"  # noqa: S105

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
        "cadrumo_secret_store_dir": storage_root / "fallback-store",
        "cadrumo_secret_store_backend": "auto",
        "cadrumo_output_language": "en",
    }
    if with_passphrase:
        settings["cadrumo_secret_passphrase"] = _PASSPHRASE
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
    from ....adapters.persistence.storage.master_key import close_active_bucket_session
    from ....application.user_profile import register_profile_with_credentials
    from ....core.config import override_settings

    with override_settings(cadrumo_local_storage_root=storage_root):
        outcome = register_profile_with_credentials(label="session-operator", passphrase=_PASSPHRASE)
        close_active_bucket_session()
    return outcome.bucket_id


def _session_record(storage_root: Path, bucket_id: str) -> Path:
    """Return the on-disk persisted-session path for ``bucket_id``."""
    from ....adapters.persistence.storage.custody import profile_session_path

    return profile_session_path(storage_root=storage_root, profile_id=UUID(bucket_id))


class TestSessionLifecycle:
    """Login, resume, and logout driven end-to-end through real processes."""

    def test_login_resume_and_logout_lifecycle(self, tmp_path: Path) -> None:
        """One full pass: gate, login, follow-on process, logout idempotence."""
        storage_root = tmp_path / _STORAGE_DIRNAME
        storage_root.mkdir()
        bucket_id = _create_profile(storage_root)

        # Start from a clean slate. logout is a STRONG close: it clears the
        # active-profile pointer too, so the login below must name its
        # target rather than relying on a selection that no longer exists.
        first_logout = _run(storage_root, ("config", "logout"), as_json=True)
        assert first_logout.returncode == 0, _output(first_logout)

        # 1. login over the bounded strict-JSON secrets channel; the
        #    passphrase is never an argv value.
        logged_in = _run(
            storage_root,
            ("config", "login", bucket_id, "--secrets-stdin"),
            as_json=True,
            stdin_payload=json.dumps({"passphrase": _PASSPHRASE}),
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
        assert isinstance(persisted, bool)
        record = _session_record(storage_root, bucket_id)
        assert record.is_file() is persisted, f"session_persisted={persisted} disagrees with on-disk record at {record}"

        # 3. The follow-on process must behave the way that claim implies.
        follow_on = _run(storage_root, ("config", "profile", "show"))
        if persisted:
            # Resumed silently: no prompt, no re-authentication.
            assert follow_on.returncode == 0, _output(follow_on)
            assert "aeat config login" not in _output(follow_on), _output(follow_on)
        else:
            # A pointer may still name the current profile, so a degraded
            # host projects the explicit acceleration outcome rather than
            # pretending the profile selection is absent.
            assert follow_on.returncode != 0, _output(follow_on)
            assert "OS keychain is unavailable for profile-session acceleration" in _output(follow_on)

        # 4. Logout is a strong close, and a second logout is a clean
        #    idempotent no-op rather than a refusal.
        logged_out = _run(storage_root, ("config", "logout"), as_json=True)
        assert logged_out.returncode == 0, _output(logged_out)
        assert not record.exists(), "logout left the persisted session record behind"

        again = _run(storage_root, ("config", "logout"), as_json=True)
        assert again.returncode == 0, _output(again)
        repeat = _envelope(again)["result"]
        assert repeat["already_logged_out"] is True
        assert repeat["logged_out_profile"] is None

    def test_login_reports_persistence_warning_when_it_cannot_persist(
        self,
        tmp_path: Path,
    ) -> None:
        """A non-persisted login MUST warn; a persisted one MUST NOT.

        The warning is the operator's only signal that the session will
        not outlive the command, so its presence is bound to the same
        ``session_persisted`` flag the record on disk is bound to.
        """
        storage_root = tmp_path / _STORAGE_DIRNAME
        storage_root.mkdir()
        bucket_id = _create_profile(storage_root)
        _run(storage_root, ("config", "logout"))

        logged_in = _run(
            storage_root,
            ("config", "login", bucket_id, "--secrets-stdin"),
            as_json=True,
            stdin_payload=json.dumps({"passphrase": _PASSPHRASE}),
        )
        assert logged_in.returncode == 0, _output(logged_in)
        envelope = _envelope(logged_in)
        codes = {notice["code"] for notice in envelope.get("notices", ())}

        if envelope["result"]["session_persisted"]:
            assert "config.login.session_not_persisted" not in codes
            assert envelope["status"] == "success"
        else:
            assert "config.login.session_not_persisted" in codes
            assert envelope["status"] == "warning"

    def test_repeat_login_is_an_idempotent_no_op_when_the_session_persists(
        self,
        tmp_path: Path,
    ) -> None:
        """A second login for the same profile resumes rather than re-minting.

        Only reachable where the session actually persists: with no
        keychain there is nothing for the retry to resume, so the second
        login is a genuine fresh authentication and the idempotence
        contract does not apply.
        """
        storage_root = tmp_path / _STORAGE_DIRNAME
        storage_root.mkdir()
        bucket_id = _create_profile(storage_root)
        _run(storage_root, ("config", "logout"))

        payload = json.dumps({"passphrase": _PASSPHRASE})
        first = _run(
            storage_root,
            ("config", "login", bucket_id, "--secrets-stdin"),
            as_json=True,
            stdin_payload=payload,
        )
        assert first.returncode == 0, _output(first)
        first_result = _envelope(first)["result"]

        second = _run(
            storage_root,
            ("config", "login", bucket_id, "--secrets-stdin"),
            as_json=True,
            stdin_payload=payload,
        )
        assert second.returncode == 0, _output(second)
        second_result = _envelope(second)["result"]

        if first_result["session_persisted"]:
            # The retry resumed: no new record, and the original login
            # instant is never re-stamped.
            assert second_result["already_authenticated"] is True
            assert second_result["authenticated_at"] == first_result["authenticated_at"]
        else:
            # Nothing to resume, so this is a fresh authentication.
            assert second_result["already_authenticated"] is False
