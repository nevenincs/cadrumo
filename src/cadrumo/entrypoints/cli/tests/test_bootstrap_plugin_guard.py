"""The console host disables pydantic's plugin scan without overriding an operator.

Pydantic walks every installed distribution's entry points on its first model
build. Cadrumo ships no pydantic plugin, so every process pays that walk for
nothing, and a third-party plugin would observe taxpayer models. The host sets
the disabling default itself; an operator who exports their own value keeps it.
"""

from __future__ import annotations

import os
import sys

import pytest

from cadrumo.tests.audited_process import run_audited_process

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_VARIABLE = "PYDANTIC_DISABLE_PLUGINS"

_PROBE = """
import os, sys

import cadrumo.entrypoints.cli.bootstrap as bootstrap

sys.argv = ["aeat", "--version"]
try:
    bootstrap.main()
except SystemExit:
    pass
print("VALUE=" + os.environ.get("PYDANTIC_DISABLE_PLUGINS", "<unset>"), file=sys.stderr)
"""


def _probe_value(preset: str | None) -> str:
    environment = {key: value for key, value in os.environ.items() if key != _VARIABLE}
    if preset is not None:
        environment[_VARIABLE] = preset
    completed = run_audited_process(
        [sys.executable, "-c", _PROBE],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    stderr = str(completed.stderr)
    line = next(part for part in stderr.splitlines() if part.startswith("VALUE="))
    return line.removeprefix("VALUE=")


def test_the_console_host_disables_the_plugin_scan_by_default() -> None:
    assert _probe_value(None) == "__all__"


def test_an_operator_value_survives_the_host_default() -> None:
    assert _probe_value("logfire") == "logfire"
