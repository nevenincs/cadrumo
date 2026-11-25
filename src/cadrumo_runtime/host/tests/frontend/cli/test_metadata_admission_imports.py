"""The installed CLI keeps admission out of metadata-only invocations."""

from pathlib import Path
from textwrap import dedent

import pytest

from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location
from cadrumo.tests.subprocess_cli import run_subprocess_cli_harness

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    "arguments",
    [
        ("--version",),
        ("--version", "--detail"),
        ("--help",),
        ("app", "--help"),
        ("--language", "en", "config", "profile", "view", "--help"),
    ],
)
def test_installed_metadata_commands_do_not_load_admission(arguments: tuple[str, ...], tmp_path: Path) -> None:
    """Exercise the host bootstrap, not only the product's uninjected command tree."""
    storage_root = tmp_path / "storage"
    completed = run_subprocess_cli_harness(
        dedent(
            """
            import sys
            from cadrumo_runtime.host.frontend.cli.bootstrap import main

            try:
                main()
            except SystemExit as error:
                assert error.code in (0, None), error.code

            forbidden = (
                'cadrumo_client.commands.profile_admission',
                'cadrumo_client.commands.profile_selection',
                'cadrumo_client.transport.installed_client',
                'cadrumo_client.transport.installation_client',
            )
            loaded = [name for name in forbidden if name in sys.modules]
            assert not loaded, loaded
            print('metadata-without-admission')
            """
        ),
        arguments,
        env_strip_prefixes=("AEAT_", "PYTEST_", "CADRUMO_"),
        extra_env={"CADRUMO_STORAGE_ROOT": str(storage_root)},
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    output = completed.stdout.strip().splitlines()
    assert len(output) > 1, completed.stdout
    assert output[-1] == "metadata-without-admission"
    # The only state a metadata invocation touches is the scratch member it
    # removes again; no profile, secret or database file is created.
    temporary = storage_root / storage_location(StorageCategory.TEMPORARY_FILES).relative_path()
    assert sorted(storage_root.rglob("*")) == [temporary]
