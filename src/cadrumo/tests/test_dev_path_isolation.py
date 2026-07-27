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

Anti-tautology coverage
-----------------------
Each of the two checks is proven by injecting a deliberate violation into a
temporary tree and asserting the scanner returns it.  A vacuity floor asserts
the live scan visited a realistic number of shipped modules so an empty-scan
false-pass can never read as a clean tree.
"""

from __future__ import annotations

import ast
import fnmatch
import tomllib
from pathlib import Path
from typing import Final

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

# Path-prefix tokens that identify a string constant as a reference into the
# dev tree.  These are checked as *starts-with* predicates on the raw string
# value (not via fnmatch or regex) to avoid false positives.
_DEV_PATH_PREFIXES: Final[tuple[str, ...]] = (
    "dev/",
    "./dev/",
    "../dev/",
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
# Check 2: no shipped module embeds a ``dev/`` path literal
# ---------------------------------------------------------------------------


def _looks_like_dev_path(value: object) -> bool:
    """True if ``value`` is a string constant that looks like a path into ``dev/``.

    Checks for the string-literal form that an import scan cannot catch: a
    shipped module embedding ``"dev/some_file.json"`` or ``"./dev/..."`` to
    open a runtime artifact from the dev tree.
    """
    if not isinstance(value, str):
        return False
    return any(value.startswith(prefix) for prefix in _DEV_PATH_PREFIXES)


def find_dev_path_literal_violations(
    py_files: list[Path],
    *,
    src_root: Path,
    exclude_globs: tuple[str, ...],
) -> list[tuple[str, int, str]]:
    """Return ``(rel_path, lineno, literal_value)`` for every violation.

    Scans every shipped module in ``py_files`` for AST string constants whose
    value starts with a ``dev/`` path prefix (``"dev/"``, ``"./dev/"``,
    ``"../dev/"``).  This is the metadata-loophole check that an import scan
    alone cannot see: a module that reads ``open("dev/baseline.json")`` does
    not import ``dev.*`` but still depends on a dev artifact at runtime.

    Args:
        py_files: Module files to scan.
        src_root: Source root used to resolve shipped status and relative paths.
        exclude_globs: Wheel exclude globs from the packaging config.
    """
    violations: list[tuple[str, int, str]] = []
    for path in py_files:
        if not _is_shipped_module(path, src_root=src_root, exclude_globs=exclude_globs):
            continue
        rel = path.relative_to(src_root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and _looks_like_dev_path(node.value)
            ):
                violations.append((rel, node.lineno, node.value))
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
# Live-tree gate: Check 2 — no shipped module embeds a dev/ path literal
# ---------------------------------------------------------------------------


def test_no_shipped_module_embeds_dev_path_literal() -> None:
    """No shipped module under ``src/cadrumo`` may embed a ``dev/`` path literal.

    This is the metadata-loophole complement to the import check: a shipped
    module can reference dev/ artifacts through ``open("dev/baseline.json")``
    without any ``import dev`` statement.  Both forms make the shipped module
    depend on development infrastructure that is absent from the installed
    wheel — the import check catches the code dependency; this check catches
    the data dependency.

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

    violations = find_dev_path_literal_violations(py_files, src_root=_SRC_ROOT, exclude_globs=globs)

    offenders = [f"{rel}:{lineno} -> {value!r}" for rel, lineno, value in violations]
    assert offenders == [], (
        "shipped module(s) under src/cadrumo embed a dev/ path literal.  Move the "
        "artifact under src/cadrumo/_data/ or equivalent so the shipped side reads "
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
# Anti-tautology: Check 2 — the path literal scanner MUST fire on a planted violation
# ---------------------------------------------------------------------------


def test_path_literal_scanner_catches_planted_dev_path(tmp_path: Path) -> None:
    """A ``"dev/some_file.json"`` string literal in a shipped module MUST be caught.

    Without this proof the hard-zero assertion above is indistinguishable from
    a detector that cannot fire — the failure mode that lets a gate pass while
    blind to the thing it guards.
    """
    body = (
        "from pathlib import Path\n"
        "\n"
        "def load_baseline():\n"
        '    return Path("dev/import_hygiene_baseline.json").read_text()\n'
    )
    _planted_module(tmp_path, "cadrumo/reads_dev_file.py", body)
    empty_globs: tuple[str, ...] = ()

    violations = find_dev_path_literal_violations(
        [tmp_path / "cadrumo" / "reads_dev_file.py"],
        src_root=tmp_path,
        exclude_globs=empty_globs,
    )

    assert len(violations) == 1, f"expected exactly 1 path-literal violation; got {violations!r}"
    rel, _lineno, value = violations[0]
    assert rel == "cadrumo/reads_dev_file.py"
    assert value == "dev/import_hygiene_baseline.json"


def test_path_literal_scanner_catches_relative_prefix_forms(tmp_path: Path) -> None:
    """Both ``"./dev/"`` and ``"../dev/"`` path prefixes MUST be caught."""
    body = (
        "def load_a():\n"
        '    return open("./dev/some_config.json")\n'
        "\n"
        "def load_b():\n"
        '    return open("../dev/other_baseline.json")\n'
    )
    _planted_module(tmp_path, "cadrumo/relative_paths.py", body)
    empty_globs: tuple[str, ...] = ()

    violations = find_dev_path_literal_violations(
        [tmp_path / "cadrumo" / "relative_paths.py"],
        src_root=tmp_path,
        exclude_globs=empty_globs,
    )

    values = {v for _, _, v in violations}
    assert "./dev/some_config.json" in values, f"'./dev/' prefix not caught; violations={violations!r}"
    assert "../dev/other_baseline.json" in values, f"'../dev/' prefix not caught; violations={violations!r}"


def test_path_literal_scanner_does_not_fire_on_path_join_usage(tmp_path: Path) -> None:
    """``Path(root) / 'dev' / 'file'`` is NOT a dev-path literal and must not fire.

    This form uses ``"dev"`` as a bare string segment in a ``pathlib.Path``
    join, not as a ``"dev/"``-prefixed path literal.  The check targets only
    the literal form that names a path into dev/ directly.
    """
    body = (
        "from pathlib import Path\n"
        "\n"
        "PROJECT_ROOT = Path(__file__).resolve().parents[3]\n"
        "\n"
        "def path_join_form():\n"
        '    return PROJECT_ROOT / "dev" / "import_hygiene_baseline.json"\n'
    )
    _planted_module(tmp_path, "cadrumo/path_join.py", body)
    empty_globs: tuple[str, ...] = ()

    violations = find_dev_path_literal_violations(
        [tmp_path / "cadrumo" / "path_join.py"],
        src_root=tmp_path,
        exclude_globs=empty_globs,
    )
    assert violations == [], (
        f"the path literal scanner fired on a Path-join usage of 'dev' (not a path literal violation): {violations!r}"
    )


def test_path_literal_scanner_does_not_fire_on_excluded_test_module(tmp_path: Path) -> None:
    """A ``"dev/"`` literal in an EXCLUDED test module is NOT a violation.

    Test trees run from the repo checkout and may reference dev/ paths.
    """
    body = 'from pathlib import Path\n\nBASELINE = Path("dev/import_hygiene_baseline.json")\n'
    _planted_module(tmp_path, "cadrumo/tests/test_with_dev_path.py", body)
    test_excludes: tuple[str, ...] = (
        "src/cadrumo/tests",
        "src/cadrumo/tests/**",
        "src/cadrumo/**/tests",
        "src/cadrumo/**/tests/**",
    )
    violations = find_dev_path_literal_violations(
        [tmp_path / "cadrumo" / "tests" / "test_with_dev_path.py"],
        src_root=tmp_path,
        exclude_globs=test_excludes,
    )
    assert violations == [], f"the path literal scanner fired on an excluded test module: {violations!r}"
