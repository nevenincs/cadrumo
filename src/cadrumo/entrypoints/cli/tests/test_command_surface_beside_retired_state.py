"""The command surface builds on a machine that still carries retired ``aeat`` state.

Describing the commands reads the published registry -- a modelo parameter's
choice set is the authority's own modelo list -- and no taxpayer storage, so it
must not stop at the storage root's refusal. The MCP server builds its tools
from exactly this manifest, which is why a refusal here kept it from starting.
A command that touches storage or profile state still refuses on the same
machine, and the retired state is never touched.

Each case runs in a fresh interpreter: the refusal comes from state fixed
before the process starts, which an in-process invocation sharing this
interpreter's settings and authority cannot observe.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ....core.config_state_root import StateRootInputs, platform_user_data_root
from ....domain.calculations.registry.authority import bundled_indexed_authority
from .subprocess_cli import run_subprocess_cli_harness

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CONSOLE_HARNESS = """
import sys

sys.argv = ["aeat", *sys.argv[1:]]

from cadrumo.entrypoints.cli.bootstrap import main

main()
"""
_RETIRED_MARKER = b"retired-aeat-state-must-remain"
#: Every ``CADRUMO_`` variable is withheld, as on an upgrader's machine: the
#: storage root must come from the platform default. The shared harness still
#: carries the session's authority root through, because a checkout has no
#: packaged authority to fall back to.
_STRIPPED_PREFIXES = ("AEAT_", "PYTEST_", "CADRUMO_")


def _platform_beside_retired_state(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """Return a child environment whose platform data root sits beside retired ``aeat`` state."""
    environment = {
        "LOCALAPPDATA": str(tmp_path / "platform-data"),
        "XDG_DATA_HOME": str(tmp_path / "platform-data"),
        "HOME": str(tmp_path / "home"),
    }
    inputs = StateRootInputs(platform=sys.platform, environ=environment, home=Path(environment["HOME"]))
    retired = platform_user_data_root(inputs).parent / "aeat"
    retired.mkdir(parents=True)
    (retired / "custody-marker.bin").write_bytes(_RETIRED_MARKER)
    return environment, retired


def _assert_retired_state_untouched(retired: Path) -> None:
    assert sorted(entry.name for entry in retired.iterdir()) == ["custody-marker.bin"]
    assert (retired / "custody-marker.bin").read_bytes() == _RETIRED_MARKER


def test_the_command_surface_manifest_carries_the_published_modelos_beside_retired_state(tmp_path: Path) -> None:
    environment, retired = _platform_beside_retired_state(tmp_path)
    with bundled_indexed_authority().operation() as operation:
        published_modelos = sorted(operation.modelo_ids())

    completed = run_subprocess_cli_harness(
        _CONSOLE_HARNESS,
        ["--cadrumo-command-surface"],
        env_strip_prefixes=_STRIPPED_PREFIXES,
        extra_env=environment,
        cwd=tmp_path,
        timeout=300.0,
    )

    assert completed.returncode == 0, completed.stderr[-4000:]
    manifest = json.loads(completed.stdout)
    modelo = next(
        parameter
        for parameter in manifest["input_schemas"]["modelo.history"]["parameters"]
        if parameter["name"] == "modelo"
    )
    assert modelo["choices"] == published_modelos
    _assert_retired_state_untouched(retired)


def test_a_storage_command_still_refuses_beside_retired_state(tmp_path: Path) -> None:
    environment, retired = _platform_beside_retired_state(tmp_path)

    completed = run_subprocess_cli_harness(
        _CONSOLE_HARNESS,
        ["config", "profile", "list"],
        env_strip_prefixes=_STRIPPED_PREFIXES,
        extra_env={**environment, "CADRUMO_OUTPUT_LANGUAGE": "en"},
        cwd=tmp_path,
        timeout=300.0,
    )

    combined = f"{completed.stdout}\n{completed.stderr}"
    assert completed.returncode != 0, combined
    assert "Traceback" not in combined
    assert "incompatible retired `aeat` state" in combined
    assert "storage.former_product_state.absent" in combined
    _assert_retired_state_untouched(retired)
