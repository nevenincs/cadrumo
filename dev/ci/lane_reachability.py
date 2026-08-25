"""Compute which test files any declared pytest lane can actually select.

A test nobody runs is worse than a missing test: it reports nothing while
looking like coverage, and its rot is invisible until somebody reads it. The
fourteen channel-generator tests sat in exactly that state long enough for two
independent breakages to accumulate, and the author of the second had no signal
at all, because no lane selected them and nothing said so.

Reachability is a two-part question and both parts must be modelled. Those tests
were excluded *twice over*: the lanes that reached ``packaging/`` did not accept
the ``serial`` marker, and the lanes that accepted it did not reach
``packaging/``. A path-only model would have declared them reachable, the gate
would have passed, and the hole would have stayed open. So a lane selects a file
only when its path scope covers the file AND its marker expression can select at
least one test in it.

Two precisions the naive version gets wrong:

*Only pytest invocations carry marker expressions.* ``-m`` is also git's message
flag, and this repository's workflows use it that way. Reading a commit subject
as a marker expression yields nonsense that happens to parse.

*Markers are per-test, and must not be flattened into one set per file.*
Collecting only ``pytestmark`` would call a file unmarked when its tests carry
their own decorators. But unioning module-level and per-test markers into a
single set is just as wrong in the other direction, and it produced a real false
positive: ``src/cadrumo/tests/test_secure_sql.py`` is module-marked ``unit`` and
carries ONE test decorated ``os_keychain``, and every lane excludes
``os_keychain`` -- so the flattened set matched no lane and the whole file read
as unreachable while most of its tests run in the unit lane every day. The unit
of reachability is therefore the TEST: a test is reachable when some lane covers
its file and selects its own effective markers (module, class, and function
decorators combined), and a file is unreachable only when NONE of its tests is.

Reporting per test rather than per file is not just precision, it is the finding
the file-level view destroys. Underneath that false positive sat a real hole --
no lane names ``test_secure_sql.py`` for ``os_keychain``, so that one test never
runs anywhere -- and a per-file model that stopped flagging the file would have
closed the false positive and buried the defect with it.

Discovery reads git-TRACKED files. This repository is worked by many agents at
once, so an untracked path is a peer's uncommitted scratch that CI will never
see, and a tracked path may be momentarily absent from disk while a peer stages
a deletion. Neither is a coverage defect, and both would red a shared gate.
Unreadable tracked files are skipped and counted rather than assumed unmarked,
because assuming unmarked would report a peer's in-flight deletion as an orphan.

TWO QUESTIONS ARE ASKED, not one, and the second exists because the first has
blind spots. The per-test question ("does some lane select this test") is the
powerful one. The path-level question ("does any lane's scope name this file at
all") is cheap and weaker, and it is retained deliberately because the per-test
model cannot see two input classes:

* A ``test_*.py`` holding NO test functions. There are no tests to be
  unreachable, so the per-test model reports nothing however orphaned the file.
* A tracked file absent from disk, which cannot be read and so yields no tests.

Both classes are EMPTY in this tree today -- 0 testless modules of 182 tracked
under ``dev/`` at the time of writing -- but empty is not the same claim as
impossible, and a consolidation that conflates them is how a gate silently
sheds a capability. The path-level check is a few lines and costs nothing at
runtime; dropping it during the merge would have been a regression wearing a
consolidation's clothes, which is the same shape as the ``os_keychain`` hole
this module was corrected to expose.

DECLARED IS NOT RUN, and the difference is a third question this module now
answers. A justfile recipe is a declaration, and for the reachability question
that is correct -- but a recipe no workflow ever invokes has never executed, so
a gate that accepts it reports coverage over tests CI has never run. That was
not hypothetical either: ``just test-integration`` (370 integration-marked
modules under ``src/`` -- every cross-layer test the product has) and
``just test-dev-tooling`` (ten ``dev/`` subsystems, whose own recipe docstring
reads "the gates that no other lane reaches") were both declared, both healthy,
and named by no workflow at all. :func:`ci_invoked_lanes` narrows the lane set
to what CI actually reaches, so the two questions can be asked separately and
neither can quietly answer for the other.

See Also:
    :func:`declared_lanes`
        Every lane the repository declares, from config, recipes, and workflows.
    :func:`ci_invoked_lanes`
        The subset CI actually runs: workflow-inline invocations plus the
        recipes workflows name, transitively.
    :func:`analyse_reachability`
        The gate's finding: individual tests no declared lane can select, plus
        the files no lane names at all.
"""

from __future__ import annotations

import ast
import re
import shlex
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml

from cadrumo.core.directory_scan import scan_directory

from .._paths import UTF_8

_UTF_8: Final[str] = UTF_8

#: Directories that never contain runnable project tests.
_PRUNED: Final[frozenset[str]] = frozenset(
    {".git", ".venv", "node_modules", "__pycache__", "_build", ".mypy_cache", ".ruff_cache", ".pytest_cache"},
)

#: Top-level directories a pytest invocation can positionally name. A BARE
#: reference to one of these -- no slash, e.g. a hypothetical `pytest
#: packaging` -- would otherwise match none of `_paths_of`'s other checks and
#: silently fall back to the configured testpaths, the same silent-widening
#: shape as the `--ignore` and `{{}}`-residue defects already fixed here. No
#: current recipe exercises the bare form -- every real invocation already
#: names a subpath (`src/cadrumo`, `packaging/homebrew/tests`), which the
#: `"/" in token` check catches -- so this only closes the gap for whenever
#: one does.
_TOP_LEVEL_TEST_DIRS: Final[frozenset[str]] = frozenset({"src", "dev", "packaging"})

#: Where lane declarations live. Anything else is not a lane.
_WORKFLOW_DIR: Final[str] = ".github/workflows"

#: A justfile recipe header: a name at column zero, optional parameters and
#: attributes, then a bare `:` -- never `:=`, which is a variable assignment.
_RECIPE_HEADER: Final = re.compile(r"^(?P<name>[a-z][\w-]*)\b[^:\n]*:(?![=])")

#: A `just <recipe>` call, in a workflow `run:` or in another recipe's body.
_JUST_CALL: Final = re.compile(r"\bjust\s+(?P<recipe>[a-z][\w-]*)")

#: A bare `{{name}}` justfile interpolation. Deliberately narrow: an expression
#: like `{{ if durations == "" { "" } else { ... } }}` does not match a bare
#: identifier and is left exactly as written, per the rule that an unresolved
#: template must stay visibly unresolved rather than being guessed at.
_JUST_VARIABLE_REF: Final = re.compile(r"\{\{\s*(?P<name>[A-Za-z_]\w*)\s*\}\}")

#: A `just --evaluate` output line: `name := "value"`, one per top-level variable.
_JUST_EVALUATE_LINE: Final = re.compile(r'^(?P<name>\S+)\s*:=\s*"(?P<value>.*)"\s*$')


@dataclass(frozen=True, slots=True)
class TestMarkers:
    """One test and the effective markers pytest resolves for it."""

    test: str
    markers: frozenset[str]


@dataclass(frozen=True, slots=True)
class UnreachableTest:
    """One test no declared lane can select, named so the remedy is decidable."""

    path: str
    test: str
    markers: frozenset[str]

    def describe(self) -> str:
        """Return a one-line report naming the test and why it is held out."""
        markers = ", ".join(sorted(self.markers)) or "no markers"
        return f"{self.path}::{self.test} [{markers}]"


@dataclass(frozen=True, slots=True)
class ReachabilityReport:
    """The reachability finding plus the corpus it was computed over.

    ``analysed`` and ``skipped`` exist so the gate can refuse a vacuous pass: an
    empty ``unreachable`` means nothing if the reader parsed nothing, and a
    reader that silently stopped matching is the false-green this whole module
    is built to refuse.
    """

    unreachable: tuple[UnreachableTest, ...]
    unnamed: tuple[str, ...]
    analysed: int
    skipped: tuple[str, ...]

    def affected_files(self) -> tuple[str, ...]:
        """Return every file holding at least one unreachable test.

        Deliberately NOT "files where no test is selectable": that weaker
        question is what hid the ``os_keychain`` hole, because the file also
        held reachable tests and so never appeared.
        """
        return tuple(sorted({entry.path for entry in self.unreachable}))


@dataclass(frozen=True, slots=True)
class Lane:
    """One declared pytest invocation: what it reaches and what it accepts.

    ``recipe`` names the justfile recipe the invocation sits in, or None when
    the invocation is written inline in a workflow. It is what makes
    :func:`ci_invoked_lanes` able to ask whether CI actually reaches a lane,
    rather than only whether the repository declares one.
    """

    source: str
    paths: tuple[str, ...]
    marker_expression: str | None
    recipe: str | None = None
    exclusions: tuple[str, ...] = ()

    def covers(self, relative_path: str) -> bool:
        """Return whether this lane's path scope reaches ``relative_path``.

        A path inside an excluded ``--ignore`` scope is not covered even when
        it sits inside a covered ``paths`` scope: ``covers()`` had no concept
        of ``--ignore`` at all, so a lane that both selects ``src/`` and
        excludes two files under it read as reaching them anyway.
        """
        if not self.paths:
            # A pathless invocation takes the configured testpaths, which the
            # caller supplies as this lane's paths. An empty scope reaches
            # nothing rather than everything: treating it as everything is how a
            # gate silently reports full coverage.
            return False
        posix = relative_path.replace("\\", "/")
        if any(posix == excluded or posix.startswith(f"{excluded.rstrip('/')}/") for excluded in self.exclusions):
            return False
        return any(posix == scope or posix.startswith(f"{scope.rstrip('/')}/") for scope in self.paths)


def _marker_expression_of(tokens: list[str]) -> str | None:
    """Return the ``-m`` value from a pytest argv, or None when absent."""
    marker_flag = "-m"  # a pytest selector, not a credential
    for index, token in enumerate(tokens):
        if token == marker_flag and index + 1 < len(tokens):
            return tokens[index + 1]
        if token.startswith(marker_flag) and len(token) > 2:
            return token[2:]
    return None


def _paths_of(tokens: list[str]) -> tuple[str, ...]:
    """Return positional path arguments from a pytest argv."""
    paths: list[str] = []
    skip_next = False
    for index, token in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        if token in {"-m", "-k", "-n", "--timeout", "--ignore", "--durations"}:
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        if index == 0 or token in {"pytest", "uv", "run", "python", "-m"}:
            continue
        if token.endswith(".py") or "/" in token or token.split("/")[0] in _TOP_LEVEL_TEST_DIRS:
            paths.append(token.split("::")[0])
    return tuple(paths)


def _exclusions_of(tokens: list[str]) -> tuple[str, ...]:
    """Return every path a pytest argv's ``--ignore`` flags exclude.

    Pytest accepts two spellings for the same flag -- ``--ignore=PATH`` as one
    token and ``--ignore PATH`` as two -- and a lane declared with either form
    excludes the path just as much as the other. Modelling only one form is how
    a lane written the other way keeps reading as if it still reached the file.
    """
    ignore_flag = "--ignore"  # a pytest selector, not a credential
    excluded: list[str] = []
    take_next = False
    for token in tokens:
        if take_next:
            excluded.append(token.split("::")[0])
            take_next = False
            continue
        if token == ignore_flag:
            take_next = True
            continue
        if token.startswith(f"{ignore_flag}="):
            excluded.append(token[len(ignore_flag) + 1 :].split("::")[0])
    return tuple(excluded)


def _pytest_invocations(text: str, *, source: str, default_paths: tuple[str, ...]) -> list[Lane]:
    """Return one lane per pytest invocation in ``text``.

    Only invocations, never every ``-m`` in the file: git's message flag shares
    the spelling, and this repository uses it in the same files.
    """
    lanes: list[Lane] = []
    for raw in text.splitlines():
        line = raw.strip()
        if "pytest" not in line or line.startswith("#"):
            continue
        # Drop shell continuations and interpolations that shlex cannot parse.
        cleaned = line.rstrip("\\").replace("${{", "").replace("}}", "")
        try:
            tokens = shlex.split(cleaned)
        except ValueError:
            continue
        if "pytest" not in tokens and not any(token.endswith("pytest") for token in tokens):
            continue
        paths = _paths_of(tokens) or default_paths
        lanes.append(
            Lane(
                source=source,
                paths=paths,
                marker_expression=_marker_expression_of(tokens),
                exclusions=_exclusions_of(tokens),
            )
        )
    return lanes


def _justfile_lanes(text: str, *, default_paths: tuple[str, ...]) -> list[Lane]:
    """Return the justfile's pytest lanes, each attributed to its recipe.

    Attribution is what lets a caller ask whether CI reaches a lane. A recipe
    header sits at column zero and ends in a bare ``:`` (``:=`` is a variable
    assignment); every indented line beneath it belongs to that recipe.
    """
    lanes: list[Lane] = []
    current: str | None = None
    for raw in text.splitlines():
        header = _RECIPE_HEADER.match(raw)
        if header is not None:
            current = header.group("name")
            continue
        # A non-indented, non-header, non-comment line ends the preceding recipe
        # body: an attribute (`[group('testing')]`) or a variable assignment.
        # Comments do not, because a `#` line between a doc attribute and its
        # header sits at column zero without interrupting anything.
        if raw[:1] not in {" ", "\t", "@"} and raw.strip() and not raw.lstrip().startswith("#"):
            current = None
        for lane in _pytest_invocations(raw, source="justfile", default_paths=default_paths):
            lanes.append(
                Lane(
                    source=lane.source,
                    paths=lane.paths,
                    marker_expression=lane.marker_expression,
                    recipe=current,
                    exclusions=lane.exclusions,
                )
            )
    return lanes


def _recipes_invoked_by(text: str) -> set[str]:
    """Return every recipe name a ``just <recipe>`` call in ``text`` names."""
    return {match.group("recipe") for match in _JUST_CALL.finditer(text)}


def _recipe_bodies(text: str) -> dict[str, str]:
    """Return each justfile recipe's body, keyed by recipe name."""
    bodies: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        header = _RECIPE_HEADER.match(raw)
        if header is not None:
            current = header.group("name")
            bodies.setdefault(current, [])
            continue
        if current is not None:
            if raw.strip() and raw[:1] not in {" ", "\t", "@"} and not raw.lstrip().startswith("#"):
                current = None
                continue
            bodies[current].append(raw)
    return {name: "\n".join(lines) for name, lines in bodies.items()}


def _workflow_run_commands(text: str) -> str:
    """Return every ``run:`` command in a workflow, and nothing else.

    Read from the parsed document rather than the raw file, for the same reason
    :func:`_pytest_invocations` refuses to treat every ``-m`` as a marker flag:
    the word "just" is ordinary English, and these workflows use it that way in
    step names and comments ("Ensure just is available", "provision just
    natively"). Scanning raw text harvested `is`, `uses`, and `natively` as
    recipe names -- three recipes that do not exist -- which is harmless only
    until one of those words happens to BE a recipe name, at which point an
    unreached lane reads as reached.
    """
    document = yaml.safe_load(text)
    if not isinstance(document, dict):
        return ""
    commands: list[str] = []
    for job in (document.get("jobs") or {}).values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if isinstance(step, dict) and "run" in step:
                commands.append(str(step["run"]))
    return "\n".join(commands)


def ci_invoked_recipes(root: Path) -> frozenset[str]:
    """Return every justfile recipe a workflow reaches, transitively.

    A recipe is CI-invoked when a workflow ``run:`` names it, or when a
    CI-invoked recipe's own body names it. The transitive step matters: the
    recipes workflows call are increasingly thin wrappers, and stopping at the
    first hop would report a delegated lane as unreached.
    """
    justfile = root / "justfile"
    if not justfile.exists():
        return frozenset()
    bodies = _recipe_bodies(justfile.read_text(encoding=_UTF_8))

    reached: set[str] = set()
    workflow_dir = root / _WORKFLOW_DIR
    if workflow_dir.is_dir():
        for workflow in scan_directory(workflow_dir, pattern="*.yml"):
            reached |= _recipes_invoked_by(_workflow_run_commands(workflow.read_text(encoding=_UTF_8)))

    # Close over recipe-to-recipe calls until nothing new is reached.
    frontier = set(reached)
    while frontier:
        nxt: set[str] = set()
        for name in frontier:
            for called in _recipes_invoked_by(bodies.get(name, "")):
                if called not in reached:
                    reached.add(called)
                    nxt.add(called)
        frontier = nxt
    return frozenset(reached)


def ci_invoked_lanes(root: Path) -> tuple[Lane, ...]:
    """Return only the lanes CI actually runs.

    The distinction this draws is the whole point. :func:`declared_lanes`
    answers "does the repository declare a lane for this test", and a justfile
    recipe counts — which is correct for its question and dangerously
    reassuring for the one a reader usually means. Two lanes proved that:
    ``just test-integration`` (370 integration-marked modules under ``src/``)
    and ``just test-dev-tooling`` (ten ``dev/`` subsystems, including the
    deploy-authority tests) were both declared, both healthy, and invoked by no
    workflow at all, so the declared-lane gate reported full coverage over
    tests CI had never once run.
    """
    resolved = declared_lanes(root)
    invoked = ci_invoked_recipes(root)
    return tuple(lane for lane in resolved if lane.recipe is None or lane.recipe in invoked)


def configured_testpaths(root: Path) -> tuple[str, ...]:
    """Return the ``testpaths`` a pathless invocation inherits."""
    text = (root / "pyproject.toml").read_text(encoding=_UTF_8)
    match = re.search(r"^testpaths\s*=\s*\[(.*?)\]", text, re.MULTILINE | re.DOTALL)
    if not match:
        return ()
    return tuple(item.strip().strip("\"'") for item in match.group(1).split(",") if item.strip())


def configured_marker_expression(root: Path) -> str | None:
    """Return the default ``-m`` expression from addopts, if any."""
    text = (root / "pyproject.toml").read_text(encoding=_UTF_8)
    match = re.search(r"^addopts\s*=\s*\"(.*?)\"", text, re.MULTILINE)
    if not match:
        return None
    inner = re.search(r"-m\s+'([^']+)'", match.group(1)) or re.search(r'-m\s+"([^"]+)"', match.group(1))
    return inner.group(1) if inner else None


def resolve_just_executable() -> str:
    """Return the absolute path to ``just`` on PATH.

    The sole canonical resolution point for this repository's tooling. Fails
    closed: a missing ``just`` raises rather than returning ``None`` or an
    empty string for a caller to silently treat as "nothing to check" --
    exactly the failure mode the module docstring's reachability rationale
    warns against, generalised to every ``just``-dependent gate and script.
    """
    executable = shutil.which("just")
    if executable is None:
        message = "just is not on PATH"
        raise RuntimeError(message)
    return executable


def _just_variables(root: Path) -> dict[str, str]:
    """Return every top-level justfile variable, resolved by ``just`` itself.

    This module parses the justfile as TEXT, so a recipe body that names a
    variable (``{{harness_exclusions}}``) reads as the literal eight characters
    ``harness_exclusions`` wrapped in braces -- not the ``--ignore=...`` string
    it expands to at run time -- unless that expansion is resolved here first.
    An unresolved template can still happen to parse as a plausible-looking
    path, which is exactly how this class of gap produces a wrong answer
    instead of a loud one. Delegating to ``just`` rather than hand-rolling
    justfile expression evaluation keeps this module honest about what it can
    and cannot parse: a construct richer than a bare variable reference (an
    ``if`` expression, a function call) is not attempted and is left visibly
    unresolved.

    Fails closed: a missing or failing ``just`` raises rather than silently
    falling back to the unresolved text, because a silent fallback is
    indistinguishable from a correct empty result.
    """
    just = resolve_just_executable()
    completed = subprocess.run(  # noqa: S603 - resolved executable, fixed argv, no caller input
        [just, "--evaluate"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    variables: dict[str, str] = {}
    for line in completed.stdout.decode(_UTF_8).splitlines():
        match = _JUST_EVALUATE_LINE.match(line)
        if match is not None:
            variables[match.group("name")] = match.group("value")
    return variables


def _substitute_just_variables(text: str, variables: dict[str, str]) -> str:
    """Replace every bare ``{{name}}`` reference in ``text`` with its value.

    A reference naming a variable ``just --evaluate`` did not resolve -- an
    unrecognised name, or a richer expression this module does not attempt --
    is left exactly as written rather than guessed at.
    """
    return _JUST_VARIABLE_REF.sub(lambda match: variables.get(match.group("name"), match.group(0)), text)


def resolved_justfile_text(root: Path) -> str:
    """Return the justfile's text with every top-level ``{{name}}`` resolved.

    The one place any consumer should ask "what does this justfile actually
    say": resolution is real ``just`` resolution (``just --evaluate``), not a
    hand-rolled regex against raw text, so a consumer reading this text sees
    exactly what ``just`` would substitute -- never a literal ``{{name}}``
    token misread as a nonsense path. Returns the empty string when there is
    no justfile, so a caller can treat "no justfile" and "empty justfile" the
    same way without a separate existence check.
    """
    justfile = root / "justfile"
    if not justfile.exists():
        return ""
    return _substitute_just_variables(justfile.read_text(encoding=_UTF_8), _just_variables(root))


def resolved_recipe_commands(root: Path, recipe: str) -> tuple[str, ...]:
    """Return one justfile recipe's command lines, resolved and ``@``-stripped.

    This is what ``just <recipe>`` actually executes, in order. A consumer that
    instead regexed raw justfile text for a recipe's body would see the
    literal token ``{{name}}`` in place of the value it expands to, which stops
    matching the moment a recipe's paths move into a variable -- exactly the
    shape that broke when the harness recipe's member paths did.
    """
    body = _recipe_bodies(resolved_justfile_text(root)).get(recipe, "")
    # `_recipe_bodies` does not treat an unindented comment as ending a body (a
    # doc comment can sit between a header and its own body without splitting
    # it), so a trailing comment block belonging to the NEXT recipe reads as
    # part of THIS one until the next non-comment line. A real command line is
    # never a bare comment, so it is filtered here rather than by widening the
    # shared boundary rule other callers already depend on.
    return tuple(
        line.strip().removeprefix("@")
        for line in body.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def declared_lanes(root: Path) -> tuple[Lane, ...]:
    """Return every lane declared by config, recipes, and workflows."""
    testpaths = configured_testpaths(root)
    default_expression = configured_marker_expression(root)
    lanes: list[Lane] = []

    text = resolved_justfile_text(root)
    if text:
        lanes.extend(_justfile_lanes(text, default_paths=testpaths))

    workflow_dir = root / _WORKFLOW_DIR
    if workflow_dir.is_dir():
        for workflow in scan_directory(workflow_dir, pattern="*.yml"):
            lanes.extend(
                _pytest_invocations(
                    workflow.read_text(encoding=_UTF_8),
                    source=f"{_WORKFLOW_DIR}/{workflow.name}",
                    default_paths=testpaths,
                ),
            )

    # A pathless invocation inherits both testpaths and the addopts expression.
    resolved: list[Lane] = []
    for lane in lanes:
        expression = lane.marker_expression if lane.marker_expression is not None else default_expression
        resolved.append(
            Lane(
                source=lane.source,
                paths=lane.paths,
                marker_expression=expression,
                recipe=lane.recipe,
                exclusions=lane.exclusions,
            ),
        )
    return tuple(resolved)


def _marker_name(node: ast.AST) -> str | None:
    """Return the NAME of a ``pytest.mark.NAME`` node, called or bare."""
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Attribute) and target.value.attr == "mark":
        return target.attr
    return None


def _module_markers(tree: ast.Module) -> frozenset[str]:
    """Return the module-level ``pytestmark`` markers every test inherits."""
    found: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets):
            continue
        values = node.value.elts if isinstance(node.value, ast.List | ast.Tuple) else [node.value]
        for value in values:
            name = _marker_name(value)
            if name is not None:
                found.add(name)
    return frozenset(found)


def marker_sets_in(path: Path) -> tuple[TestMarkers, ...] | None:
    """Return each test's EFFECTIVE markers, or None when the file is unreadable.

    Effective means module-level ``pytestmark`` plus any enclosing class's
    decorators plus the test function's own -- the set pytest itself resolves.
    Per test, never unioned across the file: one ``os_keychain`` test must not
    make its unit-marked siblings read as unreachable.

    Args:
        path: The test module to read.

    Returns:
        One entry per discovered test, or None when the file cannot be read.
        None is distinct from an empty tuple: absent (a peer staging a
        deletion) is not the same finding as present-with-no-tests.
    """
    try:
        tree = ast.parse(path.read_text(encoding=_UTF_8, errors="replace"))
    except (SyntaxError, ValueError, OSError):
        return None

    found: list[TestMarkers] = []

    def _walk(body: list[ast.stmt], inherited: frozenset[str]) -> None:
        for node in body:
            own = (
                frozenset(name for name in (_marker_name(d) for d in node.decorator_list) if name is not None)
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
                else frozenset()
            )
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test"):
                found.append(TestMarkers(test=node.name, markers=inherited | own))
            elif isinstance(node, ast.ClassDef):
                _walk(node.body, inherited | own)

    _walk(tree.body, _module_markers(tree))
    return tuple(found)


def tracked_test_files(root: Path) -> tuple[Path, ...]:
    """Return every git-TRACKED test module, repository-relative.

    Tracked rather than on-disk: an untracked file is a peer's uncommitted work
    that no lane could name and CI will never see, so counting it would red a
    shared gate on private state. Field-validated -- a peer's staged deletion of
    a whole test package arrived while this was in use and the gate correctly
    stayed quiet.
    """
    git = shutil.which("git")
    if git is None:
        message = "git is not on PATH, so tracked-file discovery cannot run"
        raise RuntimeError(message)
    completed = subprocess.run(  # noqa: S603 - resolved executable, fixed argv, no caller input
        [git, "ls-files"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    return tuple(
        Path(entry)
        for entry in completed.stdout.decode(_UTF_8).split("\n")
        if entry.endswith(".py") and Path(entry).name.startswith("test_")
    )


def expression_selects(expression: str | None, markers: frozenset[str]) -> bool:
    """Return whether a pytest ``-m`` expression can select these markers.

    Evaluated structurally rather than by string matching: ``unit or (integration
    and not serial)`` accepts a file marked integration only when it is not also
    marked serial, and that distinction is the whole reason the generator tests
    were unreachable.
    """
    if expression is None or not expression.strip():
        return True
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        # An unparseable expression is not evidence of reachability.
        return False

    def _evaluate(node: ast.AST) -> bool:
        if isinstance(node, ast.Expression):
            return _evaluate(node.body)
        if isinstance(node, ast.BoolOp):
            results = [_evaluate(value) for value in node.values]
            return all(results) if isinstance(node.op, ast.And) else any(results)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not _evaluate(node.operand)
        if isinstance(node, ast.Name):
            return node.id in markers
        if isinstance(node, ast.Constant):
            return bool(node.value)
        # An unmodelled construct must not be read as selection.
        return False

    return _evaluate(tree)


def discover_test_files(root: Path) -> tuple[Path, ...]:
    """Return every runnable test module under ``root``."""
    return scan_directory(root, pattern="test_*.py", recursive=True, prune_directories=_PRUNED)


def analyse_reachability(
    root: Path,
    *,
    lanes: Iterable[Lane] | None = None,
    files: Iterable[Path] | None = None,
) -> ReachabilityReport:
    """Return every test no declared lane can select, with its corpus size.

    Args:
        root: The repository root the lanes and paths are relative to.
        lanes: Declared lanes; read from ``root`` when omitted.
        files: Repository-relative test modules; git-tracked discovery when
            omitted. Injectable so the anti-tautology proofs can drive a
            synthetic tree that is not a git repository.

    Returns:
        The unreachable tests, the number of files successfully analysed, and
        the tracked files that could not be read.
    """
    resolved = tuple(lanes) if lanes is not None else declared_lanes(root)
    candidates = tuple(files) if files is not None else tracked_test_files(root)

    unreachable: list[UnreachableTest] = []
    unnamed: list[str] = []
    skipped: list[str] = []
    analysed = 0

    for path in candidates:
        relative = (path.relative_to(root) if path.is_absolute() else path).as_posix()
        covering = [lane for lane in resolved if lane.covers(relative)]

        # The path-level question, asked BEFORE the file is read so it still
        # holds for the two inputs the per-test model is blind to: a module with
        # no test functions, and a tracked file absent from disk. Both classes
        # are empty today; neither is impossible.
        if not covering:
            unnamed.append(relative)

        tests = marker_sets_in(root / relative)
        if tests is None:
            skipped.append(relative)
            continue
        analysed += 1
        for entry in tests:
            if not any(expression_selects(lane.marker_expression, entry.markers) for lane in covering):
                unreachable.append(UnreachableTest(path=relative, test=entry.test, markers=entry.markers))

    return ReachabilityReport(
        unreachable=tuple(unreachable),
        unnamed=tuple(unnamed),
        analysed=analysed,
        skipped=tuple(skipped),
    )
