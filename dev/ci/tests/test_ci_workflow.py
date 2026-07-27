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


_FULL_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci-full.yml"


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
    # Explicit -n 8, never -n auto: three runners share the machine
    # (machine-aware sizing, test_machine_aware_load.py).
    assert (
        'pytest -q -n 8 --timeout=900 -m "unit or (integration and not serial)"'
        " dev/ci/tests dev/packaging/tests dev/quality/tests dev/release/tests" in static_commands
    )

    unit = document["jobs"]["cadrumo-unit"]
    unit_commands = "\n".join(str(step.get("run", "")) for step in unit["steps"])
    assert "uv run pytest --durations=50 -n 8" in unit_commands


def test_ci_per_push_jobs_carry_the_speed_budget_ceilings() -> None:
    """Ten-minute-wall discipline: hard job ceilings so a wedge dies in minutes.

    Operator directive 2026-07-20. The historical failure mode was a 5.5-hour
    wedged unit run under the 6-hour default; pytest-timeout caps each test
    and these ceilings cap the jobs. The slow conformance surfaces (docs
    build, CVE audit, hook replay) must stay out of the per-push lane — they
    live in the dispatch-only full lane.
    """
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert document["jobs"]["cadrumo-static"]["timeout-minutes"] <= 25
    assert document["jobs"]["cadrumo-unit"]["timeout-minutes"] <= 40
    commands = "\n".join(str(step.get("run", "")) for job in document["jobs"].values() for step in job["steps"])
    assert "docs-check" not in commands
    assert "pip-audit" not in commands
    assert "check-pre-commit" not in commands


def test_full_lane_carries_every_slow_conformance_surface() -> None:
    """The dispatch-only full lane keeps docs, CVE, hooks, and the unit suite.

    Dispatch-only per the 2026-07-21 operator ruling (manual cadence, no
    standing compute); the no-schedule invariant itself is pinned repo-wide
    in test_change_class_tiers.py.
    """
    document = yaml.safe_load(_FULL_WORKFLOW.read_text(encoding="utf-8"))
    assert document["name"] == "Cadrumo CI Full"
    assert set(document["jobs"]) == {"cadrumo-full-conformance"}
    triggers = document[True] if True in document else document["on"]
    assert set(triggers) == {"workflow_dispatch"}

    commands = "\n".join(str(step.get("run", "")) for step in document["jobs"]["cadrumo-full-conformance"]["steps"])
    assert "just docs-check" in commands
    assert "pip-audit --strict" in commands
    assert "just check-pre-commit" in commands
    assert "uv run pytest --durations=100 -n 8" in commands
    assert "uv run --no-sync aeat app registry verify" in commands
    assert _prohibited_aeat_product_forms(_FULL_WORKFLOW.read_text(encoding="utf-8")) == ()


def test_ci_lanes_use_no_actions_artifact_storage() -> None:
    """CI enrolls in the repo's zero-Actions-artifact posture.

    The packaging workflows are already banned from artifact actions by the
    transport conformance gate; the CI lanes carry the same rule here — the
    storage quota is broken on the Free plan, and the duration profile lives
    in the job log, so an `if: always()` junit upload is both a quota risk
    and a policy inconsistency.
    """
    for path in (_WORKFLOW, _FULL_WORKFLOW):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        offending = [
            str(step.get("uses"))
            for job in document["jobs"].values()
            for step in job["steps"]
            if "upload-artifact" in str(step.get("uses", "")) or "download-artifact" in str(step.get("uses", ""))
        ]
        assert offending == [], f"{path.name} uses Actions artifact storage: {offending}"


def test_ci_workflow_does_not_materialise_operator_dotenv() -> None:
    """CI stays hermetic instead of loading operator-template overrides."""
    for path in (_WORKFLOW, _FULL_WORKFLOW):
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


def test_full_lane_runs_the_channel_generator_tests_explicitly_and_serially() -> None:
    """The fourteen generator tests must be selected by an actual lane.

    Nothing ran them before: the per-push lanes scope to dev/ paths AND exclude
    serial, the pathless invocations inherit testpaths that cannot reach
    packaging/, and the acquisition workflows invoke the generators but never
    their tests. Two independent breakages accumulated there unobserved.

    Explicit paths and -n0 are the assertion, not incidental style. A
    marker-filtered xdist run HOLDS serial tests out while reporting a clean
    pass, which is the same false green that hid those breakages, so selecting
    them by marker alone would reinstate it.
    """
    document = yaml.safe_load(_FULL_WORKFLOW.read_text(encoding="utf-8"))
    steps = document["jobs"]["cadrumo-full-conformance"]["steps"]
    generator = next(
        (str(step["run"]) for step in steps if "packaging/homebrew/tests" in str(step.get("run", ""))),
        None,
    )
    assert generator is not None, "no lane selects the Homebrew generator tests"
    assert "packaging/scoop/tests" in generator, "the Scoop generator tests share this lane"
    assert "-n0" in generator, "serial tests must run single-worker or they are held out silently"
    assert "-m serial" in generator, "the lane must select the serial marker these tests carry"
