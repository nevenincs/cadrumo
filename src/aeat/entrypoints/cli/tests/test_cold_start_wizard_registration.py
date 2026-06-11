"""Cold-process guard: the CLI composition root registers the wizard catalogue.

The profile-setup wizard catalogue (``SETUP_FLOW`` / ``WIZARD_FLOWS``) and the
project-answers projection are core registry slots that a domain module reaches
during ``app modelo work create``. They are populated by importing
:mod:`aeat.application.wizard._catalogue` and
:mod:`aeat.application.wizard._persistence` for their registration side effect.

The CLI root callback owns that side-effect import — the same contract as the
active-profile language resolver. A relocation that drops the import leaves the
production CLI raising ``"Wizard catalogue has not been registered"`` /
``"project_answers has not been registered"`` on the first modelo work-create,
*while the in-process test suite stays green* because some other test in the
session imports the catalogue and registers it process-wide.

That is why this guard runs in a **fresh interpreter**: profile creation and
work-create execute in two separate cold processes sharing one storage root, so
the work-create process must register the catalogue through the root callback
itself. An in-process ``CliRunner`` test cannot observe the regression.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from ....core.config import SecretStoreBackend, Settings

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# The internal registration-guard messages that must never reach the operator
# from the composition root. Each is raised by a core registry-slot accessor
# when its slot was not populated at application startup.
_REGISTRATION_LEAKS: tuple[str, ...] = (
    "Wizard catalogue has not been registered",
    "project_answers has not been registered",
    "profile keys are not registered",
)


def _run_cli_cold(storage_root: Path, argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Invoke the ``aeat`` CLI in a fresh interpreter against ``storage_root``.

    A new process guarantees an empty ``sys.modules``: the only path that can
    register the wizard catalogue is the root callback exercised by ``argv``.
    """

    code = f"""
        import sys
        from click.testing import CliRunner
        from typer.main import get_command
        from aeat.entrypoints.cli import app

        result = CliRunner().invoke(get_command(app), {argv!r})
        sys.stdout.write(result.output)
        sys.exit(result.exit_code)
        """
    setting_env = str.upper
    base_settings = Settings(_env_file=None)  # type: ignore[call-arg]  # ty: ignore[unknown-argument]
    env = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
    env.update(
        {
            setting_env("aeat_local_storage_root"): str(storage_root),
            setting_env("aeat_secret_store_backend"): SecretStoreBackend.FILE.value,
            setting_env("aeat_secret_passphrase"): base_settings.aeat_dev_test_database_password.get_secret_value(),
        },
    )
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env=env,
    )


def test_cold_process_work_create_registers_wizard_catalogue(tmp_path: Path) -> None:
    """A cold ``app modelo work create`` registers the wizard catalogue itself.

    Profile creation runs in its own fresh process (writing the storage root);
    the work-create then runs in a *separate* fresh process whose only
    callback dispatch is the work-create. If the root callback does not
    register the wizard catalogue and project-answers projection, work-create
    raises the internal registration error instead of creating the unit.
    """

    setup = _run_cli_cold(
        tmp_path,
        ["config", "profile", "create", "coldwiz", "--tax-id", "45678912S", "--quiet"],
    )
    assert setup.returncode == 0, f"profile create failed: {setup.stdout}\n{setup.stderr}"

    created = _run_cli_cold(
        tmp_path,
        [
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "100",
            "--year",
            "2024",
            "--period",
            "0A",
            "--revision",
            "2024",
        ],
    )

    for leak in _REGISTRATION_LEAKS:
        assert leak not in created.stdout, f"work create surfaced an unregistered core slot: {leak!r}\n{created.stdout}"
    assert created.returncode == 0, f"work create failed in a cold process: {created.stdout}\n{created.stderr}"
