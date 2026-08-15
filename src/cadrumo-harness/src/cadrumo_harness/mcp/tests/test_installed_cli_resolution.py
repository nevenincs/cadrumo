"""Installed MCP subprocess resolution is independent of checkout and ``PATH``.

This is a real distribution test, not an in-process unit test. It builds the
committed three-wheel cohort, installs ``cadrumo[agent]`` into a fresh stdlib
virtual environment, launches that environment's absolute ``cadrumo-mcp``
console script outside the checkout, removes product scripts and ``PYTHONPATH``
from the child environment, and completes the public grounded Modelo 200 MCP
itinerary through the direct calculation tool and observation resource.

The call can succeed only if the installed server resolves and executes the
``aeat`` console script beside itself. A source import, ambient executable, or
checkout shim cannot satisfy the probe.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from dev.packaging._smoke_common import (
    build_companion_wheels,
    build_wheel,
    create_pip_venv,
    head_extract,
    run_checked,
    venv_bin_dir,
    venv_python_path,
)
from dev.packaging.installed_mcp_oracle import run_installed_mcp_oracle
from dev.packaging.installed_tax_oracle import EXPECTED_LEGAL_REF

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_REPO_ROOT = Path(__file__).resolve().parents[6]


def _installed_script(venv: Path, name: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return (venv_bin_dir(venv) / f"{name}{suffix}").resolve()


@pytest.fixture(scope="module")
def installed_agent_environment(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Build and install one committed command/data/agent cohort."""
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to build the real installed cohort"

    work_dir = tmp_path_factory.mktemp("installed-mcp-cli-resolution")
    build_root = head_extract(_REPO_ROOT, work_dir)
    root_wheel = build_wheel(_REPO_ROOT, work_dir, uv, build_root=build_root)
    data_wheels = build_companion_wheels(work_dir, uv, build_root=build_root)
    venv = create_pip_venv(work_dir, f"{sys.version_info.major}.{sys.version_info.minor}")
    run_checked(
        [
            str(venv_python_path(venv)),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            f"{root_wheel.resolve()}[agent]",
            *(str(wheel.resolve()) for wheel in data_wheels),
        ],
        cwd=work_dir,
    )
    run_checked([str(venv_python_path(venv)), "-m", "pip", "check"], cwd=work_dir)

    mcp_server = _installed_script(venv, "cadrumo-mcp")
    cli = _installed_script(venv, "aeat")
    assert mcp_server.is_file()
    assert cli.is_file()
    return work_dir, mcp_server


def test_installed_mcp_executes_sibling_cli_without_checkout_or_path(
    installed_agent_environment: tuple[Path, Path],
) -> None:
    work_dir, mcp_server = installed_agent_environment
    evidence = run_installed_mcp_oracle(
        mcp_server,
        storage_root=work_dir / "product-state",
        work_dir=work_dir / "outside-checkout",
        timeout_seconds=240.0,
    )

    assert Path(evidence.resolved_executable) == mcp_server
    assert evidence.target_casilla == "DP200014:00562"
    assert evidence.target_value == "23000.00"
    assert evidence.formula_id == "modelo-200-cuota-integra"
    assert EXPECTED_LEGAL_REF in evidence.legal_refs
    assert evidence.observations_resource == f"cadrumo://observations/{evidence.calculation_revision_id}"
    assert any(
        call.tool_name == "cadrumo_modelo_work_calculate" and call.command_key == "modelo.work.calculate"
        for call in evidence.calls
    )
