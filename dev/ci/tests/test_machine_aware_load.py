"""Structural gate: CI lanes are sized for the shared machines, never `-n auto`.

The fleet is six runners on TWO physical machines (three per box, see
`.github/ci-control-plane.md`), so a lane that sizes itself as if it owns the machine
(`pytest -n auto` grabbing every logical CPU) over-subscribes whatever runs
beside it. Every CI pytest invocation must carry an explicit worker count, the
packaging campaign legs must pass their per-machine sizing env, and the
Homebrew matrix — two of whose three legs live on the one MacBook — must be
parallelism-bounded.
"""

from __future__ import annotations

import ast
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from ...packaging._command import run_command

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[3]
_WORKFLOWS_DIR: Final = _REPOSITORY_ROOT / ".github" / "workflows"
_JUSTFILE: Final = _REPOSITORY_ROOT / "justfile"
_EXPLICIT_WORKERS: Final = re.compile(r"pytest\b[^\n]*\s-n\s*\d+")
# A justfile recipe header: `name`, optional params/attributes, then a bare
# `:` (not `:=`, which is a variable assignment). Must handle parameterized
# recipes (`test-unit durations="":`) as well as bare ones (`foo:`).
_RECIPE_HEADER: Final = re.compile(r"^(?P<name>[a-z][\w-]*)\b(?P<params>[^:]*):(?![=])")
# A single justfile recipe parameter, e.g. `workers="auto"` or `*run_ids`.
_RECIPE_PARAM: Final = re.compile(r"[a-zA-Z_]\w*(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'))?")
# A top-level justfile variable backed by an env var, e.g.
# `pytest_workers := env_var_or_default("CADRUMO_PYTEST_WORKERS", "auto")`.
_ENV_BACKED_VARIABLE: Final = re.compile(
    r'^(?P<name>[a-z_]\w*)\s*:=\s*env_var_or_default\(\s*"(?P<env>[A-Z_]\w*)"',
)
# A workflow `run:` line delegating to a justfile recipe, e.g.
# `CADRUMO_PYTEST_WORKERS=8 just test-unit 50`.
_JUST_CALL: Final = re.compile(r"\bjust\s+(?P<recipe>[a-z][\w-]*)")
_TEMPLATE_REF: Final = re.compile(r"\{\{\s*(?P<name>[a-zA-Z_]\w*)\s*\}\}")


def _document(name: str) -> dict[str, Any]:
    return yaml.safe_load((_WORKFLOWS_DIR / name).read_text(encoding="utf-8"))


def _justfile_recipe_bodies() -> dict[str, list[str]]:
    """Return every justfile recipe name -> its indented body lines."""
    bodies: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in _JUSTFILE.read_text(encoding="utf-8").splitlines():
        header = _RECIPE_HEADER.match(raw_line)
        if header is not None:
            current = header.group("name")
            bodies.setdefault(current, [])
            continue
        if current is not None and raw_line[:1].isspace():
            bodies[current].append(raw_line.strip())
    return bodies


def _justfile_recipe_params() -> dict[str, list[str]]:
    """Return every justfile recipe name -> its ordered parameter names."""
    params: dict[str, list[str]] = {}
    for raw_line in _JUSTFILE.read_text(encoding="utf-8").splitlines():
        header = _RECIPE_HEADER.match(raw_line)
        if header is None:
            continue
        params[header.group("name")] = [
            match.group(0).split("=")[0].strip().lstrip("*") for match in _RECIPE_PARAM.finditer(header.group("params"))
        ]
    return params


def _justfile_env_backed_variables() -> dict[str, str]:
    """Return every top-level justfile variable name -> its backing env var.

    Only covers the `name := env_var_or_default("ENV_VAR", ...)` shape this
    justfile uses (e.g. `pytest_workers`); any other declaration shape is
    absent, and an absent mapping resolves as unpinned (fails the gate).
    """
    variables: dict[str, str] = {}
    for raw_line in _JUSTFILE.read_text(encoding="utf-8").splitlines():
        match = _ENV_BACKED_VARIABLE.match(raw_line.strip())
        if match is not None:
            variables[match.group("name")] = match.group("env")
    return variables


def _resolve_recipe_line(
    body_line: str,
    *,
    params: list[str],
    call_args: list[str],
    env_prefix: str,
    env_backed_variables: dict[str, str],
) -> str:
    """Substitute every `{{name}}` template in a recipe body line for one call site.

    A template resolves two ways, matching how `just` itself resolves it: a
    recipe's OWN parameter (`docs-check workers="auto":`, positionally
    supplied by the caller, `just docs-check 8`), or a top-level env-backed
    justfile variable (`pytest_workers`, overridden by an env-var prefix on
    the calling line, `CADRUMO_PYTEST_WORKERS=8 just test-unit 50`). A
    template that resolves to neither, or whose caller supplies no value, is
    left untouched -- textually distinct from any explicit integer, so it
    correctly fails the explicit-`-n` check below exactly as `-n auto` would.
    """

    def _substitute(match: re.Match[str]) -> str:
        name = match.group("name")
        if name in params:
            index = params.index(name)
            return call_args[index] if index < len(call_args) else match.group(0)
        env_var = env_backed_variables.get(name)
        if env_var is not None:
            found = re.search(rf"\b{re.escape(env_var)}=(\S+)", env_prefix)
            if found is not None:
                return found.group(1)
        return match.group(0)

    return _TEMPLATE_REF.sub(_substitute, body_line)


def _pytest_lines(
    document: dict[str, Any],
    recipe_bodies: dict[str, list[str]],
    recipe_params: dict[str, list[str]],
    env_backed_variables: dict[str, str],
) -> list[str]:
    """Resolve every pytest invocation a workflow reaches, following `just <recipe>` delegation.

    A workflow step's `run:` line either carries `pytest` directly, or
    delegates to a `just <recipe>` whose body carries it. Routing a pytest
    invocation into a recipe moved the run line's substance, not just
    its label -- a workflow line naming a recipe with no pytest in it, or
    naming nothing at all, must still fail this gate exactly as an empty
    `-n auto` invocation would have. The recipe's own worker-count template is
    substituted using the CALLING line's positional args and env-var prefix,
    so the check below applies to what CI actually executes, not to the
    recipe's local-dev default.
    """
    lines: list[str] = []
    for job in document["jobs"].values():
        for step in job.get("steps") or []:
            for raw_line in str(step.get("run", "")).splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                if "pytest" in line:
                    lines.append(line)
                    continue
                match = _JUST_CALL.search(line)
                if match is None:
                    continue
                recipe = match.group("recipe")
                env_prefix = line[: match.start()]
                call_args = line[match.end() :].split()
                for body_line in recipe_bodies.get(recipe, []):
                    if "pytest" not in body_line:
                        continue
                    resolved = _resolve_recipe_line(
                        body_line,
                        params=recipe_params.get(recipe, []),
                        call_args=call_args,
                        env_prefix=env_prefix,
                        env_backed_variables=env_backed_variables,
                    )
                    lines.append(f"{env_prefix}{resolved}")
    return lines


@pytest.mark.parametrize(
    "workflow",
    ("ci.yml", "ci-full.yml", "agent-harness-eval.yml", "aeat-drift-detector.yml"),
)
def test_ci_pytest_invocations_carry_explicit_worker_counts(workflow: str) -> None:
    """Every CI pytest run line declares an explicit ``-n <int>``.

    ``-n auto`` — spelled out, inherited from the addopts default, or reached
    through an unpinned `just <recipe>` delegation — must never reach a
    shared machine from CI.
    """
    lines = _pytest_lines(
        _document(workflow),
        _justfile_recipe_bodies(),
        _justfile_recipe_params(),
        _justfile_env_backed_variables(),
    )
    assert lines, f"{workflow} carries no pytest invocation to gate"
    for line in lines:
        assert "-n auto" not in line, (workflow, line)
        assert _EXPLICIT_WORKERS.search(line) or re.search(r"pytest\b[^\n]*\s-n0\b", line), (workflow, line)


def test_campaign_legs_pass_machine_share_sizing() -> None:
    """Each packaging-smoke campaign step sets the per-machine sizing env.

    Workstation legs (24 logical CPUs / 3 runners) get 8 test workers; the
    MacBook leg (6 CPUs / 3 runners) gets 2; lane concurrency is bounded per
    leg. The campaign driver turns CADRUMO_TEST_WORKERS into an explicit
    `-n N` on its preflight pytest pass.
    """
    document = _document("packaging-smoke.yml")
    campaign_steps = [
        step
        for job in document["jobs"].values()
        for step in job.get("steps") or []
        if "packaging campaign" in str(step.get("name", ""))
    ]
    assert len(campaign_steps) == 3, [step.get("name") for step in campaign_steps]
    sizes = sorted(
        (step["env"]["CADRUMO_TEST_WORKERS"], step["env"]["CADRUMO_PACKAGING_LANE_CONCURRENCY"])
        for step in campaign_steps
    )
    assert sizes == [("2", "2"), ("8", "2"), ("8", "3")], sizes


def test_homebrew_matrix_is_parallelism_bounded_with_per_leg_make_jobs() -> None:
    """Two of the three homebrew legs share the MacBook: bound them.

    ``max-parallel: 2`` caps co-landing legs, and brew's build-from-source
    parallelism is sized per leg via ``HOMEBREW_MAKE_JOBS``.
    """
    document = _document("packaging-homebrew.yml")
    strategy = document["jobs"]["cadrumo-homebrew-acquisition"]["strategy"]
    assert strategy["max-parallel"] == 2
    rows = strategy["matrix"]["include"]
    jobs_by_id = {row["id"]: row["make_jobs"] for row in rows}
    assert jobs_by_id == {
        "macos-arm64": "2",
        "linux-arm64": "2",
        "linux-x86_64": "8",
    }
    audit = next(
        step
        for job in document["jobs"].values()
        for step in job.get("steps") or []
        if step.get("name") == "Audit install and exercise Cadrumo through Homebrew"
    )
    assert audit["env"]["HOMEBREW_MAKE_JOBS"] == "${{ matrix.make_jobs }}"


# ── Outer-serial harness lane: the multiplicative-cost boundary ──────────────
#
# The harness proofs reach their subject by spawning a real child pytest -- one
# boots a full xdist worker pool, the other recursively collects the entire
# first-party corpus. Their cost inside another lane's pool is multiplicative,
# not additive: N outer workers each boot an inner pool, so a box sized for N
# processes gets N*M. Holding them out is therefore a machine-load contract,
# which is why it is gated here rather than beside the recipe's shape pins.
#
# Both the member set and the labelled set are DERIVED -- one from the enrolling
# recipe, one from an AST scan of the tree -- and proven equal. Neither is a
# hand-written list, so a new harness proof, a rename, or a deletion moves both
# sides or fails.

_HARNESS_MARKER: Final = "harness"
# The combined real-proof line of the enrolling recipe, whose trailing arguments
# are its declared members. The `--collect-only` preflights name one member each.
_HARNESS_RUN_LINE: Final = re.compile(r"(?m)^test-harness:\r?\n(?:.*\r?\n)*?\s+@(?P<command>[^\r\n]*-rsf[^\r\n]*)")
_COLLECTION_TIMEOUT_SECONDS: Final = 180
_PYTEST_NO_TESTS_COLLECTED: Final = 5
# A justfile `{{ ... }}` template, including the conditional form whose own
# braces and quotes make the surrounding line unparseable as a shell word list.
_TEMPLATE_EXPRESSION: Final = re.compile(r"\{\{.*?\}\}", re.DOTALL)
# A path argument restricting a lane's collection, e.g. `dev/quality/tests` or
# `src/cadrumo/tests/test_x.py`. Matched only outside quotes-bearing templates.
_PATH_ARGUMENT: Final = re.compile(r"(?<!\S)(?!-)[\w.]+/\S*")


def _declared_harness_members() -> tuple[str, ...]:
    """Return the member paths the enrolling ``just test-harness`` recipe runs."""
    match = _HARNESS_RUN_LINE.search(_JUSTFILE.read_text(encoding="utf-8"))
    assert match is not None, "no justfile `test-harness` recipe line running the real proofs"
    return tuple(argument for argument in shlex.split(match.group("command")) if argument.endswith(".py"))


def _harness_labelled_modules() -> tuple[str, ...]:
    """Return every tracked test module whose ``pytestmark`` carries the label.

    Read statically rather than through pytest so the scan sees the label at
    its declaration site even when the module is deselected everywhere, which
    is precisely the state this contract governs.
    """
    labelled: list[str] = []
    for path in sorted(_REPOSITORY_ROOT.glob("src/cadrumo/**/test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        marks = {
            node.attr
            for statement in tree.body
            if isinstance(statement, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in statement.targets)
            for node in ast.walk(statement.value)
            if isinstance(node, ast.Attribute)
        }
        if _HARNESS_MARKER in marks:
            labelled.append(path.relative_to(_REPOSITORY_ROOT).as_posix())
    return tuple(labelled)


def _parallel_marker_expressions() -> tuple[tuple[str, str], ...]:
    """Return every unrestricted parallel justfile pytest lane as (recipe, marker).

    A lane is parallel unless it pins ``-n0``; a lane naming explicit paths
    cannot reach a member it does not name, so only the path-unrestricted lanes
    -- the ones selecting the whole corpus by marker -- are in scope here.
    """
    lanes: list[tuple[str, str]] = []
    for recipe, body in _justfile_recipe_bodies().items():
        for line in body:
            if "pytest" not in line or "-n0" in line:
                continue
            marker = re.search(r"-m\s+(?P<quote>[\"'])(?P<expression>.+?)(?P=quote)", line)
            if marker is None:
                continue
            if _PATH_ARGUMENT.search(_TEMPLATE_EXPRESSION.sub(" ", line)):
                continue
            lanes.append((recipe, marker.group("expression")))
    return tuple(lanes)


def _collect(marker_expression: str, members: tuple[str, ...]) -> Any:
    """Collect the declared members under one marker expression, outer-serially."""
    return run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--collect-only",
            "-n0",
            "-m",
            marker_expression,
            *members,
        ],
        cwd=_REPOSITORY_ROOT,
        timeout_seconds=_COLLECTION_TIMEOUT_SECONDS,
    )


def test_the_harness_label_and_the_enrolling_recipe_name_the_same_members() -> None:
    """The label cannot remove a test from every lane without enrolling it.

    ``harness`` is excluded by every routine lane, so on its own it is a mute
    button: any red proof could wear it and silently leave automated execution.
    Requiring exact equality with the enrolling recipe's member list makes the
    label and the verdict that pays for it inseparable.
    """
    declared = _declared_harness_members()
    labelled = _harness_labelled_modules()

    assert declared, "the enrolling recipe declares no harness member"
    assert sorted(declared) == sorted(labelled), (
        "every `harness`-labelled module must be a declared `just test-harness` member and vice versa\n"
        f"recipe declares: {sorted(declared)}\nmodules labelled: {sorted(labelled)}"
    )


def test_no_parallel_lane_collects_an_outer_serial_harness_member() -> None:
    """No path-unrestricted parallel lane may nest a harness proof in its pool.

    This runs each lane's real marker expression against the real member files,
    so it measures what pytest selects rather than what the expression looks
    like it excludes.
    """
    members = _declared_harness_members()
    lanes = _parallel_marker_expressions()
    assert lanes, "no path-unrestricted parallel lane found to gate"

    offenders: list[tuple[str, str, str]] = []
    for recipe, expression in lanes:
        result = _collect(expression, members)
        if result.returncode != _PYTEST_NO_TESTS_COLLECTED:
            offenders.append((recipe, expression, result.stdout))
    assert not offenders, (
        "these parallel lanes collect an outer-serial harness member, nesting its child "
        f"pytest pool inside their own:\n{offenders}"
    )


def test_the_harness_exclusion_is_what_holds_the_members_out() -> None:
    """The control: drop the exclusion and the same lane collects the members.

    Without this, the gate above would pass identically if the members were
    renamed, deleted, or unmarked -- an empty collection proves nothing on its
    own about which clause did the work.
    """
    members = _declared_harness_members()
    lanes = _parallel_marker_expressions()
    guarded = next(
        (expression for _, expression in lanes if f"not {_HARNESS_MARKER}" in expression),
        None,
    )
    assert guarded is not None, "no parallel lane declares the harness exclusion this control exercises"

    without_exclusion = guarded.replace(f" and not {_HARNESS_MARKER}", "")
    result = _collect(without_exclusion, members)

    assert result.returncode == 0, (
        "the control must collect the members once the exclusion is dropped; an empty "
        f"result here means the gate above is vacuous\ncommand marker: {without_exclusion}\n{result.stdout}"
    )
    assert "5 tests collected" in result.stdout or " tests collected" in result.stdout, result.stdout
