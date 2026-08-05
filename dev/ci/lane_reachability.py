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

See Also:
    :func:`declared_lanes`
        Every lane the repository declares, from config, recipes, and workflows.
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

_UTF_8: Final[str] = "utf-8"

#: Directories that never contain runnable project tests.
_PRUNED: Final[frozenset[str]] = frozenset(
    {".git", ".venv", "node_modules", "__pycache__", "_build", ".mypy_cache", ".ruff_cache", ".pytest_cache"},
)

#: Where lane declarations live. Anything else is not a lane.
_WORKFLOW_DIR: Final[str] = ".github/workflows"


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
    """One declared pytest invocation: what it reaches and what it accepts."""

    source: str
    paths: tuple[str, ...]
    marker_expression: str | None

    def covers(self, relative_path: str) -> bool:
        """Return whether this lane's path scope reaches ``relative_path``."""
        if not self.paths:
            # A pathless invocation takes the configured testpaths, which the
            # caller supplies as this lane's paths. An empty scope reaches
            # nothing rather than everything: treating it as everything is how a
            # gate silently reports full coverage.
            return False
        posix = relative_path.replace("\\", "/")
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
        if token.endswith(".py") or "/" in token or token.startswith("src") or token.startswith("dev"):
            paths.append(token.split("::")[0])
    return tuple(paths)


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
        lanes.append(Lane(source=source, paths=paths, marker_expression=_marker_expression_of(tokens)))
    return lanes


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


def declared_lanes(root: Path) -> tuple[Lane, ...]:
    """Return every lane declared by config, recipes, and workflows."""
    testpaths = configured_testpaths(root)
    default_expression = configured_marker_expression(root)
    lanes: list[Lane] = []

    justfile = root / "justfile"
    if justfile.exists():
        lanes.extend(
            _pytest_invocations(justfile.read_text(encoding=_UTF_8), source="justfile", default_paths=testpaths)
        )

    workflow_dir = root / _WORKFLOW_DIR
    if workflow_dir.is_dir():
        for workflow in sorted(workflow_dir.glob("*.yml")):
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
        resolved.append(Lane(source=lane.source, paths=lane.paths, marker_expression=expression))
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
    found: list[Path] = []
    for path in root.rglob("test_*.py"):
        if any(part in _PRUNED for part in path.parts):
            continue
        found.append(path)
    return tuple(sorted(found))


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
