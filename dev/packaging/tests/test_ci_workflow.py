"""Structural behavior gate for the Cadrumo CI workflow."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"
_PROHIBITED_AEAT_PRODUCT_FORMS = (
    (
        "python-import",
        re.compile(
            r"""(?i)\b(?:from\s+aeat(?:\.|\s+import\b)|import\s+(?:[a-z_]\w*(?:\.[a-z_]\w*)*\s*,\s*)*aeat(?:\.|(?=\s|$|[;"'])))"""
        ),
    ),
    (
        "python-module",
        re.compile(r"(?i)\bpython(?:\d+(?:\.\d+)*)?\s+-m\s+aeat(?:\.[a-z_]\w*)*(?=\s|$)"),
    ),
    (
        "distribution-install",
        re.compile(
            r"""(?i)\b(?:(?:uv\s+)?pip\s+install|uv\s+add)\b[^&|;\r\n]*?(?<![\w-])aeat(?=\[|\s|$|[<>=!~@;"'])"""
        ),
    ),
    (
        "uv-package",
        re.compile(
            r"""(?i)\b(?:uv\s+run\s+--(?:package|with)|uvx\s+--from)(?:=|\s+)["']?aeat(?=\[|\s|$|[<>=!~@;"'])"""
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


def test_ci_workflow_runs_canonical_cadrumo_commands_and_paths() -> None:
    """The real workflow invokes Cadrumo entry points over the Cadrumo source root."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert document["name"] == "Cadrumo CI"
    assert set(document["jobs"]) == {"cadrumo-lint-and-test"}

    job = document["jobs"]["cadrumo-lint-and-test"]
    assert job["name"] == "Cadrumo / ${{ matrix.os }} / Python ${{ matrix.python-version }}"
    commands = "\n".join(str(step.get("run", "")) for step in job["steps"])
    assert "uv run --no-sync aeat app registry verify" in commands
    assert "uv run --no-sync aeat app registry audit-oracles" in commands
    assert "semgrep --config .semgrep/rules/ --error src/cadrumo/" in commands


def test_ci_workflow_product_surface_has_no_former_identity() -> None:
    """CI retains `aeat` only as the human CLI, never as a product identity."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    job = document["jobs"]["cadrumo-lint-and-test"]
    product_surface = "\n".join(
        (
            document["name"],
            job["name"],
            *(str(step.get("name", "")) for step in job["steps"]),
            *(str(step.get("run", "")) for step in job["steps"]),
        ),
    )
    commands = tuple(
        line.strip() for step in job["steps"] for line in str(step.get("run", "")).splitlines() if line.strip()
    )
    registry_commands = {command for command in commands if " app registry " in command}

    assert registry_commands == {
        "uv run --no-sync aeat app registry verify",
        "uv run --no-sync aeat app registry audit-oracles",
    }
    assert not any(re.match(r"^(?:uv run(?: --no-sync)? )?cadrumo(?:\s|$)", command) for command in commands)

    assert _prohibited_aeat_product_forms(product_surface) == ()


@pytest.mark.parametrize(
    "surface",
    (
        "uv run --no-sync aeat app registry verify",
        "aeat --version",
        "echo 'AEAT is the Spanish tax authority'",
        "uv add cadrumo && aeat --version",
        "pip install cadrumo && echo AEAT is the Spanish tax authority",
    ),
)
def test_aeat_human_cli_and_authority_forms_are_allowed(surface: str) -> None:
    """Exact human CLI and authority references are not former product identities."""
    assert _prohibited_aeat_product_forms(surface) == ()


@pytest.mark.parametrize(
    ("surface", "expected_family"),
    (
        ("from aeat import core", "python-import"),
        ("from aeat.core import Settings", "python-import"),
        ("import aeat", "python-import"),
        ("import aeat.core", "python-import"),
        ('python -c "import os, aeat as retired"', "python-import"),
        ("python -m aeat config check", "python-module"),
        ("python -m aeat.cli check", "python-module"),
        ("uv pip install aeat", "distribution-install"),
        ('uv pip install "aeat"', "distribution-install"),
        ('pip install "aeat[agent]>=1"', "distribution-install"),
        ("uv add cadrumo aeat", "distribution-install"),
        ("pip install cadrumo aeat>=1", "distribution-install"),
        ("uv run --package aeat python verify.py", "uv-package"),
        ("uv run --package=aeat python verify.py", "uv-package"),
        ("uv run --with 'aeat==1.2.3' python verify.py", "uv-package"),
        ("uvx --from aeat==1.2.3 aeat --version", "uv-package"),
        ("uv build packaging/aeat_data_manuals", "former-distribution"),
        ("ruff check src/aeat/", "former-source-path"),
    ),
)
def test_former_aeat_product_forms_are_rejected(surface: str, expected_family: str) -> None:
    """Former import, package, install, and source families remain prohibited."""
    assert expected_family in _prohibited_aeat_product_forms(surface)
