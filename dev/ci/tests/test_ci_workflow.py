"""Structural behavior gate for the Cadrumo CI workflow."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest
import yaml

from dev._paths import REPO_ROOT

from ...packaging._command import run_command
from ..lane_reachability import declared_lanes, resolved_recipe_commands

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
_JUSTFILE = REPO_ROOT / "justfile"
#: The one tool-dependent module the unit lane must not collect. Named here so
#: the lane's exclusion is asserted against the module's real marker rather
#: than against whichever mechanism happens to exclude it today.
_WORKBOOK_PARITY = REPO_ROOT / "dev" / "registry" / "tests" / "test_workbook_parity.py"
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


_FULL_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci-full.yml"
_REPOSITORY_ROOT = _WORKFLOW.parents[2]
_PYPROJECT = _REPOSITORY_ROOT / "pyproject.toml"
#: Per-test wall ceiling for the harness lane's combined real-proof pass, in
#: seconds. Deliberately above the ini default: this lane's subject is a real
#: child pytest that collects the whole first-party corpus, which takes minutes
#: by design rather than by defect.
_HARNESS_WALL_CEILING_SECONDS = 900


def _declared_harness_members() -> tuple[str, ...]:
    """Return the harness recipe's member paths, from the one canonical parser.

    Derived, never restated: the combined real-proof line is the ``test-harness``
    lane carrying the most paths, so a member added, dropped, or renamed at its
    one declaration site (the justfile) moves this without a second edit here.
    """
    harness_lanes = [lane for lane in declared_lanes(_REPOSITORY_ROOT) if lane.recipe == "test-harness"]
    return max((lane.paths for lane in harness_lanes), key=len, default=())


def test_ci_workflow_runs_canonical_cadrumo_commands_and_paths() -> None:
    """Per-push CI has independent static, unit, and harness verdicts."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert document["name"] == "Cadrumo CI"
    assert set(document["jobs"]) == {"cadrumo-static", "cadrumo-unit", "cadrumo-test-harness"}

    static = document["jobs"]["cadrumo-static"]
    static_commands = "\n".join(str(step.get("run", "")) for step in static["steps"])
    assert "uv run --no-sync aeat app registry verify" in static_commands
    assert "uv run --no-sync python -m dev.registry.parity.maintenance_cli audit-oracles" in static_commands
    assert "semgrep --config .semgrep/rules/ --error src/cadrumo/" in static_commands
    # The dev-tree workflow/tooling conformance gates run per-push here, via the
    # `test-dev-ci` recipe. The workflow names the recipe and the recipe owns the
    # paths, because the justfile is the sole declaration site for every `dev/`
    # lane; the substance of the invocation is pinned in the recipe, below.
    assert "just test-dev-ci" in static_commands
    # The four cross-layer conformance gates (rule-surface, status-frontend,
    # self-referential-string, suggestion-command) run per-push here, via the
    # `test-per-push-integration-gates` recipe -- previously reachable by no
    # automatically-triggered workflow at all.
    assert "just test-per-push-integration-gates" in static_commands

    unit = document["jobs"]["cadrumo-unit"]
    unit_commands = "\n".join(str(step.get("run", "")) for step in unit["steps"])
    # Routed through the `test-unit` recipe (same one `just test-unit` runs
    # locally) so the marker expression and the durations/worker overrides
    # have one declaration site; the recipe's substance is pinned below.
    assert "CADRUMO_PYTEST_WORKERS=8 just test-unit 50" in unit_commands


def test_harness_recipe_runs_every_real_proof_outer_serially_and_non_vacuously() -> None:
    """Each declared harness proof preflights alone before their exact combined run.

    The worker-hook and full-corpus collectors are intentionally explicit
    members rather than a marker selection: losing either must surface as that
    member's pytest exit 5, not as an empty green aggregate. All calls are
    outer-serial, preventing their real child processes from nesting inside an
    xdist pool.
    """
    members = _declared_harness_members()
    assert members, "no justfile recipe named test-harness declares any member"
    commands = resolved_recipe_commands(_REPOSITORY_ROOT, "test-harness")

    pytest_prefix = "uv run --no-sync pytest -q -m integration"
    assert commands == (
        *(f"{pytest_prefix} --collect-only -n0 {member}" for member in members),
        f"{pytest_prefix} -rsf -n0 --timeout={_HARNESS_WALL_CEILING_SECONDS} {' '.join(members)}",
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
    ini_ceiling = int(re.search(r"(?m)^timeout\s*=\s*(\d+)", _PYPROJECT.read_text(encoding="utf-8")).group(1))
    commands = resolved_recipe_commands(_REPOSITORY_ROOT, "test-harness")
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
    empty_member = tmp_path / "test_empty_harness_member.py"
    empty_member.write_text("import pytest\n\npytestmark = pytest.mark.integration\n", encoding="utf-8")
    populated_member = tmp_path / "test_populated_harness_member.py"
    populated_member.write_text(
        "import pytest\n\n"
        "pytestmark = pytest.mark.integration\n\n"
        "def test_real_item_is_collectable() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )

    members = _declared_harness_members()
    commands = resolved_recipe_commands(_REPOSITORY_ROOT, "test-harness")
    preflight = next(
        (command for command in commands if "--collect-only" in command and members[0] in command),
        None,
    )
    assert preflight is not None, "the resolved test-harness recipe has no worker-hook member preflight"
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

    aggregate = run_command(
        [*command[:-1], str(populated_member), str(empty_member)],
        cwd=_REPOSITORY_ROOT,
        timeout_seconds=30,
    )
    assert aggregate.returncode == 0, (
        "the populated control must make aggregate collection non-empty\n"
        f"command: {shlex.join([*command[:-1], str(populated_member), str(empty_member)])}\n"
        f"stdout:\n{aggregate.stdout}\nstderr:\n{aggregate.stderr}"
    )

    empty_preflight = run_command(
        [*command[:-1], str(empty_member)],
        cwd=_REPOSITORY_ROOT,
        timeout_seconds=30,
    )
    assert empty_preflight.returncode == 5, (
        "the per-member collect preflight must preserve pytest exit 5 for an empty member\n"
        f"command: {shlex.join([*command[:-1], str(empty_member)])}\n"
        f"stdout:\n{empty_preflight.stdout}\nstderr:\n{empty_preflight.stderr}"
    )


def test_ci_harness_verdict_is_a_standalone_blocking_job() -> None:
    """The deterministic proof reports independently from static and unit work."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    harness = document["jobs"]["cadrumo-test-harness"]
    assert "needs" not in harness
    assert harness["timeout-minutes"] <= 25
    assert harness.get("continue-on-error") is not True

    commands = tuple(str(step.get("run", "")) for step in harness["steps"] if step.get("run"))
    assert commands[-1] == "just test-harness"
    assert sum(command == "just test-harness" for command in commands) == 1

    routine_commands = "\n".join(
        str(step.get("run", ""))
        for job_name in ("cadrumo-static", "cadrumo-unit")
        for step in document["jobs"][job_name]["steps"]
    )
    assert "just test-harness" not in routine_commands


def test_the_dev_ci_recipe_carries_the_substance_the_workflow_delegates() -> None:
    """The workflow names a recipe, so the recipe is where the pin has to bite.

    Delegating the step to `just test-dev-ci` moves the paths and the marker
    expression out of the workflow, which is the point -- the justfile is the
    sole declaration site for every `dev/` lane. But a pin that only checked the
    workflow says "a recipe is invoked" and nothing about what it does, so
    emptying the recipe would pass it while running no gates at all. This asserts
    the substance at its new home.

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
    assert 'pytest -q -n 8 --timeout=900 -m "unit or (integration and not serial)"' in recipe
    for directory in ("dev/ci/tests", "dev/packaging/tests", "dev/quality/tests", "dev/release/tests"):
        assert directory in recipe, f"the delegated lane no longer reaches {directory}"


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
    assert "-m 'unit and not external_tool and not os_keychain'" in body
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
    parity_markers = _WORKBOOK_PARITY.read_text(encoding="utf-8")
    assert "pytest.mark.external_tool" in parity_markers, (
        "test_workbook_parity.py no longer carries external_tool, so nothing holds it out of the "
        "unit lane; either restore the marker or give the lane an explicit exclusion"
    )


def test_the_per_push_integration_gates_recipe_carries_the_substance_the_workflow_delegates() -> None:
    """The four named gates, not just any `integration`-marked test, must be named.

    Same rationale as the two recipe-substance pins above: the workflow names a
    recipe, so the recipe -- not the workflow line -- is where the path-set and
    marker-expression pin has to bite.
    """
    recipe = next(
        (
            line
            for line in _JUSTFILE.read_text(encoding="utf-8").splitlines()
            if line.startswith("test-per-push-integration-gates:")
        ),
        None,
    )
    assert recipe is not None, "no justfile recipe line named test-per-push-integration-gates"

    body = next(
        (
            line
            for line in _JUSTFILE.read_text(encoding="utf-8").splitlines()
            if "test_suggestion_command_conformance.py" in line
        ),
        None,
    )
    assert body is not None, "no justfile line carries the recipe body; the delegated lane has no home"
    assert "not serial and not perf and not external_tool and not os_keychain and not resident_service" in body
    for target in (
        "src/cadrumo/entrypoints/cli/_config/tests/test_status_frontend_gate.py",
        "src/cadrumo/entrypoints/cli/tests/test_self_referential_string_conformance.py",
        "dev/tests/test_suggestion_command_conformance.py",
    ):
        assert target in body, f"the delegated lane no longer names {target}"


def test_ci_per_push_integration_conformance_step_is_exact_and_blocking() -> None:
    """The four-gate per-push verdict delegates once and cannot be made advisory."""
    document = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    static = document["jobs"]["cadrumo-static"]
    step = next(
        (
            candidate
            for candidate in static["steps"]
            if candidate.get("name")
            == "Per-push integration conformance gates (rule-surface, status-frontend, self-referential-string, suggestion-command)"
        ),
        None,
    )

    assert step is not None, "the per-push integration conformance step is missing"
    assert step["run"] == "CADRUMO_PYTEST_WORKERS=8 just test-per-push-integration-gates"
    assert "continue-on-error" not in step


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
    # Same `test-unit` recipe ci.yml routes through, with the full lane's own
    # durations value; the recipe's substance is pinned in
    # test_the_test_unit_recipe_carries_the_substance_the_workflow_delegates.
    assert "CADRUMO_PYTEST_WORKERS=8 just test-unit 100" in commands
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
    }
    assert "uv run --no-sync python -m dev.registry.parity.maintenance_cli audit-oracles" in commands
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
    them by marker alone would reinstate it. Routed through the
    `test-channel-artifacts` recipe, so the workflow step names the recipe and
    the recipe -- not the workflow line -- is where this pin has to bite (same
    pattern as `test_the_dev_ci_recipe_carries_the_substance_the_workflow_delegates`).
    """
    document = yaml.safe_load(_FULL_WORKFLOW.read_text(encoding="utf-8"))
    steps = document["jobs"]["cadrumo-full-conformance"]["steps"]
    step = next(
        (str(step["run"]) for step in steps if "test-channel-artifacts" in str(step.get("run", ""))),
        None,
    )
    assert step is not None, "no full-lane step invokes the test-channel-artifacts recipe"

    generator = next(
        (line for line in _JUSTFILE.read_text(encoding="utf-8").splitlines() if "packaging/homebrew/tests" in line),
        None,
    )
    assert generator is not None, "no justfile line names packaging/homebrew/tests; the delegated lane has no home"
    assert "packaging/scoop/tests" in generator, "the Scoop generator tests share this lane"
    assert "-n0" in generator, "serial tests must run single-worker or they are held out silently"
    assert "-m serial" in generator, "the lane must select the serial marker these tests carry"
