"""Help and usage-error surfaces never demand the secret-store passphrase.

Operator-surface regression for the help-tree black hole: with an active
profile configured but ``CADRUMO_SECRET_PASSPHRASE`` unset and a
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
from pathlib import Path

import pytest

from ....core.config import load_settings

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: The sanctioned non-interactive secret channel, spelled out as a literal
#: rather than imported from the master-key adapter that emits it: importing
#: the producer's own constant would assert the code against itself.
_PASSPHRASE_ENV_VAR = "CADRUMO_SECRET_PASSPHRASE"  # noqa: S105 - env var name, not a secret value

#: Matches an actual passphrase VALUE materialization (an env-style
#: assignment, e.g. leaked from ``os.environ`` or a diagnostic dump), never
#: a bare instructional mention of the variable's NAME. Operator-facing help
#: prose is allowed to name ``CADRUMO_SECRET_PASSPHRASE`` when explaining where
#: it must be set for an isolated run (``application/operator_surface/_help.py``);
#: only an actual ``KEY=value`` leak is a genuine secret disclosure.
_PASSPHRASE_VALUE_LEAK_PATTERN = re.compile(r"CADRUMO_SECRET_PASSPHRASE\s*=\s*\S")

#: Profile-shape arguments for a non-interactive ``profile create``. Only the
#: fields the verb requires; the value set is irrelevant to every assertion
#: here, which is why it is shared by the cold-start refusal control and the
#: real provisioning step.
_PROFILE_ARGS = (
    "--quiet",
    "--tax-id",
    "12345678Z",
    "--name",
    "Control Operator",
    "--entity-type",
    "natural_person",
    "--surnames",
    "Operator",
    "--activity",
    "design",
    "--iva-regime",
    "GENERAL",
)


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
    env.pop(_PASSPHRASE_ENV_VAR, None)
    env.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
            "CADRUMO_TOKEN_DIR": str(tmp_path / "tokens"),
            "CADRUMO_RUNS_DIR": str(tmp_path / "runs"),
            "CADRUMO_SECRET_STORE_DIR": str(tmp_path / "storage" / "secrets"),
            "CADRUMO_SECRET_STORE_BACKEND": "file",
        },
    )
    return env


def _run(
    args: list[str],
    tmp_path: Path,
    *,
    passphrase: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the real console script; ``passphrase`` unlocks the store when given."""
    aeat_exe = shutil.which("aeat")
    assert aeat_exe is not None, "aeat console script must be installed for this gate"
    env = _passphraseless_env(tmp_path)
    if passphrase is not None:
        env[_PASSPHRASE_ENV_VAR] = passphrase
    return subprocess.run(
        [aeat_exe, *args],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


def _provisioning_passphrase() -> str:
    """Resolve the dev/test passphrase through the sanctioned settings accessor."""
    return load_settings().cadrumo_dev_test_database_password.get_secret_value()


def _provision_profile(tmp_path: Path, passphrase: str) -> None:
    """Create a REAL encrypted profile in the isolated root, with its pointer.

    Provisioning goes through the same real console script as every other
    case, carrying the passphrase on its sanctioned environment channel.
    A failure here is asserted loudly: a silently unprovisioned root would
    make the differential control below vacuous.
    """
    created = _run(["config", "profile", "create", "control", *_PROFILE_ARGS], tmp_path, passphrase=passphrase)
    combined = f"{created.stdout}\n{created.stderr}"
    assert created.returncode == 0, combined
    assert (tmp_path / "storage" / "secrets" / "master.key").is_file(), combined
    assert passphrase not in combined


@pytest.mark.parametrize(
    ("args", "expected_row"),
    [
        (["config", "--help"], "aeat config profile create"),
        (["app", "--help"], "aeat app ledger import"),
        (["app", "ledger", "--help"], "import"),
        (["app", "modelo", "--help"], "work"),
        # Custody surfaces: browsing the recovery/recover/passphrase help must
        # never open the encrypted session or demand any secret.
        (["config", "recovery", "--help"], "status"),
        (["config", "recovery", "create", "--help"], "retyped"),
        (["config", "recovery", "verify", "--help"], "--secrets-stdin"),
        (["config", "recover", "--help"], "--secrets-stdin"),
        (["config", "passphrase", "--help"], "change"),
    ],
)
def test_subgroup_help_renders_without_passphrase(
    tmp_path: Path,
    args: list[str],
    expected_row: str,
) -> None:
    """Every subgroup help renders exit 0 with real content, no master key.

    Help prose may legitimately NAME ``CADRUMO_SECRET_PASSPHRASE`` (e.g. the
    isolated-run instructions on ``aeat config --help``); only an actual
    value assignment is a genuine leak, so the gate checks for that
    narrower pattern rather than a blanket substring match.
    """
    result = _run(args, tmp_path)
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    assert expected_row in result.stdout, combined
    assert not _PASSPHRASE_VALUE_LEAK_PATTERN.search(combined), combined
    assert "Traceback" not in combined


def test_unknown_command_renders_usage_error_without_passphrase(tmp_path: Path) -> None:
    """A typo'd subcommand yields the exit-2 usage error, not a key refusal."""
    result = _run(["config", "nosuchcmd"], tmp_path)
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 2, combined
    assert "nosuchcmd" in combined
    assert "CADRUMO_SECRET_PASSPHRASE" not in combined


def test_bare_config_profile_renders_subgroup_help_without_passphrase(tmp_path: Path) -> None:
    """Bare `config profile` is discovery, not a profile-data read."""
    result = _run(["config", "profile"], tmp_path)
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 2, combined
    assert "create" in result.stdout
    assert "show" in result.stdout
    assert "CADRUMO_SECRET_PASSPHRASE" not in combined


def test_store_writing_verb_still_demands_the_passphrase(tmp_path: Path) -> None:
    """Anti-tautology: a verb that writes the store still names the secret channel.

    ``profile create`` is the store-writing verb that reaches master-key
    resolution from a cold start, so it observes the passphrase gate
    directly and reports the variable the operator must supply.

    If this ever turns green-by-accident (exit 0), the introspection gate
    has started skipping the session for real verb execution and every
    help assertion above is meaningless. Naming the variable is what makes
    the refusal attributable to the SECRET rather than to any other
    cold-start precondition — a refusal alone would also be produced by an
    unwritable root or a missing profile, neither of which is the contract
    under test.
    """
    result = _run(["config", "profile", "create", "control", *_PROFILE_ARGS], tmp_path)
    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0, combined
    assert _PASSPHRASE_ENV_VAR in combined, combined
    # Naming the variable is correct; materializing a value is the leak.
    assert not _PASSPHRASE_VALUE_LEAK_PATTERN.search(combined), combined
    assert "Traceback" not in combined


def test_data_verb_still_refuses_without_passphrase(tmp_path: Path) -> None:
    """Anti-tautology: the secret stays load-bearing for real verb execution.

    A differential over one variable. The SAME data verb runs twice
    against the SAME real encrypted profile in the SAME isolated root; the
    only difference is whether the passphrase is on the environment. It
    renders with the passphrase and is refused without it, which is what
    proves the secret is genuinely required to execute a verb — the
    premise every help assertion above depends on.

    The paired successful run is the load-bearing half: it establishes
    that the profile and root are usable, so the refusal cannot be
    explained away by a broken fixture. That is why the refusal is
    asserted as a differential against a proven-working baseline rather
    than as a bare non-zero exit, and why no refusal prose is asserted —
    the wording of the refusal is free to change (a session door now
    fronts the key gate for this route), the secret's necessity is not.
    """
    passphrase = _provisioning_passphrase()
    _provision_profile(tmp_path, passphrase)

    unlocked = _run(["app", "ledger", "list"], tmp_path, passphrase=passphrase)
    unlocked_combined = f"{unlocked.stdout}\n{unlocked.stderr}"
    assert unlocked.returncode == 0, unlocked_combined
    assert unlocked.stdout.strip(), unlocked_combined

    refused = _run(["app", "ledger", "list"], tmp_path)
    refused_combined = f"{refused.stdout}\n{refused.stderr}"
    assert refused.returncode != 0, refused_combined
    # The listing the unlocked run rendered must not appear without the secret.
    assert unlocked.stdout not in refused.stdout, refused_combined
    assert "Traceback" not in refused_combined
    # Neither run may materialize the passphrase, in prose or as an assignment.
    for combined in (unlocked_combined, refused_combined):
        assert passphrase not in combined, combined
        assert not _PASSPHRASE_VALUE_LEAK_PATTERN.search(combined), combined
