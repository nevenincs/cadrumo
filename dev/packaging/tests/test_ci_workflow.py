"""Structural behavior gate for the Cadrumo CI workflow."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"


def test_ci_workflow_runs_canonical_cadrumo_commands_and_paths() -> None:
    """The real workflow invokes Cadrumo entry points over the Cadrumo source root."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert document["name"] == "Cadrumo CI"
    assert set(document["jobs"]) == {"cadrumo-lint-and-test"}

    job = document["jobs"]["cadrumo-lint-and-test"]
    assert job["name"] == "Cadrumo / ${{ matrix.os }} / Python ${{ matrix.python-version }}"
    commands = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "uv run --no-sync cadrumo app registry verify --json" in commands
    assert "uv run --no-sync cadrumo app registry audit-oracles --json" in commands
    assert "semgrep --config .semgrep/rules/ --error src/cadrumo/" in commands


def test_ci_workflow_product_surface_has_no_former_identity() -> None:
    """Product-facing CI labels and commands contain no former product name."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    job = document["jobs"]["cadrumo-lint-and-test"]
    product_surface = "\n".join(
        (
            document["name"],
            job["name"],
            *(str(step.get("name", "")) for step in job["steps"]),
            *(str(step.get("run", "")) for step in job["steps"]),
        ),
    ).casefold()
    assert "aeat" not in product_surface
