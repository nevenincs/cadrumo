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
            "CADRUMO_TOKEN_DIR": str(tmp_path / "probe-tokens"),
            "CADRUMO_RUNS_DIR": str(tmp_path / "probe-runs"),
            "CADRUMO_SECRET_STORE_DIR": str(tmp_path / "storage" / "fallback-store"),
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
    """Register a REAL encrypted profile in the isolated root, with its pointer.

    Registration runs in-process rather than through the console script,
    because credential registration is the only creation door and it takes a
    passphrase as an argument: no CLI verb can mint a profile. Everything the
    differential control below actually measures still runs in a subprocess
    against this root.

    The ``master.key`` assertion this helper carried was dropped with the
    change. That file belongs to the file-fallback secret store the retired
    creation path provisioned; a registered profile's custody rides its own
    capsule envelope, and the whole control below runs against a root that
    never grows a secrets directory. A silently unprovisioned root would
    still make the control vacuous, so the successful ``ledger list`` run in
    the caller -- which cannot pass against an empty root -- is what carries
    that guarantee now.
    """
    from ....core.config import SecretStoreBackend, override_settings
    from ....tests.user_profile import register_cli_profile

    with override_settings(
        cadrumo_local_storage_root=tmp_path / "storage",
        cadrumo_secret_store_dir=tmp_path / "storage" / "fallback-store",
        cadrumo_secret_store_backend=SecretStoreBackend.FILE,
        cadrumo_secret_passphrase=passphrase,
        cadrumo_active_profile=None,
    ):
        register_cli_profile(
            label="control",
            facts={
                "identity.tax_id": "12345678Z",
                "taxpayer_type.entity_type": "natural_person",
                "identity.name": "Control",
                "identity.surnames": "Operator",
                "activities.description": "design",
            },
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
    assert "show" in combined, combined
    assert "CADRUMO_SECRET_PASSPHRASE" not in combined


def test_store_writing_verb_still_demands_the_passphrase(tmp_path: Path) -> None:
    """Anti-tautology: a verb that writes the store still names the secret channel.

    ``profile edit`` is the store-writing verb here. It replaced
    ``profile create``, which used to serve this role from a cold start and
    now refuses every invocation for an unrelated reason -- credential
    registration is the only creation door -- so it can no longer observe the
    passphrase gate at all. ``edit`` writes profile facts through the same
    encrypted store and reaches the same gate, which is the property under
    test.

    If this ever turns green-by-accident (exit 0), the introspection gate
    has started skipping the session for real verb execution and every
    help assertion above is meaningless. Naming the variable is what makes
    the refusal attributable to the SECRET rather than to any other
    precondition — a refusal alone would also be produced by an unwritable
    root or a missing profile, neither of which is the contract under test,
    which is why the profile is provisioned first.
    """
    _provision_profile(tmp_path, _provisioning_passphrase())

    result = _run(["config", "profile", "edit", "control", "--quiet", "--activity", "consulting"], tmp_path)
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
