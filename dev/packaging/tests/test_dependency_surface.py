"""Real-behavior tests for the dependency-surface packaging preflight."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from .._smoke_common import find_repo_root, pyproject_surfaces
from ..dependency_surface import _summary

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


#: Floors, not pinned counts, with the live figures recorded: the project
#: declares 31 runtime dependencies and 51 development-only ones. `> 0` let
#: a reader that parsed one dependency table and stopped report success.
_MINIMUM_PROJECT_DEPENDENCIES = 20
_MINIMUM_DEV_ONLY_DEPENDENCIES = 35


def test_dependency_surface_summary_names_runtime_optional_registry() -> None:
    """The summary must expose the capability-gated optional extras."""
    summary = _summary()

    assert summary["ok"] is True
    assert summary["registry_extras"] == ["anthropic", "browser", "google", "llm", "ofx"]
    assert summary["project_dependency_count"] > _MINIMUM_PROJECT_DEPENDENCIES, summary
    assert summary["optional_dependency_count"] >= len(summary["registry_extras"])
    assert summary["dev_only_dependency_count"] > _MINIMUM_DEV_ONLY_DEPENDENCIES, summary


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
    assert payload["registry_extras"] == ["anthropic", "browser", "google", "llm", "ofx"]
    assert payload["project_dependency_count"] > _MINIMUM_PROJECT_DEPENDENCIES, payload
    # Split from a chained comparison, which read as one claim but carried a
    # `> 0` floor inside it that was easy to miss.
    assert payload["dev_dependency_count"] >= payload["dev_only_dependency_count"]
    assert payload["dev_only_dependency_count"] > _MINIMUM_DEV_ONLY_DEPENDENCIES, payload


def test_dependency_surface_expands_included_registry_group() -> None:
    """The default dev install includes the direct registry tooling group."""
    surfaces = pyproject_surfaces(find_repo_root())

    assert {"grimp"} <= surfaces.dev_only_names
