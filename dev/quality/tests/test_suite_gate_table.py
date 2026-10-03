"""Gate: the aggregate suite's gate table is well-formed and complete.

``dev.quality.suite`` is the only surface that runs every static gate in one
pass, which makes a defect in its TABLE more dangerous than a defect in any
single gate: an entry that does not unpack takes the whole suite down before
a single gate runs, and a gate whose row is absent simply never executes
while the suite still reports on everything else.

Both failures have happened here in one edit. Four ratchet commands were added
under a single name, leaving a five-element row: the suite raised
``ValueError: too many values to unpack`` at import of the table, so
``check-code`` ran nothing at all, and three of the four ratchets had no row of
their own to run from even once the crash was fixed. Neither condition is
visible by reading the file -- the rows look like a list of commands either
way -- so it is asserted here.

The same gate-defined-twice drift applies to the composed audit dashboards
(``dev.audit.report`` and ``dev.audit.advisory``), which consume gates and
scanners their own recipes also run. The report once wrapped the import gate's
recipe in a 300 s timeout shorter than the gate's own runtime under load, so
the report and the recipe reached different verdicts on one tree. The
dashboard checks below hold: the report runs the import recipe unmodified, and
it is the suite's row; every recipe a dashboard cites exists; and no dashboard
re-bounds a consumed gate with ``timeout=`` or overrides a scanner runner's
arguments. They stop at the dashboards' own source: how a recipe's launched
module calls its runner (for example, argparse defaults) is that module's
contract and is not inspected here.
"""

from __future__ import annotations

import ast
import re
import shlex
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Final

import pytest

from dev._paths import REPO_ROOT
from dev.audit.report import IMPORT_QUALITY_RECIPE, import_quality_command

from ..suite import GATES, run_gate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_JUSTFILE: Final[Path] = REPO_ROOT / "justfile"

#: The composed audit dashboards that consume gates and scanners.
_DASHBOARDS: Final[tuple[Path, ...]] = (
    REPO_ROOT / "dev" / "audit" / "report.py",
    REPO_ROOT / "dev" / "audit" / "advisory.py",
)

#: Scanner modules whose runners the dashboards call in-process; each recipe
#: launching one of them runs it with the runner's own defaults.
_SCANNER_MODULES: Final[frozenset[str]] = frozenset({"complexity", "dead_code", "duplication", "security"})

#: A recipe header, parameterised or not; ``name := value`` assignments excluded.
_RECIPE_HEADER: Final[re.Pattern[str]] = re.compile(r"^([a-z][a-z0-9-]*)(?:\s+[^:]*)?:(?!=)")
_CITED_RECIPE: Final[re.Pattern[str]] = re.compile(r"`just ([a-z][a-z0-9-]*)")

#: Recipes in the justfile's static-check group that the aggregate suite
#: deliberately does not run: they re-run gates the suite already covers, or
#: need a local-only service.
_NOT_AGGREGATED: Final[frozenset[str]] = frozenset(
    {
        "check-code",
        "check-repository",
        "check-workflows",
        "check-gate-contracts",
        "check-hooks",
        "check-dependency-vulnerabilities",
        "check-rag",
        "check-corpus-text",
        "check-corpus-sidecars",
        "check-registry",
        "check-registry-valid",
        "check-registry-integrity",
        "check-registry-oracles",
        "check-registry-runtime-load",
        "check-registry-target-current",
        # The registry family's CI aggregate, and the one the list above
        # missed while naming all six of its siblings. It is NOT unverified:
        # merge-gate.yml runs it as its own step. It is unaggregated, which is
        # correct -- `check-code` is the LOCAL portable static-check aggregate,
        # and putting a registry conformance sweep into every local run to
        # duplicate what the required gate already does would buy no new
        # failure mode for the time it costs.
        "check-registry-gate",
        "check-identity",
        "check-locales",
        "check-docs-api",
        "check-docs-synonyms",
        # Registry capability checks, like the check-registry family above.
        "check-bindings",
        # Third-party security scanners fetched by uvx; the portable code
        # aggregate runs no network-fetched tool.
        "check-security-full",
        "check-workflow-security",
    }
)

# Only these rows belong to the portable code-quality aggregate. The subject
# aggregate itself and every repository/control-plane or capability check are
# deliberately excluded from ``dev.quality.suite.GATES``.
_CODE_GATES: Final[frozenset[str]] = frozenset(
    {
        "check-style",
        "check-format",
        "check-data-format",
        "check-types",
        "check-import-boundaries",
        "check-dependency-declarations",
        "check-module-reachability",
        "check-symbol-usage",
        "check-export-consumption",
        "check-secure-store-write-paths",
        "check-persistence-write-paths",
        "check-docstring-references",
    }
)


#: Tokens that name HOW a gate is launched rather than WHAT it checks. The
#: justfile goes through the quiet wrapper and the suite calls the interpreter
#: directly, so these differ by construction and are not drift.
#: The module every recorded run is launched through; its own arguments end
#: at the ``--`` separator.
_TEST_RUN_LAUNCHER: Final[str] = "dev.test_runs.command"

_RUNNER_TOKENS: Final[frozenset[str]] = frozenset(
    {"@uv", "uv", "run", "--no-sync", "python", "-m", "dev.quality.quiet", "@"}
)


def _without_test_run_wrapper(tokens: list[str]) -> list[str]:
    """Drop the test-run launcher prefix, keeping the command it launches.

    A recipe routed through ``dev.test_runs.command`` states its family, label
    and signal before the ``--`` separator. Those name HOW the run is recorded,
    not WHAT is checked, so the suite calling the same module directly is not
    drift.
    """
    if _TEST_RUN_LAUNCHER not in tokens or "--" not in tokens:
        return tokens
    return tokens[tokens.index("--") + 1 :]


def _significant(tokens: list[str]) -> list[str]:
    """Strip launcher tokens, leaving the arguments that decide what is checked."""
    unwrapped = _without_test_run_wrapper(tokens)
    # The suite launches its Python gates through ``sys.executable``, which is a
    # ``bin/python`` path on POSIX and a ``python.exe`` path on Windows.
    kept = [
        token
        for token in unwrapped
        if token not in _RUNNER_TOKENS and token != sys.executable and not token.endswith("python.exe")
    ]
    # The justfile carries shell quoting the argv list does not; a quoted regex
    # and its bare twin are the same argument.
    return [token.strip('"').strip("'") for token in kept]


def _recipe_commands(justfile: Path = _JUSTFILE) -> dict[str, list[str]]:
    """Return each static-check recipe's command tokens, keyed by recipe name."""
    lines = justfile.read_text(encoding="utf-8").splitlines()
    commands: dict[str, list[str]] = {}
    static_checks = _justfile_static_checks(justfile)
    for index, line in enumerate(lines):
        match = re.match(r"^([a-z][a-z0-9-]*):", line)
        if not match or match.group(1) not in static_checks:
            continue
        body: list[str] = []
        for candidate in lines[index + 1 :]:
            if not candidate.startswith((" ", "	")):
                break
            body.extend(shlex.split(candidate.strip().lstrip("@"), posix=False))
        if body:
            commands[match.group(1)] = _significant(body)
    return commands


def _justfile_static_checks(justfile: Path = _JUSTFILE) -> set[str]:
    """Return the recipe names in the justfile's static-checks group."""
    lines = justfile.read_text(encoding="utf-8").splitlines()
    names: set[str] = set()
    for index, line in enumerate(lines):
        match = re.match(r"^([a-z][a-z0-9-]*):", line)
        if not match:
            continue
        # A recipe's attributes are the bracketed lines immediately above it.
        # Reading forward from a group marker instead would attribute a recipe
        # to whichever group appeared earlier in the file, which silently
        # pulled a [group('packaging')] recipe into this population.
        for above in reversed(lines[:index]):
            stripped = above.strip()
            if not stripped.startswith(("[", "#")):
                break
            if "group('check')" in stripped:
                names.add(match.group(1))
                break
    return names


def _recipe_names(justfile: Path = _JUSTFILE) -> set[str]:
    """Return every recipe the justfile defines, in any group."""
    lines = justfile.read_text(encoding="utf-8").splitlines()
    return {match.group(1) for line in lines if (match := _RECIPE_HEADER.match(line))}


def _malformed_rows(rows: Iterable[Sequence[object]]) -> list[Sequence[object]]:
    """Return rows whose runtime shape is not the suite's two-column contract."""
    return [row for row in rows if len(row) != 2]


def _drifted_rows(gates: Iterable[tuple[str, tuple[str, ...]]], recipes: Mapping[str, list[str]]) -> list[str]:
    """Return gate rows whose significant arguments differ from their recipe's."""
    drifted: list[str] = []
    for name, command in gates:
        recipe = recipes.get(name)
        if recipe is not None and _significant([str(part) for part in command]) != recipe:
            drifted.append(name)
    return drifted


def _import_invocation_drift(
    command: tuple[str, ...],
    *,
    just: str,
    static_checks: set[str],
    gate_rows: set[str],
) -> list[str]:
    """Return every way the report's import-gate command departs from its recipe."""
    problems: list[str] = []
    recipe = command[1] if len(command) > 1 else ""
    if command[:1] != (just,):
        problems.append(f"does not launch just: {command!r}")
    if recipe not in static_checks:
        problems.append(f"{recipe!r} is not a static-check recipe")
    if recipe not in gate_rows:
        problems.append(f"{recipe!r} is not a dev.quality.suite.GATES row")
    if command[2:]:
        problems.append(f"adds arguments the recipe does not carry: {command[2:]!r}")
    return problems


def _cited_missing_recipes(source: str, recipe_names: set[str]) -> list[str]:
    """Return every ``just <recipe>`` a dashboard cites that names no recipe."""
    return sorted({name for name in _CITED_RECIPE.findall(source) if name not in recipe_names})


def _scanner_runners(tree: ast.Module) -> set[str]:
    """Return the names a dashboard imports from the in-process scanner modules."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        relative = node.level == 1
        absolute = node.level == 0 and node.module.startswith("dev.audit.")
        if (relative or absolute) and node.module.rsplit(".", 1)[-1] in _SCANNER_MODULES:
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _dashboard_overrides(source: str) -> list[str]:
    """Return calls that re-bound a consumed gate or override a scanner runner.

    Any ``timeout=`` keyword is a dashboard-side wall-clock bound layered over
    the bound the gate or scanner already owns. Any keyword on a call to an
    imported scanner runner makes the dashboard measure something other than
    what the runner's recipe measures.
    """
    tree = ast.parse(source)
    runners = _scanner_runners(tree)
    overrides: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        keywords = [keyword.arg for keyword in node.keywords]
        if "timeout" in keywords:
            overrides.append(f"line {node.lineno}: timeout=")
        callee = node.func.id if isinstance(node.func, ast.Name) else None
        if callee in runners and node.keywords:
            overrides.append(f"line {node.lineno}: {callee}() overrides {keywords}")
    return overrides


def test_every_row_unpacks_as_a_name_and_a_command() -> None:
    """A malformed row takes down the whole suite before any gate runs."""
    rows: tuple[Sequence[object], ...] = GATES
    malformed = _malformed_rows(rows)
    assert not malformed, f"each GATES row must be (name, command): {malformed}"


def test_every_row_carries_a_name_and_a_non_empty_argv() -> None:
    """A row whose command is empty would run nothing and report success."""
    for name, command in GATES:
        assert isinstance(name, str) and name, f"gate name must be a non-empty string: {name!r}"
        assert command and all(isinstance(part, str) for part in command), f"{name}: bad argv {command!r}"


def test_no_gate_name_is_registered_twice() -> None:
    """A duplicate name hides one of the two rows in the dashboard."""
    names = [name for name, _ in GATES]
    assert len(names) == len(set(names)), f"duplicate gate names: {names}"


def test_every_static_check_recipe_is_either_aggregated_or_declared_exempt() -> None:
    """A gate with a justfile recipe but no row never runs in the suite."""
    missing = sorted(_justfile_static_checks() - {name for name, _ in GATES} - _NOT_AGGREGATED)
    assert not missing, (
        "these static-check recipes have no row in dev.quality.suite.GATES, so "
        f"`just check-code` never runs them: {missing}"
    )


def test_the_recipe_scan_finds_the_group() -> None:
    """A scan returning nothing would make the completeness check vacuous."""
    assert len(_justfile_static_checks()) > 5


def test_the_gate_catches_a_malformed_row() -> None:
    """Detector teeth: the exact five-element shape that broke the suite."""
    planted: tuple[Sequence[object], ...] = (("check-a", ("x",), ("y",), ("z",)),)
    assert _malformed_rows(planted) == list(planted)


def test_each_gate_runs_the_same_command_its_recipe_does() -> None:
    """A gate defined twice drifts, and the halves disagree in silence.

    ``check-dependency-declarations`` is declared in the justfile and again in the suite's
    table. The recipe scanned the harness package and the table did not, so
    ``just check-dependency-declarations`` passed while ``just check-code`` reported the
    same two dependencies as declared-but-unused -- a scan-scope artefact that
    reads exactly like real debt. Only the arguments are compared: how each
    half launches the tool differs by construction.
    """
    drifted = _drifted_rows(GATES, _recipe_commands())
    assert not drifted, (
        "these gates run different arguments in dev.quality.suite than in their "
        f"justfile recipe, so the two halves can disagree: {drifted}"
    )


def test_the_recipe_command_scan_reads_real_commands() -> None:
    """A scan returning nothing would make the drift check vacuous."""
    commands = _recipe_commands()
    assert commands.get("check-style"), f"check-style recipe not parsed: {commands.get('check-style')!r}"


def test_only_code_quality_primitives_are_enrolled() -> None:
    commands = dict(GATES)

    assert set(commands) == _CODE_GATES
    assert commands["check-import-boundaries"] == (
        sys.executable,
        "-m",
        "dev.quality.import_gate",
    )
    assert commands["check-dependency-declarations"][:3] == (
        "deptry",
        "src/cadrumo",
        "src/cadrumo_harness",
    )
    assert commands["check-persistence-write-paths"] == (
        sys.executable,
        "-m",
        "dev.quality.write_path_coverage",
    )
    assert commands["check-secure-store-write-paths"] == (
        sys.executable,
        "-m",
        "dev.quality.secure_store_write_path",
    )


def test_governed_literal_discovery_findings_are_non_blocking_when_run_by_suite(tmp_path: Path) -> None:
    (tmp_path / "policy.py").write_text("TAX_RATE = 21\n", encoding="utf-8")

    result = run_gate(
        "report-governed-literal-discovery",
        (
            sys.executable,
            "-m",
            "dev.registry.analysis.governed_literal_discovery",
            "--source-root",
            str(tmp_path),
        ),
    )

    assert result.returncode == 0
    assert "1 governed-literal candidate(s); report only" in result.output


# ---------------------------------------------------------------------------
# Composed audit dashboards: one invocation authority per consumed gate
# ---------------------------------------------------------------------------

_FIXTURE_JUSTFILE: Final[str] = """\
set shell := ["sh", "-c"]

[group('check')]
check-a:
    @uv run --no-sync python -m dev.quality.a --strict

[group('audit')]
audit-b *ARGS:
    @uv run --no-sync python -m dev.audit.b {{ARGS}}
"""

_FIXTURE_DASHBOARD: Final[str] = """\
import subprocess

from .security import run_security_scan


def measure(root):
    subprocess.run(["just", "check-a"], timeout=300)
    run_security_scan(root, timeout=5)
    return run_security_scan(root)
"""


def _fixture_justfile(tmp_path: Path) -> Path:
    path = tmp_path / "justfile"
    path.write_text(_FIXTURE_JUSTFILE, encoding="utf-8", newline="\n")
    return path


def test_the_health_report_runs_the_import_gate_exactly_as_its_recipe() -> None:
    """The report's import dimension is the recipe's process result, nothing added."""
    problems = _import_invocation_drift(
        import_quality_command("just"),
        just="just",
        static_checks=_justfile_static_checks(),
        gate_rows={name for name, _ in GATES},
    )

    assert not problems, f"dev.audit.report runs the import gate differently from its recipe: {problems}"
    assert IMPORT_QUALITY_RECIPE == "check-import-boundaries"


def test_every_recipe_a_dashboard_cites_exists() -> None:
    """A pointer to a retired recipe sends the reader to a command that fails."""
    recipes = _recipe_names()
    missing = {
        dashboard.name: cited
        for dashboard in _DASHBOARDS
        if (cited := _cited_missing_recipes(dashboard.read_text(encoding="utf-8"), recipes))
    }

    assert not missing, f"audit dashboards cite recipes the justfile does not define: {missing}"


def test_no_dashboard_rebounds_a_gate_or_overrides_a_scanner_runner() -> None:
    """The dashboards consume each gate and runner exactly as its recipe runs it."""
    overrides = {
        dashboard.name: found
        for dashboard in _DASHBOARDS
        if (found := _dashboard_overrides(dashboard.read_text(encoding="utf-8")))
    }

    assert not overrides, f"audit dashboards re-bound or re-parameterise a consumed gate: {overrides}"


def test_the_dashboard_scans_read_real_recipes_and_runners() -> None:
    """Empty recipe or runner populations would make the dashboard checks vacuous."""
    runners = set().union(*(_scanner_runners(ast.parse(path.read_text(encoding="utf-8"))) for path in _DASHBOARDS))

    assert {"check-import-boundaries", "audit-dead-weight", "audit-code", "report-code-health"} <= _recipe_names()
    assert {"run_duplication_scan", "run_dead_code_scan", "run_security_scan", "scan_complexity"} <= runners


def test_the_import_invocation_check_catches_drift(tmp_path: Path) -> None:
    """Detector teeth: an unknown recipe, a non-suite recipe and added arguments are all caught."""
    justfile = _fixture_justfile(tmp_path)
    checks = _justfile_static_checks(justfile)

    def drift(command: tuple[str, ...]) -> list[str]:
        return _import_invocation_drift(command, just="just", static_checks=checks, gate_rows={"check-a"})

    assert drift(("just", "check-a")) == []
    assert len(drift(("just", "check-gone"))) == 2
    assert drift(("just", "check-a", "--timeout", "5")) == [
        "adds arguments the recipe does not carry: ('--timeout', '5')"
    ]
    assert drift(("uv", "check-a")) == ["does not launch just: ('uv', 'check-a')"]


def test_the_cited_recipe_check_catches_a_retired_recipe(tmp_path: Path) -> None:
    """Detector teeth: a parameterised recipe resolves, a retired one is reported."""
    recipes = _recipe_names(_fixture_justfile(tmp_path))

    assert recipes == {"check-a", "audit-b"}
    assert _cited_missing_recipes("see `just audit-b` or `just audit-gone`", recipes) == ["audit-gone"]


def test_the_override_check_catches_a_timeout_and_a_runner_argument() -> None:
    """Detector teeth: the exact shape that made the report flaky, plus a runner override."""
    found = _dashboard_overrides(_FIXTURE_DASHBOARD)

    assert found == ["line 7: timeout=", "line 8: timeout=", "line 8: run_security_scan() overrides ['timeout']"]


def test_the_recipe_comparison_catches_a_drifted_argument(tmp_path: Path) -> None:
    """Detector teeth for the suite-versus-recipe comparison: one extra recipe flag is drift."""
    recipes = _recipe_commands(_fixture_justfile(tmp_path))

    assert recipes == {"check-a": ["dev.quality.a", "--strict"]}
    assert _drifted_rows((("check-a", (sys.executable, "-m", "dev.quality.a")),), recipes) == ["check-a"]
    assert _drifted_rows((("check-a", (sys.executable, "-m", "dev.quality.a", "--strict")),), recipes) == []
