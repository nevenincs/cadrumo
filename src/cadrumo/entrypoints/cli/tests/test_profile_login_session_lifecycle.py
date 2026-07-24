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
(silent resume when persisted, an instructive refusal naming ``aeat
config login`` when not). That coupling fails loudly if either half
drifts, on a healthy host and a degraded one alike.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

from ....core.redaction import CLI_PROFILE_ID_PLACEHOLDER

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PASSPHRASE = "lifecycle-session-passphrase"  # noqa: S105

#: Harness that runs the production entrypoint against a scoped storage
#: root. ``with_passphrase`` decides whether the sanctioned headless
#: secret channel is configured: the login gate only engages when it is
#: NOT, so the session assertions below run with it withheld.
_CLI_HARNESS = dedent(
    """
    from __future__ import annotations

    import sys
    from pathlib import Path

    from cadrumo.core import config as config_module
    from cadrumo.core.config import Settings

    storage_root = Path(sys.argv[1])
    with_passphrase = sys.argv[2] == "1"
    passphrase = sys.argv[3]
    cli_args = sys.argv[4:]
    overrides = {}
    if with_passphrase:
        overrides["cadrumo_secret_passphrase"] = passphrase
    settings = Settings(
        _env_file=None,
        cadrumo_local_storage_root=storage_root,
        cadrumo_secret_store_dir=storage_root / "secrets",
        cadrumo_secret_store_backend="file",
        cadrumo_output_language="en",
        **overrides,
    )
    token = config_module._settings_override.set(settings)
    try:
        sys.argv = ["cadrumo", *cli_args]
        from cadrumo.entrypoints.cli import main

        main()
    finally:
        config_module._settings_override.reset(token)
    """,
)


def _env() -> dict[str, str]:
    """Return a parent environment stripped of ambient Cadrumo/pytest state."""
    env = {key: value for key, value in os.environ.items() if not key.startswith(("AEAT_", "CADRUMO_", "PYTEST_"))}
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    return env


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
    subcommand path rather than appended to it.
    """
    root_flags = ("--format", "json") if as_json else ()
    passphrase_flag = "1" if with_passphrase else "0"
    argv = [
        sys.executable,
        "-c",
        _CLI_HARNESS,
        str(storage_root),
        passphrase_flag,
        _PASSPHRASE,
        *root_flags,
        *args,
    ]
    return subprocess.run(
        argv,
        cwd=Path(__file__).parents[3],
        env=_env(),
        input=stdin_payload,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=120.0,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def _envelope(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """Parse the JSON envelope from a ``--format json`` invocation."""
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


def _create_profile(storage_root: Path) -> str:
    """Provision one real profile bucket and return its bucket id."""
    created = _run(
        storage_root,
        (
            "config",
            "profile",
            "create",
            "session-operator",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--name",
            "Session Operator",
            "--entity-type",
            "natural_person",
            "--surnames",
            "Operator",
            "--activity",
            "design",
            "--iva-regime",
            "GENERAL",
        ),
        with_passphrase=True,
    )
    assert created.returncode == 0, _output(created)
    bucket_dirs = [path for path in (storage_root / "buckets").iterdir() if path.is_dir()]
    assert len(bucket_dirs) == 1, f"expected exactly one bucket, got {bucket_dirs}"
    return bucket_dirs[0].name


def _session_record(storage_root: Path, bucket_id: str) -> Path:
    """Return the on-disk persisted-session path for ``bucket_id``."""
    from ....adapters.persistence.storage.master_key import profile_session_path

    return profile_session_path(storage_root=storage_root, bucket_id=bucket_id)


class TestSessionLifecycle:
    """Login, resume, and logout driven end-to-end through real processes."""

    def test_login_resume_and_logout_lifecycle(self, tmp_path: Path) -> None:
        """One full pass: gate, login, follow-on process, logout idempotence."""
        storage_root = tmp_path / "storage"
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
            # Degraded host: the login was process-scoped, so the next
            # process is correctly back at the gate.
            assert follow_on.returncode != 0, _output(follow_on)
            assert "aeat config login" in _output(follow_on), _output(follow_on)

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
        storage_root = tmp_path / "storage"
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
        storage_root = tmp_path / "storage"
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
