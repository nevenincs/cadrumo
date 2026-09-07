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

The release-path exemption is RETIRED. `HOSTED_WORKFLOWS` is empty, so
`release-please.yml` and `publish.yml` are gated like everything else and the
mandate above holds without a carve-out.

The carve-out was granted on the ground that publication must not be gated on
a fleet runner being free, which remains a real property and is now owned
where it belongs: enrolment and availability are driven by the `ci-fleet`
repository, which is binding for every `nevenincs` repo, and whose `fleetctl
guards` audit reports a release guard scheduled onto the fleet it judges. A
cadrumo-local exemption cannot express a fleet-wide policy, and while it stood
the two surfaces disagreed -- the workflows moved onto the fleet under that
policy and this gate refused them, so `main` carried a red gate with neither
side wrong on its own terms.

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
from ..workflow_runner_targets import UNRESOLVED_ZERO_TARGETS, is_fleet_label_set, is_hosted_image, runner_targets
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
_WORKFLOWS_DIR: Final = REPO_ROOT / '.github' / 'workflows'
_RUNTIME_MATRIX_REFERENCE: Final = '${{ fromJSON(needs.inventory.outputs.matrix) }}'
HOSTED_WORKFLOWS: Final[frozenset[str]] = frozenset()
_MINIMUM_FLEET_WORKFLOWS = 8
_MINIMUM_GATED_WORKFLOWS = 6

def _collect_violations(workflows_dir: Path, *, excused: frozenset[str]=HOSTED_WORKFLOWS) -> list[tuple[str, str, object]]:
    """Return every (workflow, job, target) whose runner is not self-hosted.

    ``excused`` defaults to the live set, which is empty. It is a parameter so
    the keying case can hand in a non-empty one: the skip below is otherwise
    unreachable, and an exemption seam nothing can reach is a seam nothing
    proves works the day someone adds an entry to it.
    """
    workflows = sorted({*scan_directory(workflows_dir, pattern='*.yml'), *scan_directory(workflows_dir, pattern='*.yaml')})
    assert workflows, f'no workflows found to gate under {workflows_dir}'
    violations: list[tuple[str, str, object]] = []
    for workflow in workflows:
        if workflow.name in excused:
            continue
        document = yaml.safe_load(workflow.read_text(encoding='utf-8'))
        violations.extend(_fleet_violations(workflow.name, document))
    return violations

def _fleet_violations(workflow_name: str, document: dict[str, Any]) -> list[tuple[str, str, object]]:
    """Return every target in ``document`` that is not a self-hosted label set."""
    return [(workflow_name, job_name, target) for job_name, job in (document.get('jobs') or {}).items() for target in runner_targets(job, document) if not is_fleet_label_set(target)]

def _hosted_violations(workflow_name: str, document: dict[str, Any]) -> list[tuple[str, str, object]]:
    """Return every target in ``document`` that is not a hosted runner image."""
    return [(workflow_name, job_name, target) for job_name, job in (document.get('jobs') or {}).items() for target in runner_targets(job, document) if not is_hosted_image(target)]

def test_the_release_path_is_gated_like_everything_else() -> None:
    """The retired exemption must leave the release path COVERED, not skipped.

    Emptying `HOSTED_WORKFLOWS` is only a strengthening if the census then
    reaches those files. An exemption list that is merely emptied while the
    helpers still skip the names would read exactly the same green as this,
    so both halves are asserted: nothing is excused, and the release path is
    on the fleet like every other workflow.
    """
    assert frozenset() == HOSTED_WORKFLOWS, 'an exemption needs a reason recorded beside it'
    workflows = sorted({*scan_directory(_WORKFLOWS_DIR, pattern='*.yml'), *scan_directory(_WORKFLOWS_DIR, pattern='*.yaml')})
    names = {workflow.name for workflow in workflows}
    for release_path in ('release-please.yml', 'publish.yml'):
        assert release_path in names, f'{release_path} vanished from the census'
    violations = _collect_violations(_WORKFLOWS_DIR)
    assert violations == [], f'hosted (or unresolvable) runner targets found: {violations}'

def _census_shortfalls(workflows_dir: Path, *, excused: frozenset[str]=HOSTED_WORKFLOWS, minimum_total: int=_MINIMUM_FLEET_WORKFLOWS, minimum_gated: int=_MINIMUM_GATED_WORKFLOWS) -> list[str]:
    """Return the census floors ``workflows_dir`` fails, named and quantified.

    Floored here rather than inside ``_collect_violations`` because that helper
    is deliberately dual-purpose: five teeth cases drive it over a temporary
    directory holding a single planted workflow, and a census floor inside it
    would refuse exactly the fixtures that prove the gate can fail. Two sibling
    modules floor this same directory at eight.

    ``excused`` is a parameter for the same reason it is one on
    ``_collect_violations``, and the reason is sharper here. With
    ``HOSTED_WORKFLOWS`` empty the gated subset EQUALS the whole census by
    construction, so the gated floor cannot fail while the total floor passes:
    deleting the filter, and deleting the gated floor outright, each left this
    module fourteen-green. Taking the excused set as an argument is what lets
    the census case below drive the branch a repopulated exemption list would
    take, instead of pinning a comparison no input can reach.
    """
    workflows = sorted({*scan_directory(workflows_dir, pattern='*.yml'), *scan_directory(workflows_dir, pattern='*.yaml')})
    gated = [workflow for workflow in workflows if workflow.name not in excused]
    shortfalls: list[str] = []
    if len(workflows) < minimum_total:
        shortfalls.append(f'total: only {len(workflows)} workflow(s) under {workflows_dir}, below {minimum_total}; a narrowed census reports an empty violation list exactly as a compliant fleet does')
    if len(gated) < minimum_gated:
        shortfalls.append(f'gated: only {len(gated)} of {len(workflows)} workflow(s) are gated, below {minimum_gated}; {sorted(excused)} are excused, and an exclusion list grown to cover the fleet would empty the violations without a word')
    return shortfalls

def test_the_live_fleet_census_reaches_the_whole_workflow_directory() -> None:
    """The gate below asserts an EMPTY violation list, which nothing proves alone."""
    assert _census_shortfalls(_WORKFLOWS_DIR) == []

def test_the_census_floor_refuses_a_workflow_set_narrowed_by_exemptions(tmp_path: Path) -> None:
    """A census whittled down by exemptions is refused by the gated floor alone.

    The contrast is the claim, as with the keying case: the SAME eight planted
    workflows clear both floors with nothing excused, and excusing three of
    them trips the gated floor while the total floor still passes. That is the
    only run in this module in which the gated floor decides anything -- from
    the live tree it is implied by the total floor and can never fail on its
    own. The plants come from ``_hosted_workflow`` because the census counts
    files and never reads their runners; their hosted jobs are irrelevant here.
    """
    for index in range(8):
        _hosted_workflow(tmp_path, f'lane-{index}.yml')
    assert _census_shortfalls(tmp_path) == []
    shortfalls = _census_shortfalls(tmp_path, excused=frozenset({'lane-0.yml', 'lane-1.yml', 'lane-2.yml'}))
    assert len(shortfalls) == 1, shortfalls
    assert shortfalls[0].startswith('gated: only 5 of 8 workflow(s) are gated, below 6;')

def test_every_workflow_job_runs_on_the_self_hosted_fleet() -> None:
    """Zero GitHub-hosted runner images anywhere; no workflow is exempt."""
    violations = _collect_violations(_WORKFLOWS_DIR)
    assert violations == [], f'hosted (or unresolvable) runner targets found: {violations}'

def _hosted_workflow(directory: Path, name: str) -> None:
    """Plant one workflow at ``name`` whose single job runs on a hosted image."""
    (directory / name).write_text(f"name: {name.removesuffix('.yml')}" + chr(10) + 'on: workflow_dispatch' + chr(10) + 'jobs:' + chr(10) + '  campaign:' + chr(10) + '    runs-on: ubuntu-latest' + chr(10) + '    steps: []' + chr(10), encoding='utf-8')

def test_the_exemption_is_keyed_to_the_workflow_filename_not_the_hosted_label(tmp_path: Path) -> None:
    """Two identical hosted jobs, different filenames, different verdicts.

    The contrast is the whole claim. Asserting only that a hosted job in some
    unexcused file is refused reads identically whether the exemption is keyed
    to the filename, keyed to the label, or absent altogether -- and with the
    live set empty it is absent, so that case exercised the exemption not at
    all. Deleting the skip outright left this module fully green.

    So the excused set is planted rather than taken from the live constant:
    both files carry the same `ubuntu-latest` job, and only the name differs.
    The excused one is passed over and the other is refused, which is the
    keying, and it is also the only run in which the skip executes.
    """
    _hosted_workflow(tmp_path, 'excused.yml')
    _hosted_workflow(tmp_path, 'other.yml')
    violations = _collect_violations(tmp_path, excused=frozenset({'excused.yml'}))
    assert violations == [('other.yml', 'campaign', 'ubuntu-latest')]
    assert _collect_violations(tmp_path) == [('excused.yml', 'campaign', 'ubuntu-latest'), ('other.yml', 'campaign', 'ubuntu-latest')]

def test_gate_refuses_a_hosted_yaml_extension_workflow(tmp_path: Path) -> None:
    """GitHub honors .yaml too; a hosted foo.yaml cannot slip past the glob."""
    (tmp_path / 'sneaky.yaml').write_text('name: sneaky\non: workflow_dispatch\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps: []\n', encoding='utf-8')
    violations = _collect_violations(tmp_path)
    assert violations == [('sneaky.yaml', 'build', 'ubuntu-latest')]

def test_gate_refuses_a_hosted_top_level_matrix_dimension(tmp_path: Path) -> None:
    """A list-dimension matrix (matrix.os: [ubuntu-latest]) is expanded and refused."""
    (tmp_path / 'matrixed.yml').write_text('name: matrixed\non: workflow_dispatch\njobs:\n  build:\n    strategy:\n      matrix:\n        os: [ubuntu-latest, [self-hosted, Linux, X64]]\n    runs-on: ${{ matrix.os }}\n    steps: []\n', encoding='utf-8')
    violations = _collect_violations(tmp_path)
    assert violations == [('matrixed.yml', 'build', 'ubuntu-latest')]

def test_gate_fails_closed_on_an_unresolvable_matrix_reference(tmp_path: Path) -> None:
    """A matrix runs-on resolving to zero targets is a violation, never a pass."""
    (tmp_path / 'opaque.yml').write_text('name: opaque\non: workflow_dispatch\njobs:\n  build:\n    strategy:\n      matrix:\n        other: [x]\n    runs-on: ${{ matrix.runner }}\n    steps: []\n', encoding='utf-8')
    violations = _collect_violations(tmp_path)
    assert violations == [('opaque.yml', 'build', UNRESOLVED_ZERO_TARGETS)]

def _rewrite_emitted_images(document: dict[str, Any], replacement: str) -> int:
    """Point every emitted hosted image at ``replacement``, in memory.

    Returns the number of run scripts rewritten, so a caller can tell an edit
    that changed nothing from one that changed the document.
    """
    rewritten = 0
    for job in (document.get('jobs') or {}).values():
        for step in job.get('steps') or []:
            script = str(_dp_get('dev/ci/tests/test_self_hosted_fleet.py:325:get', step, 'run', ''))
            if '"ubuntu-latest"' in script:
                step['run'] = script.replace('"ubuntu-latest"', f'"{replacement}"')
                rewritten += 1
    return rewritten

def _runtime_matrix_workflow(*, emitted_labels: str, matrix: str=_RUNTIME_MATRIX_REFERENCE) -> dict[str, Any]:
    """Return a release-shaped document whose matrix is computed at runtime.

    Modelled on the publication workflow: one job validates an inventory and
    writes the smoke matrix to an output, and the job that consumes it names no
    runner of its own. The runner labels exist only inside the producing
    script, which is the whole difficulty this fixture exists to reproduce.
    """
    return yaml.safe_load(f'name: runtime\non: workflow_dispatch\njobs:\n  inventory:\n    runs-on: ubuntu-latest\n    outputs:\n      matrix: ${{{{ steps.emit-matrix.outputs.matrix }}}}\n    steps:\n      - name: Emit\n        id: emit-matrix\n        run: |\n          emit --targets {emitted_labels}\n  smoke:\n    needs: inventory\n    strategy:\n      matrix: {matrix}\n    runs-on: ${{{{ matrix.os }}}}\n    steps: []\n')

def test_the_gate_reads_the_labels_a_runtime_matrix_producer_emits() -> None:
    """The release path's own shape resolves to real targets, not to a shrug.

    This is the positive control for the refusals below. Without it a resolver
    that reported every runtime matrix unresolvable would look identical to one
    that reads them, and the exemption would be pinned by a gate that never
    agrees the document is fine.
    """
    document = _runtime_matrix_workflow(emitted_labels='"ubuntu-latest" "macos-latest" "windows-latest"')
    targets = runner_targets(document['jobs']['smoke'], document)
    assert targets == ['ubuntu-latest', 'macos-latest', 'windows-latest']
    assert _hosted_violations('runtime.yml', document) == []

def test_a_runtime_matrix_producer_emitting_a_fleet_label_is_refused() -> None:
    """Detector teeth: a release job put back on the fleet is caught.

    The label never appears in the consuming job -- it is written in the script
    that computes the matrix -- so this is exactly the drift the previous
    reader could not see, and the one the exemption cannot survive.
    """
    document = _runtime_matrix_workflow(emitted_labels='"ubuntu-latest" "self-hosted"')
    assert _hosted_violations('runtime.yml', document) == [('runtime.yml', 'smoke', 'self-hosted')]

def test_a_runtime_matrix_producer_naming_no_label_is_refused() -> None:
    """A producer whose labels are invisible fails closed rather than passing."""
    document = _runtime_matrix_workflow(emitted_labels='--from-file targets.json')
    violations = _hosted_violations('runtime.yml', document)
    assert len(violations) == 1
    assert 'names no runner label literal' in str(violations[0][2])

@pytest.mark.parametrize(('matrix', 'expected'), [('${{ fromJSON(inputs.matrix) }}', 'not a fromJSON(needs.<job>.outputs.<output>) reference'), ('${{ fromJSON(needs.absent.outputs.matrix) }}', 'is not declared in this workflow'), ('${{ fromJSON(needs.inventory.outputs.absent) }}', 'not a ${{ steps.<id>.outputs.<key> }} reference')], ids=('not-a-job-output', 'producer-absent', 'output-absent'))
def test_a_runtime_matrix_reference_the_gate_cannot_follow_is_refused(matrix: str, expected: str) -> None:
    """Each way the indirection can break is a refusal, never a silent pass."""
    document = _runtime_matrix_workflow(emitted_labels='"ubuntu-latest"', matrix=matrix)
    violations = _hosted_violations('runtime.yml', document)
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
    (tmp_path / 'fleet.yml').write_text(yaml.safe_dump(document), encoding='utf-8')
    violations = _collect_violations(tmp_path)
    assert ('fleet.yml', 'smoke', 'self-hosted') in violations