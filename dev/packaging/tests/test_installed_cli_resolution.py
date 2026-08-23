"""Installed MCP subprocess resolution is independent of checkout and ``PATH``.

This is a real distribution test, not an in-process unit test. It builds the
committed closed-world wheel cohort including the exact ``cadrumo-harness`` wheel (the
retired ``cadrumo[agent]`` extra no longer exists, so the harness installs as
its own distribution), installs them into a fresh stdlib virtual environment,
launches that environment's absolute ``cadrumo-mcp`` console script outside
the checkout, removes product scripts and ``PYTHONPATH`` from the child
environment, and completes the public grounded Modelo 200 MCP itinerary
through the direct calculation tool and observation resource.

The call can succeed only if the installed server resolves and executes the
``aeat`` console script beside itself. A source import, ambient executable, or
checkout shim cannot satisfy the probe.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.packaging._hashing import sha256_path
from dev.packaging._smoke_common import (
    build_companion_wheels,
    build_harness_wheel,
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

_REPO_ROOT = REPO_ROOT


def _installed_script(venv: Path, name: str) -> Path:
    suffix = ".exe" if sys.platform == "win32" else ""
    return (venv_bin_dir(venv) / f"{name}{suffix}").resolve()


@pytest.fixture(scope="module")
def installed_agent_environment(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Path, str, str, str, str]:
    """Build and install one committed command/data/harness cohort."""
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to build the real installed cohort"

    work_dir = tmp_path_factory.mktemp("installed-mcp-cli-resolution")
    build_root = head_extract(_REPO_ROOT, work_dir)
    root_wheel = build_wheel(_REPO_ROOT, work_dir, uv, build_root=build_root)
    data_wheels = build_companion_wheels(work_dir, uv, build_root=build_root)
    harness_wheel = build_harness_wheel(work_dir, uv, build_root=build_root)
    venv = create_pip_venv(work_dir, f"{sys.version_info.major}.{sys.version_info.minor}")
    run_checked(
        [
            str(venv_python_path(venv)),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            str(root_wheel.resolve()),
            str(harness_wheel.resolve()),
            *(str(wheel.resolve()) for wheel in data_wheels),
        ],
        cwd=work_dir,
    )
    run_checked([str(venv_python_path(venv)), "-m", "pip", "check"], cwd=work_dir)

    mcp_server = _installed_script(venv, "cadrumo-mcp")
    cli = _installed_script(venv, "aeat")
    assert mcp_server.is_file()
    assert cli.is_file()
    source_commit = run_checked(["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT).stdout.strip()
    root_sha256 = sha256_path(root_wheel)
    harness_sha256 = sha256_path(harness_wheel)
    capture_manifest = work_dir / "capture-cohort.json"
    capture_manifest.write_text(
        json.dumps(
            {
                "source_commit": source_commit,
                "cadrumo-wheel": root_sha256,
                "cadrumo-harness-wheel": harness_sha256,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return work_dir, mcp_server, source_commit, sha256_path(capture_manifest), root_sha256, harness_sha256


def test_installed_mcp_executes_sibling_cli_without_checkout_or_path(
    installed_agent_environment: tuple[Path, Path, str, str, str, str],
) -> None:
    work_dir, mcp_server, source_commit, manifest_sha256, root_sha256, harness_sha256 = installed_agent_environment
    evidence = run_installed_mcp_oracle(
        mcp_server,
        storage_root=work_dir / "product-state",
        work_dir=work_dir / "outside-checkout",
        cohort_source_commit=source_commit,
        cohort_manifest_sha256=manifest_sha256,
        cohort_root_wheel_sha256=root_sha256,
        cohort_harness_wheel_sha256=harness_sha256,
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
