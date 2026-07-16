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
        'uv run --no-sync pytest -q -n0 -m "integration and serial" dev/packaging/tests/test_installed_oracles.py',
        "uv run --no-sync python -m dev.packaging.evidence --prune-completed",
        "uv run --no-sync python -m dev.packaging.evidence",
    } <= commands


def test_workflow_evidence_and_product_identity_follow_the_binding_tuple() -> None:
    """Labels use Cadrumo, artifacts use cadrumo, and commands keep the aeat boundary."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    job = document["jobs"]["cadrumo-packaging-smoke"]
    upload = next(step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/upload-artifact@"))
    docker = next(step for step in job["steps"] if step.get("run") == "just packaging-smoke-docker")
    checkpoint = next(
        step for step in job["steps"] if step.get("run") == "uv run --no-sync python -m dev.packaging.evidence"
    )

    assert upload["name"] == "Upload Cadrumo packaging smoke evidence"
    assert upload["with"]["name"] == "cadrumo-packaging-smoke-evidence"
    assert upload["with"]["path"].splitlines() == [
        "var/packaging-smoke-evidence/*.json",
        "var/distribution-install-readiness/installed-cohorts/**/evidence.json",
    ]
    assert checkpoint["if"] == "always()"
    assert upload["if"] == "always()"
    assert job["steps"].index(docker) < job["steps"].index(checkpoint) < job["steps"].index(upload)

    label_surface = "\n".join(
        (
            document["name"],
            job["name"],
            *(step.get("name", "") for step in job["steps"]),
            upload["with"]["name"],
        ),
    ).casefold()
    assert "aeat" not in label_surface

    commands = "\n".join(str(step["run"]) for step in job["steps"] if "run" in step)
    assert _PROHIBITED_CADRUMO_HUMAN_COMMAND.search(commands) is None

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
