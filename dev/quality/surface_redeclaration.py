"""Shrink-only gate: entry points must not grow new redeclarations of backend meaning.

The CLI, the Textual workbench, the MCP service and the desktop window render
what the Python backend serves. When a surface hand-copies a wire shape or
decides a state again from served raw fields, two surfaces can show two answers
for one request. This gate counts four kinds of such redeclaration, keyed by
path and symbol, and compares them with a committed baseline:

``wire-type``
    An exported ``type`` or ``interface`` in the desktop window's ``ipc``,
    ``shell`` or ``components`` source that crosses the host IPC boundary: an
    IPC call or event signature, or a port over the host's answers, reaches it
    through type references, however it is renamed, nested or re-exported
    (``window_wire_reach`` says how the signatures are found). A type no IPC
    signature reaches is window state (layout, calendar drawing, docking, hook
    state) and is not counted, nor is a field-less alias of generated contract
    types or a shape only the documentation frame's bridge carries. Generated modules
    (whose header says they are generated and not to be edited), component
    props (names ending ``Props``) and test, story and fixture files are never
    counted.
``tui-date-decision``
    A Textual workbench function that orders dates against each other or
    against the day (``as_of``, ``today``, ``*_on``, ``*_date``, ``*_at`` or a
    call to ``today``/``today_madrid``/``now``).
``tui-precedence``
    A module-level rank, order, precedence or level table whose entries are
    enum members, counted when it decides a state rather than presents one: its
    values are ranks (integers), or it maps enum members to enum members (a
    served state folded into a local one), or a workbench module consumes it in
    a decision: a lookup in it, or a name bound from a lookup, is compared; a
    value is tested for membership in it; or it keys a ``sorted``, ``min``,
    ``max`` or ``sort``. A table that maps states to glyphs, colours or locale
    keys, or that is only looked up or stepped through for display, is
    presentation and is not counted.
``duplicated-helper``
    A module-level entry-point function (CLI, workbench, MCP) whose body and
    signature are structurally identical to a same-named function in another
    entry-point module, or whose multi-word name (``blank_to_none``,
    ``parse_date``, leading underscores dropped) the shared core or application
    layer also defines with a compatible signature: the same kinds and number
    of parameters with the same annotations, and the same return annotation,
    parameter names aside. A same-named function with another signature is a
    homonym (a CLI wrapper that emits an envelope beside the application read
    it calls, a parser beside a formatter) and is not counted. A single-word
    name (``read``, ``emit``) says too little to match a shared owner, so only
    an identical copy counts for it.

The gate prints each check's raw count (every candidate, before the rulings
above set window state, presentation tables and homonyms aside) beside the
counted one.

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
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from dev.first_party_source import MCP_PACKAGE, is_test_source
from dev.paths import REPO_ROOT
from dev.source_tree import repository_files

from .window_wire_reach import is_generated, wire_declarations

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
    MCP_PACKAGE,
)
CANONICAL_ROOTS: Final[tuple[str, ...]] = ("src/cadrumo/core", "src/cadrumo/application")

CHECKS: Final[tuple[str, ...]] = ("wire-type", "tui-date-decision", "tui-precedence", "duplicated-helper")

type Measured = tuple[set[str], set[str]]
"""A check's raw candidate keys and the keys it counts."""

_TYPESCRIPT_SUFFIXES: Final[frozenset[str]] = frozenset({".ts", ".tsx"})
_NON_WIRE_FILE: Final[re.Pattern[str]] = re.compile(r"\.(test|spec|stories)\.tsx?$|/(__tests__|fixtures|dev)/")
_EXPORTED_TYPE: Final[re.Pattern[str]] = re.compile(
    r"^export\s+(?:declare\s+)?(?:type|interface)\s+([A-Z][A-Za-z0-9_]*)", re.MULTILINE
)
_DATE_NAME: Final[re.Pattern[str]] = re.compile(r"^(as_of|today|now|.+_on|.+_date|.+_at|fecha_.+)$")
_DAY_CALLS: Final[frozenset[str]] = frozenset({"today", "today_madrid", "now"})
_TABLE_NAME: Final[re.Pattern[str]] = re.compile(r"(RANK|ORDER|PRECEDENCE|PRIORITY|LEVEL)S?(_|$)")
_ORDERING: Final[tuple[type[ast.cmpop], ...]] = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)
_ENUM_CLASS: Final[re.Pattern[str]] = re.compile(r"^_?[A-Z][A-Za-z0-9]*[a-z][A-Za-z0-9]*$")
_ENUM_MEMBER: Final[re.Pattern[str]] = re.compile(r"^[A-Z][A-Z0-9_]*$")
_LOOKUPS: Final[frozenset[str]] = frozenset({"get", "index"})
_ORDERING_CALLS: Final[frozenset[str]] = frozenset({"sorted", "min", "max"})


def _python_modules(root: Path, bases: Iterable[str]) -> list[str]:
    return [
        relative
        for relative in repository_files(root, under=tuple(bases))
        if relative.endswith(".py") and not is_test_source(relative)
    ]


def _parse(root: Path, relative: str) -> ast.Module | None:
    try:
        return ast.parse((root / relative).read_text(encoding="utf-8"), filename=relative)
    except (SyntaxError, UnicodeDecodeError):
        return None


def _excluded_window_file(relative: str) -> bool:
    return bool(_NON_WIRE_FILE.search(relative))


def _wire_key(site: tuple[str, str]) -> str:
    return f"wire-type:{site[0]}:{site[1]}"


def wire_type_keys(root: Path = REPO_ROOT) -> Measured:
    """Every hand-written exported window type, and those an IPC signature reaches, as ``wire-type:<path>:<name>``."""
    raw: set[tuple[str, str]] = set()
    for relative in repository_files(root, under=WINDOW_ROOTS):
        if PurePosixPath(relative).suffix not in _TYPESCRIPT_SUFFIXES or _excluded_window_file(relative):
            continue
        text = (root / relative).read_text(encoding="utf-8")
        if not is_generated(text):
            raw.update((relative, name) for name in _EXPORTED_TYPE.findall(text) if not name.endswith("Props"))
    crossing = raw & wire_declarations(root, _excluded_window_file)
    return {_wire_key(site) for site in raw}, {_wire_key(site) for site in crossing}


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


def _precedence_tables(module: ast.Module) -> Iterator[tuple[str, ast.expr]]:
    for statement in module.body:
        names, value = _assigned_names(statement)
        if value is not None and _holds_enum_members(value):
            yield from ((name, value) for name in names if _TABLE_NAME.search(name.upper()))


def _table_entries(value: ast.expr) -> ast.expr:
    return _table_entries(value.args[0]) if isinstance(value, ast.Call) and value.args else value


def _is_enum_member(node: ast.expr | None) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and bool(_ENUM_CLASS.match(node.value.id))
        and bool(_ENUM_MEMBER.match(node.attr))
    )


def _is_rank(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and type(node.value) is int


def _ranks_or_reclassifies(value: ast.expr) -> bool:
    """Whether a table's values are ranks, or it maps enum members to enum members."""
    table = _table_entries(value)
    if not isinstance(table, ast.Dict) or not table.values:
        return False
    if all(_is_rank(entry) for entry in table.values):
        return True
    return all(_is_enum_member(entry) for entry in (*table.keys, *table.values))


def _refers(node: ast.AST, name: str) -> bool:
    return (isinstance(node, ast.Name) and node.id == name) or (isinstance(node, ast.Attribute) and node.attr == name)


def _is_lookup(node: ast.AST, name: str) -> bool:
    if isinstance(node, ast.Subscript):
        return _refers(node.value, name)
    func = node.func if isinstance(node, ast.Call) else None
    return isinstance(func, ast.Attribute) and func.attr in _LOOKUPS and _refers(func.value, name)


def _bound_from_lookup(scope: ast.AST, name: str) -> set[str]:
    return {
        target.id
        for node in ast.walk(scope)
        if isinstance(node, ast.Assign) and _is_lookup(node.value, name)
        for target in node.targets
        if isinstance(target, ast.Name)
    }


def _compares_with(node: ast.Compare, name: str, bound: set[str]) -> bool:
    operands = (node.left, *node.comparators)
    if any(
        _is_lookup(operand, name) or (isinstance(operand, ast.Name) and operand.id in bound) for operand in operands
    ):
        return True
    return any(
        isinstance(op, ast.In | ast.NotIn) and _refers(comparator, name)
        for op, comparator in zip(node.ops, node.comparators, strict=True)
    )


def _orders_by(node: ast.Call, name: str) -> bool:
    func = node.func
    ordering = (isinstance(func, ast.Name) and func.id in _ORDERING_CALLS) or (
        isinstance(func, ast.Attribute) and func.attr == "sort"
    )
    return ordering and any(
        keyword.arg == "key" and any(_refers(part, name) for part in ast.walk(keyword.value))
        for keyword in node.keywords
    )


def _decides_in(module: ast.Module, name: str) -> bool:
    """Whether a function in ``module`` compares a lookup in, tests membership in or sorts by the table ``name``."""
    for scope in ast.walk(module):
        if not isinstance(scope, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        bound = _bound_from_lookup(scope, name)
        for node in ast.walk(scope):
            if isinstance(node, ast.Compare) and _compares_with(node, name, bound):
                return True
            if isinstance(node, ast.Call) and _orders_by(node, name):
                return True
    return False


def _reads(module: ast.Module, name: str) -> bool:
    return any(
        (isinstance(node, ast.ImportFrom) and any(alias.name == name for alias in node.names))
        or (isinstance(node, ast.Attribute) and node.attr == name)
        for node in ast.walk(module)
    )


def _decides_a_state(modules: Mapping[str, ast.Module], relative: str, name: str, value: ast.expr) -> bool:
    if _ranks_or_reclassifies(value):
        return True
    consumers = (module for other, module in modules.items() if other == relative or _reads(module, name))
    return any(_decides_in(module, name) for module in consumers)


def _precedence_keys(modules: Mapping[str, ast.Module]) -> Measured:
    raw: set[str] = set()
    counted: set[str] = set()
    for relative, module in modules.items():
        for name, value in _precedence_tables(module):
            key = f"tui-precedence:{relative}:{name}"
            raw.add(key)
            if _decides_a_state(modules, relative, name, value):
                counted.add(key)
    return raw, counted


def tui_state_keys(root: Path = REPO_ROOT) -> tuple[Measured, Measured]:
    """Workbench date decisions and enum precedence tables, keyed by path and symbol, each raw and counted."""
    modules = {
        relative: module
        for relative in _python_modules(root, (TUI_ROOT,))
        if (module := _parse(root, relative)) is not None
    }
    dates = {key for relative, module in modules.items() for key in _date_decision_keys(relative, module)}
    return (dates, set(dates)), _precedence_keys(modules)


def _without_docstring(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    body = function.body
    first = body[0] if body else None
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return body[1:]
    return body


def _shape(function: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    body = ast.Module(body=_without_docstring(function), type_ignores=[])
    return ast.dump(function.args, annotate_fields=False) + ast.dump(body, annotate_fields=False)


def _annotation(node: ast.arg | ast.expr | None) -> str:
    if isinstance(node, ast.arg):
        node = node.annotation
    return "" if node is None else ast.unparse(node)


def _signature(function: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Parameter kinds and annotations and the return annotation, parameter names aside."""
    arguments = function.args
    kinds = (
        ("/", arguments.posonlyargs),
        ("p", arguments.args),
        ("*", [arguments.vararg] if arguments.vararg else []),
        ("k", arguments.kwonlyargs),
        ("**", [arguments.kwarg] if arguments.kwarg else []),
    )
    parameters = ",".join(f"{kind}{_annotation(argument)}" for kind, group in kinds for argument in group)
    return f"{type(function).__name__}({parameters})->{_annotation(function.returns)}"


@dataclass(frozen=True)
class _Definition:
    shape: str
    signature: str


def _module_functions(root: Path, bases: Iterable[str]) -> dict[str, dict[str, _Definition]]:
    """Each module-level function name, leading underscores dropped, to its shape and signature by module."""
    defined: dict[str, dict[str, _Definition]] = defaultdict(dict)
    for relative in _python_modules(root, bases):
        module = _parse(root, relative)
        if module is None:
            continue
        for statement in module.body:
            if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
                defined[statement.name.lstrip("_")][relative] = _Definition(_shape(statement), _signature(statement))
    return defined


def _copies(name: str, definitions: Mapping[str, _Definition]) -> set[str]:
    by_shape: dict[str, list[str]] = defaultdict(list)
    for relative, definition in definitions.items():
        by_shape[definition.shape].append(relative)
    return {
        f"duplicated-helper:{relative}:{name}" for copies in by_shape.values() if len(copies) > 1 for relative in copies
    }


def _beside_owner(name: str, definitions: Mapping[str, _Definition], owners: Iterable[_Definition]) -> Measured:
    """Same-named definitions beside a shared owner, and those that copy it or share its signature."""
    owned = list(owners)
    shapes = {owner.shape for owner in owned}
    signatures = {owner.signature for owner in owned}
    raw: set[str] = {f"duplicated-helper:{relative}:{name}" for relative in definitions} if owned else set()
    counted = {
        f"duplicated-helper:{relative}:{name}"
        for relative, definition in definitions.items()
        if definition.shape in shapes or definition.signature in signatures
    }
    return raw, counted


def duplicated_helper_keys(root: Path = REPO_ROOT) -> Measured:
    """Entry-point helpers copied between entry points, or redefined beside their shared owner, raw and counted."""
    surface = _module_functions(root, ENTRYPOINT_ROOTS)
    canonical = _module_functions(root, CANONICAL_ROOTS)
    raw: set[str] = set()
    counted: set[str] = set()
    for name, definitions in surface.items():
        if not name:
            continue
        copies = _copies(name, definitions)
        owners = canonical.get(name, {}).values() if "_" in name else ()
        named, matching = _beside_owner(name, definitions, owners)
        raw |= copies | named
        counted |= copies | matching
    return raw, counted


def measure(root: Path = REPO_ROOT) -> dict[str, Measured]:
    """Every raw candidate and every counted occurrence under ``root``, by check."""
    dates, precedence = tui_state_keys(root)
    return {
        "wire-type": wire_type_keys(root),
        "tui-date-decision": dates,
        "tui-precedence": precedence,
        "duplicated-helper": duplicated_helper_keys(root),
    }


def current_keys(root: Path = REPO_ROOT) -> dict[str, set[str]]:
    """Every counted occurrence under ``root``, by check."""
    return {check: counted for check, (_, counted) in measure(root).items()}


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


def _counts(found: Mapping[str, set[str]], raw: Mapping[str, set[str]] | None = None) -> str:
    return ", ".join(
        f"{check} {len(found[check])}" + ("" if raw is None else f" (raw {len(raw[check])})") for check in CHECKS
    )


def _shrink_baseline(found: Mapping[str, set[str]], baseline: Mapping[str, set[str]] | None, path: Path) -> int:
    if baseline is not None and (added := compare(found, baseline)[0]):
        print("refused: the baseline only shrinks, and the tree adds:", *added, sep="\n  ", file=sys.stderr)
        return 1
    path.write_text(baseline_text(found), encoding="utf-8", newline="\n")
    print(f"wrote {BASELINE_RELATIVE}: {_counts(found)}")
    return 0


def _gate(found: Mapping[str, set[str]], baseline: Mapping[str, set[str]], raw: Mapping[str, set[str]]) -> int:
    added, gone = compare(found, baseline)
    for key in added:
        print(f"new surface redeclaration: {key}")
    for key in gone:
        print(f"fixed, remove from the baseline: {key}")
    print(f"surface redeclaration: {_counts(found, raw)}")
    return 1 if added or gone else 0


def main(argv: list[str] | None = None, root: Path = REPO_ROOT) -> int:
    """Run the gate, or shrink the baseline with ``--write-baseline``."""
    arguments = sys.argv[1:] if argv is None else argv
    baseline_path = root / BASELINE_RELATIVE
    if not repository_files(root, under=WINDOW_ROOTS) or not _python_modules(root, ENTRYPOINT_ROOTS):
        print(f"found no window or entry-point source under {root}, so nothing was measured", file=sys.stderr)
        return 1
    measured = measure(root)
    raw = {check: candidates for check, (candidates, _) in measured.items()}
    found = {check: counted for check, (_, counted) in measured.items()}
    baseline = read_baseline(baseline_path) if baseline_path.exists() else None
    if "--write-baseline" in arguments:
        return _shrink_baseline(found, baseline, baseline_path)
    if baseline is None:
        print(f"{BASELINE_RELATIVE} is missing", file=sys.stderr)
        return 1
    return _gate(found, baseline, raw)


if __name__ == "__main__":
    sys.exit(main())
