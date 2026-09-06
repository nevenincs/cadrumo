"""Structural gate: every workflow job runs on the self-hosted fleet only.

Operator mandate 2026-07-21: NO hosted/cloud runners were ever authorized —
expense control is absolute, and the ARM MacBook is the only permitted
non-workstation avenue. Every ``runs-on`` (including every matrix value
feeding one, list-dimension or include-row alike, in ``.yml`` and ``.yaml``
workflows both) must be a self-hosted label set; a GitHub-hosted image
(``ubuntu-latest``, ``windows-2022``, ``macos-15-intel``,
``ubuntu-24.04-arm``, ...) anywhere in the tree is a spend regression this
gate refuses. Fail-closed: a matrix-referencing ``runs-on`` that resolves to
zero concrete targets is itself a violation, never a silent pass.

The release path is exempt as a whole, enumerated in :data:`HOSTED_WORKFLOWS`
and pinned in both directions by the tests below. It is not a softening of the
mandate: those workflows build a `py3-none-any` artifact the host cannot
affect, and publication must not be gated on a fleet runner being free. The
spend premise does not apply either - this repository is public, and hosted
runners are free for public repositories.

Both directions resolve their targets through the shared runner-target
authority, including the runtime-computed matrix the release path uses: the
hosted split had never once been inspected there, because the reader raised
before it reached an assertion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from cadrumo.core.directory_scan import scan_directory

from ..._paths import REPO_ROOT
from ..workflow_runner_targets import (
    UNRESOLVED_ZERO_TARGETS,
    is_fleet_label_set,
    is_hosted_image,
    runner_targets,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR: Final = REPO_ROOT / ".github" / "workflows"
#: The release path's own matrix indirection, reused by the fixtures below so
#: the refusals are driven against the shape this repository actually ships.
_RUNTIME_MATRIX_REFERENCE: Final = "${{ fromJSON(needs.inventory.outputs.matrix) }}"

#: Workflows whose every job runs on a GitHub-hosted image.
#:
#: The release path belongs here for three standing reasons. The distributions
#: are `py3-none-any`, so the build host cannot affect the artifact. The
#: repository is public, so hosted runners cost nothing. And publication must
#: not be gated on a self-hosted runner being free, which this fleet cannot
#: guarantee: it carries one Linux x86-64 runner, and its macOS host serves
#: only on mains power.
#:
#: Every other workflow proves behaviour on a real target platform and stays on
#: the fleet.
HOSTED_WORKFLOWS: Final[frozenset[str]] = frozenset({"release-please.yml", "publish.yml"})


#: Floors for the workflow census this fleet gate reads. Two sibling modules
#: floor the same directory at eight; this one carried only a truthiness.
#: Live: sixteen workflows, of which fourteen are gated (publish and
#: release-please run on hosted images by design).
_MINIMUM_FLEET_WORKFLOWS = 8
_MINIMUM_GATED_WORKFLOWS = 6


def _collect_violations(workflows_dir: Path) -> list[tuple[str, str, object]]:
    """Return every (workflow, job, target) whose runner is not self-hosted."""
    workflows = sorted(
        {*scan_directory(workflows_dir, pattern="*.yml"), *scan_directory(workflows_dir, pattern="*.yaml")}
    )
    assert workflows, f"no workflows found to gate under {workflows_dir}"
    violations: list[tuple[str, str, object]] = []
    for workflow in workflows:
        if workflow.name in HOSTED_WORKFLOWS:
            continue
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        violations.extend(_fleet_violations(workflow.name, document))
    return violations


def _fleet_violations(workflow_name: str, document: dict[str, Any]) -> list[tuple[str, str, object]]:
    """Return every target in ``document`` that is not a self-hosted label set."""
    return [
        (workflow_name, job_name, target)
        for job_name, job in (document.get("jobs") or {}).items()
        for target in runner_targets(job, document)
        if not is_fleet_label_set(target)
    ]


def _hosted_violations(workflow_name: str, document: dict[str, Any]) -> list[tuple[str, str, object]]:
    """Return every target in ``document`` that is not a hosted runner image."""
    return [
        (workflow_name, job_name, target)
        for job_name, job in (document.get("jobs") or {}).items()
        for target in runner_targets(job, document)
        if not is_hosted_image(target)
    ]


def test_the_release_path_workflows_run_on_hosted_images() -> None:
    """The hosted split is pinned in BOTH directions.

    A release job that drifts onto the fleet reintroduces the availability
    dependency the split exists to remove, and does so silently: the run does
    not error, it queues behind whatever already holds the runner.

    The release path computes one of its matrices at runtime, so its runner
    labels are read from the step that emits them rather than from a matrix
    mapping that does not exist yet. An unresolvable reference is a violation
    here exactly as a fleet label would be: an exemption granted on the ground
    that every job is hosted has to be able to see every job.
    """
    for workflow_name in sorted(HOSTED_WORKFLOWS):
        workflow = _WORKFLOWS_DIR / workflow_name
        assert workflow.is_file(), f"{workflow_name} is declared hosted but does not exist"
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        jobs = document.get("jobs") or {}
        assert jobs, f"{workflow_name} declares no jobs"
        violations = _hosted_violations(workflow_name, document)
        assert violations == [], f"release-path jobs not on a hosted image: {violations}"


def test_the_live_fleet_census_reaches_the_whole_workflow_directory() -> None:
    """The gate below asserts an EMPTY violation list, which nothing proves alone.

    Floored here rather than inside ``_collect_violations`` because that helper
    is deliberately dual-purpose: five teeth cases drive it over a temporary
    directory holding a single planted workflow, and a census floor inside it
    would refuse exactly the fixtures that prove the gate can fail. Two sibling
    modules floor this same directory at eight.
    """
    workflows = sorted(
        {*scan_directory(_WORKFLOWS_DIR, pattern="*.yml"), *scan_directory(_WORKFLOWS_DIR, pattern="*.yaml")}
    )
    gated = [workflow for workflow in workflows if workflow.name not in HOSTED_WORKFLOWS]

    assert len(workflows) >= _MINIMUM_FLEET_WORKFLOWS, (
        f"only {len(workflows)} workflow(s) under {_WORKFLOWS_DIR}; a narrowed census "
        "reports an empty violation list exactly as a compliant fleet does"
    )
    assert len(gated) >= _MINIMUM_GATED_WORKFLOWS, (
        f"only {len(gated)} of {len(workflows)} workflow(s) are gated; "
        f"{sorted(HOSTED_WORKFLOWS)} are excused, and an exclusion list grown to cover "
        "the fleet would empty the violations without a word"
    )


def test_every_workflow_job_runs_on_the_self_hosted_fleet() -> None:
    """Zero GitHub-hosted runner images anywhere; no workflow is exempt."""
    violations = _collect_violations(_WORKFLOWS_DIR)
    assert violations == [], f"hosted (or unresolvable) runner targets found: {violations}"


def test_gate_refuses_a_hosted_job_outside_the_exemption(tmp_path: Path) -> None:
    """The exemption is keyed to the workflow filename, not to the hosted label.

    A job in some other workflow is not part of the release path, so the gate
    must still refuse it. This is what stops the exemption widening into
    "hosted runners are fine if you pick the right job name".
    """
    workflow = tmp_path / "other.yml"
    workflow.write_text(
        """name: other
on: workflow_dispatch
jobs:
  campaign:
    runs-on: ubuntu-latest
    steps: []
""",
        encoding="utf-8",
    )
    assert _collect_violations(tmp_path) == [("other.yml", "campaign", "ubuntu-latest")]


def test_gate_refuses_a_hosted_yaml_extension_workflow(tmp_path: Path) -> None:
    """GitHub honors .yaml too; a hosted foo.yaml cannot slip past the glob."""
    (tmp_path / "sneaky.yaml").write_text(
        "name: sneaky\non: workflow_dispatch\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps: []\n",
        encoding="utf-8",
    )
    violations = _collect_violations(tmp_path)
    assert violations == [("sneaky.yaml", "build", "ubuntu-latest")]


def test_gate_refuses_a_hosted_top_level_matrix_dimension(tmp_path: Path) -> None:
    """A list-dimension matrix (matrix.os: [ubuntu-latest]) is expanded and refused."""
    (tmp_path / "matrixed.yml").write_text(
        "name: matrixed\n"
        "on: workflow_dispatch\n"
        "jobs:\n"
        "  build:\n"
        "    strategy:\n"
        "      matrix:\n"
        "        os: [ubuntu-latest, [self-hosted, Linux, X64]]\n"
        "    runs-on: ${{ matrix.os }}\n"
        "    steps: []\n",
        encoding="utf-8",
    )
    violations = _collect_violations(tmp_path)
    assert violations == [("matrixed.yml", "build", "ubuntu-latest")]


def test_gate_fails_closed_on_an_unresolvable_matrix_reference(tmp_path: Path) -> None:
    """A matrix runs-on resolving to zero targets is a violation, never a pass."""
    (tmp_path / "opaque.yml").write_text(
        "name: opaque\n"
        "on: workflow_dispatch\n"
        "jobs:\n"
        "  build:\n"
        "    strategy:\n"
        "      matrix:\n"
        "        other: [x]\n"
        "    runs-on: ${{ matrix.runner }}\n"
        "    steps: []\n",
        encoding="utf-8",
    )
    violations = _collect_violations(tmp_path)
    assert violations == [("opaque.yml", "build", UNRESOLVED_ZERO_TARGETS)]


def _rewrite_emitted_images(document: dict[str, Any], replacement: str) -> int:
    """Point every emitted hosted image at ``replacement``, in memory.

    Returns the number of run scripts rewritten, so a caller can tell an edit
    that changed nothing from one that changed the document.
    """
    rewritten = 0
    for job in (document.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            script = str(step.get("run", ""))
            if '"ubuntu-latest"' in script:
                step["run"] = script.replace('"ubuntu-latest"', f'"{replacement}"')
                rewritten += 1
    return rewritten


def test_the_gate_notices_the_real_release_path_moving_onto_the_fleet() -> None:
    """Detector teeth on the shipped document, not on a look-alike.

    The fixtures below prove the resolver's rules; this proves those rules bind
    the file the exemption is actually granted to. The workflow is parsed, the
    script that emits its smoke targets is rewritten in the parsed copy, and
    the copy re-read -- nothing on disk is touched, and the clean reading taken
    first is what makes the second reading mean something.
    """
    document = yaml.safe_load((_WORKFLOWS_DIR / "publish.yml").read_text(encoding="utf-8"))
    assert _hosted_violations("publish.yml", document) == []

    assert _rewrite_emitted_images(document, "self-hosted") > 0, (
        "no step in the release path emits a hosted image literal, so this proves nothing"
    )
    violations = _hosted_violations("publish.yml", document)

    assert violations, "a release job emitting a fleet label was not reported"
    assert {target for *_, target in violations} == {"self-hosted"}


def _runtime_matrix_workflow(*, emitted_labels: str, matrix: str = _RUNTIME_MATRIX_REFERENCE) -> dict[str, Any]:
    """Return a release-shaped document whose matrix is computed at runtime.

    Modelled on the publication workflow: one job validates an inventory and
    writes the smoke matrix to an output, and the job that consumes it names no
    runner of its own. The runner labels exist only inside the producing
    script, which is the whole difficulty this fixture exists to reproduce.
    """
    return yaml.safe_load(
        "name: runtime\n"
        "on: workflow_dispatch\n"
        "jobs:\n"
        "  inventory:\n"
        "    runs-on: ubuntu-latest\n"
        "    outputs:\n"
        "      matrix: ${{ steps.emit-matrix.outputs.matrix }}\n"
        "    steps:\n"
        "      - name: Emit\n"
        "        id: emit-matrix\n"
        "        run: |\n"
        f"          emit --targets {emitted_labels}\n"
        "  smoke:\n"
        "    needs: inventory\n"
        "    strategy:\n"
        f"      matrix: {matrix}\n"
        "    runs-on: ${{ matrix.os }}\n"
        "    steps: []\n",
    )


def test_the_gate_reads_the_labels_a_runtime_matrix_producer_emits() -> None:
    """The release path's own shape resolves to real targets, not to a shrug.

    This is the positive control for the refusals below. Without it a resolver
    that reported every runtime matrix unresolvable would look identical to one
    that reads them, and the exemption would be pinned by a gate that never
    agrees the document is fine.
    """
    document = _runtime_matrix_workflow(emitted_labels='"ubuntu-latest" "macos-latest" "windows-latest"')

    targets = runner_targets(document["jobs"]["smoke"], document)

    assert targets == ["ubuntu-latest", "macos-latest", "windows-latest"]
    assert _hosted_violations("runtime.yml", document) == []


def test_a_runtime_matrix_producer_emitting_a_fleet_label_is_refused() -> None:
    """Detector teeth: a release job put back on the fleet is caught.

    The label never appears in the consuming job -- it is written in the script
    that computes the matrix -- so this is exactly the drift the previous
    reader could not see, and the one the exemption cannot survive.
    """
    document = _runtime_matrix_workflow(emitted_labels='"ubuntu-latest" "self-hosted"')

    assert _hosted_violations("runtime.yml", document) == [("runtime.yml", "smoke", "self-hosted")]


def test_a_runtime_matrix_producer_naming_no_label_is_refused() -> None:
    """A producer whose labels are invisible fails closed rather than passing."""
    document = _runtime_matrix_workflow(emitted_labels="--from-file targets.json")

    violations = _hosted_violations("runtime.yml", document)

    assert len(violations) == 1
    assert "names no runner label literal" in str(violations[0][2])


@pytest.mark.parametrize(
    ("matrix", "expected"),
    [
        ("${{ fromJSON(inputs.matrix) }}", "not a fromJSON(needs.<job>.outputs.<output>) reference"),
        ("${{ fromJSON(needs.absent.outputs.matrix) }}", "is not declared in this workflow"),
        ("${{ fromJSON(needs.inventory.outputs.absent) }}", "not a ${{ steps.<id>.outputs.<key> }} reference"),
    ],
    ids=("not-a-job-output", "producer-absent", "output-absent"),
)
def test_a_runtime_matrix_reference_the_gate_cannot_follow_is_refused(matrix: str, expected: str) -> None:
    """Each way the indirection can break is a refusal, never a silent pass."""
    document = _runtime_matrix_workflow(emitted_labels='"ubuntu-latest"', matrix=matrix)

    violations = _hosted_violations("runtime.yml", document)

    assert len(violations) == 1
    assert expected in str(violations[0][2])


def test_a_runtime_matrix_cannot_prove_a_fleet_lane(tmp_path: Path) -> None:
    """Outside the exemption the same document is refused, and must be.

    A self-hosted lane is a label LIST, and a runtime matrix carries labels one
    string at a time with no way to say which of them belong to the same job.
    So a fleet workflow declares `runs-on:` statically -- as every fleet
    workflow here already does -- and one that stops doing so fails rather than
    being taken on trust.
    """
    document = _runtime_matrix_workflow(emitted_labels='"self-hosted" "Linux" "X64"')
    (tmp_path / "fleet.yml").write_text(yaml.safe_dump(document), encoding="utf-8")

    violations = _collect_violations(tmp_path)

    assert ("fleet.yml", "smoke", "self-hosted") in violations
