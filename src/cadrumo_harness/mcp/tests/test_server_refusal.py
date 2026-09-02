"""The MCP server refuses gracefully when the harness runtime is incomplete.

The refusal contract is tested directly via :func:`emit_missing_sdk_refusal`, so
the test is environment-independent (no skip) whether or not the MCP SDK happens
to be installed in the running environment.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from .._server import emit_missing_sdk_refusal

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_missing_sdk_refusal_exits_non_zero_with_install_hint(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        emit_missing_sdk_refusal()
    assert exc.value.code == 3
    captured = capsys.readouterr()
    assert captured.err == (
        "the MCP server is provided by the cadrumo-harness distribution: "
        "pip install cadrumo-harness; launch it with cadrumo-mcp\n"
    )


def test_installed_service_refuses_a_plugin_requiring_another_cohort_version() -> None:
    """The real console script fails closed before opening the MCP transport."""
    executable = shutil.which("cadrumo-mcp")
    assert executable is not None
    completed = subprocess.run(  # noqa: S603 - installed project console script
        [executable],
        env={**os.environ, "CADRUMO_MCP_REQUIRED_VERSION": "999.0.0"},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 4
    assert completed.stdout == ""
    assert "required 999.0.0" in completed.stderr
    assert "version mismatch: cadrumo=" in completed.stderr
    assert "cadrumo-data-manuals=" in completed.stderr
    assert "cadrumo-data-official=" in completed.stderr
    assert completed.stderr.endswith(
        "pip install cadrumo-harness==999.0.0 cadrumo==999.0.0 "
        "cadrumo-data-manuals==999.0.0 cadrumo-data-official==999.0.0\n"
    )
