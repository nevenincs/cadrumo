"""Cold-process guard: the CLI composition root registers the wizard catalogue.

The profile-setup wizard catalogue (``SETUP_FLOW`` / ``WIZARD_FLOWS``) and the
project-answers projection are core registry slots that a domain module reaches
during ``app modelo work create``. They are populated by importing
:mod:`cadrumo.application.wizard._catalogue` and
:mod:`cadrumo.application.wizard._persistence` for their registration side effect.

The CLI root callback owns that side-effect import — the same contract as the
active-profile language resolver. A relocation that drops the import leaves the
production CLI raising ``"Wizard catalogue has not been registered"`` /
``"project_answers has not been registered"`` on the first modelo work-create,
*while the in-process test suite stays green* because some other test in the
session imports the catalogue and registers it process-wide.

That is why this guard runs in a **fresh interpreter**: the profile is
registered in-process and the work-create then runs in a *separate* cold
process against the same storage root, so the work-create process must
register the catalogue through the root callback itself. An in-process runner
cannot observe the regression.

The profile is seeded in-process rather than by a cold ``profile create``
because credential registration is the only creation door and it takes a
passphrase as an argument: no CLI verb, and therefore no subprocess, can mint
a profile. Only the SEED moved; the assertion still runs in a fresh
interpreter, which is the whole point of the guard.

``cold_process_profile_create_uses_local_storage_secret_store`` was retired
with that change. It asserted that a cold ``profile create`` writes
``master.key`` and ``master.kdf`` under the storage root, and no live door
writes that store at all any more -- a registered profile's custody rides its
own capsule envelope. The workspace-pollution half it also carried is covered
by the fingerprint assertion retained in the work-create guard below.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Final

import pytest

from ....core.config import SecretStoreBackend, Settings
from ....tests import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset(
    {"secrets", "master.key", "master.kdf", "master.recovery.key"},
)
"""Taxonomy-vocabulary literals this module deliberately pins.

These names outlived the code that wrote them, and that makes the assertions
STRONGER rather than stale. The shared-master file store was retired, so no
surviving path can create ``master.key``, ``master.kdf`` or
``master.recovery.key`` at all: an assertion that they are absent used to mean
"this flow did not write them" and now also means "nothing could have". Do not
read these literals as leftovers of a deleted surface and sweep them -- the
absence they pin is the point, and pinning it by literal is what keeps the
check independent of the taxonomy accessors it is checking.

``_workspace_secret_store_fingerprint`` targets the real, shared dev-workspace
secret store (``REPO_ROOT / "var" / "secrets"``), never a taxonomy accessor --
that is the point of the fingerprint, which exists to catch a cold-process
test polluting the real workspace. The cold-process CLI assertions in
``test_cold_process_profile_create_uses_local_storage_secret_store`` set no
``CADRUMO_SECRET_STORE_DIR`` override, so they check production's real
DEFAULT-derived location, not an injected value; migrating either to the
accessor would make the assertion agree with the code path it exists to
independently confirm. ``"master.key"``, ``"master.kdf"``, and
``"master.recovery.key"`` are :data:`_SECRET_STORE_FILES`'s three real leaf
names, checked by the same fingerprint and asserted directly under the
``"secrets"`` directory (``"salt"`` is the fourth entry but is not a taxonomy
member: the per-store salt lives inside ``master.kdf``, no standalone file is
ever written).
"""

# The internal registration-guard messages that must never reach the operator
# from the composition root. Each is raised by a core registry-slot accessor
# when its slot was not populated at application startup.
_REGISTRATION_LEAKS: tuple[str, ...] = (
    "Wizard catalogue has not been registered",
    "project_answers has not been registered",
    "profile keys are not registered",
)
_SECRET_STORE_FILES: tuple[str, ...] = (
    "master.key",
    "master.kdf",
    "salt",
    "master.recovery.key",
)


def _workspace_secret_store_fingerprint() -> dict[str, tuple[int, int] | None]:
    secret_root = REPO_ROOT / "var" / "secrets"
    fingerprint: dict[str, tuple[int, int] | None] = {}
    for filename in _SECRET_STORE_FILES:
        path = secret_root / filename
        if path.exists():
            stat = path.stat()
            fingerprint[filename] = (stat.st_size, stat.st_mtime_ns)
        else:
            fingerprint[filename] = None
    return fingerprint


def _run_cli_cold(storage_root: Path, argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Invoke the ``cadrumo`` CLI in a fresh interpreter against ``storage_root``.

    A new process guarantees an empty ``sys.modules``: the only path that can
    register the wizard catalogue is the root callback exercised by ``argv``.
    """

    code = f"""
        import sys

        sys.argv = ["cadrumo", *{argv!r}]
        from cadrumo.entrypoints.cli import main

        try:
            main()
        except SystemExit as exit_:
            raise SystemExit(exit_.code)
        """
    setting_env = str.upper
    base_settings = Settings.model_validate({})
    env = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
    env.update(
        {
            setting_env("cadrumo_local_storage_root"): str(storage_root),
            setting_env("cadrumo_secret_store_backend"): SecretStoreBackend.AUTO.value,
            setting_env(
                "cadrumo_secret_passphrase"
            ): base_settings.cadrumo_dev_test_database_password.get_secret_value(),
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


def _register_profile_for_cold_run(storage_root: Path, label: str, **facts: str) -> str:
    """Register one profile in-process against ``storage_root``, and return its id."""
    from ....core.config import load_settings, override_settings
    from ....tests.user_profile import register_cli_profile

    with override_settings(
        cadrumo_local_storage_root=storage_root,
        cadrumo_secret_store_backend=SecretStoreBackend.AUTO,
        cadrumo_secret_passphrase=load_settings().cadrumo_dev_test_database_password,
        cadrumo_active_profile=None,
    ):
        return register_cli_profile(label=label, facts=facts)


def test_cold_process_overview_status_without_profile_registers_profile_keys(tmp_path: Path) -> None:
    """A cold no-profile overview status renders a normal status report.

    `overview status` builds the shared state projection even before a
    profile exists. In a fresh interpreter no prior test has imported the
    wizard package, so the projection itself must ensure the profile-key
    registry is populated before any profile-key read.
    """

    result = _run_cli_cold(tmp_path, ["app", "overview", "status"])

    for leak in _REGISTRATION_LEAKS:
        assert leak not in result.stdout, (
            f"overview status surfaced an unregistered core slot: {leak!r}\n{result.stdout}"
        )
    assert "Internal." not in result.stdout
    assert "Traceback" not in result.stdout
    assert result.returncode == 0, (
        f"overview status failed in a cold no-profile process: {result.stdout}\n{result.stderr}"
    )
    assert "aeat config profile create NAME" in result.stdout


def test_cold_process_work_create_registers_wizard_catalogue(tmp_path: Path) -> None:
    """A cold ``app modelo work create`` registers the wizard catalogue itself.

    Profile creation runs in its own fresh process (writing the storage root);
    the work-create then runs in a *separate* fresh process whose only
    callback dispatch is the work-create. If the root callback does not
    register the wizard catalogue and project-answers projection, work-create
    raises the internal registration error instead of creating the unit.
    """

    workspace_secret_store_before = _workspace_secret_store_fingerprint()
    _register_profile_for_cold_run(
        tmp_path,
        "coldwiz",
        **{
            "identity.tax_id": "45678912S",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Cold",
            "identity.surnames": "Wizard",
            "activities.description": "Servicios",
        },
    )
    assert _workspace_secret_store_fingerprint() == workspace_secret_store_before

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


def test_cold_process_m100_2025_work_create_keeps_intracom_type_import_boundary(tmp_path: Path) -> None:
    """M100/2025 work-create must not crash importing invoice intracom types.

    The work-create path imports the CLI composition root in a cold process and
    then resolves the modelo source mesh. That transitively imports the invoice
    resolver, which consumes ``IntracomOperationType`` from its core enum home.
    A boundary regression previously surfaced as a raw ImportError before any
    user-facing refusal could be rendered.
    """

    _register_profile_for_cold_run(
        tmp_path,
        "empleada-arrendadora-2025",
        **{
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": "12345678Z",
            "identity.name": "Ana",
            "identity.surnames": "Empleada",
            "activities.description": "arrendamiento",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "irpf.estimation_regime": "directa_normal",
        },
    )

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
            "2025",
            "--period",
            "0A",
            "--revision",
            "2025",
            "--name",
            "empleada-arrendadora-2025",
            "--by",
            "Ana",
        ],
    )

    assert "ImportError" not in created.stdout
    assert "ImportError" not in created.stderr
    assert "cannot import name 'IntracomOperationType'" not in created.stdout
    assert "cannot import name 'IntracomOperationType'" not in created.stderr
    assert created.returncode == 0, f"work create failed in a cold process: {created.stdout}\n{created.stderr}"
    assert "operation\tmodelo.work.create" in created.stdout
    assert "status\tcreated" in created.stdout
