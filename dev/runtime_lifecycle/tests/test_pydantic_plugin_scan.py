"""Cadrumo's console entries switch pydantic plugin discovery off before it can scan.

Pydantic reads the entry-point metadata of every installed distribution on its first model build
unless ``PYDANTIC_DISABLE_PLUGINS`` is set. Each case runs a real entry in a fresh interpreter, then
builds a model and counts the ``entry_points.txt`` files opened through an audit hook. The explicit
value case proves the hook sees a scan, so a zero count is evidence rather than blindness.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from cadrumo.core.pydantic_plugins import PYDANTIC_PLUGINS_DISABLED, PYDANTIC_PLUGINS_VARIABLE

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_ENTRIES = {
    "aeat": ("cadrumo_runtime.host.frontend.cli.bootstrap", "main"),
    "cadrumo-mcp": ("cadrumo_mcp.mcp.main", "main"),
    "cadrumo-agent-service": ("cadrumo_agent_service.bootstrap", "main"),
}


def _run_entry(entry: str, storage_root: Path, *, explicit: str | None) -> tuple[int, int, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key != PYDANTIC_PLUGINS_VARIABLE and not key.upper().startswith("PYTHON")
    }
    environment["CADRUMO_STORAGE_ROOT"] = str(storage_root)
    if explicit is not None:
        environment[PYDANTIC_PLUGINS_VARIABLE] = explicit
    module, function = _ENTRIES[entry]
    environment["PROBE_MODULE"] = module
    environment["PROBE_FUNCTION"] = function
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import importlib
import os
import sys

opened = []


def watch(event, args):
    if event == "open" and str(args[0]).endswith("entry_points.txt"):
        opened.append(args[0])


sys.addaudithook(watch)
module_name = os.environ.pop("PROBE_MODULE")
function_name = os.environ.pop("PROBE_FUNCTION")
sys.argv = [module_name, "--help"]
try:
    getattr(importlib.import_module(module_name), function_name)()
except SystemExit:
    pass
before_model = len(opened)
from pydantic import BaseModel


class Probe(BaseModel):
    value: int


Probe(value=1)
print(before_model, len(opened) - before_model, os.environ.get("PYDANTIC_DISABLE_PLUGINS", "<unset>"))
""",
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    scans_during_entry, scans_at_model_build, value = completed.stdout.splitlines()[-1].split()
    return int(scans_during_entry), int(scans_at_model_build), value


@pytest.mark.parametrize("entry", sorted(_ENTRIES))
def test_entry_disables_plugin_discovery_before_the_first_model_build(entry: str, tmp_path: Path) -> None:
    during_entry, at_model_build, value = _run_entry(entry, tmp_path, explicit=None)

    assert value == PYDANTIC_PLUGINS_DISABLED
    assert at_model_build == 0
    assert during_entry == 0


@pytest.mark.parametrize("entry", sorted(_ENTRIES))
def test_entry_keeps_an_explicit_operator_value_and_the_scan_it_asks_for(entry: str, tmp_path: Path) -> None:
    during_entry, at_model_build, value = _run_entry(entry, tmp_path, explicit="0")

    assert value == "0"
    assert during_entry + at_model_build > 0
