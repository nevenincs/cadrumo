"""Structural gate: CI lanes are sized for the shared machines, never `-n auto`.

Runners share physical machines with other repositories' runners, so a lane
that sizes itself as if it owns the box over-subscribes whatever runs beside
it. `pytest -n auto` grabs every logical CPU, so every CI pytest
invocation carries an explicit worker count, the packaging campaign legs pass
their per-machine sizing env, and the Homebrew matrix is parallelism-bounded.

The invariant holds at any runner count, so this gate names none.
"""

from __future__ import annotations

import re
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from ..._paths import REPO_ROOT
from ...packaging._command import run_command
from ..lane_reachability import Lane, declared_lanes, expression_selects, marker_sets_in

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REPOSITORY_ROOT: Final = REPO_ROOT
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
# The exclusion is by explicit path, never by a runtime-cost marker competing
# with the execution and hexagonal taxonomies. That costs a restated member list
# at each lane, so the list is not trusted: both sides are DERIVED from the one
# justfile lane authority (`lane_reachability.declared_lanes`, which already
# resolves `{{harness_members}}` and `--ignore=` templates the way `just` itself
# does) -- the enrolled members from the recipe that runs them, the excluded
# members from each lane -- and proven exactly equal.
#
# Which lanes are in scope is measured against `Lane.covers()` and
# `expression_selects()`, the same predicates the reachability authority itself
# uses, rather than a subprocess replay: a lane reaches a member only when its
# path scope covers it AND its marker expression would select the member's own
# markers. Path scope alone overstates reach -- the unit lane's pathless
# invocation covers `src/cadrumo/tests` with no `--ignore` of its own, yet never
# collects an `integration`-only harness member, because its marker expression
# excludes it. One control still runs real pytest collection, so the static
# model is proven against ground truth rather than trusted on its own say-so.

_HARNESS_RECIPE: Final = "test-harness"
_COLLECTION_TIMEOUT_SECONDS: Final = 300
# A directory containing the harness members, so collection walks to them the
# way a path-unrestricted lane does. Passing the member FILES directly would not
# test the contract: an explicit path argument overrides `--ignore`.
_MEMBER_PARENT: Final = "src/cadrumo/tests"


def _harness_members(root: Path) -> tuple[str, ...]:
    """Return the member paths the enrolling ``test-harness`` recipe runs.

    Derived from the declared-lane authority as the UNION of every
    ``test-harness`` lane's paths, order-preserved by first appearance: each of
    the recipe's three pytest lines is its own :class:`Lane`, and a member can
    appear in a per-member preflight line without (yet) appearing in the
    combined ``{{harness_members}}`` line the aggregate run uses. Picking only
    the single longest lane would miss exactly that divergence -- a member
    preflighted alone but silently dropped from the aggregate run and from
    every other lane's exclusion would never surface.
    """
    members: dict[str, None] = {}
    for lane in declared_lanes(root):
        if lane.recipe == _HARNESS_RECIPE:
            for path in lane.paths:
                members.setdefault(path, None)
    return tuple(members)


def _member_markers(root: Path, members: tuple[str, ...]) -> dict[str, frozenset[str]]:
    """Return each member's effective test markers, keyed by its path.

    A member is a file or a directory scope, and both must resolve: the worker
    hook can only be named as a file because it sits among hundreds of ordinary
    unit modules, while the harness package is named as a directory so that a
    proof added to it is enrolled by where it lives rather than by an edit
    nobody remembers to make. A directory member resolves through the modules
    inside it, in name order so the representative is deterministic.

    Every member is single-purpose and uniformly module-marked, so one test's
    effective markers stand in for the member's reachability. The assertion is
    the non-vacuity control: a scope holding no test resolves no markers, and
    the exclusion checks downstream would otherwise quantify over nothing.
    """
    markers: dict[str, frozenset[str]] = {}
    for member in members:
        target = root / member
        modules = sorted(target.glob("test_*.py")) if target.is_dir() else [target]
        entries = tuple(entry for module in modules for entry in (marker_sets_in(module) or ()))
        assert entries, f"{member} holds no test to resolve markers from"
        markers[member] = entries[0].markers
    return markers


def _corpus_lanes(root: Path) -> tuple[Lane, ...]:
    """Return every declared lane outside the enrolling recipe."""
    return tuple(lane for lane in declared_lanes(root) if lane.recipe != _HARNESS_RECIPE)


def _reaches(lane: Lane, member: str, member_markers: frozenset[str], *, ignore_exclusions: bool) -> bool:
    """Return whether ``lane`` would select ``member``, by path scope AND marker."""
    candidate = replace(lane, exclusions=()) if ignore_exclusions else lane
    return candidate.covers(member) and expression_selects(candidate.marker_expression, member_markers)


def _lanes_reaching_members_with_exclusions_dropped(
    root: Path,
    members: tuple[str, ...],
    member_markers: dict[str, frozenset[str]],
) -> tuple[Lane, ...]:
    """Return lanes that would select a harness member once ``--ignore`` is dropped."""
    return tuple(
        lane
        for lane in _corpus_lanes(root)
        if any(_reaches(lane, member, member_markers[member], ignore_exclusions=True) for member in members)
    )


def _unreached_members(
    lanes: tuple[Lane, ...],
    members: tuple[str, ...],
    member_markers: dict[str, frozenset[str]],
) -> dict[str, tuple[str, ...]]:
    """Return each member no lane selects, mapped to the lanes covering its path.

    The mapping is the diagnosis, not a detail. A member no lane reaches is
    unremarkable when no lane's path scope contains it -- only the enrolling
    recipe can run it, so excluding it elsewhere is belt and braces. It is a
    finding when a lane's paths DO contain it and every one of them declines it
    on markers alone: the exclusions naming that member are then decoration,
    and the equality check pins a name nothing depends on.
    """
    unreached: dict[str, tuple[str, ...]] = {}
    for member in members:
        if any(_reaches(lane, member, member_markers[member], ignore_exclusions=True) for lane in lanes):
            continue
        unreached[member] = tuple(
            f"{lane.source}/{lane.recipe}" for lane in lanes if replace(lane, exclusions=()).covers(member)
        )
    return unreached


def test_a_lane_reaching_the_harness_members_is_measurable_at_all() -> None:
    """Anti-vacuity: the exclusion checks must quantify over something real.

    Every assertion below quantifies over the reaching set. If that set were
    empty -- because the members were renamed, deleted, or the lane authority
    stopped resolving the justfile the way `just` itself does -- the other
    checks would pass over nothing.

    Per member rather than per lane. The members no longer share one path
    scope: the corpus-collectability proof sits outside every corpus lane's
    paths, so no single lane can reach both, and demanding one only measured
    where the files happen to live. What each member owes is that its exclusion
    is either load-bearing (some lane would collect it) or unnecessary (no
    lane's paths contain it) -- never the third state, where a lane's paths
    reach it and only a marker keeps it out.
    """
    members = _harness_members(_REPOSITORY_ROOT)
    member_markers = _member_markers(_REPOSITORY_ROOT, members)
    lanes = _corpus_lanes(_REPOSITORY_ROOT)
    reaching = _lanes_reaching_members_with_exclusions_dropped(_REPOSITORY_ROOT, members, member_markers)

    assert members, "the enrolling recipe declares no harness member"
    assert reaching, (
        "no lane reaches a harness member even with its exclusions dropped; the declared-lane "
        "authority is no longer resolving real lane scopes, so the exclusion checks would be vacuous"
    )
    unreached = _unreached_members(lanes, members, member_markers)
    marker_only = {member: covering for member, covering in unreached.items() if covering}
    assert not marker_only, (
        "these harness members sit inside a lane's path scope yet no lane would collect them even with "
        f"exclusions dropped, so their `--ignore` entries prove nothing: {marker_only}"
    )


def test_the_gate_refuses_a_member_held_out_by_marker_alone() -> None:
    """Proof the classification above can fail, on a lane built to fail it.

    A lane whose paths contain a member but whose marker expression declines it
    is the state the check refuses. Driving it with a synthetic lane keeps the
    proof independent of where the real members happen to sit today.
    """
    members = _harness_members(_REPOSITORY_ROOT)
    member_markers = _member_markers(_REPOSITORY_ROOT, members)
    member = next(candidate for candidate in members if candidate.startswith(f"{_MEMBER_PARENT}/"))
    covering = Lane(
        source="synthetic",
        paths=(_MEMBER_PARENT,),
        marker_expression="unit",
        recipe="synthetic-unit",
    )
    selecting = replace(covering, marker_expression="integration", recipe="synthetic-integration")

    assert "integration" in member_markers[member], f"{member} is no longer an integration proof"
    assert _unreached_members((covering,), (member,), member_markers) == {member: ("synthetic/synthetic-unit",)}
    assert _unreached_members((selecting,), (member,), member_markers) == {}


def test_every_lane_reaching_the_members_excludes_exactly_the_declared_set() -> None:
    """Each restatement of the member list is proven equal to the enrolling one.

    Excluding by path rather than by marker puts the member list at every lane.
    A restated list is a drift surface, so it is never read as authoritative:
    the recipe that actually runs the members is the one source, and a lane that
    adds, drops, renames, or misspells an entry fails here.
    """
    members = _harness_members(_REPOSITORY_ROOT)
    member_markers = _member_markers(_REPOSITORY_ROOT, members)
    declared = sorted(members)
    mismatched = {
        lane.source: sorted(lane.exclusions)
        for lane in _lanes_reaching_members_with_exclusions_dropped(_REPOSITORY_ROOT, members, member_markers)
        if sorted(lane.exclusions) != declared
    }

    assert not mismatched, (
        "every lane that can reach the harness members must exclude exactly the members the "
        f"enrolling recipe runs\nrecipe declares: {declared}\nlanes disagreeing: {mismatched}"
    )


def test_no_lane_collects_an_outer_serial_harness_member_as_it_actually_runs() -> None:
    """No lane may nest a harness proof's child pytest inside its own pool.

    Checked against each lane's REAL, undropped exclusions: a lane offends here
    only when its own path scope AND marker expression would select a member
    despite whatever `--ignore` it declares.
    """
    members = _harness_members(_REPOSITORY_ROOT)
    member_markers = _member_markers(_REPOSITORY_ROOT, members)
    offenders = [
        (lane.source, lane.recipe, member)
        for lane in _corpus_lanes(_REPOSITORY_ROOT)
        for member in members
        if _reaches(lane, member, member_markers[member], ignore_exclusions=False)
    ]

    assert not offenders, (
        f"these lanes collect an outer-serial harness member, nesting its child pytest pool: {offenders}"
    )


def test_dropping_the_exclusion_lets_a_real_lane_actually_collect_a_member() -> None:
    """Ground the static exclusion model in one real pytest collection.

    `Lane.covers()` and `expression_selects()` are a path-and-marker MODEL, not
    pytest itself; a divergence between the two would let every check above
    pass while proving nothing. This replays one reaching lane's own marker
    expression against the members' directory with its exclusion actually
    dropped, and confirms real pytest collection -- not just the model --
    picks a member up.
    """
    members = _harness_members(_REPOSITORY_ROOT)
    member_markers = _member_markers(_REPOSITORY_ROOT, members)
    reaching = _lanes_reaching_members_with_exclusions_dropped(_REPOSITORY_ROOT, members, member_markers)
    assert reaching, "no lane reaches a harness member even with exclusions dropped"
    lane = reaching[0]
    assert lane.marker_expression, f"lane `{lane.source}/{lane.recipe}` carries no marker expression to replay"

    result = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--collect-only",
            "-n0",
            "-p",
            "no:cacheprovider",
            "-m",
            lane.marker_expression,
            _MEMBER_PARENT,
        ],
        cwd=_REPOSITORY_ROOT,
        timeout_seconds=_COLLECTION_TIMEOUT_SECONDS,
    )
    collected = result.stdout.replace("\\", "/")
    assert any(member in collected for member in members), (
        f"dropping `{lane.source}/{lane.recipe}`'s exclusion did not make real pytest collect a "
        f"harness member\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
