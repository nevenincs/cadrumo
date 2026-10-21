"""Cold-process guard: the CLI composition root registers the wizard catalogue.

The profile-setup wizard catalogue (``SETUP_FLOW`` / ``WIZARD_FLOWS``) and the
project-answers projection are core registry slots that a domain module reaches
during ``app modelo work create``. They are populated by importing
:mod:`cadrumo.application.wizard.catalogue` and
:mod:`cadrumo.application.wizard.persistence` for their registration side effect.

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

import json
import subprocess
import sys
import textwrap
from collections.abc import Generator
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.core.config import load_settings, override_settings
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location
from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.tests.installed_process_ports import InstalledProcessWorld
from cadrumo.tests.inventory import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _owned_cold_runtime(tmp_path: Path, *, installed_process_world: InstalledProcessWorld) -> Generator[None]:
    """Serve the cold processes from their real runtime without importing their CLI."""
    scripts = Path(sys.prefix) / ("Scripts" if sys.platform == "win32" else "bin")
    executable = scripts / ("aeat.exe" if sys.platform == "win32" else "aeat")
    tmp_path.mkdir(parents=True, exist_ok=True)
    environment = installed_process_world.environment(
        storage_root=tmp_path, authority_root=bundled_authority_descriptor_path().parent
    )
    with installed_process_world.runtime(executable, environment, tmp_path.parent / "caller-owned-runtime.log"):
        try:
            yield
        finally:
            close_active_bucket_session()


# The newest Modelo 100 edition the registry authors.
_M100_REVIEWED_EDITION = newest_authored_edition("100")


# The internal registration-guard messages that must never reach the operator
# from the composition root. Each is raised by a core registry-slot accessor
# when its slot was not populated at application startup.
_REGISTRATION_LEAKS: tuple[str, ...] = (
    "Wizard catalogue has not been registered",
    "project_answers has not been registered",
)
_SECRET_STORE_FILES: tuple[str, ...] = (
    "master.key",
    "master.kdf",
    "salt",
    "master.recovery.key",
)


def _workspace_secret_store_fingerprint() -> dict[str, tuple[int, int] | None]:
    secret_root = REPO_ROOT / "var" / storage_location(StorageCategory.SECRETS).relative_path()
    fingerprint: dict[str, tuple[int, int] | None] = {}
    for filename in _SECRET_STORE_FILES:
        path = secret_root / filename
        if path.exists():
            stat = path.stat()
            fingerprint[filename] = (stat.st_size, stat.st_mtime_ns)
        else:
            fingerprint[filename] = None
    return fingerprint


def _run_cli_cold(
    storage_root: Path, argv: list[str], *, authenticate: bool = False, installed_process_world: InstalledProcessWorld
) -> subprocess.CompletedProcess[str]:
    """Invoke the ``cadrumo`` CLI in a fresh interpreter against ``storage_root``.

    A new process guarantees an empty ``sys.modules``: the only path that can
    register the wizard catalogue is the root callback exercised by ``argv``.
    """

    if authenticate:
        argv = ["--profile-secrets-stdin", *argv]
    code = f"""
        import sys

        sys.argv = ["aeat", *{argv!r}]
        from cadrumo_runtime.host.frontend.cli.bootstrap import main

        try:
            main()
        except SystemExit as exit_:
            raise SystemExit(exit_.code)
        """
    env = installed_process_world.environment(
        storage_root=storage_root, authority_root=bundled_authority_descriptor_path().parent
    )
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        input=(
            json.dumps({"profile_passphrase": load_settings().cadrumo_dev_test_database_password.get_secret_value()})
            if authenticate
            else None
        ),
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
        env=env,
    )


def _register_profile_for_cold_run(storage_root: Path, label: str, **facts: str) -> str:
    """Register one profile in-process against ``storage_root``, and return its id."""
    from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile

    with override_settings(
        cadrumo_local_storage_root=storage_root,
        cadrumo_active_profile=None,
    ):
        profile_id = register_cli_profile(label=label, facts=facts, log_in=False)
        close_active_bucket_session()
        return profile_id


def test_cold_process_overview_status_without_profile_resolves_profile_keys(
    tmp_path: Path, *, installed_process_world: InstalledProcessWorld
) -> None:
    """A cold no-profile overview returns the translated profile-creation action.

    `overview status` builds the shared state projection even before a
    profile exists. In a fresh interpreter no prior test has imported the
    wizard package, so the application profile-key catalogue must resolve on
    demand before any profile-key read.
    """

    result = _run_cli_cold(tmp_path, ["app", "overview", "status"], installed_process_world=installed_process_world)
    output = result.stdout + result.stderr

    for leak in _REGISTRATION_LEAKS:
        assert leak not in output, f"overview status surfaced an unregistered core slot: {leak!r}\n{output}"
    assert "Internal." not in output
    assert "Traceback" not in output
    assert result.returncode == 2, (
        f"overview status did not refuse a cold no-profile process: {result.stdout}\n{result.stderr}"
    )
    assert "aeat config profile create" in " ".join(output.split()), output


def test_cold_process_work_create_registers_wizard_catalogue(
    tmp_path: Path, *, installed_process_world: InstalledProcessWorld
) -> None:
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
        authenticate=True,
        installed_process_world=installed_process_world,
    )

    for leak in _REGISTRATION_LEAKS:
        assert leak not in created.stdout, f"work create surfaced an unregistered core slot: {leak!r}\n{created.stdout}"
    assert created.returncode == 0, f"work create failed in a cold process: {created.stdout}\n{created.stderr}"


def test_cold_process_m100_work_create_keeps_intracom_type_import_boundary(
    tmp_path: Path, *, installed_process_world: InstalledProcessWorld
) -> None:
    """M100 work-create must not crash importing invoice intracom types.

    The work-create path imports the CLI composition root in a cold process and
    then resolves the modelo source mesh. That transitively imports the invoice
    resolver, which consumes ``IntracomOperationType`` from its core enum home.
    A boundary regression previously surfaced as a raw ImportError before any
    user-facing refusal could be rendered.
    """

    edition = str(_M100_REVIEWED_EDITION)
    _register_profile_for_cold_run(
        tmp_path,
        f"empleada-arrendadora-{edition}",
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
            edition,
            "--period",
            "0A",
            "--revision",
            edition,
            "--name",
            f"empleada-arrendadora-{edition}",
            "--by",
            "Ana",
        ],
        authenticate=True,
        installed_process_world=installed_process_world,
    )

    assert "ImportError" not in created.stdout
    assert "ImportError" not in created.stderr
    assert "cannot import name 'IntracomOperationType'" not in created.stdout
    assert "cannot import name 'IntracomOperationType'" not in created.stderr
    assert created.returncode == 0, f"work create failed in a cold process: {created.stdout}\n{created.stderr}"
    assert "operation\tmodelo.work.create" in created.stdout
    assert "status\tcreated" in created.stdout
