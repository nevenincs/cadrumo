"""Help and usage-error surfaces never demand the secret-store passphrase.

Operator-surface regression for the help-tree black hole: with an active
profile configured but ``CADRUMO_SECRET_CREDENTIAL_INPUT`` unset and a
non-interactive stdin, the root callback's bucket-session activation used
to run before any help or usage rendering, so EVERY subgroup help
(``aeat config --help``, ``aeat app --help``, ``aeat app ledger --help``)
and every unknown-command typo died with the master-key refusal (exit 5)
instead of rendering. A newcomer could not browse the command tree before
creating secrets and scripted ``--help`` introspection was dead. The
introspection cases below reproduce the newcomer end of that condition —
cold start, nothing provisioned — while the differential control at the
bottom covers the provisioned-profile end against a real encrypted store.

The contract under test: help and usage-error renderings are
introspection surfaces — like ``--version`` and the bare landing card —
and must not open the encrypted session; the master key unlocks only when
a verb actually executes against the store, where the existing refusal
stays intact.

Real-behavior only: each case runs the REAL installed ``aeat`` console
script in a subprocess with a controlled environment (no passphrase,
isolated storage root and secret store) and captured stdio (so stdin is
genuinely non-interactive — the exact operator condition).

Two anti-tautology controls sit at the bottom of the module and keep the
help assertions above falsifiable; see their docstrings. They exist
because "help renders exit 0 without a passphrase" is only meaningful
while the secret is still genuinely load-bearing for real verb
execution in this same environment.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import ensure_text_completed_process, run_audited_process
from cadrumo_runtime.commands.tests.runtime_profile_cli_fixture import native_cli_profile_scope

from .cli_runner import invoke_unbound_cli
from .profile_password_cli import invoke_with_profile_password, refused_for_want_of_an_operator

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The sanctioned non-interactive secret channel, spelled out as a literal
#: rather than imported from the master-key adapter that emits it: importing
#: the producer's own constant would assert the code against itself.
_CREDENTIAL_ENV_VAR = "CADRUMO_SECRET_CREDENTIAL_INPUT"

#: Matches an actual passphrase VALUE materialization (an env-style
#: assignment, e.g. leaked from ``os.environ`` or a diagnostic dump), never
#: a bare instructional mention of the variable's NAME. Operator-facing help
#: prose is allowed to name ``CADRUMO_SECRET_CREDENTIAL_INPUT`` when explaining where
#: it must be set for an isolated run (``application/operator_surface/help.py``);
#: only an actual ``KEY=value`` leak is a genuine secret disclosure.
_CREDENTIAL_INPUT_VALUE_LEAK_PATTERN = re.compile(r"CADRUMO_SECRET_CREDENTIAL_INPUT\s*=\s*\S")


def _passphraseless_env(tmp_path: Path) -> dict[str, str]:
    """Isolated environment carrying NO secret-store passphrase.

    Three properties make the cases below deterministic rather than
    machine-dependent:

    - The passphrase variable is explicitly removed, so an exported value
      in the developer's own shell cannot silently satisfy the gate the
      controls exist to observe.
    - The secret-store backend is pinned to ``file``. Under the default
      ``auto`` backend a machine with a usable OS keychain can serve the
      master key without any passphrase, which would turn the controls
      green for a reason that has nothing to do with the contract.
    - Storage root and secret store both live under ``tmp_path``, so no
      case can read the operator's real store.

    No active profile is selected: ``CADRUMO_ACTIVE_PROFILE`` is severed
    from the environment by design (``core/config.py``
    ``_NON_ENVIRONMENT_SELECTION_NAMES`` — selection belongs to the
    ``active-profile`` pointer file and the in-process ``--profile``
    channel), so setting it here would configure nothing while reading
    as though it did. Cold start is also the exact newcomer condition
    this module was written for: browsing the command tree before any
    profile or secret exists.
    """
    env = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
    env.pop(_CREDENTIAL_ENV_VAR, None)
    # Explicit directory overrides are the operator's to provision; the CLI
    # validates them and never creates them.
    for directory in ("probe-tokens", "probe-runs", "storage/fallback-store"):
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)
    env.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
            "CADRUMO_TOKEN_DIR": str(tmp_path / "probe-tokens"),
            "CADRUMO_RUNS_DIR": str(tmp_path / "probe-runs"),
            "CADRUMO_SECRET_STORE_DIR": str(tmp_path / "storage" / "fallback-store"),
        },
    )
    return env


def _run(args: list[str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Run the real console script with no secret anywhere in its environment."""
    aeat_exe = shutil.which("aeat")
    assert aeat_exe is not None, "aeat console script must be installed for this gate"
    env = _passphraseless_env(tmp_path)
    return ensure_text_completed_process(
        run_audited_process(
            [aeat_exe, *args],
            cwd=Path.cwd(),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=None,
            check=False,
        ),
    )


@pytest.mark.parametrize(
    ("args", "expected_row"),
    [
        (["config", "--help"], "aeat config profile create"),
        (["app", "--help"], "aeat app ledger import"),
        (["app", "ledger", "--help"], "import"),
        (["app", "modelo", "--help"], "work"),
        # Custody surfaces: browsing the session and repair help must never
        # open the encrypted session or demand any secret. Five rows here
        # addressed the recovery and passphrase families until the custody
        # cutover left all of them unregistered, at which point they asserted
        # nothing about secret handling and only reported the absent verbs.
        # The property is re-founded on the custody verbs that do resolve.
        (["config", "login", "--help"], "login"),
        (["config", "logout", "--help"], "logout"),
        (["config", "repair", "--help"], "quarantine"),
    ],
)
def test_subgroup_help_renders_without_passphrase(
    tmp_path: Path,
    args: list[str],
    expected_row: str,
) -> None:
    """Every subgroup help renders exit 0 with real content, no master key.

    Help prose may legitimately NAME ``CADRUMO_SECRET_CREDENTIAL_INPUT`` (e.g. the
    isolated-run instructions on ``aeat config --help``); only an actual
    value assignment is a genuine leak, so the gate checks for that
    narrower pattern rather than a blanket substring match.
    """
    result = _run(args, tmp_path)
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    assert expected_row in result.stdout, combined
    assert not _CREDENTIAL_INPUT_VALUE_LEAK_PATTERN.search(combined), combined
    assert "Traceback" not in combined


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_live_config_help_only_documents_explicit_secret_channels(tmp_path: Path, locale: str) -> None:
    """Every shipped locale rejects the retired environment-secret instruction."""
    result = _run(["--language", locale, "config", "--help"], tmp_path)
    combined = f"{result.stdout}\n{result.stderr}"

    assert result.returncode == 0, combined
    assert _CREDENTIAL_ENV_VAR not in combined, combined
    for option in (
        "--profile-secrets-stdin",
        "--profile-secrets-fd",
        "--secrets-stdin",
        "--secrets-fd",
    ):
        assert option in combined, combined


def test_unknown_command_renders_usage_error_without_passphrase(tmp_path: Path) -> None:
    """A typo'd subcommand yields the exit-2 usage error, not a key refusal."""
    result = _run(["config", "nosuchcmd"], tmp_path)
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 2, combined
    assert "nosuchcmd" in combined
    assert "CADRUMO_SECRET_CREDENTIAL_INPUT" not in combined


def test_bare_config_profile_renders_subgroup_help_without_passphrase(tmp_path: Path) -> None:
    """Bare `config profile` is discovery, not a profile-data read.

    Like ``test_unknown_command_renders_usage_error_without_passphrase``, this
    is Click's exit-2 usage-error path (missing subcommand), which writes its
    rendered help to stderr -- unlike the exit-0 ``--help`` cases above, which
    write to stdout. The content assertions therefore check ``combined``, not
    ``result.stdout``.
    """
    result = _run(["config", "profile"], tmp_path)
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 2, combined
    assert "create" in combined, combined
    assert "view" in combined, combined
    assert "CADRUMO_SECRET_CREDENTIAL_INPUT" not in combined


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
@pytest.mark.usefixtures("authority_operation")
def test_the_profile_password_stays_load_bearing_for_a_data_verb_and_a_store_writing_verb(tmp_path: Path) -> None:
    """Anti-tautology: help needs no secret, but executing a verb still does.

    A differential over one variable, against one real encrypted profile
    served by a real runtime: the SAME verb runs without the person's password
    and then with it on the protected standard-input channel. It is refused
    for want of a sign-in without it, before any effect, and served with it.
    The served run is the load-bearing half: it proves the profile and runtime
    are usable, so the refusal cannot be explained away by a broken fixture.
    The environment-variable secret this gate once named is retired; the
    protected channel is the only way the password reaches a command.
    """
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(
            label="help-without-secrets",
            facts={"identity.name": "Synthetic", "identity.surnames": "Secret Gate"},
        )
        assert profile.label is not None
        passphrase = profile.passphrase
        for verb in (
            ["app", "ledger", "list"],
            ["config", "profile", "edit", profile.label, "--quiet", "--activity", "consulting"],
        ):
            refused = invoke_unbound_cli(["--format", "json", *verb])
            served = invoke_with_profile_password(["--format", "json", *verb], label=profile.label)
            assert refused_for_want_of_an_operator(refused), refused.output
            assert '"result"' not in refused.stdout, refused.output
            assert served.exit_code == 0, served.output
            assert '"result"' in served.stdout, served.output
            for result in (refused, served):
                assert passphrase not in result.output
                assert not _CREDENTIAL_INPUT_VALUE_LEAK_PATTERN.search(result.output)
                assert "Traceback" not in result.output
