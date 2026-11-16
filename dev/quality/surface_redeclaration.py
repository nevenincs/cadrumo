"""Shrink-only gate: entry points must not grow new redeclarations of backend meaning.

The CLI, the Textual workbench, the MCP service and the desktop window render
what the Python backend serves. When a surface hand-copies a wire shape or
decides a state again from served raw fields, two surfaces can show two answers
for one request. This gate counts three kinds of such redeclaration, keyed by
path and symbol, and compares them with a committed baseline:

``wire-type``
    An exported ``type`` or ``interface`` in the desktop window's ``ipc``,
    ``shell`` or ``components`` source that is not in a generated module (one
    whose header says it is generated and not to be edited). Component props
    (names ending ``Props``) and test, story and fixture files are not wire
    shapes and are not counted.
``tui-date-decision`` and ``tui-precedence``
    A Textual workbench function that orders dates against each other or
    against the day (``as_of``, ``today``, ``*_on``, ``*_date``, ``*_at`` or a
    call to ``today``/``today_madrid``/``now``), and a module-level rank, order,
    precedence or level table whose entries are enum members. Both decide a
    state the backend should serve as a typed field.
``duplicated-helper``
    A module-level entry-point function (CLI, workbench, MCP) whose body and
    signature are structurally identical to a same-named function in another
    entry-point module, or whose multi-word name (``blank_to_none``,
    ``parse_date``, leading underscores dropped) the shared core or application
    layer also defines. A single-word name (``read``, ``emit``) says too little
    to match a shared owner, so only an identical copy counts for it.

How the baseline works
----------------------
A new key fails the gate: serve the value from the backend, or call the
canonical helper, instead. A baseline key the tree no longer holds also fails
the gate, so a fix removes its key in the same change and the baseline stays
an exact, shrinking record. ``--write-baseline`` rewrites the file only when
that removes keys; it refuses to add one.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path, PurePosixPath
from typing import Final

from dev.paths import REPO_ROOT
from dev.source_tree import repository_files

BASELINE_RELATIVE: Final[str] = "dev/quality/metadata/surface_redeclaration_baseline.json"
SCHEMA_VERSION: Final[int] = 1

WINDOW_ROOTS: Final[tuple[str, ...]] = (
    "native/desktop/frontend/src/ipc",
    "native/desktop/frontend/src/shell",
    "native/desktop/frontend/src/components",
)
TUI_ROOT: Final[str] = "src/cadrumo/entrypoints/tui"
ENTRYPOINT_ROOTS: Final[tuple[str, ...]] = (
    "src/cadrumo/entrypoints/tui",
    "src/cadrumo/entrypoints/cli",
    "src/cadrumo_mcp",
)
CANONICAL_ROOTS: Final[tuple[str, ...]] = ("src/cadrumo/core", "src/cadrumo/application")

CHECKS: Final[tuple[str, ...]] = ("wire-type", "tui-date-decision", "tui-precedence", "duplicated-helper")

_TYPESCRIPT_SUFFIXES: Final[frozenset[str]] = frozenset({".ts", ".tsx"})
_NON_WIRE_FILE: Final[re.Pattern[str]] = re.compile(r"\.(test|spec|stories)\.tsx?$|/(__tests__|fixtures|dev)/")
_EXPORTED_TYPE: Final[re.Pattern[str]] = re.compile(
    r"^export\s+(?:declare\s+)?(?:type|interface)\s+([A-Z][A-Za-z0-9_]*)", re.MULTILINE
)
_GENERATED_HEADER_LINES: Final[int] = 6
_DATE_NAME: Final[re.Pattern[str]] = re.compile(r"^(as_of|today|now|.+_on|.+_date|.+_at|fecha_.+)$")
_DAY_CALLS: Final[frozenset[str]] = frozenset({"today", "today_madrid", "now"})
_TABLE_NAME: Final[re.Pattern[str]] = re.compile(r"(RANK|ORDER|PRECEDENCE|PRIORITY|LEVEL)S?(_|$)")
_ORDERING: Final[tuple[type[ast.cmpop], ...]] = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)


def _is_test_python(relative: str) -> bool:
    parts = PurePosixPath(relative).parts
    return "tests" in parts or PurePosixPath(relative).name.startswith("test_")


def _python_modules(root: Path, bases: Iterable[str]) -> list[str]:
    return [
        relative
        for relative in repository_files(root, under=tuple(bases))
        if relative.endswith(".py") and not _is_test_python(relative)
    ]


def _parse(root: Path, relative: str) -> ast.Module | None:
    try:
        return ast.parse((root / relative).read_text(encoding="utf-8"), filename=relative)
    except (SyntaxError, UnicodeDecodeError):
        return None


def _is_generated(text: str) -> bool:
    head = "\n".join(text.splitlines()[:_GENERATED_HEADER_LINES]).lower()
    return "generated" in head and "do not edit" in head


def wire_type_keys(root: Path = REPO_ROOT) -> set[str]:
    """Every hand-written exported window type, as ``wire-type:<path>:<name>``."""
    keys: set[str] = set()
    for relative in repository_files(root, under=WINDOW_ROOTS):
        if PurePosixPath(relative).suffix not in _TYPESCRIPT_SUFFIXES or _NON_WIRE_FILE.search(relative):
            continue
        text = (root / relative).read_text(encoding="utf-8")
        if _is_generated(text):
            continue
        for name in _EXPORTED_TYPE.findall(text):
            if not name.endswith("Props"):
                keys.add(f"wire-type:{relative}:{name}")
    return keys


def _names_a_day(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return bool(_DATE_NAME.match(node.id))
    if isinstance(node, ast.Attribute):
        return bool(_DATE_NAME.match(node.attr))
    if isinstance(node, ast.Call):
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
        return name in _DAY_CALLS
    return False


def _decides_on_dates(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for node in ast.walk(function):
        if not isinstance(node, ast.Compare) or not any(isinstance(op, _ORDERING) for op in node.ops):
            continue
        if any(_names_a_day(operand) for operand in (node.left, *node.comparators)):
            return True
    return False


def _functions(module: ast.Module) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    def walk(body: list[ast.stmt], prefix: str) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
        for statement in body:
            if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
                yield f"{prefix}{statement.name}", statement
            elif isinstance(statement, ast.ClassDef):
                yield from walk(statement.body, f"{prefix}{statement.name}.")

    yield from walk(module.body, "")


def _holds_enum_members(value: ast.expr) -> bool:
    if isinstance(value, ast.Call) and value.args:
        return _holds_enum_members(value.args[0])
    if isinstance(value, ast.Dict):
        entries = [*(key for key in value.keys if key is not None), *value.values]
    elif isinstance(value, ast.Tuple | ast.List | ast.Set):
        entries = list(value.elts)
    else:
        return False
    return any(isinstance(entry, ast.Attribute) for entry in entries)


def _assigned_names(statement: ast.stmt) -> tuple[list[str], ast.expr | None]:
    if isinstance(statement, ast.Assign):
        return [target.id for target in statement.targets if isinstance(target, ast.Name)], statement.value
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        return [statement.target.id], statement.value
    return [], None


def _date_decision_keys(relative: str, module: ast.Module) -> set[str]:
    return {
        f"tui-date-decision:{relative}:{qualname}"
        for qualname, function in _functions(module)
        if _decides_on_dates(function)
    }


def _precedence_table_names(statement: ast.stmt) -> list[str]:
    names, value = _assigned_names(statement)
    if value is None or not _holds_enum_members(value):
        return []
    return [name for name in names if _TABLE_NAME.search(name.upper())]


def _precedence_keys(relative: str, module: ast.Module) -> set[str]:
    return {
        f"tui-precedence:{relative}:{name}" for statement in module.body for name in _precedence_table_names(statement)
    }


def tui_state_keys(root: Path = REPO_ROOT) -> set[str]:
    """Workbench date decisions and enum precedence tables, keyed by path and symbol."""
    keys: set[str] = set()
    for relative in _python_modules(root, (TUI_ROOT,)):
        module = _parse(root, relative)
        if module is not None:
            keys |= _date_decision_keys(relative, module) | _precedence_keys(relative, module)
    return keys


def _without_docstring(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    body = function.body
    first = body[0] if body else None
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return body[1:]
    return body


def _shape(function: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    body = ast.Module(body=_without_docstring(function), type_ignores=[])
    return ast.dump(function.args, annotate_fields=False) + ast.dump(body, annotate_fields=False)


def _module_functions(root: Path, bases: Iterable[str]) -> dict[str, dict[str, str]]:
    """Each module-level function name, leading underscores dropped, to its shape by module."""
    defined: dict[str, dict[str, str]] = defaultdict(dict)
    for relative in _python_modules(root, bases):
        module = _parse(root, relative)
        if module is None:
            continue
        for statement in module.body:
            if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
                defined[statement.name.lstrip("_")][relative] = _shape(statement)
    return defined


def duplicated_helper_keys(root: Path = REPO_ROOT) -> set[str]:
    """Entry-point helpers copied between entry points, or redefined beside their shared owner."""
    surface = _module_functions(root, ENTRYPOINT_ROOTS)
    canonical = _module_functions(root, CANONICAL_ROOTS)
    keys: set[str] = set()
    for name, shapes in surface.items():
        if not name:
            continue
        if "_" in name and name in canonical:
            keys.update(f"duplicated-helper:{relative}:{name}" for relative in shapes)
            continue
        by_shape: dict[str, list[str]] = defaultdict(list)
        for relative, shape in shapes.items():
            by_shape[shape].append(relative)
        for copies in by_shape.values():
            if len(copies) > 1:
                keys.update(f"duplicated-helper:{relative}:{name}" for relative in copies)
    return keys


def current_keys(root: Path = REPO_ROOT) -> dict[str, set[str]]:
    """Every counted occurrence under ``root``, by check."""
    found: dict[str, set[str]] = {check: set() for check in CHECKS}
    for key in (*wire_type_keys(root), *tui_state_keys(root), *duplicated_helper_keys(root)):
        found[key.split(":", 1)[0]].add(key)
    return found


def read_baseline(path: Path) -> dict[str, set[str]]:
    """The committed baseline, refused when it is not this schema."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{path} is not a schema {SCHEMA_VERSION} surface redeclaration baseline")
    occurrences = document.get("occurrences")
    if not isinstance(occurrences, dict) or set(occurrences) != set(CHECKS):
        raise ValueError(f"{path} must list exactly the checks {', '.join(CHECKS)}")
    return {check: {str(key) for key in occurrences[check]} for check in CHECKS}


def baseline_text(found: Mapping[str, set[str]]) -> str:
    """The baseline document for ``found``, in its committed sorted form."""
    document = {
        "schema_version": SCHEMA_VERSION,
        "counts": {check: len(found[check]) for check in CHECKS},
        "occurrences": {check: sorted(found[check]) for check in CHECKS},
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def compare(found: Mapping[str, set[str]], baseline: Mapping[str, set[str]]) -> tuple[list[str], list[str]]:
    """The keys the tree added and the baseline keys the tree no longer holds."""
    added = sorted(key for check in CHECKS for key in found[check] - baseline[check])
    gone = sorted(key for check in CHECKS for key in baseline[check] - found[check])
    return added, gone


def _counts(found: Mapping[str, set[str]]) -> str:
    return ", ".join(f"{check} {len(found[check])}" for check in CHECKS)


def _shrink_baseline(found: Mapping[str, set[str]], baseline: Mapping[str, set[str]] | None, path: Path) -> int:
    if baseline is not None and (added := compare(found, baseline)[0]):
        print("refused: the baseline only shrinks, and the tree adds:", *added, sep="\n  ", file=sys.stderr)
        return 1
    path.write_text(baseline_text(found), encoding="utf-8", newline="\n")
    print(f"wrote {BASELINE_RELATIVE}: {_counts(found)}")
    return 0


def _gate(found: Mapping[str, set[str]], baseline: Mapping[str, set[str]]) -> int:
    added, gone = compare(found, baseline)
    for key in added:
        print(f"new surface redeclaration: {key}")
    for key in gone:
        print(f"fixed, remove from the baseline: {key}")
    print(f"surface redeclaration: {_counts(found)}")
    return 1 if added or gone else 0


def main(argv: list[str] | None = None, root: Path = REPO_ROOT) -> int:
    """Run the gate, or shrink the baseline with ``--write-baseline``."""
    arguments = sys.argv[1:] if argv is None else argv
    baseline_path = root / BASELINE_RELATIVE
    if not repository_files(root, under=WINDOW_ROOTS) or not _python_modules(root, ENTRYPOINT_ROOTS):
        print(f"found no window or entry-point source under {root}, so nothing was measured", file=sys.stderr)
        return 1
    found = current_keys(root)
    baseline = read_baseline(baseline_path) if baseline_path.exists() else None
    if "--write-baseline" in arguments:
        return _shrink_baseline(found, baseline, baseline_path)
    if baseline is None:
        print(f"{BASELINE_RELATIVE} is missing", file=sys.stderr)
        return 1
    return _gate(found, baseline)


if __name__ == "__main__":
    sys.exit(main())
