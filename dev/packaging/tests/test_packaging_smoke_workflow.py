"""Structural gate for the Cadrumo packaging-smoke GitHub workflow."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "packaging-smoke.yml"


def test_workflow_runs_canonical_cadrumo_packaging_gates() -> None:
    """The real workflow retains the core, split-distribution, and Docker gates."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert document["name"] == "Cadrumo Packaging Smoke"
    assert set(document["jobs"]) == {"cadrumo-packaging-smoke"}

    job = document["jobs"]["cadrumo-packaging-smoke"]
    assert job["name"] == "Cadrumo / Ubuntu / Python 3.13 / wheel artifacts"
    commands = {step["run"] for step in job["steps"] if "run" in step}
    assert {
        "just packaging-smoke-linux",
        "just packaging-smoke-split",
        "just packaging-smoke-docker",
    } <= commands


def test_workflow_evidence_and_product_identity_are_cadrumo_only() -> None:
    """Product-facing labels and uploaded evidence use no former product identity."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    job = document["jobs"]["cadrumo-packaging-smoke"]
    upload = next(step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/upload-artifact@"))

    assert upload["name"] == "Upload Cadrumo packaging smoke evidence"
    assert upload["with"]["name"] == "cadrumo-packaging-smoke-evidence"
    assert upload["with"]["path"] == "var/packaging-smoke/**/packaging-smoke-manifest.json"

    product_surface = "\n".join(
        (
            document["name"],
            job["name"],
            *(step.get("name", "") for step in job["steps"]),
            *(step.get("run", "") for step in job["steps"]),
            upload["with"]["name"],
        ),
    ).casefold()
    assert "aeat" not in product_surface
