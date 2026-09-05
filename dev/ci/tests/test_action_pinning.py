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

import json
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


def _upload_arguments(run: str) -> list[str]:
    """The file arguments an `uv publish` command line hands to the index."""
    return [token for token in run.split() if token.startswith("dist")]


def _publish_command(path: Path) -> str:
    """The `uv publish` command line in a workflow, or a refusal if it has none."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    for job in document["jobs"].values():
        for step in job.get("steps") or []:
            run = str(step.get("run", ""))
            if "uv publish" in run:
                return run
    raise AssertionError(f"{path.name} no longer runs `uv publish`")


def test_the_publish_step_uploads_distributions_only() -> None:
    """A bare directory glob offers the index files it will refuse.

    The build job seals a checksum manifest into the same directory it uploads,
    and `uv build` leaves its own marker there. Neither is an uploadable file,
    and the upload is not atomic, so offering them fails the step part-way
    through rather than before it starts.
    """
    arguments = _upload_arguments(_publish_command(_WORKFLOWS_DIR / "publish.yml"))

    assert arguments, "the publish step names no files to upload"
    assert all(argument.endswith((".whl", ".tar.gz")) for argument in arguments), (
        f"the publish step offers the index files that are not distributions: {arguments}"
    )


def test_the_gate_refuses_a_bare_directory_glob() -> None:
    """Teeth: the shape this replaced is reported, not tolerated."""
    arguments = _upload_arguments("uv publish --trusted-publishing always dist/*")

    assert arguments == ["dist/*"]
    assert not all(argument.endswith((".whl", ".tar.gz")) for argument in arguments)


def test_release_please_bumps_every_version_surface_the_release_gate_compares() -> None:
    """The versioning tool and the readiness gate must agree on what a version is.

    The gate refuses a release unless the root project, both companion projects,
    the package initialiser, the manifest and both exact companion pins report
    one version. The tool bumps the root, the initialiser and the manifest on
    its own; everything else it touches only because it is configured to.

    Configured wrong, the release still happens: the branch is written, the tag
    is cut, and the refusal arrives afterwards from the product's own gate,
    against a version that already exists. So the two are compared here.
    """
    config = json.loads((REPO_ROOT / "release-please-config.json").read_text(encoding="utf-8"))
    extra_files = set(config["packages"]["."].get("extra-files", []))

    companions = sorted(
        path.relative_to(REPO_ROOT).as_posix() for path in (REPO_ROOT / "packaging").glob("*/pyproject.toml")
    )
    required = {"src/cadrumo/__init__.py", "pyproject.toml", *companions}

    assert required <= extra_files, (
        f"release-please does not bump these version surfaces: {sorted(required - extra_files)}. "
        "The release-readiness gate compares them, so a release would be cut and then refused."
    )


#: Surfaces the `python` release type rewrites from its own knowledge of the
#: shape. A run confirmed it bumps `__version__` in a package initialiser with
#: no annotation present, so requiring one there would fail against a file the
#: tool already handles.
_NATIVELY_UPDATED: Final = frozenset({"src/cadrumo/__init__.py"})


#: Below this the extra-files key has moved or emptied. Live: four entries
#: configured, three of them reaching the annotation check. A floor.
_MINIMUM_ANNOTATED_EXTRA_FILES: Final = 2


def test_every_other_configured_extra_file_carries_the_annotation_that_moves_it() -> None:
    """A path in `extra-files` with no annotation is a surface silently left behind.

    Outside the shapes the release type knows, the generic updater rewrites a
    version only on lines marked `x-release-please-version`. A file listed
    without one is read, matched against nothing, and written back unchanged -
    which reports success and ships a stale version.
    """
    config = json.loads((REPO_ROOT / "release-please-config.json").read_text(encoding="utf-8"))

    # The corpus arrives through a `.get` default, so a renamed or emptied
    # `extra-files` key yields no entries and every claim below holds. That is
    # the same silent success this gate exists to prevent, one level up: the
    # release tool would stop bumping these files and the gate would agree.
    configured = [
        entry for entry in config["packages"]["."].get("extra-files", []) if isinstance(entry, str)
    ]
    checked = [entry for entry in configured if entry not in _NATIVELY_UPDATED]

    assert len(checked) >= _MINIMUM_ANNOTATED_EXTRA_FILES, (
        f"only {len(checked)} configured extra-file(s) reach the annotation check, from "
        f"{len(configured)} configured; below this the key has moved or emptied and this "
        "gate is inert rather than satisfied"
    )

    unmarked = [
        entry
        for entry in checked
        if "x-release-please-version" not in (REPO_ROOT / entry).read_text(encoding="utf-8")
    ]

    assert unmarked == [], f"these files are configured for bumping but carry no version annotation: {unmarked}"
