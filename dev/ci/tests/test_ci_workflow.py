"""Structural gates for the recipes the CI lanes delegate to, and for the lanes' shared surface."""

from __future__ import annotations

import ast
import pathlib
import re
import shlex
from pathlib import Path
from typing import Any

import pytest
import yaml

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command

from ..lane_reachability import declared_lanes, resolved_recipe_commands
from ..workflow_run_text import executed_text

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
_MERGE_GATE = _WORKFLOWS_DIR / "merge-gate.yml"
#: The three lanes every change and release passes through.
_LANES = tuple(_WORKFLOWS_DIR / name for name in ("merge-gate.yml", "release.yml", "release-please.yml"))
_JUSTFILE = REPO_ROOT / "justfile"
#: The one tool-dependent module the unit lane must not collect. Named here so
#: the lane's exclusion is asserted against the module's real marker rather
#: than against whichever mechanism happens to exclude it today.
_WORKBOOK_PARITY = REPO_ROOT / "dev" / "registry" / "parity" / "tests" / "test_workbook_parity.py"
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


_REPOSITORY_ROOT = REPO_ROOT
_PYPROJECT = _REPOSITORY_ROOT / "pyproject.toml"
#: Per-test wall ceiling for the harness lane's combined real-proof pass, in
#: seconds. Deliberately above the ini default: this lane's subject is a real
#: child pytest that collects the whole first-party corpus, which takes minutes
#: by design rather than by defect.
_HARNESS_WALL_CEILING_SECONDS = 900


def _declared_harness_members() -> tuple[str, ...]:
    """Return the harness recipe's member paths, from the one canonical parser.

    Derived, never restated: the combined real-proof line is the ``test-pytest-harness``
    lane carrying the most paths, so a member added, dropped, or renamed at its
    one declaration site (the justfile) moves this without a second edit here.
    """
    harness_lanes = [lane for lane in declared_lanes(_REPOSITORY_ROOT) if lane.recipe == "test-pytest-harness"]
    return max((lane.paths for lane in harness_lanes), key=len, default=())


def test_workflow_lint_is_a_standalone_blocking_verdict_over_every_workflow() -> None:
    """The static workflow check is a gate, not a decoration.

    Its subject is the failure class that produces no failure: a `runs-on:`
    label no registered runner carries does not error at dispatch, it queues
    unbounded and silently. A job that lints one file, tolerates its own
    failure, or runs an archive it never verified would report the same green
    tick while proving none of that, so each is asserted separately.

    Ordering is load-bearing in the same way the checksum is: verifying an
    archive after executing it verifies nothing.
    """
    job = yaml.safe_load(_MERGE_GATE.read_text(encoding="utf-8"))["jobs"]["lint"]
    assert "needs" not in job, "an independent verdict must not be gated behind another job"
    assert job.get("continue-on-error") is not True
    assert job["timeout-minutes"] <= 30

    executed = executed_text(step.get("run") for step in job["steps"])
    assert "just check-workflows" in executed, (
        "the workflow lint is dispatched by recipe; a gate re-listed in YAML "
        "cannot be proven to match the gate a developer can run"
    )

    # The three properties this job used to assert INLINE - every workflow is
    # read, the archive is pinned by content, and the digest is checked before
    # the binary is executed - did not stop being required when the download
    # moved into `dev/actionlint.py`. They moved with it, so they are asserted
    # at their new home rather than deleted along with the shell that carried
    # them. This repository previously kept its own copy of that download,
    # already at a different version from vaultspec-dashboard's copy of the
    # same thirty lines.
    from dev import actionlint

    assert actionlint.VERSION.replace(".", "").isdigit() and actionlint.VERSION.count(".") >= 2, (
        "actionlint must be pinned to a dotted numeric version"
    )
    assert actionlint.ARCHIVES, "actionlint must pin at least one platform"
    for (system, machine), (suffix, digest) in actionlint.ARCHIVES.items():
        assert len(digest) == 64, (
            f"the {system}/{machine} archive must be pinned by content as well "
            "as by version, so a retagged release fails the gate rather than "
            "quietly changing what lints these workflows"
        )
        assert system in suffix, f"the {system}/{machine} entry names {suffix!r}"

    # Ordering, read from the ONE function that downloads: anchoring on the
    # whole module would find `_extract_member` at its definition, above the
    # call site, and compare two things that are not in sequence at all.
    source = pathlib.Path(actionlint.__file__).read_text(encoding="utf-8")
    acquire = source[source.index("def ensure()") :]
    assert acquire.index("_verify(archive, expected)") < acquire.index("_extract_member(archive"), (
        "the archive is unpacked before its digest is checked"
    )
    # The CALL, not the word: the module explains in a comment why it does not
    # use `extractall`, and a substring test over the source would read that
    # explanation as the defect it describes.
    calls = {
        node.func.attr
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "extractall" not in calls, (
        "an archive names its own paths and the digest says nothing about "
        "whether they are safe to write to; one member, by basename"
    )
    assert "-no-color" in source and "actionlint" in source, (
        "the provisioner must still be the thing that runs actionlint"
    )


def test_harness_recipe_runs_every_real_proof_outer_serially_and_non_vacuously() -> None:
    """Each declared harness proof preflights alone before their exact combined run.

    The worker-hook and full-corpus collectors are intentionally explicit
    members rather than a marker selection: losing either must surface as that
    member's pytest exit 5, not as an empty green aggregate. All calls are
    outer-serial, preventing their real child processes from nesting inside an
    xdist pool.
    """
    members = _declared_harness_members()
    assert members, "no justfile recipe named test-pytest-harness declares any member"
    commands = resolved_recipe_commands(_REPOSITORY_ROOT, "test-pytest-harness")

    # A lane names only what SELECTS it: markers, paths, worker count, and the
    # wall ceiling. How pytest REPORTS is declared once in
    # `[tool.pytest.ini_options] addopts` and asserted there instead, so this
    # pin cannot drift from the reporting decision the way it did while every
    # lane restated `-rsf --tb=short`.
    #
    # `-v` is the exception, and only on the real proof: it streams each
    # verdict as its test finishes, which is what makes a lane running for
    # minutes readable while it is still going. A collect-only preflight
    # finishes instantly and has nothing to stream, so it stays quiet.
    assert commands == (
        *(f"uv run --no-sync pytest -q -m integration --collect-only -n0 {member}" for member in members),
        f"uv run --no-sync pytest -v -m integration -n0 --timeout={_HARNESS_WALL_CEILING_SECONDS} {' '.join(members)}",
    )

    # The other half of that contract: the reporting flags must actually be in
    # addopts. Without this, dropping them from the lane above would silently
    # lose the skip report and the bounded traceback rather than relocate them.
    addopts = re.search(r'(?m)^addopts\s*=\s*"(.*)"', _PYPROJECT.read_text(encoding="utf-8"))
    assert addopts is not None, "no addopts declaration to carry the reporting flags"
    for flag in ("-ra", "--tb=short"):
        assert flag in addopts.group(1), (
            f"{flag} is on neither the lane nor addopts; a red lane then loses its "
            "skip report, or writes the unbounded tracebacks that once produced a "
            "ten-million-line log"
        )
    assert "-rsf" not in addopts.group(1), (
        "-ra already reports every non-passing outcome, skips included; -rsf beside "
        "it is the restatement this pin exists to prevent"
    )
    assert all("-n0" in command for command in commands)
    assert all("||" not in command and ";" not in command for command in commands)


def test_the_harness_real_proof_outruns_the_default_per_test_wall_ceiling() -> None:
    """The lane raises its own wall ceiling, because its subject legitimately runs minutes.

    One member recursively collects the entire first-party corpus in a real
    child pytest. Measured at 75 s on a quiet tree and 272 s on a loaded one,
    against a 300 s ini default -- so under load the default kills a HEALTHY
    proof and reports it as a harness failure, which is the least useful thing
    a verdict can do. The raised ceiling belongs to the combined real-proof
    pass only; the collect-only preflights stay on the default, since they do
    no work beyond importing.
    """
    timeout_match = re.search(
        r"(?m)^timeout\s*=\s*(\d+)",
        _PYPROJECT.read_text(encoding="utf-8"),
    )
    assert timeout_match is not None, "pyproject.toml must declare a pytest timeout"
    ini_ceiling = int(timeout_match.group(1))
    commands = resolved_recipe_commands(_REPOSITORY_ROOT, "test-pytest-harness")
    real_proof = commands[-1]

    assert ini_ceiling < _HARNESS_WALL_CEILING_SECONDS, (
        f"the harness ceiling ({_HARNESS_WALL_CEILING_SECONDS}s) must exceed the ini default ({ini_ceiling}s), "
        "or raising it accomplishes nothing"
    )
    assert f"--timeout={_HARNESS_WALL_CEILING_SECONDS}" in real_proof
    assert all("--timeout=" not in command for command in commands[:-1]), (
        "only the combined real-proof pass needs the raised ceiling; a preflight that needs it is doing real work"
    )


def test_harness_member_preflight_rejects_empty_collection_even_when_another_member_exists(tmp_path: Path) -> None:
    """A per-member preflight catches the empty proof an aggregate would hide."""
    # Both fixture members carry a `hex_*` marker beside `integration`: this
    # repository requires exactly one of them on every collected item and
    # enforces that during collection. Without it the populated control fails
    # the marker gate instead of collecting, and a control that never collects
    # proves nothing about the empty member it exists to contrast with.
    header = "import pytest\n\npytestmark = [pytest.mark.integration, pytest.mark.hex_core]\n"
    empty_member = tmp_path / "test_empty_harness_member.py"
    empty_member.write_text(header, encoding="utf-8")
    populated_member = tmp_path / "test_populated_harness_member.py"
    populated_member.write_text(
        header + "\n\ndef test_real_item_is_collectable() -> None:\n    pass\n",
        encoding="utf-8",
    )

    members = _declared_harness_members()
    commands = resolved_recipe_commands(_REPOSITORY_ROOT, "test-pytest-harness")
    preflight = next(
        (command for command in commands if "--collect-only" in command and members[0] in command),
        None,
    )
    assert preflight is not None, "the resolved test-pytest-harness recipe has no worker-hook member preflight"
    command = shlex.split(preflight)
    assert command == [
        "uv",
        "run",
        "--no-sync",
        "pytest",
        "-q",
        "-m",
        "integration",
        "--collect-only",
        "-n0",
        members[0],
    ]

    # The fixture members live outside the repository, and pytest builds its
    # collection tree from the ancestors of the paths it is given. Without an
    # explicit root it therefore walks up to the drive root and stats every
    # entry on the way -- which aborts collection outright on a host whose
    # profile directory holds an untraversable mount point (a cloud-sync
    # placeholder, a disconnected network drive), before either member is read.
    # Naming the root bounds that walk to the fixture directory.
    invocation = [*command[:-1], "--rootdir", str(tmp_path)]

    aggregate = run_command(
        [*invocation, str(populated_member), str(empty_member)],
        cwd=_REPOSITORY_ROOT,
        timeout_seconds=30,
    )
    assert aggregate.returncode == 0, (
        "the populated control must make aggregate collection non-empty\n"
        f"command: {shlex.join([*invocation, str(populated_member), str(empty_member)])}\n"
        f"stdout:\n{aggregate.stdout}\nstderr:\n{aggregate.stderr}"
    )

    empty_preflight = run_command(
        [*invocation, str(empty_member)],
        cwd=_REPOSITORY_ROOT,
        timeout_seconds=30,
    )
    assert empty_preflight.returncode == 5, (
        "the per-member collect preflight must preserve pytest exit 5 for an empty member\n"
        f"command: {shlex.join([*invocation, str(empty_member)])}\n"
        f"stdout:\n{empty_preflight.stdout}\nstderr:\n{empty_preflight.stderr}"
    )


def test_the_ci_contracts_recipe_carries_the_substance_the_workflow_delegates() -> None:
    """The workflow names a recipe, so the recipe is where the pin has to bite.

    Delegating the step to `just test-ci-contracts` moves the paths and the
    marker expression out of the workflow, which is the point -- the recipe becomes
    the one declaration site for the CI/repository contract population. A pin
    that only checked the workflow says "a recipe is invoked" and nothing about
    what it does, so emptying the recipe would pass it while running no gates at
    all. This asserts the substance at its canonical home.

    Explicit -n 8, never -n auto: three runners share the machine (machine-aware
    sizing, test_machine_aware_load.py). The marker expression is explicit
    because the default `-m unit` addopts deselects the integration-marked
    workflow pins and still exits zero.
    """
    recipe = next(
        (line for line in _JUSTFILE.read_text(encoding="utf-8").splitlines() if "dev/ci/tests" in line),
        None,
    )
    assert recipe is not None, "no justfile line names dev/ci/tests; the delegated lane has no home"
    # `-v`, not `-q`: this lane streams each verdict as it finishes, so a run
    # that is killed or still going has already named what failed. The
    # reporting flags it used to restate (`-rsf --tb=short`) now live in
    # `[tool.pytest.ini_options] addopts`, pinned by
    # `test_harness_recipe_runs_every_real_proof_outer_serially_and_non_vacuously`.
    assert 'pytest -v -n {{pytest_workers}} -m "(unit or integration) and not serial' in recipe
    for directory in ("dev/ci/tests", "dev/deploy/tests", "dev/release/tests"):
        assert directory in recipe, f"the delegated lane no longer reaches {directory}"


def test_ci_contracts_builds_real_docs_before_running_deployment_tests() -> None:
    """Provision the real HTML corpus before deployment preflight tests read it.

    The deployment search-index contracts intentionally copy real built pages
    from ``docs/_build/html``.  A clean checkout therefore needs the small
    single-page build before any pytest pass; a full docs build would make this
    CI contract unnecessarily expensive.
    """
    lines = _JUSTFILE.read_text(encoding="utf-8").splitlines()
    # `test-ci-contracts-gate`, not the `test-ci-contracts` aggregate above it:
    # the aggregate is two `just` calls, and the docs corpus has to exist before
    # the pytest pass that reads it, which is this recipe's.
    start = lines.index("test-ci-contracts-gate:")
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line and not line.startswith((" ", "\t")):
            break
        body.append(line.strip())

    build = "uv run --no-sync python -m dev.docs.build --single-page docs/index.md"
    assert body.count(f"@{build}") == 1, "the CI contract must provision one canonical single-page docs build"
    build_index = body.index(f"@{build}")
    pytest_indices = [index for index, line in enumerate(body) if " pytest " in f" {line} "]
    assert pytest_indices, "the CI contract has no pytest pass to exercise deployment tests"
    assert build_index < min(pytest_indices), "the docs corpus must be built before any CI-contract pytest pass"


def test_the_test_unit_recipe_carries_the_substance_the_workflow_delegates() -> None:
    """`test-unit` is the same recipe local runs invoke; emptying it must not pass.

    Same rationale as `test_the_dev_ci_recipe_carries_the_substance_the_workflow_delegates`:
    the workflow now names a recipe, so the recipe -- not the workflow line --
    is where the marker-expression pin has to bite.
    """
    recipe = next(
        (line for line in _JUSTFILE.read_text(encoding="utf-8").splitlines() if line.startswith("test-unit ")),
        None,
    )
    assert recipe is not None, "no justfile recipe line named test-unit; the delegated lane has no home"

    body = next(
        (line for line in _JUSTFILE.read_text(encoding="utf-8").splitlines() if "--dist=loadfile" in line),
        None,
    )
    assert body is not None, "no justfile line carries the test-unit body; the delegated lane has no home"
    assert (
        "-m 'unit and not perf and not external_tool and not os_keychain "
        "and not windows_only and not tui_render and not resident_service'"
    ) in body
    assert "--durations=" in body, "the durations override the CI step passes must reach the underlying pytest call"

    # The workbook-parity module is held out of this lane by its OWN marker,
    # not by a path ignore. This gate used to pin the ignore directive, which
    # made it red the moment that redundant directive was correctly deleted:
    # a marker states its reason where a path ignore states nothing, so the
    # directive's removal was the improvement and the pin was the defect.
    # Re-pinning on the mechanism would have meant undoing the improvement to
    # make its own gate pass. What the lane actually needs is that the module
    # carries the marker the expression above excludes, so that is what is
    # asserted -- otherwise a marker dropped from that module would silently
    # pull a tool-dependent test into the offline unit lane.
    parity_markers = _module_level_markers(_WORKBOOK_PARITY)
    assert "external_tool" in parity_markers, (
        "test_workbook_parity.py no longer carries external_tool, so nothing holds it out of the "
        f"unit lane; either restore the marker or give the lane an explicit exclusion (found {sorted(parity_markers)})"
    )


def _module_level_markers(module: Path) -> frozenset[str]:
    """Return the marker names a module applies to every test it collects.

    Read from the parsed `pytestmark` assignment rather than from the file's
    bytes: a substring search is satisfied by the marker's name appearing in a
    docstring, a comment, or a note explaining that the marker was REMOVED, so
    the exact regression this gate exists to catch -- a dropped marker that
    pulls a tool-dependent module into the offline unit lane -- would read as
    green.
    """
    names: set[str] = set()
    for node in ast.parse(module.read_text(encoding="utf-8")).body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets):
            continue
        elements = node.value.elts if isinstance(node.value, (ast.List, ast.Tuple)) else [node.value]
        for element in elements:
            if isinstance(element, ast.Call):
                element = element.func
            if isinstance(element, ast.Attribute):
                names.add(element.attr)
    return frozenset(names)


def test_product_integration_parallel_recipe_carries_the_canonical_selection() -> None:
    """The product integration aggregate owns the cross-layer integration population."""
    lines = _JUSTFILE.read_text(encoding="utf-8").splitlines()
    recipe = next((line for line in lines if line == "test-integration-parallel:"), None)
    assert recipe is not None, "no canonical product integration recipe was declared"

    body = next((line for line in lines if "integration and not serial" in line), None)
    assert body is not None, "the canonical integration recipe has no parallel marker selection"
    assert "not perf and not external_tool and not os_keychain" in body


#: Below these the lanes have stopped carrying a surface to inspect. Floors,
#: not pinned counts.
_MINIMUM_LANE_JOBS = 1
_MINIMUM_LANE_STEPS = 8


def _lane_documents(paths: tuple[Path, ...] = _LANES) -> tuple[tuple[Path, dict[str, Any]], ...]:
    """Load the lanes, with the three of them asserted to carry real steps.

    The gates below assert that NO step does some forbidden thing. A lane
    parsing to `jobs: {}` satisfies every one of those claims while running
    nothing, so the collection is floored rather than trusted.
    """
    loaded: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        jobs = document["jobs"]
        assert len(jobs) >= _MINIMUM_LANE_JOBS, f"{path.name} declares no job"
        loaded.append((path, document))
    steps = sum(len(job.get("steps") or ()) for _, document in loaded for job in document["jobs"].values())
    assert steps >= _MINIMUM_LANE_STEPS, (
        f"the lanes declare {steps} step(s); below this the prohibitions hold because there is nothing to prohibit"
    )
    return tuple(loaded)


def _fixture_workflow(name: str, filler: str, offending: str) -> str:
    """A one-job workflow carrying enough steps to pass the floor, then one offending step."""
    steps = "".join(f"      - run: {command}\n" for command in (*(filler,) * _MINIMUM_LANE_STEPS, offending))
    header = f"name: {name}\non: workflow_dispatch\njobs:\n  lane:\n    runs-on: [self-hosted, Linux, X64]\n"
    return f"{header}    steps:\n{steps}"


def _lane_commands(document: dict[str, Any]) -> str:
    return executed_text(step.get("run") for job in document["jobs"].values() for step in job.get("steps") or [])


def _mutating_repair_offenders(documents: tuple[tuple[Path, dict[str, Any]], ...]) -> list[str]:
    offenders: list[str] = []
    for path, document in documents:
        commands = _lane_commands(document)
        offenders.extend(f"{path.name}: {token}" for token in ("fix-code", "dev.quality.fixes") if token in commands)
    return offenders


def test_ci_lanes_never_invoke_the_mutating_path_repair() -> None:
    """The lanes keep read-only gates authoritative and never rewrite sources."""
    assert _mutating_repair_offenders(_lane_documents()) == []


def test_the_mutating_repair_gate_refuses_a_lane_that_repairs(tmp_path: Path) -> None:
    """Teeth: a lane running the mutating repair is reported."""
    workflow = tmp_path / "repairing.yml"
    workflow.write_text(_fixture_workflow("Cadrumo Repairing", "just check-style", "just fix-code"), encoding="utf-8")
    assert _mutating_repair_offenders(_lane_documents((workflow,))) == ["repairing.yml: fix-code"]


def _dotenv_offenders(documents: tuple[tuple[Path, dict[str, Any]], ...]) -> list[str]:
    offenders: list[str] = []
    for path, document in documents:
        commands = _lane_commands(document)
        offenders.extend(f"{path.name}: {token}" for token in ("env-setup", "env/.env") if token in commands)
    return offenders


def test_ci_lanes_do_not_materialise_operator_dotenv() -> None:
    """The lanes stay hermetic instead of loading operator-template overrides."""
    assert _dotenv_offenders(_lane_documents()) == []


def test_the_dotenv_gate_refuses_a_lane_that_loads_operator_overrides(tmp_path: Path) -> None:
    """Teeth: a lane materialising the operator dotenv is reported."""
    workflow = tmp_path / "dotenv.yml"
    workflow.write_text(_fixture_workflow("Cadrumo Dotenv", "just test-unit", "just env-setup"), encoding="utf-8")
    assert _dotenv_offenders(_lane_documents((workflow,))) == ["dotenv.yml: env-setup"]


def _product_surface(document: dict[str, Any]) -> str:
    jobs = list(document["jobs"].values())
    return "\n".join(
        (
            str(document["name"]),
            *(str(job.get("name", "")) for job in jobs),
            *(str(step.get("name", "")) for job in jobs for step in job.get("steps") or []),
            _lane_commands(document),
        )
    )


def test_ci_lanes_product_surface_has_no_former_identity() -> None:
    """The lanes retain `aeat` only as the human CLI, never as a product identity."""
    offenders = {
        path.name: forms
        for path, document in _lane_documents()
        if (forms := _prohibited_aeat_product_forms(_product_surface(document)))
    }
    assert offenders == {}

    recipe_commands = resolved_recipe_commands(_REPOSITORY_ROOT, "check-registry")
    assert recipe_commands, "`just check-registry` resolves to no command"
    assert _prohibited_aeat_product_forms("\n".join(recipe_commands)) == ()


def test_the_identity_gate_refuses_a_lane_that_installs_the_former_distribution() -> None:
    """Teeth: a lane step naming the former distribution is reported."""
    document = {
        "name": "Cadrumo Former",
        "jobs": {"smoke": {"name": "Test: Smoke (Linux)", "steps": [{"run": "uv pip install aeat"}]}},
    }
    assert "distribution-install" in _prohibited_aeat_product_forms(_product_surface(document))


@pytest.mark.parametrize(
    "surface",
    (
        "uv run --no-sync python -m dev.registry.conformance integrity",
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
