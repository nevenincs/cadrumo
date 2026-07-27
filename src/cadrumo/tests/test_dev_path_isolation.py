"""Dev-path isolation gate: the one-way ``src/cadrumo`` → ``dev/`` boundary.

``dev/`` is removable development scaffolding; ``src/cadrumo/`` is the shipped
application.  The dependency is strictly one-way:

* ``dev/`` imports from ``src/cadrumo`` through its public top-level facades.
* ``src/cadrumo/`` must never import ``dev.*`` and must never embed a path
  literal that reaches into the ``dev/`` tree at runtime.

This gate enforces both halves against **shipped modules** — the set that
lands in the installed wheel, read from the packaging config rather than
restated here.  Test trees are excluded from the wheel and sdist and may
freely use dev tooling (they encode "this suite requires the repo checkout
and the dev dependency group", which is always true and intended).  A shipped
module importing dev tooling raises ``ModuleNotFoundError`` for every
installed user; a shipped module reading a ``dev/`` path at runtime silently
fails the same way.

The gate is self-contained: it does not import from ``dev.*`` and reads no
file under ``dev/``.  That is not an oversight — the gate demonstrates the
boundary it enforces.  The shared detection logic from
``dev/import_hygiene_scan.py`` is re-implemented inline rather than imported,
keeping the gate deployable and testable against an injectable root with zero
circular dependence.

Duplicated import detector (pending ruling)
-------------------------------------------
Check 1 (no shipped module imports ``dev.*``) is a **second implementation** of
a detector that ``dev/import_hygiene_scan.py`` already owns and that
``test_import_hygiene_gate.py`` already asserts.  Only the path-reach half
(Check 2) was newly required.  Two detectors for one rule can drift — and had
already begun to: the shipped-``conftest.py`` case was proven on the other side
and absent here until it was mirrored below.  Whether this module or the
``dev/``-side scanner is the single authority is an open question deferred to an
ADR ruling; until it is answered, neither detector is deleted and every case
proven on one side is mirrored on the other.  Do not resolve the duplication by
quietly dropping a check.

Anti-tautology coverage
-----------------------
Each of the two checks is proven by injecting a deliberate violation into a
temporary tree and asserting the scanner returns it.  Every detected *form* has
its own firing proof, and every near-miss the detector must stay silent on
(``/dev/tty``, a ``devengada`` Spanish stem, ``"".join``) has its own silence
proof — a firing proof alone cannot show the difference between a precise
detector and one that fires on everything.  A vacuity floor asserts the live
scan visited a realistic number of shipped modules so an empty-scan false-pass
can never read as a clean tree.
"""

from __future__ import annotations

import ast
import fnmatch
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Final, NamedTuple

import pytest

from ..core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# ---------------------------------------------------------------------------
# Repo layout constants
# ---------------------------------------------------------------------------

_SRC_ROOT: Final[Path] = PROJECT_ROOT / "src"
_PKG_ROOT: Final[Path] = _SRC_ROOT / "cadrumo"
_PYPROJECT_PATH: Final[Path] = PROJECT_ROOT / "pyproject.toml"

_UTF_8: Final[str] = "utf-8"

# Every shipped module must visit at least this many files before a hard-zero
# result is accepted.  Keeps an accidental empty-scan from reading as clean.
_VACUITY_FLOOR: Final[int] = 500

# Callables whose first string-literal argument names a module to import.
# A dynamically-built target is invisible to the AST import walk, so a
# ``dev.`` reach expressed via ``importlib.import_module`` would otherwise
# slip the import check entirely.
_DYNAMIC_IMPORT_CALLABLES: Final[frozenset[str]] = frozenset({"import_module", "__import__"})

# The dev tree's directory name.  Matched as a whole path SEGMENT, never as a
# substring: "devengada", "devolucion", "device" and "dev.example.com" are all
# common in this codebase and none of them is a reach into dev/.
_DEV_DIR: Final[str] = "dev"

# Leading segments that carry no path identity of their own.
_RELATIVE_MARKERS: Final[frozenset[str]] = frozenset({".", ".."})

# Callables that assemble a filesystem path from separate segment arguments, so
# a bare "dev" argument names the dev directory.  ``join`` is deliberately gated
# on an arity of two or more: ``sep.join(iterable)`` is a string operation with
# a single argument and must never be read as a path assembly.
_SEGMENT_JOIN_CALLABLES: Final[frozenset[str]] = frozenset({"join"})
_PATH_FACTORY_CALLABLES: Final[frozenset[str]] = frozenset(
    {
        "Path",
        "PurePath",
        "PosixPath",
        "PurePosixPath",
        "WindowsPath",
        "PureWindowsPath",
        "joinpath",
    }
)


# ---------------------------------------------------------------------------
# Packaging helpers (self-contained; no dev.* import)
# ---------------------------------------------------------------------------


def _wheel_exclude_globs(pyproject_path: Path = _PYPROJECT_PATH) -> tuple[str, ...]:
    """Return the wheel ``exclude`` globs from the project config.

    Read from the packaging config rather than restated so the
    shipped/unshipped boundary stays true if the packaging config changes.
    A missing table raises immediately: silently defaulting to "nothing is
    excluded" would classify every module as shipped, and silently defaulting
    to "everything excluded" would mute the gate.
    """
    data = tomllib.loads(pyproject_path.read_text(encoding=_UTF_8))
    excludes = data["tool"]["hatch"]["build"]["targets"]["wheel"]["exclude"]
    return tuple(str(g) for g in excludes)


def _is_shipped_module(
    path: Path,
    *,
    src_root: Path,
    exclude_globs: tuple[str, ...],
) -> bool:
    """True if ``path`` would land in the installed wheel.

    Mirrors the logic in ``dev/import_hygiene_scan.py`` (``is_shipped_module``)
    without importing it.

    Args:
        path: Module file to classify.
        src_root: Source root ``path`` is relative to; used to build the
            packaging-config-relative path.
        exclude_globs: Wheel exclude globs read from the packaging config.
    """
    rel = "src/" + path.relative_to(src_root).as_posix()
    for glob in exclude_globs:
        bare_prefix = glob.rstrip("*").rstrip("/") + "/"
        if fnmatch.fnmatchcase(rel, glob) or rel.startswith(bare_prefix):
            return False
    return True


# ---------------------------------------------------------------------------
# Check 1: no shipped module imports ``dev.*``
# ---------------------------------------------------------------------------


def _targets_dev(mod: str) -> bool:
    """True if ``mod`` names the dev tooling root or anything beneath it."""
    return mod == "dev" or mod.startswith("dev.")


def _iter_dynamic_dev_targets(path: Path) -> list[tuple[int, str]]:
    """Return ``(lineno, module)`` pairs from detectable dynamic dev imports.

    Only a string-literal first argument to ``importlib.import_module`` /
    ``__import__`` is resolvable by static reading; a target assembled from
    variables is out of reach and left to review.
    """
    try:
        tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            called = func.attr
        elif isinstance(func, ast.Name):
            called = func.id
        else:
            continue
        if called not in _DYNAMIC_IMPORT_CALLABLES:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            found.append((node.lineno, first.value))
    return found


def find_dev_import_violations(
    py_files: list[Path],
    *,
    src_root: Path,
    exclude_globs: tuple[str, ...],
) -> list[tuple[str, int, str, bool]]:
    """Return ``(rel_path, lineno, target_mod, is_dynamic)`` for every violation.

    Scans every shipped module in ``py_files`` for:

    * ``import dev`` / ``import dev.X`` (bare ``import`` statement)
    * ``from dev import ...`` / ``from dev.X import ...``
    * ``importlib.import_module("dev...")`` (dynamic, literal-target form only)

    Args:
        py_files: Module files to scan.
        src_root: Source root used to resolve shipped status and importer names.
        exclude_globs: Wheel exclude globs from the packaging config.
    """
    violations: list[tuple[str, int, str, bool]] = []
    for path in py_files:
        if not _is_shipped_module(path, src_root=src_root, exclude_globs=exclude_globs):
            continue
        rel = path.relative_to(src_root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _targets_dev(alias.name):
                        violations.append((rel, node.lineno, alias.name, False))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if _targets_dev(mod):
                    violations.append((rel, node.lineno, mod, False))
        for lineno, target in _iter_dynamic_dev_targets(path):
            if _targets_dev(target):
                violations.append((rel, lineno, target, True))
    return sorted(violations)


# ---------------------------------------------------------------------------
# Check 2: no shipped module reaches a ``dev/`` path
# ---------------------------------------------------------------------------


class DevPathForm(StrEnum):
    """The syntactic shape a shipped module used to reach into ``dev/``."""

    LITERAL = "literal"
    PATH_JOIN = "path_join"
    CALL_JOIN = "call_join"
    FSTRING = "fstring"


class DevPathViolation(NamedTuple):
    """One shipped-module reach into the ``dev/`` tree."""

    rel_path: str
    lineno: int
    form: DevPathForm
    detail: str


def _posix_segments(value: str) -> list[str]:
    """Split ``value`` into path segments on either separator.

    Windows and POSIX separators are folded together so ``"dev\\\\x.json"`` and
    ``"dev/x.json"`` are the same path to this scanner.
    """
    return value.replace("\\", "/").split("/")


def _names_dev_directory(value: str) -> bool:
    """True if ``value`` is a *relative* path whose leading component is ``dev``.

    Segment-aware, never a substring test.  Three discriminations carry the
    precision of this whole check:

    * An **absolute** ``/dev/...`` value is a POSIX device node, not the repo
      tree.  ``src/cadrumo/entrypoints/cli/_config/_secure_input.py`` opens
      ``"/dev/tty"`` in shipped code and is correct; firing there would red the
      gate on sound code and teach the next author to weaken it.
    * A segment must **equal** ``dev``.  ``devengada``, ``devolucion``,
      ``device`` and ``dev.example.com`` are all near-misses this codebase
      really contains.
    * ``dev`` must be used as a **directory** — something has to follow it.  A
      bare ``"dev"`` string carries no path meaning on its own; it is caught by
      the join forms below, which supply the surrounding path context.

    A value containing a newline is prose (a docstring or a message), never a
    path literal, and is rejected; docstrings are skipped wholesale by
    :func:`_docstring_constant_ids`.  A single-line NON-docstring string that
    begins with a dev path — an assertion message, say — is still reported.
    That is deliberate: narrowing further (rejecting any value containing a
    space) would let ``"dev/my baseline.json"`` through, and in a hard-zero
    boundary gate an over-fire costs a reword while an under-fire ships a
    broken wheel.  A shipped module has no business naming the dev tree even
    in prose.
    """
    if not value or "\n" in value or "\r" in value:
        return False
    normalised = value.replace("\\", "/")
    if normalised.startswith("/"):
        return False
    segments = normalised.split("/")
    index = 0
    while index < len(segments) and segments[index] in _RELATIVE_MARKERS:
        index += 1
    return index + 1 < len(segments) and segments[index] == _DEV_DIR


def _continues_into_dev_directory(text: str) -> bool:
    """True for an f-string tail like ``"/dev/x.json"`` that follows a root interpolation.

    Read only for a constant segment PRECEDED by an interpolation, where the
    leading separator joins onto an interpolated root rather than marking an
    absolute path.  That preceding-interpolation requirement is what keeps a
    plain ``f"/dev/null"`` out: with nothing interpolated before it, the value
    is an absolute device path and is judged by :func:`_names_dev_directory`.
    """
    segments = _posix_segments(text)
    return len(segments) >= 2 and segments[0] == "" and segments[1] == _DEV_DIR


def _is_bare_dev_segment(node: ast.expr) -> bool:
    """True if ``node`` is the string constant ``"dev"``."""
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value == _DEV_DIR


def _divided_dev_segment(node: ast.BinOp) -> str | None:
    """Return a detail string if ``node`` is a ``pathlib`` join onto ``"dev"``.

    Matches ``PROJECT_ROOT / "dev"`` — the realistic form of this violation,
    since a bare ``open("dev/x.json")`` is CWD-relative and would not survive a
    single test run from outside the repo root.  ``PROJECT_ROOT`` is exported
    from ``cadrumo.core.paths``, so a shipped module can anchor a fully working
    dev-tree read this way and break only once installed as a wheel.

    Both operands are checked: ``Path.__rtruediv__`` makes ``"dev" / root`` a
    valid join too.  Only the BARE ``"dev"`` segment matches here; a
    ``root / "dev/x.json"`` operand is already a dev path literal and is
    reported once, by :func:`_names_dev_directory`, rather than twice.
    """
    if not isinstance(node.op, ast.Div):
        return None
    if _is_bare_dev_segment(node.right) or _is_bare_dev_segment(node.left):
        return f'{ast.unparse(node)!s} (path join onto "{_DEV_DIR}")'
    return None


def _called_function_name(func: ast.expr) -> str | None:
    """Return the trailing callable name of ``func``, or ``None`` if unreadable."""
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _call_assembled_dev_segment(node: ast.Call) -> str | None:
    """Return a detail string if ``node`` assembles a path from a ``"dev"`` segment.

    Covers ``os.path.join(root, "dev", "x.json")`` and the ``Path(root, "dev")``
    / ``root.joinpath("dev")`` factory forms.  ``join`` requires two or more
    arguments so ``"".join(parts)`` — a string operation, not a path assembly —
    can never match.
    """
    name = _called_function_name(node.func)
    if name is None:
        return None
    if name in _SEGMENT_JOIN_CALLABLES:
        if len(node.args) < 2:
            return None
    elif name not in _PATH_FACTORY_CALLABLES:
        return None
    if not node.args:
        return None
    if any(_is_bare_dev_segment(arg) for arg in node.args):
        return f'{name}(...) with a "{_DEV_DIR}" path segment'
    return None


def _joined_str_dev_parts(node: ast.JoinedStr) -> list[str]:
    """Return every constant part of an f-string that reaches into ``dev/``.

    An f-string hides the reach from a constant scan: ``f"{root}/dev/x.json"``
    stores the segment as the constant ``"/dev/x.json"``, which starts with a
    separator and matches no ``dev/`` prefix.
    """
    parts: list[str] = []
    interpolated = False
    for part in node.values:
        if isinstance(part, ast.FormattedValue):
            interpolated = True
            continue
        if not isinstance(part, ast.Constant) or not isinstance(part.value, str):
            continue
        text = part.value
        if _names_dev_directory(text) or (interpolated and _continues_into_dev_directory(text)):
            parts.append(text)
    return parts


def _docstring_constant_ids(tree: ast.Module) -> set[int]:
    """Return the node ids of every module, class, and function docstring.

    A docstring is documentation, never a runtime path read.  Several shipped
    modules legitimately name ``dev/`` tooling in their prose (the terminology
    handbook authoring tool, the corpus extractor), and that prose must not be
    read as a dependency.
    """
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            ids.add(id(first.value))
    return ids


def _dev_path_hits(tree: ast.Module) -> list[tuple[int, DevPathForm, str]]:
    """Return every ``(lineno, form, detail)`` dev-tree reach in one parsed module."""
    skip = _docstring_constant_ids(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            skip.update(id(part) for part in node.values if isinstance(part, ast.Constant))

    hits: list[tuple[int, DevPathForm, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            hits.extend((node.lineno, DevPathForm.FSTRING, text) for text in _joined_str_dev_parts(node))
        elif isinstance(node, ast.BinOp):
            detail = _divided_dev_segment(node)
            if detail is not None:
                hits.append((node.lineno, DevPathForm.PATH_JOIN, detail))
        elif isinstance(node, ast.Call):
            detail = _call_assembled_dev_segment(node)
            if detail is not None:
                hits.append((node.lineno, DevPathForm.CALL_JOIN, detail))
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in skip
            and _names_dev_directory(node.value)
        ):
            hits.append((node.lineno, DevPathForm.LITERAL, node.value))
    return hits


def find_dev_path_reach_violations(
    py_files: list[Path],
    *,
    src_root: Path,
    exclude_globs: tuple[str, ...],
) -> list[DevPathViolation]:
    """Return every shipped-module reach into the ``dev/`` tree.

    This is the metadata-loophole check that an import scan alone cannot see: a
    module reading a dev artifact at runtime does not import ``dev.*`` but is
    just as broken for every installed user, because ``dev/`` ships in neither
    the wheel nor the sdist.

    Four forms are detected, because the boundary breaks in all four and a
    scanner covering only the first is a scanner that cannot see the realistic
    case:

    * ``literal`` — ``"dev/baseline.json"``, ``"./dev/..."``, ``"..\\dev\\..."``
    * ``path_join`` — ``PROJECT_ROOT / "dev" / "baseline.json"``
    * ``call_join`` — ``os.path.join(root, "dev", ...)``, ``Path(root, "dev")``
    * ``fstring`` — ``f"{root}/dev/baseline.json"``

    **Construction is the trigger, not the read.** A reach is reported where the
    path is BUILT, without requiring an adjacent ``open``/``read_text`` call.
    Demanding proof of a read would reopen the hole this check exists to close:
    a module constant assigned once and consumed elsewhere (exactly how the two
    real baselines in the excluded test tree are written) would then pass while
    depending on a dev artifact at runtime. A shipped module has no legitimate
    reason to name the dev tree at all.

    Args:
        py_files: Module files to scan.
        src_root: Source root used to resolve shipped status and relative paths.
        exclude_globs: Wheel exclude globs from the packaging config.
    """
    violations: list[DevPathViolation] = []
    for path in py_files:
        if not _is_shipped_module(path, src_root=src_root, exclude_globs=exclude_globs):
            continue
        rel = path.relative_to(src_root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        violations.extend(DevPathViolation(rel, lineno, form, detail) for lineno, form, detail in _dev_path_hits(tree))
    return sorted(violations)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _planted_module(root: Path, rel: str, body: str) -> Path:
    """Write a synthetic module at ``rel`` under ``root`` and return its path."""
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding=_UTF_8)
    return target


def _shipped_py_files(
    pkg_root: Path = _PKG_ROOT,
    *,
    exclude_globs: tuple[str, ...] | None = None,
) -> list[Path]:
    """Return every ``.py`` file under ``pkg_root`` excluding ``__pycache__``."""
    globs = exclude_globs if exclude_globs is not None else _wheel_exclude_globs()
    return sorted(
        p
        for p in pkg_root.rglob("*.py")
        if "__pycache__" not in p.parts and _is_shipped_module(p, src_root=_SRC_ROOT, exclude_globs=globs)
    )


# ---------------------------------------------------------------------------
# Live-tree gate: Check 1 — no shipped module imports dev.*
# ---------------------------------------------------------------------------


def test_no_shipped_module_imports_dev_tooling() -> None:
    """No shipped module under ``src/cadrumo`` may import ``dev.*``.

    ``dev/`` is development tooling absent from both the wheel and the sdist.
    A shipped module importing it raises ``ModuleNotFoundError`` for every
    installed user while resolving fine in the repo checkout — a defect no
    in-repository test run surfaces.

    Hard zero: no allowlist.  A new violation is fixed by moving what the
    shipped side needs under ``src/cadrumo``, never by recording an exception.
    """
    globs = _wheel_exclude_globs()
    py_files = sorted(p for p in _PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts)
    shipped = [p for p in py_files if _is_shipped_module(p, src_root=_SRC_ROOT, exclude_globs=globs)]

    assert len(shipped) >= _VACUITY_FLOOR, (
        f"vacuity check: fewer than {_VACUITY_FLOOR} shipped modules were found under "
        f"{_PKG_ROOT} (found {len(shipped)}).  Either the packaging config changed or the "
        "scan resolved an empty tree; investigate before accepting a zero result."
    )

    violations = find_dev_import_violations(py_files, src_root=_SRC_ROOT, exclude_globs=globs)

    offenders = [
        f"{'[dynamic] ' if is_dyn else ''}{rel}:{lineno} -> {target}" for rel, lineno, target, is_dyn in violations
    ]
    assert offenders == [], (
        "shipped module(s) under src/cadrumo import the unshipped dev/ tooling.  "
        "Move what the shipped side needs under src/cadrumo; do not add an allowlist:\n  " + "\n  ".join(offenders)
    )


# ---------------------------------------------------------------------------
# Live-tree gate: Check 2 — no shipped module reaches a dev/ path
# ---------------------------------------------------------------------------


def test_no_shipped_module_reaches_a_dev_path() -> None:
    """No shipped module under ``src/cadrumo`` may build a path into ``dev/``.

    This is the metadata-loophole complement to the import check: a shipped
    module can reference dev/ artifacts through ``PROJECT_ROOT / "dev" /
    "baseline.json"`` without any ``import dev`` statement.  Both forms make the
    shipped module depend on development infrastructure that is absent from the
    installed wheel — the import check catches the code dependency; this check
    catches the data dependency.

    Hard zero: no allowlist.  A new violation is fixed by moving the artifact
    under ``src/cadrumo`` where it belongs.
    """
    globs = _wheel_exclude_globs()
    py_files = sorted(p for p in _PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts)
    shipped = [p for p in py_files if _is_shipped_module(p, src_root=_SRC_ROOT, exclude_globs=globs)]

    assert len(shipped) >= _VACUITY_FLOOR, (
        f"vacuity check: fewer than {_VACUITY_FLOOR} shipped modules were found under "
        f"{_PKG_ROOT} (found {len(shipped)}).  Either the packaging config changed or the "
        "scan resolved an empty tree; investigate before accepting a zero result."
    )

    violations = find_dev_path_reach_violations(py_files, src_root=_SRC_ROOT, exclude_globs=globs)

    offenders = [f"{v.rel_path}:{v.lineno} [{v.form}] -> {v.detail!r}" for v in violations]
    assert offenders == [], (
        "shipped module(s) under src/cadrumo build a path into the unshipped dev/ tree.  "
        "Move the artifact under src/cadrumo/_data/ or equivalent so the shipped side reads "
        "only its own tree; do not add an allowlist:\n  " + "\n  ".join(offenders)
    )


# ---------------------------------------------------------------------------
# Anti-tautology: Check 1 — the import scanner MUST fire on a planted violation
# ---------------------------------------------------------------------------


def test_import_scanner_catches_planted_static_dev_import(tmp_path: Path) -> None:
    """A planted ``from dev.X import y`` in a shipped module MUST be detected.

    Without this proof the hard-zero assertion above is indistinguishable from
    a detector that cannot fire — the failure mode that lets a gate pass while
    blind to the thing it guards.
    """
    # Build a minimal synthetic src tree: one shipped module with a dev import.
    _planted_module(
        tmp_path,
        "cadrumo/shipped_module.py",
        "from dev.registry.matrix import manager\n",
    )
    # Simulate a pyproject.toml with no test-excluding globs (so the planted
    # file IS shipped) — but we pass globs explicitly so no real file is read.
    empty_globs: tuple[str, ...] = ()

    py_files = [tmp_path / "cadrumo" / "shipped_module.py"]
    violations = find_dev_import_violations(py_files, src_root=tmp_path, exclude_globs=empty_globs)

    assert len(violations) == 1, f"expected exactly 1 violation for the planted dev import; got {violations!r}"
    rel, _lineno, target, is_dynamic = violations[0]
    assert rel == "cadrumo/shipped_module.py"
    assert target == "dev.registry.matrix"
    assert is_dynamic is False


def test_import_scanner_catches_bare_dev_import(tmp_path: Path) -> None:
    """A bare ``import dev`` statement in a shipped module MUST be detected."""
    _planted_module(tmp_path, "cadrumo/bare_import.py", "import dev\n")
    empty_globs: tuple[str, ...] = ()

    violations = find_dev_import_violations(
        [tmp_path / "cadrumo" / "bare_import.py"],
        src_root=tmp_path,
        exclude_globs=empty_globs,
    )

    assert any(t == "dev" for _, _, t, _ in violations), f"bare 'import dev' was not caught; violations={violations!r}"


def test_import_scanner_catches_planted_dynamic_dev_import(tmp_path: Path) -> None:
    """A ``importlib.import_module("dev...")`` literal in a shipped module MUST be caught.

    A dynamically-built module string is invisible to a naive AST import walk;
    this proves the dynamic-target branch fires on the literal-argument form.
    """
    body = (
        'import importlib\n\ndef load_manager():\n    return importlib.import_module("dev.registry.matrix.manager")\n'
    )
    _planted_module(tmp_path, "cadrumo/dynamic_import.py", body)
    empty_globs: tuple[str, ...] = ()

    violations = find_dev_import_violations(
        [tmp_path / "cadrumo" / "dynamic_import.py"],
        src_root=tmp_path,
        exclude_globs=empty_globs,
    )

    dynamic_hits = [(rel, lineno, target) for rel, lineno, target, is_dyn in violations if is_dyn]
    assert dynamic_hits, f"dynamic dev import was not caught; all violations={violations!r}"
    assert dynamic_hits[0][2] == "dev.registry.matrix.manager"


def test_import_scanner_does_not_fire_on_excluded_test_module(tmp_path: Path) -> None:
    """The ruling proven: an identical import in an EXCLUDED test tree is NOT a violation.

    Pins the scope decision: test trees are excluded from the wheel/sdist and
    may legitimately import dev tooling (they run from the repo checkout).
    If someone widens the family to test trees this test fails, forcing the
    change to be a deliberate ruling rather than a silent broadening.
    """
    _planted_module(
        tmp_path,
        "cadrumo/tests/test_planted.py",
        "from dev.import_hygiene_scan import find_dev_tooling_import_violations\n",
    )
    # Simulate wheel excludes that shed the tests tree.
    test_excludes: tuple[str, ...] = (
        "src/cadrumo/tests",
        "src/cadrumo/tests/**",
        "src/cadrumo/**/tests",
        "src/cadrumo/**/tests/**",
    )
    violations = find_dev_import_violations(
        [tmp_path / "cadrumo" / "tests" / "test_planted.py"],
        src_root=tmp_path,
        exclude_globs=test_excludes,
    )
    assert violations == [], (
        f"the import scanner fired on an excluded test module, contradicting its documented scope: {violations!r}"
    )


def test_import_scanner_does_not_fire_on_cadrumo_import(tmp_path: Path) -> None:
    """The scanner must not over-reach onto a legitimate ``cadrumo.*`` import."""
    _planted_module(
        tmp_path,
        "cadrumo/clean_module.py",
        "from cadrumo.core import config\nfrom cadrumo.domain.calculations import registry\n",
    )
    empty_globs: tuple[str, ...] = ()

    violations = find_dev_import_violations(
        [tmp_path / "cadrumo" / "clean_module.py"],
        src_root=tmp_path,
        exclude_globs=empty_globs,
    )
    assert violations == [], f"the import scanner fired on a legitimate cadrumo.* import: {violations!r}"


# ---------------------------------------------------------------------------
# Anti-tautology: Check 2 — the path scanner MUST fire on every planted form
# ---------------------------------------------------------------------------

_TEST_TREE_EXCLUDES: Final[tuple[str, ...]] = (
    "src/cadrumo/tests",
    "src/cadrumo/tests/**",
    "src/cadrumo/**/tests",
    "src/cadrumo/**/tests/**",
)


def _scan_planted(tmp_path: Path, rel: str, body: str, *, excludes: tuple[str, ...] = ()) -> list[DevPathViolation]:
    """Plant one module under ``tmp_path`` and return the dev-path reaches found in it."""
    planted = _planted_module(tmp_path, rel, body)
    return find_dev_path_reach_violations([planted], src_root=tmp_path, exclude_globs=excludes)


def test_path_scanner_catches_planted_dev_path_literal(tmp_path: Path) -> None:
    """A ``"dev/some_file.json"`` string literal in a shipped module MUST be caught.

    Without this proof the hard-zero assertion above is indistinguishable from
    a detector that cannot fire — the failure mode that lets a gate pass while
    blind to the thing it guards.
    """
    violations = _scan_planted(
        tmp_path,
        "cadrumo/reads_dev_file.py",
        'from pathlib import Path\n\ndef load_baseline():\n    return Path("dev/import_hygiene_baseline.json").read_text()\n',
    )

    assert len(violations) == 1, f"expected exactly 1 dev-path reach; got {violations!r}"
    assert violations[0].rel_path == "cadrumo/reads_dev_file.py"
    assert violations[0].form is DevPathForm.LITERAL
    assert violations[0].detail == "dev/import_hygiene_baseline.json"


def test_path_scanner_catches_relative_and_windows_separator_forms(tmp_path: Path) -> None:
    """``"./dev/"``, ``"../dev/"`` and the Windows ``"dev\\x"`` separator MUST be caught.

    The backslash form is the one a Windows-authored path literal takes; a
    scanner reading only ``/`` separators is blind to it on the platform this
    repository is developed on.
    """
    violations = _scan_planted(
        tmp_path,
        "cadrumo/relative_paths.py",
        "def load_a():\n"
        '    return open("./dev/some_config.json")\n'
        "def load_b():\n"
        '    return open("../dev/other_baseline.json")\n'
        "def load_c():\n"
        '    return open("dev\\\\windows_baseline.json")\n'
        "def load_d():\n"
        '    return open("..\\\\dev\\\\windows_parent.json")\n',
    )

    values = {v.detail for v in violations}
    assert values == {
        "./dev/some_config.json",
        "../dev/other_baseline.json",
        "dev\\windows_baseline.json",
        "..\\dev\\windows_parent.json",
    }, f"a relative or Windows-separator dev path was missed; violations={violations!r}"


def test_path_scanner_catches_project_root_anchored_join(tmp_path: Path) -> None:
    """``PROJECT_ROOT / "dev" / "file"`` MUST fire — this is the realistic violation.

    An earlier revision of this gate pinned this exact form as NOT a violation,
    on the reasoning that ``"dev"`` here is a bare segment rather than a
    ``"dev/"``-prefixed literal.  That reasoning inverted the risk: a bare
    ``open("dev/baseline.json")`` is CWD-relative and breaks on the first run
    from any other directory, so nobody writes it, while the
    ``PROJECT_ROOT``-anchored join works perfectly in the repo checkout and
    breaks only once installed as a wheel — silently, for users only.
    ``PROJECT_ROOT`` is exported from ``cadrumo.core.paths``, which this very
    module imports, so the form is one line away at all times.

    The scanner must therefore fire here, and this test is the pin that keeps
    it firing.
    """
    violations = _scan_planted(
        tmp_path,
        "cadrumo/anchored_join.py",
        "from cadrumo.core.paths import PROJECT_ROOT\n"
        "\n"
        'CONFORMANCE_BASELINE = PROJECT_ROOT / "dev" / "conformance_baseline.json"\n'
        "\n"
        "def load_baseline() -> str:\n"
        "    return CONFORMANCE_BASELINE.read_text(encoding='utf-8')\n",
    )

    assert len(violations) == 1, f"expected exactly 1 reach for the anchored join; got {violations!r}"
    assert violations[0].form is DevPathForm.PATH_JOIN, (
        f"the PROJECT_ROOT-anchored dev join was not reported as a path join: {violations!r}"
    )
    assert violations[0].lineno == 3


def test_path_scanner_catches_call_assembled_dev_segment(tmp_path: Path) -> None:
    """``os.path.join``, the ``Path(...)`` factory and ``joinpath`` MUST all fire."""
    violations = _scan_planted(
        tmp_path,
        "cadrumo/call_joins.py",
        "import os\n"
        "from pathlib import Path\n"
        "\n"
        "def a(root):\n"
        '    return open(os.path.join(root, "dev", "baseline.json"))\n'
        "def b(root):\n"
        '    return Path(root, "dev", "worklist.json")\n'
        "def c(root):\n"
        '    return Path(root).joinpath("dev")\n',
    )

    assert [v.form for v in violations] == [DevPathForm.CALL_JOIN] * 3, (
        f"a call-assembled dev path segment was missed; violations={violations!r}"
    )
    assert sorted(v.lineno for v in violations) == [5, 7, 9]


def test_path_scanner_catches_fstring_composed_dev_path(tmp_path: Path) -> None:
    """An f-string composing a dev path MUST fire.

    ``f"{root}/dev/x.json"`` stores its segment as the constant
    ``"/dev/x.json"``, which starts with a separator and matches no ``dev/``
    prefix — invisible to a prefix-only scan.
    """
    violations = _scan_planted(
        tmp_path,
        "cadrumo/fstrings.py",
        "def a(root):\n"
        '    return open(f"{root}/dev/conformance_baseline.json")\n'
        "def b(name):\n"
        '    return open(f"dev/{name}.json")\n',
    )

    assert [v.form for v in violations] == [DevPathForm.FSTRING] * 2, (
        f"an f-string-composed dev path was missed; violations={violations!r}"
    )
    assert {v.detail for v in violations} == {"/dev/conformance_baseline.json", "dev/"}


# ---------------------------------------------------------------------------
# Anti-tautology: Check 2 — the near-misses the scanner MUST stay silent on
# ---------------------------------------------------------------------------


def test_path_scanner_does_not_fire_on_posix_device_paths(tmp_path: Path) -> None:
    """``/dev/tty`` and ``/dev/null`` are device nodes, NOT the repo dev tree.

    This is not hypothetical: shipped code at
    ``src/cadrumo/entrypoints/cli/_config/_secure_input.py`` opens ``/dev/tty``
    to read a secret without echo, and is correct to do so.  A substring match
    on ``/dev/`` would red this gate on sound code — and a gate that fires on
    correct code teaches the next author to weaken it.
    """
    violations = _scan_planted(
        tmp_path,
        "cadrumo/device_paths.py",
        "import sys\n"
        "\n"
        "def tty_path() -> str:\n"
        '    return "CONOUT$" if sys.platform == "win32" else "/dev/tty"\n'
        "def null_sink():\n"
        '    return open("/dev/null", "w")\n',
    )

    assert violations == [], f"the scanner fired on a POSIX device path, which is not the dev tree: {violations!r}"


def test_path_scanner_does_not_fire_on_spanish_stems_or_dev_substrings(tmp_path: Path) -> None:
    """``devengada``, ``devolucion``, ``device`` and ``dev.example.com`` MUST stay silent.

    The Spanish stems are pervasive in this codebase (IVA devengada, solicitud
    de devolucion).  A substring match on ``dev`` would fire on hundreds of
    correct sites; matching must be whole-path-segment.
    """
    violations = _scan_planted(
        tmp_path,
        "cadrumo/near_misses.py",
        'CUOTA = "iva/devengada/total.json"\n'
        'DEVOLUCION = "devolucion/pendiente.json"\n'
        'DEVICE = "device/serial.json"\n'
        'LOCALE_KEY = "cli.config.dev.help"\n'
        'DOCS_URL = "https://dev.example.com/guide"\n'
        "\n"
        "def totals(root):\n"
        '    return root / "devengada" / "cuota.json"\n'
        "def refund(root):\n"
        '    return open(f"{root}/devolucion.json")\n',
    )

    assert violations == [], f"the scanner fired on a 'dev' substring that is not a dev/ path segment: {violations!r}"


def test_path_scanner_does_not_fire_on_string_join(tmp_path: Path) -> None:
    """``"".join(parts)`` is a string operation, not a path assembly."""
    violations = _scan_planted(
        tmp_path,
        "cadrumo/string_joins.py",
        'def flatten(parts):\n    return "".join(parts)\ndef label():\n    return ", ".join(["dev", "prod"])\n',
    )

    assert violations == [], f"the scanner read a string join as a path assembly: {violations!r}"


def test_path_scanner_does_not_fire_on_prose_naming_dev_tooling(tmp_path: Path) -> None:
    """A docstring naming a ``dev/`` tool is documentation, not a runtime read.

    Shipped modules legitimately cite the dev tooling that produced a shipped
    sidecar (the corpus extractor, the terminology handbook authoring tool).
    The planted docstrings here BEGIN with the ``dev/`` path, so the
    docstring-skip is load-bearing rather than incidentally satisfied by the
    leading-segment rule.
    """
    violations = _scan_planted(
        tmp_path,
        "cadrumo/prose.py",
        '"""dev/corpus/extract_manual_corpus_text.py produces the shipped sidecar."""\n'
        "\n"
        "def parse(text):\n"
        '    """dev/docs/terminology_handbook.py authors the compiled fragments."""\n'
        "    return text\n",
    )

    assert violations == [], f"the scanner read documentation prose as a dev-tree dependency: {violations!r}"


def test_path_scanner_does_not_fire_on_excluded_test_module(tmp_path: Path) -> None:
    """Every violating form in an EXCLUDED test module is NOT a violation.

    Test trees ship in neither the wheel nor the sdist and legitimately read
    dev/ baselines from the repo checkout — this module's own siblings do.  If
    someone widens the family to the excluded trees this test fails, forcing the
    change to be a deliberate ruling rather than a silent broadening.
    """
    violations = _scan_planted(
        tmp_path,
        "cadrumo/tests/test_with_dev_path.py",
        "from pathlib import Path\n"
        "from cadrumo.core.paths import PROJECT_ROOT\n"
        "\n"
        'BASELINE = Path("dev/import_hygiene_baseline.json")\n'
        'ANCHORED = PROJECT_ROOT / "dev" / "import_hygiene_baseline.json"\n'
        "\n"
        "def composed(root):\n"
        '    return f"{root}/dev/size_budget_baseline.json"\n',
        excludes=_TEST_TREE_EXCLUDES,
    )

    assert violations == [], f"the path scanner fired on an excluded test module: {violations!r}"


# ---------------------------------------------------------------------------
# Cross-detector parity: the shipped package-root conftest.py
# ---------------------------------------------------------------------------


def test_both_scanners_catch_a_planted_shipped_conftest(tmp_path: Path) -> None:
    """A package-root ``conftest.py`` SHIPS, so both a ``dev.`` import and a dev path fire.

    ``src/cadrumo/conftest.py`` is a real wheel member: it carries no ``tests/``
    path component, so the packaging excludes never shed it.  A name-based
    "anything called conftest is test infrastructure" scope would silently
    exempt a genuinely shipped module.

    This case was proven on the ``dev/``-side detector's gate and absent here —
    the first observed drift between the two implementations of Check 1
    (see the module docstring).  It is mirrored here so the two detectors
    cannot disagree while the single-authority question is open.
    """
    body = 'import dev\nfrom cadrumo.core.paths import PROJECT_ROOT\n\nBASELINE = PROJECT_ROOT / "dev" / "x.json"\n'
    planted = _planted_module(tmp_path, "cadrumo/conftest.py", body)

    import_violations = find_dev_import_violations([planted], src_root=tmp_path, exclude_globs=_TEST_TREE_EXCLUDES)
    path_violations = find_dev_path_reach_violations([planted], src_root=tmp_path, exclude_globs=_TEST_TREE_EXCLUDES)

    assert [(rel, target) for rel, _lineno, target, _dyn in import_violations] == [("cadrumo/conftest.py", "dev")], (
        f"a shipped package-root conftest.py importing dev/ must be caught; detected {import_violations!r}"
    )
    assert [(v.rel_path, v.form) for v in path_violations] == [("cadrumo/conftest.py", DevPathForm.PATH_JOIN)], (
        f"a shipped package-root conftest.py reaching a dev/ path must be caught; detected {path_violations!r}"
    )
