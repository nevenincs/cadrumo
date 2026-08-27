"""Real-behaviour proof that a custody unlock refuses instead of blocking.

The hardened no-echo prompt is only worth what the verbs actually route
through it. ``config login`` must read the profile passphrase before it can
unwrap a capsule, and the storage substrate's own passphrase resolver ends in
a bare :func:`getpass.getpass` — a read with no real-console precondition, so
on Windows it calls ``msvcrt.getwch()`` and BLOCKS FOREVER on a console-less
host, and with no promotion of an echo-suppression failure to a refusal, so
it can degrade to an echoing read. A login that inherits that resolver hangs
with no diagnostic and no way for the operator to distinguish a hang from a
slow KDF.

This drives the real verb rather than the prompt helper, which is the whole
point: exercising :func:`prompt_secret_no_echo` in isolation proves nothing
about a path that never calls it. The child is a genuine ``DETACHED_PROCESS``
spawn with no console — no patching, no doubles — and the test fails on
timeout, so a regression that re-introduces the block cannot pass by hanging.

The child registers a REAL profile first, with the passphrase supplied
directly, so the login it then attempts has a genuine locked capsule to
unwrap. Without that the verb would refuse for want of a profile and the
gate would pass without ever reaching the secret channel it exists to guard.

Windows is where the exposure lives, and where this gate has teeth: there a
console-less stdin reports ``isatty() == True``, so the verb's cheap
interactive pre-check admits the channel and the refusal has to come from the
real-console precondition further in. On POSIX the same spawn yields a non-tty
``/dev/null`` stdin, which the pre-check refuses on its own; the assertions
below still hold there, but the platform carries no equivalent blocking read
to regress. The preconditions recorded in the verdict make which case ran
auditable rather than assumed.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import textwrap
from typing import Final

import pytest
from pydantic import TypeAdapter

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_JSON_OBJECT_ADAPTER: TypeAdapter[dict[str, object]] = TypeAdapter(dict[str, object])

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"active-profile"})
"""Taxonomy-vocabulary literals this module deliberately pins.

The active-profile pointer filename is asserted UNCHANGED across the refused
login: a refusal must not move the operator's selection to the profile it
declined to unlock."""

# A console-less child that blocks is unbounded, so any finite budget detects
# the regression; the size only trades against a false failure. The child must
# import the whole CLI tree and derive a real Argon2id key before it can even
# reach the prompt, which has been measured at over a minute on a box running
# parallel test lanes, so the budget is set well clear of that rather than
# close to it.
_CHILD_BUDGET_SECONDS = 300.0

_LABEL = "Console Less Login Subject"
_PASSPHRASE = "console-less-login-operator-secret"  # noqa: S105 - synthetic test fixture

_LOGIN_PROBE = """
import json, sys
from pathlib import Path

storage_root = Path(sys.argv[1])
verdict_path = Path(sys.argv[2])
label = sys.argv[3]
passphrase = sys.argv[4]
verdict = {}
try:
    from cadrumo.core import config as config_module
    from cadrumo.core.config import Settings
    from cadrumo.entrypoints.cli._config._secure_input import _stdin_is_a_real_console

    settings = Settings(
        _env_file=None,
        cadrumo_local_storage_root=storage_root,
        cadrumo_secret_store_dir=storage_root / "fallback-store",
        cadrumo_secret_store_backend="auto",
        cadrumo_secret_passphrase=None,
        cadrumo_output_language="en",
    )
    verdict["passphrase_configured"] = settings.cadrumo_secret_passphrase is not None
    verdict["isatty"] = sys.stdin.isatty()
    verdict["real_console"] = _stdin_is_a_real_console()

    token = config_module._settings_override.set(settings)
    try:
        # A real locked profile, so the login below has a capsule to unwrap
        # and must reach the passphrase channel to do it.
        from cadrumo.application.user_profile.login_session import logout_active_profile
        from cadrumo.application.user_profile.registration import register_profile_with_credentials

        register_profile_with_credentials(
            label=label,
            passphrase=passphrase,
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        logout_active_profile()
        verdict["profile_registered"] = True

        sys.argv = ["cadrumo", "config", "login", label]
        from cadrumo.entrypoints.cli import main

        try:
            main()
            verdict["outcome"] = "returned"
            verdict["exit_code"] = 0
        except SystemExit as exc:
            code = exc.code
            verdict["outcome"] = "exited"
            verdict["exit_code"] = code if isinstance(code, int) else (0 if code is None else 1)
    finally:
        config_module._settings_override.reset(token)
except BaseException as exc:
    verdict["outcome"] = "escaped"
    verdict["error_type"] = type(exc).__name__
verdict_path.write_text(json.dumps(verdict), encoding="utf-8")
"""


def _child_env() -> dict[str, str]:
    """Return an environment with every ambient Cadrumo setting removed.

    The probe asserts that no passphrase is configured, so the child must not
    inherit one from the developer's or CI runner's environment; scrubbing the
    whole prefix also keeps an ambient storage root or backend selection from
    silently redirecting the run away from the sandbox.
    """
    env = {key: value for key, value in os.environ.items() if not key.startswith(("CADRUMO_", "AEAT_", "PYTEST_"))}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _run_console_less_login(storage_root: pathlib.Path) -> dict[str, object]:
    """Run ``config login`` in a console-less child and return its verdict."""
    verdict_path = storage_root.parent / "verdict.json"
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
    process = subprocess.Popen(  # noqa: S603 - fixed interpreter argv with controlled test inputs.
        [
            sys.executable,
            "-c",
            textwrap.dedent(_LOGIN_PROBE),
            str(storage_root),
            str(verdict_path),
            _LABEL,
            _PASSPHRASE,
        ],
        creationflags=creationflags,
        env=_child_env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        process.wait(timeout=_CHILD_BUDGET_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        pytest.fail(
            "`config login` BLOCKED on a console-less host instead of refusing; "
            "the unlock path has regressed to the storage substrate's unguarded "
            "passphrase read",
        )

    assert verdict_path.is_file(), "the console-less login produced no verdict"
    return _JSON_OBJECT_ADAPTER.validate_python(json.loads(verdict_path.read_text(encoding="utf-8")))


def test_login_refuses_on_a_console_less_host_instead_of_blocking(tmp_path: pathlib.Path) -> None:
    """The unlock verb terminates with a refusal, unlocking nothing."""
    storage_root = tmp_path / "cadrumo-storage"

    verdict = _run_console_less_login(storage_root)

    # Precondition: the environment channel is genuinely unavailable, so the
    # passphrase really does have to be resolved interactively. Without this
    # the refusal below could be a configured value flowing through instead.
    assert verdict["passphrase_configured"] is False, (
        f"the probe inherited a configured secret-store passphrase: {verdict!r}"
    )

    # Precondition: a real locked profile exists, so the verb had to reach the
    # secret channel rather than refusing for want of a target.
    assert verdict.get("profile_registered") is True, (
        f"the probe never registered a profile, so the login never reached the secret channel: {verdict!r}"
    )

    assert verdict["outcome"] == "exited", (
        f"the login must end in a typed refusal, not an escaped exception; got {verdict!r}"
    )
    assert verdict["exit_code"] != 0, f"a refused login must exit non-zero; got {verdict!r}"
    assert "error_type" not in verdict, (
        f"the refusal must reach the operator through the CLI error boundary; got {verdict!r}"
    )

    # A refused unlock must not move the operator's selection onto the target.
    assert not (storage_root / "active-profile").is_file(), "a refused login left an active-profile selection behind"

    if verdict["isatty"] is True:
        # The Windows trap this gate exists for: the verb's cheap interactive
        # pre-check sees a TTY and admits the channel, so the refusal can only
        # have come from the real-console precondition deeper in the path.
        assert verdict["real_console"] is False, (
            f"the probe obtained a real console, so it did not construct the trap: {verdict!r}"
        )
