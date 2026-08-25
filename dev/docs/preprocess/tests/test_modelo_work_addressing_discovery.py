"""Resident-service discovery gate for the canonical Modelo work-addressing owner."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.resident_service]
_ROOT = Path(__file__).resolve().parents[4]


def test_rag_discovery_returns_the_canonical_owner() -> None:
    status_dir = Path(os.environ["_VAULTSPEC_RAG_PYTEST_SINGLETON_ROOT"]) / "modelo-addressing-client"
    status_dir.mkdir()
    command = ("uv", "tool", "run", "--from", "vaultspec-rag==0.4.2", "vaultspec-rag")
    version = subprocess.run(  # noqa: S603
        (*command, "--version"),
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert version.returncode == 0, version.stderr
    assert "0.4.2" in version.stdout, version.stdout
    result = subprocess.run(  # noqa: S603
        (
            *command,
            "--status-dir",
            str(status_dir),
            "search",
            "Modelo work-unit selector repository wrapper natural catalogue scan facade import",
            "--type",
            "code",
            "--port",
            "8766",
            "--timeout",
            "45.0",
            "--json",
        ),
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response.get("ok") is True, response
    assert any(
        "application/modelo/work_addressing.py" in str(hit.get("path", "")).replace("\\", "/")
        for hit in response.get("data", {}).get("results", [])
    )
