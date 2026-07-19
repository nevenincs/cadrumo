"""Structural gate for the Cadrumo packaging-smoke GitHub workflow."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "packaging-smoke.yml"
_SHELL_COMMAND_BOUNDARY = r"(?:^|[\r\n]|&&|\|\||[;|])"
_ENVIRONMENT_PREFIX = r"(?:(?:env\s+)?(?:[A-Za-z_]\w*=(?:[^\s;&|]+|\"[^\"]*\"|'[^']*')\s+)+)"
_UV_RUN_PREFIX = r"(?:uv\s+run(?:\s+--[a-z][\w-]*(?:=(?:[^\s;&|]+|\"[^\"]*\"|'[^']*'))?)*\s+)?"
_PROHIBITED_CADRUMO_HUMAN_COMMAND = re.compile(
    rf"(?im){_SHELL_COMMAND_BOUNDARY}[ \t]*(?:{_ENVIRONMENT_PREFIX})?{_UV_RUN_PREFIX}cadrumo(?=\s|$|[;&|])",
)
_PROHIBITED_AEAT_PRODUCT_FORMS = (
    (
        "python-import",
        re.compile(
            r"""(?i)\b(?:from\s+aeat(?:\.|\s+import\b)|import\s+(?:[a-z_]\w*(?:\.[a-z_]\w*)*\s*,\s*)*aeat(?:\.|(?=\s|$|[;"'])))""",
        ),
    ),
    (
        "python-module",
        re.compile(r"(?i)\bpython(?:\d+(?:\.\d+)*)?\s+-m\s+aeat(?:\.[a-z_]\w*)*(?=\s|$)"),
    ),
    (
        "distribution-install",
        re.compile(
            r"""(?i)\b(?:(?:uv\s+)?pip\s+install|uv\s+add)\b[^&|;\r\n]*?(?<![\w-])aeat(?=\[|\s|$|[<>=!~@;"'])""",
        ),
    ),
    (
        "former-distribution",
        re.compile(r"(?i)(?<![\w-])aeat(?:-cli|-data(?:-[\w-]+)?|_data(?:_[\w-]+)?)(?![\w-])"),
    ),
    (
        "former-source-path",
        re.compile(r"(?i)(?<![\w])(?:src|packaging)[/\\]aeat(?:[/\\_.-]|$)"),
    ),
)


def _prohibited_aeat_product_forms(surface: str) -> tuple[str, ...]:
    """Return prohibited former-product form families present in ``surface``."""
    return tuple(label for label, pattern in _PROHIBITED_AEAT_PRODUCT_FORMS if pattern.search(surface))


# The Windows and macOS legs prove the python-windows-x86-64 and
# python-macos-arm64 distribution rows on native SELF-HOSTED runners (operator
# cost directive 2026-07-19: hosted minutes bill, the operator's own machines
# are free; the label sets are the runner registration contract). Each runs the
# host-portable `packaging-smoke` aggregate (no Docker, no host package-manager
# lanes) and uploads per-OS artifacts so names never collide with the Ubuntu leg.
_PORTABLE_LEGS: dict[str, dict[str, object]] = {
    "cadrumo-packaging-smoke-windows": {
        "name": "Cadrumo / Windows / Python 3.13 / wheel artifacts",
        "runs_on": ["self-hosted", "Windows", "X64"],
        "cohort_artifact": "cadrumo-python-cohort-windows",
        "evidence_artifact": "cadrumo-packaging-smoke-evidence-windows",
    },
    "cadrumo-packaging-smoke-macos": {
        "name": "Cadrumo / macOS / Python 3.13 / wheel artifacts",
        "runs_on": ["self-hosted", "macOS", "ARM64"],
        "cohort_artifact": "cadrumo-python-cohort-macos",
        "evidence_artifact": "cadrumo-packaging-smoke-evidence-macos",
    },
}


def _run_command_lines(job: dict[str, object]) -> set[str]:
    """Return every non-empty command line across the job's run scripts.

    A step's ``run`` may be a multi-line script (the campaign step wraps the
    canonical aggregate invocation with a resource sampler), so the canonical
    command contract is asserted line-wise rather than against whole scripts.
    """
    steps = job["steps"]
    assert isinstance(steps, list)
    return {
        line.strip()
        for step in steps
        if isinstance(step, dict)
        for line in str(step.get("run", "")).splitlines()
        if line.strip()
    }


def test_workflow_runs_canonical_cadrumo_packaging_gates() -> None:
    """One Ubuntu aggregate plus native Windows/macOS host-portable legs."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert document["name"] == "Cadrumo Packaging Smoke"
    assert set(document["jobs"]) == {"cadrumo-packaging-smoke", *_PORTABLE_LEGS}

    job = document["jobs"]["cadrumo-packaging-smoke"]
    assert job["name"] == "Cadrumo / Ubuntu / Python 3.13 / wheel artifacts"
    assert job["runs-on"] == ["self-hosted", "Linux", "X64"]
    commands = _run_command_lines(job)
    assert {
        "just packaging-smoke-ci",
        "uv run --no-sync python -m dev.packaging.evidence",
    } <= commands
    assert "just packaging-smoke-linux" not in commands
    assert "just packaging-smoke-split" not in commands
    assert "just packaging-smoke-docker" not in commands

    for key, spec in _PORTABLE_LEGS.items():
        leg = document["jobs"][key]
        assert leg["name"] == spec["name"]
        assert leg["runs-on"] == spec["runs_on"]
        leg_commands = _run_command_lines(leg)
        # The portable legs run the host-portable aggregate and the same
        # evidence checkpoint, and never the Ubuntu-only CI / Docker / Linux
        # lanes (Docker is ubuntu-only; the browser-linux lane installs host
        # system deps). `just packaging-smoke` is an exact run line here, not a
        # prefix of `just packaging-smoke-ci`.
        assert {
            "just packaging-smoke",
            "uv run --no-sync python -m dev.packaging.evidence",
        } <= leg_commands
        assert "just packaging-smoke-ci" not in leg_commands
        assert "just packaging-smoke-linux" not in leg_commands
        assert "just packaging-smoke-docker" not in leg_commands
        # The Linux-only disk reclamation and bash resource sampler never run on
        # the portable legs.
        assert not any(step.get("name") == "Reclaim runner disk space" for step in leg["steps"])


def test_workflow_evidence_and_product_identity_follow_the_binding_tuple() -> None:
    """Labels use Cadrumo, artifacts use cadrumo, and commands keep the aeat boundary."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    job = document["jobs"]["cadrumo-packaging-smoke"]
    uploads = [step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/upload-artifact@")]
    upload = next(step for step in uploads if step["with"]["name"] == "cadrumo-packaging-smoke-evidence")
    cohort_upload = next(step for step in uploads if step["with"]["name"] == "cadrumo-python-cohort")
    campaign = next(step for step in job["steps"] if "just packaging-smoke-ci" in str(step.get("run", "")))
    checkpoint = next(
        step for step in job["steps"] if step.get("run") == "uv run --no-sync python -m dev.packaging.evidence"
    )

    assert upload["name"] == "Upload Cadrumo packaging smoke evidence"
    assert upload["with"]["name"] == "cadrumo-packaging-smoke-evidence"
    assert upload["with"]["path"].splitlines() == [
        "var/packaging-smoke-evidence/*.json",
        "var/distribution-install-readiness/installed-cohorts/**/evidence.json",
    ]
    assert cohort_upload["with"]["path"] == "var/packaging-smoke-cohort/python/"
    assert cohort_upload["with"]["if-no-files-found"] == "error"
    assert checkpoint["if"] == "always()"
    assert upload["if"] == "always()"
    assert job["steps"].index(campaign) < job["steps"].index(checkpoint)
    assert job["steps"].index(checkpoint) < job["steps"].index(cohort_upload)
    assert job["steps"].index(cohort_upload) < job["steps"].index(upload)

    # Each portable leg carries its own campaign, evidence checkpoint, and
    # per-OS uploads in the same campaign -> checkpoint -> cohort -> evidence
    # order, with the exact same evidence path shape as the Ubuntu leg.
    for key, spec in _PORTABLE_LEGS.items():
        leg = document["jobs"][key]
        leg_uploads = [s for s in leg["steps"] if str(s.get("uses", "")).startswith("actions/upload-artifact@")]
        leg_cohort = next(s for s in leg_uploads if s["with"]["name"] == spec["cohort_artifact"])
        leg_evidence = next(s for s in leg_uploads if s["with"]["name"] == spec["evidence_artifact"])
        leg_campaign = next(s for s in leg["steps"] if s.get("run") == "just packaging-smoke")
        leg_checkpoint = next(
            s for s in leg["steps"] if s.get("run") == "uv run --no-sync python -m dev.packaging.evidence"
        )
        assert leg_cohort["with"]["path"] == "var/packaging-smoke-cohort/python/"
        assert leg_cohort["with"]["if-no-files-found"] == "error"
        assert leg_evidence["with"]["path"].splitlines() == [
            "var/packaging-smoke-evidence/*.json",
            "var/distribution-install-readiness/installed-cohorts/**/evidence.json",
        ]
        assert leg_checkpoint["if"] == "always()"
        assert leg_evidence["if"] == "always()"
        assert leg["steps"].index(leg_campaign) < leg["steps"].index(leg_checkpoint)
        assert leg["steps"].index(leg_checkpoint) < leg["steps"].index(leg_cohort)
        assert leg["steps"].index(leg_cohort) < leg["steps"].index(leg_evidence)

    # Every upload-artifact name across all jobs is unique: parallel legs would
    # otherwise clobber each other's cohort/evidence artifacts.
    all_upload_names = [
        one_job_step["with"]["name"]
        for one_job in document["jobs"].values()
        for one_job_step in one_job["steps"]
        if str(one_job_step.get("uses", "")).startswith("actions/upload-artifact@")
    ]
    assert len(all_upload_names) == len(set(all_upload_names)), all_upload_names

    # The identity boundary holds across every job: labels use Cadrumo/cadrumo
    # and no command turns cadrumo into a human executable or revives an aeat
    # product form.
    label_lines = [document["name"]]
    command_lines = []
    for one_job in document["jobs"].values():
        label_lines.append(str(one_job["name"]))
        for step in one_job["steps"]:
            label_lines.append(str(step.get("name", "")))
            if str(step.get("uses", "")).startswith("actions/upload-artifact@"):
                label_lines.append(str(step["with"]["name"]))
            if "run" in step:
                command_lines.append(str(step["run"]))
    assert "aeat" not in "\n".join(label_lines).casefold()
    assert _PROHIBITED_CADRUMO_HUMAN_COMMAND.search("\n".join(command_lines)) is None

    assert _prohibited_aeat_product_forms(_WORKFLOW.read_text(encoding="utf-8")) == ()


@pytest.mark.parametrize(
    "surface",
    (
        "aeat --version",
        "uv run --no-sync aeat app registry verify",
        "echo 'AEAT is the Spanish tax authority'",
        "pip install cadrumo && aeat --version",
    ),
)
def test_binding_cli_and_authority_forms_are_allowed(surface: str) -> None:
    """The human CLI and Spanish-authority referent remain valid contexts."""
    assert _PROHIBITED_CADRUMO_HUMAN_COMMAND.search(surface) is None
    assert _prohibited_aeat_product_forms(surface) == ()


@pytest.mark.parametrize(
    "surface",
    (
        "echo preflight\ncadrumo --version",
        "uv run --frozen cadrumo app registry verify",
        "env MODE=ci cadrumo --version",
        "MODE=ci cadrumo --version",
        "echo preflight && cadrumo --version",
    ),
)
def test_cadrumo_human_command_forms_are_rejected(surface: str) -> None:
    """Cadrumo cannot become a human executable through shell prefixes."""
    assert _PROHIBITED_CADRUMO_HUMAN_COMMAND.search(surface) is not None


@pytest.mark.parametrize(
    ("surface", "expected_family"),
    (
        ("from aeat import core", "python-import"),
        ('python -c "import os, aeat"', "python-import"),
        ("python -m aeat config check", "python-module"),
        ("pip install aeat", "distribution-install"),
        ("pip install aeat-data-official", "former-distribution"),
        ("uv add aeat-data-manuals", "former-distribution"),
        ("ruff check src/aeat/", "former-source-path"),
        ("uv build packaging/aeat_data_official", "former-distribution"),
    ),
)
def test_former_aeat_product_forms_are_rejected(surface: str, expected_family: str) -> None:
    """Former imports, modules, distributions, and paths remain prohibited."""
    assert expected_family in _prohibited_aeat_product_forms(surface)
