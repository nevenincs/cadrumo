"""Real-command coverage for Docker packaging-smoke backend selection."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

from dev.packaging.smoke_docker import (
    _command_succeeds,
    _docker_cli,
    _preflight_docker,
    _wsl_docker_cli_available,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_command_success_probe_observes_real_exit_status() -> None:
    """Selection probes distinguish real successful and failing child processes."""
    assert _command_succeeds([sys.executable, "-c", "raise SystemExit(0)"])
    assert not _command_succeeds([sys.executable, "-c", "raise SystemExit(7)"])


def test_docker_backend_selection_reaches_the_real_healthy_daemon() -> None:
    """The selected local backend answers the same daemon preflight used by the smoke."""
    docker = _docker_cli()

    if os.name == "nt":
        wsl = shutil.which("wsl")
        distro = os.environ.get("CADRUMO_WSL_DOCKER_DISTRO", "Ubuntu")
        assert wsl is not None
        assert _wsl_docker_cli_available(wsl, distro)
        assert docker.label == f"wsl:{distro}"
        assert docker.wsl_distro == distro
    else:
        assert docker.label == "native"
        assert docker.wsl_distro is None

    _preflight_docker(docker)


def test_configured_wsl_docker_command_executes_without_windows_fallback() -> None:
    """The selected WSL prefix executes Docker directly in its configured distro."""
    if os.name != "nt":
        assert _docker_cli().label == "native"
        return

    docker = _docker_cli()
    result = subprocess.run(  # noqa: S603 - executes the production-selected, real Docker backend.
        [*docker.argv_prefix, "--version"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert docker.label.startswith("wsl:")
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("Docker version ")
