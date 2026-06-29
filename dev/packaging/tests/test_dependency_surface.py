"""Real-behavior tests for the dependency-surface packaging preflight."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from ..dependency_surface import _summary

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_dependency_surface_summary_names_runtime_optional_registry() -> None:
    """The summary must expose the capability-gated optional extras."""
    summary = _summary()

    assert summary["ok"] is True
    assert summary["registry_extras"] == ["anthropic", "browser", "google"]
    assert summary["project_dependency_count"] > 0
    assert summary["optional_dependency_count"] >= len(summary["registry_extras"])
    assert summary["dev_only_dependency_count"] > 0


def test_dependency_surface_cli_json_contract() -> None:
    """The module CLI must emit a stable machine-readable success summary."""
    result = subprocess.run(
        [sys.executable, "-m", "dev.packaging.dependency_surface", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["registry_extras"] == ["anthropic", "browser", "google"]
    assert payload["project_dependency_count"] > 0
    assert payload["dev_dependency_count"] >= payload["dev_only_dependency_count"] > 0
