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


_NIGHTLY_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci-nightly.yml"


def test_ci_workflow_runs_canonical_cadrumo_commands_and_paths() -> None:
    """Per-push CI is the two-job speed profile: static checks plus the unit suite."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert document["name"] == "Cadrumo CI"
    assert set(document["jobs"]) == {"cadrumo-static", "cadrumo-unit"}

    static = document["jobs"]["cadrumo-static"]
    static_commands = "\n".join(str(step.get("run", "")) for step in static["steps"])
    assert "uv run --no-sync aeat app registry verify" in static_commands
    assert "uv run --no-sync aeat app registry audit-oracles" in static_commands
    assert "semgrep --config .semgrep/rules/ --error src/cadrumo/" in static_commands
    # The dev-tree workflow/tooling conformance gates run per-push here: the
    # default `-m unit` addopts deselects the integration-marked workflow
    # pins from the packaging preflight invocation, so this is their home.
    assert (
        'pytest -q -m "unit or (integration and not serial)" dev/packaging/tests dev/quality/tests dev/release/tests'
        in static_commands
    )

    unit = document["jobs"]["cadrumo-unit"]
    unit_commands = "\n".join(str(step.get("run", "")) for step in unit["steps"])
    assert "uv run pytest --junitxml=junit.xml" in unit_commands


def test_ci_per_push_jobs_carry_the_speed_budget_ceilings() -> None:
    """Ten-minute-wall discipline: hard job ceilings so a wedge dies in minutes.

    Operator directive 2026-07-20. The historical failure mode was a 5.5-hour
    wedged unit run under the 6-hour default; pytest-timeout caps each test
    and these ceilings cap the jobs. The slow conformance surfaces (docs
    build, CVE audit, hook replay) must stay out of the per-push lane — they
    gate nightly.
    """
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert document["jobs"]["cadrumo-static"]["timeout-minutes"] <= 25
    assert document["jobs"]["cadrumo-unit"]["timeout-minutes"] <= 40
    commands = "\n".join(str(step.get("run", "")) for job in document["jobs"].values() for step in job["steps"])
    assert "docs-check" not in commands
    assert "pip-audit" not in commands
    assert "check-pre-commit" not in commands


def test_nightly_workflow_carries_every_slow_conformance_surface() -> None:
    """The nightly lane keeps docs, CVE, hooks, and the full unit suite gating main."""
    document = yaml.safe_load(_NIGHTLY_WORKFLOW.read_text(encoding="utf-8"))
    assert document["name"] == "Cadrumo CI Nightly"
    assert set(document["jobs"]) == {"cadrumo-nightly-full"}
    triggers = document[True] if True in document else document["on"]
    assert set(triggers) == {"workflow_dispatch", "schedule"}

    commands = "\n".join(str(step.get("run", "")) for step in document["jobs"]["cadrumo-nightly-full"]["steps"])
    assert "just docs-check" in commands
    assert "pip-audit --strict" in commands
    assert "just check-pre-commit" in commands
    assert "uv run pytest --junitxml=junit.xml" in commands
    assert "uv run --no-sync aeat app registry verify" in commands
    assert _prohibited_aeat_product_forms(_NIGHTLY_WORKFLOW.read_text(encoding="utf-8")) == ()


def test_ci_workflow_does_not_materialise_operator_dotenv() -> None:
    """CI stays hermetic instead of loading operator-template overrides."""
    for path in (_WORKFLOW, _NIGHTLY_WORKFLOW):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        commands = "\n".join(str(step.get("run", "")) for job in document["jobs"].values() for step in job["steps"])
        assert "env-setup" not in commands
        assert "env/.env.example" not in commands
        assert "env/.env" not in commands


def test_ci_workflow_provisions_browser_before_unit_tests() -> None:
    """Real browser tests run only after the canonical Chromium provisioner."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    steps = document["jobs"]["cadrumo-unit"]["steps"]
    step_names = [str(step.get("name", "")) for step in steps]
    browser_step = step_names.index("Provision Playwright Chromium")
    unit_step = step_names.index("Test (unit)")

    assert steps[browser_step]["run"] == "just env-playwright"
    assert browser_step < unit_step


def test_ci_workflow_product_surface_has_no_former_identity() -> None:
    """CI retains `aeat` only as the human CLI, never as a product identity."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    jobs = document["jobs"].values()
    product_surface = "\n".join(
        (
            document["name"],
            *(str(job["name"]) for job in jobs),
            *(str(step.get("name", "")) for job in jobs for step in job["steps"]),
            *(str(step.get("run", "")) for job in jobs for step in job["steps"]),
        ),
    )
    commands = tuple(
        line.strip()
        for job in document["jobs"].values()
        for step in job["steps"]
        for line in str(step.get("run", "")).splitlines()
        if line.strip()
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
