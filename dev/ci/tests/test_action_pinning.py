"""Gate: every workflow action is pinned to a full-length commit SHA.

The repository enforces this at the forge, and a workflow that violates it does
not fail a step - it is refused before any step runs. The run lasts a few
seconds and reports an actions-permission error, which reads as a settings
problem rather than as a defect in the workflow that was just added.

That is how the release path sat broken: `release-please` ran on every push to
the default branch and was refused in under ten seconds every time, so no
release pull request was ever opened, no tag was ever cut, and the publish
workflow it dispatches never ran once. Nothing in the tree reported it, because
the only gate asserting SHA pins covered the artifact actions of the packaging
workflows and the release path is neither.

Asserted over every workflow and every action, which is the same rule the forge
applies. A tag is a moving reference: `@v4` today and `@v4` after a force-push
are different code with identical spelling.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest
import yaml

from cadrumo.core.directory_scan import scan_directory

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
_FULL_SHA: Final = re.compile(r"^[0-9a-f]{40}$")


def _workflow_paths() -> list[Path]:
    return sorted({*scan_directory(_WORKFLOWS_DIR, pattern="*.yml"), *scan_directory(_WORKFLOWS_DIR, pattern="*.yaml")})


def _action_uses(document: dict[str, object]) -> list[str]:
    """Every `uses:` value in the document, including composite job steps."""
    uses: list[str] = []
    jobs = document.get("jobs")
    if not isinstance(jobs, dict):
        return uses
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        # A job may reuse a whole workflow rather than run steps.
        reusable = job.get("uses")
        if isinstance(reusable, str):
            uses.append(reusable)
        for step in job.get("steps") or []:
            if isinstance(step, dict) and isinstance(step.get("uses"), str):
                uses.append(step["uses"])
    return uses


def _unpinned(path: Path) -> list[str]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        return []
    offenders: list[str] = []
    for reference in _action_uses(document):
        # A local action is a path in this repository, already at this commit.
        if reference.startswith(("./", "../")) or reference.startswith("docker://"):
            continue
        _, separator, version = reference.partition("@")
        if not separator or not _FULL_SHA.match(version):
            offenders.append(f"{path.name}: {reference}")
    return offenders


def test_every_action_in_every_workflow_is_pinned_to_a_sha() -> None:
    """The forge refuses an unpinned action, so an unpinned one is a dead workflow."""
    workflows = _workflow_paths()
    assert workflows, f"no workflows found to gate under {_WORKFLOWS_DIR}"

    offenders = [entry for path in workflows for entry in _unpinned(path)]

    assert offenders == [], (
        "these actions are referenced by a tag or branch rather than a full-length commit SHA, "
        "and this repository's forge refuses a workflow that does so before any step runs:\n  " + "\n  ".join(offenders)
    )


def test_the_gate_refuses_a_tag_reference(tmp_path: Path) -> None:
    """Teeth, against an isolated file rather than the tree it is protecting."""
    workflow = tmp_path / "tagged.yml"
    workflow.write_text(
        "name: tagged\non: workflow_dispatch\njobs:\n"
        "  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n",
        encoding="utf-8",
    )

    assert _unpinned(workflow) == ["tagged.yml: actions/checkout@v4"]


def test_the_gate_refuses_a_short_sha(tmp_path: Path) -> None:
    """An abbreviated SHA is still refused by the forge, so it is refused here.

    Worth its own case: a short SHA looks pinned, and a check that only rejected
    a leading `v` would pass it.
    """
    workflow = tmp_path / "short.yml"
    workflow.write_text(
        "name: short\non: workflow_dispatch\njobs:\n"
        "  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@34e1148\n",
        encoding="utf-8",
    )

    assert _unpinned(workflow) == ["short.yml: actions/checkout@34e1148"]


def test_a_local_action_needs_no_pin(tmp_path: Path) -> None:
    """A path inside this repository is already at the commit being run."""
    workflow = tmp_path / "local.yml"
    workflow.write_text(
        "name: local\non: workflow_dispatch\njobs:\n"
        "  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: ./.github/actions/setup\n",
        encoding="utf-8",
    )

    assert _unpinned(workflow) == []
