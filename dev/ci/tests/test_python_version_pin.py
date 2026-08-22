"""Repository-wide contract for the exact CI Python toolchain pin."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
_PYTHON_VERSION_FILE: Final = REPO_ROOT / ".python-version"
_EXACT_PATCH: Final = re.compile(r"\d+\.\d+\.\d+")
_MATRIX_EXPRESSION: Final = re.compile(r"\$\{\{\s*matrix\.([A-Za-z][\w-]*)\s*\}\}")


def _python_pin() -> str:
    pin = _PYTHON_VERSION_FILE.read_text(encoding="utf-8").strip()
    assert _EXACT_PATCH.fullmatch(pin), ".python-version must select one exact Python patch"
    return pin


def _workflow_documents() -> list[tuple[Path, dict[str, Any]]]:
    paths = sorted((*_WORKFLOWS_DIR.glob("*.yml"), *_WORKFLOWS_DIR.glob("*.yaml")))
    return [(path, yaml.safe_load(path.read_text(encoding="utf-8"))) for path in paths]


def test_setup_uv_consumers_follow_the_repository_python_pin() -> None:
    """Ordinary jobs defer to .python-version; genuine compatibility matrices may vary."""
    pin = _python_pin()
    violations: list[str] = []

    for path, document in _workflow_documents():
        for job_name, job in (document.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            steps = job.get("steps") or []
            for step_index, step in enumerate(steps):
                if not isinstance(step, dict) or not str(step.get("uses", "")).startswith("astral-sh/setup-uv@"):
                    continue
                selection = (step.get("with") or {}).get("python-version")
                if selection is None:
                    # With no UV_PYTHON override, uv resolves the checked-in
                    # exact .python-version pin itself. The checkout must already
                    # exist when setup-uv establishes the job's toolchain context.
                    checked_out = any(
                        isinstance(previous, dict) and str(previous.get("uses", "")).startswith("actions/checkout@")
                        for previous in steps[:step_index]
                    )
                    if not checked_out:
                        violations.append(f"{path.name}:{job_name}: setup-uv precedes checkout")
                    continue

                match = _MATRIX_EXPRESSION.fullmatch(str(selection))
                matrix = (job.get("strategy") or {}).get("matrix") or {}
                values = matrix.get(match.group(1)) if match else None
                if (
                    not isinstance(values, list)
                    or pin not in {str(value) for value in values}
                    or not any(str(value) != pin for value in values)
                ):
                    violations.append(f"{path.name}:{job_name}: {selection!r}")

    assert violations == [], (
        "setup-uv Python overrides bypass .python-version unless they are a "
        f"compatibility matrix containing the exact pin and an alternative: {violations}"
    )


def test_release_cohort_enforces_the_repository_python_pin() -> None:
    """The reproducible cohort builder consumes the same pin as CI."""
    from dev.packaging.release_cohort import _REQUIRED_PYTHON_VERSION

    assert _python_pin() == _REQUIRED_PYTHON_VERSION
