"""Cadrumo writes must stay under configured storage or controlled temp roots.

This AST gate follows home/platform/temp path origins into filesystem writes,
and separately discovers tempfile constructors whose default is the host temp
directory. It scans production, development, packaging, and test Python from
the working tree, including untracked source files.

Unscoped tempfile constructors are accepted only in tests after the root
pytest bootstrap. Developer and product code supply an explicit ``dir=``.
No source subtree is blanket-exempt. This is a bounded syntactic guard for
listed Python sinks and direct/local path origins; it does not model arbitrary
interprocedural returns, dynamic imports, native writers, or child processes.
Repo-relative paths that escape through cross-module root calculations need
direct tests.
"""

from __future__ import annotations

import ast
import re
from functools import cache
from pathlib import Path
from typing import Final

import pytest

from dev._paths import REPO_ROOT, UTF_8
from dev.source_tree import repository_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TEMP_APIS: Final[frozenset[str]] = frozenset(
    {"mkdtemp", "mkstemp", "TemporaryDirectory", "TemporaryFile", "NamedTemporaryFile"}
)
_TEMP_READS: Final[frozenset[str]] = frozenset({"gettempdir", "gettempdirb"})
_HOME_ENV: Final[frozenset[str]] = frozenset({"HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH"})
_PLATFORM_ENV: Final[frozenset[str]] = frozenset(
    {"LOCALAPPDATA", "APPDATA", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "XDG_CONFIG_HOME"}
)
_TEMP_ENV: Final[frozenset[str]] = frozenset({"TEMP", "TMP", "TMPDIR"})
_BAD_ORIGINS: Final[frozenset[str]] = frozenset(
    {"home", "platform-data", "ambient-temp", "hardcoded-external", "uncontrolled-environment"}
)
_INTERNAL_PATH_TRANSPORTS: Final[dict[str, frozenset[str]]] = {
    # RunLog emits these after allocating each run beneath configured roots.
    # Probe destinations are subprocess handoffs set by parent tests under
    # pytest's already controlled tmp_path.
    "dev/test_runs/logging.py": frozenset({"CADRUMO_TEST_RUN_ROOT", "CADRUMO_TEST_RUN_SCRATCH"}),
    "dev/test_runs/tests/path_probe.py": frozenset(
        {"CADRUMO_PYTEST_PATH_PROBE", "CADRUMO_TEST_RUN_ROOT", "CADRUMO_TEST_RUN_SCRATCH"}
    ),
    "dev/test_runs/tests/worker_basetemp_probe.py": frozenset({"CADRUMO_WORKER_BASETEMP_PROBE"}),
}
_TEMP_DIR_POSITION: Final[dict[str, int]] = {
    "mkdtemp": 2,
    "mkstemp": 2,
    "TemporaryDirectory": 2,
    "TemporaryFile": 6,
    "NamedTemporaryFile": 6,
}


def _attribute_path(node: ast.expr) -> tuple[str, ...]:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return tuple(reversed(parts))


def _imports(tree: ast.Module) -> tuple[dict[str, str], dict[str, str]]:
    modules: dict[str, str] = {}
    symbols: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                modules[local] = alias.name if alias.asname else alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                symbols[alias.asname or alias.name] = f"{node.module or ''}.{alias.name}"
    return modules, symbols


def _call_path(call: ast.Call, modules: dict[str, str], symbols: dict[str, str]) -> tuple[str, ...]:
    path = _attribute_path(call.func)
    if not path:
        return ()
    if path[0] in symbols:
        return tuple(symbols[path[0]].split(".")) + path[1:]
    if path[0] in modules:
        return tuple(modules[path[0]].split(".")) + path[1:]
    return path


def _string_constants(tree: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    for statement in tree.body:
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = statement.value
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = value.value
    return constants


def _literal(node: ast.expr | None, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


@cache
def _documented_storage_overrides() -> frozenset[str]:
    """Read the exact path override names from the shipped environment example."""
    try:
        lines = (REPO_ROOT / "env" / ".env.example").read_text(encoding=UTF_8).splitlines()
    except (OSError, UnicodeDecodeError):
        return frozenset()
    return frozenset(
        name
        for line in lines
        if (name := line.partition("=")[0].strip()).startswith("CADRUMO_")
        and name.endswith(("_ROOT", "_DIR", "_PATH", "_BASE"))
    )


def _environment_key(
    node: ast.AST,
    constants: dict[str, str],
    modules: dict[str, str],
    symbols: dict[str, str],
) -> str | None:
    if isinstance(node, ast.Subscript):
        if not isinstance(node.ctx, ast.Load):
            return None
        value = node.value
        if (
            isinstance(value, ast.Attribute)
            and value.attr == "environ"
            and isinstance(value.value, ast.Name)
            and modules.get(value.value.id, value.value.id) == "os"
        ):
            return _literal(node.slice, constants)
        if isinstance(value, ast.Name) and symbols.get(value.id) == "os.environ":
            return _literal(node.slice, constants)
    if isinstance(node, ast.Call):
        path = _call_path(node, modules, symbols)
        if path[-1:] == ("getenv",) and path[:1] == ("os",):
            return _literal(node.args[0], constants) if node.args else None
        if path[-1:] == ("getenv",) and symbols.get(path[0], "").startswith("os.getenv"):
            return _literal(node.args[0], constants) if node.args else None
        if path[-1:] == ("get",) and isinstance(node.func, ast.Attribute):
            receiver = node.func.value
            if isinstance(receiver, ast.Attribute) and receiver.attr == "environ":
                owner = receiver.value
                if isinstance(owner, ast.Name) and modules.get(owner.id, owner.id) == "os":
                    return _literal(node.args[0], constants) if node.args else None
            if isinstance(receiver, ast.Name) and symbols.get(receiver.id) == "os.environ":
                return _literal(node.args[0], constants) if node.args else None
    return None


def _environment_origin(
    name: str | None, *, temp_controlled: bool, controlled_transports: frozenset[str]
) -> str | None:
    if name is None:
        return None
    if name in controlled_transports:
        return None
    if name in _HOME_ENV:
        return "home"
    if name in _PLATFORM_ENV:
        return "platform-data"
    if name in _TEMP_ENV and not temp_controlled:
        return "ambient-temp"
    # Accept only storage override names that the operator can discover in the
    # shipped template; arbitrary environment paths are not a storage contract.
    if name in _documented_storage_overrides():
        return None
    return "uncontrolled-environment"


def _literal_external_origin(value: str) -> str | None:
    """Recognize hard-coded absolute paths, which cannot follow storage config."""
    normalized = value.replace("\\", "/").strip().lower()
    if normalized in {"/dev/null", "/dev/tty", "nul", "conout$"}:
        return None
    if normalized.startswith("/") or re.match(r"^[a-z]:/", normalized):
        return "hardcoded-external"
    return None


def _path_literal_contexts(node: ast.AST, modules: dict[str, str], symbols: dict[str, str]) -> set[ast.AST]:
    """Return literals used as path roots, excluding ordinary string arguments."""
    parents = {child: parent for parent in ast.walk(node) for child in ast.iter_child_nodes(parent)}
    path_builders = {"Path", "PurePath", "PosixPath", "WindowsPath", "joinpath", "abspath", "expanduser"}
    contexts: set[ast.AST] = {node}
    for item in ast.walk(node):
        parent = parents.get(item)
        if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Div):
            contexts.add(item)
        elif isinstance(parent, ast.Call) and item in parent.args:
            path = _call_path(parent, modules, symbols)
            if path[-1:] and (path[-1] in path_builders or path[-3:] == ("os", "path", "join")):
                contexts.add(item)
    return contexts


def _module_aliases(tree: ast.Module) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    modules, symbols = _imports(tree)
    return modules, symbols, _string_constants(tree)


def _path_origin(
    node: ast.AST,
    *,
    names: dict[str, frozenset[str]],
    modules: dict[str, str],
    symbols: dict[str, str],
    constants: dict[str, str],
    temp_controlled: bool,
    controlled_transports: frozenset[str],
) -> set[str]:
    found: set[str] = set()
    path_components = {
        part
        for attribute in ast.walk(node)
        if isinstance(attribute, ast.Attribute) and attribute.attr == "name"
        for part in ast.walk(attribute.value)
    }
    path_literals = _path_literal_contexts(node, modules, symbols)
    for item in ast.walk(node):
        if item in path_components:
            continue
        if isinstance(item, ast.Name) and item.id in names:
            found.update(names[item.id])
        elif isinstance(item, ast.Name) and item in path_literals:
            origin = _literal_external_origin(constants.get(item.id, ""))
            if origin is not None:
                found.add(origin)
        elif isinstance(item, ast.Constant) and isinstance(item.value, str) and item in path_literals:
            origin = _literal_external_origin(item.value)
            if origin is not None:
                found.add(origin)
        key = _environment_key(item, constants, modules, symbols)
        origin = _environment_origin(key, temp_controlled=temp_controlled, controlled_transports=controlled_transports)
        if origin is not None:
            found.add(origin)
        if isinstance(item, ast.Call):
            path = _call_path(item, modules, symbols)
            if path[-2:] == ("Path", "home") or (
                path[-1:] == ("expanduser",)
                and isinstance(item.func, ast.Attribute)
                and any(
                    isinstance(part, ast.Constant) and isinstance(part.value, str) and part.value.startswith("~")
                    for part in ast.walk(item.func.value)
                )
            ):
                found.add("home")
            elif path[-3:] == ("os", "path", "expanduser"):
                subject = item.args[0] if item.args else None
                if subject is None or not any(
                    _environment_origin(
                        _environment_key(part, constants, modules, symbols),
                        temp_controlled=temp_controlled,
                        controlled_transports=controlled_transports,
                    )
                    is None
                    and _environment_key(part, constants, modules, symbols) is not None
                    and _environment_key(part, constants, modules, symbols).startswith("CADRUMO_")
                    for part in ast.walk(subject)
                ):
                    found.add("home")
            elif (
                path[-1:]
                and path[-1] in _TEMP_APIS
                and ("tempfile" in path or symbols.get(path[-1], "").startswith("tempfile."))
            ):
                directory = next((kw.value for kw in item.keywords if kw.arg == "dir"), None)
                if directory is None and len(item.args) > _TEMP_DIR_POSITION[path[-1]]:
                    directory = item.args[_TEMP_DIR_POSITION[path[-1]]]
                no_directory = directory is None or (isinstance(directory, ast.Constant) and directory.value is None)
                if no_directory and not temp_controlled:
                    found.add("ambient-temp")
            elif path[-1:] in {("gettempdir",), ("gettempdirb",)} and "tempfile" in path and not temp_controlled:
                found.add("ambient-temp")
        elif isinstance(item, ast.Attribute) and item.attr == "tempdir":
            path = _attribute_path(item)
            if (
                path
                and modules.get(path[0], path[0]) == "tempfile"
                and path[-1:] == ("tempdir",)
                and not temp_controlled
            ):
                found.add("ambient-temp")
    return found


def _assigned_names(target: ast.expr) -> tuple[str, ...]:
    if isinstance(target, ast.Name):
        return (target.id,)
    if isinstance(target, (ast.Tuple, ast.List)):
        return tuple(name for part in target.elts for name in _assigned_names(part))
    return ()


def _write_targets(
    call: ast.Call, modules: dict[str, str], symbols: dict[str, str], constants: dict[str, str]
) -> tuple[ast.AST, ...]:
    path = _call_path(call, modules, symbols)
    name = path[-1] if path else ""
    owner = path[-2] if len(path) > 1 else ""
    if name in _TEMP_APIS and ("tempfile" in path or symbols.get(name, "").startswith("tempfile.")):
        directory = next((kw.value for kw in call.keywords if kw.arg == "dir"), None)
        if directory is None and len(call.args) > _TEMP_DIR_POSITION[name]:
            directory = call.args[_TEMP_DIR_POSITION[name]]
        return (
            (call,)
            if directory is None or (isinstance(directory, ast.Constant) and directory.value is None)
            else (directory,)
        )
    if name in {"write_text", "write_bytes", "mkdir", "makedirs", "touch", "unlink", "remove", "rmdir"} and isinstance(
        call.func, ast.Attribute
    ):
        return (call.func.value,)
    if name == "open" and isinstance(call.func, ast.Attribute):
        mode = call.args[0] if call.args else next((kw.value for kw in call.keywords if kw.arg == "mode"), None)
        if _write_mode(mode, constants):
            return (call.func.value,)
    if name in {"open", "fdopen"} and owner in {"", "io"}:
        mode = (
            call.args[1] if len(call.args) > 1 else next((kw.value for kw in call.keywords if kw.arg == "mode"), None)
        )
        if call.args and _write_mode(mode, constants):
            return (call.args[0],)
    if owner == "os" and name in {"mkdir", "makedirs", "unlink", "remove", "rmdir"}:
        return tuple(call.args[:1])
    if owner == "os" and name in {"replace", "rename"}:
        return tuple(call.args[:2])
    if owner == "shutil" and name in {"copy", "copy2", "copyfile", "copytree", "move"}:
        return (call.args[1],) if len(call.args) > 1 else ()
    if (
        owner in {"sqlite3", "apsw"}
        and name == "connect"
        and call.args
        and not (isinstance(call.args[0], ast.Constant) and call.args[0].value == ":memory:")
    ):
        return (call.args[0],)
    if name in {"FileHandler", "RotatingFileHandler", "TimedRotatingFileHandler", "WatchedFileHandler"}:
        return (call.args[0],) if call.args else tuple(kw.value for kw in call.keywords if kw.arg == "filename")
    if owner == "zipfile" and name == "ZipFile":
        mode = (
            call.args[1] if len(call.args) > 1 else next((kw.value for kw in call.keywords if kw.arg == "mode"), None)
        )
        if _write_mode(mode, constants) and call.args:
            return (call.args[0],)
    if owner == "tarfile" and name == "open":
        mode = (
            call.args[1] if len(call.args) > 1 else next((kw.value for kw in call.keywords if kw.arg == "mode"), None)
        )
        if _write_mode(mode, constants) and call.args:
            return (call.args[0],)
    return ()


def _write_mode(node: ast.AST | None, constants: dict[str, str]) -> bool:
    mode = _literal(node, constants)
    return mode is not None and any(flag in mode for flag in ("w", "a", "x", "+"))


def _parse(source: str) -> ast.Module:
    return ast.parse(source)


def _local_tainted_names(
    statements: tuple[ast.stmt, ...],
    *,
    initial: dict[str, frozenset[str]],
    modules: dict[str, str],
    symbols: dict[str, str],
    constants: dict[str, str],
    temp_controlled: bool,
    controlled_transports: frozenset[str],
) -> dict[str, frozenset[str]]:
    tainted = dict(initial)
    # A few passes cover ordinary path aliases without trying to infer arbitrary
    # Python control flow or inter-module data flow.
    for _ in range(3):
        changed = False
        for statement in statements:
            for node in ast.walk(statement):
                if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
                    continue
                origins = (
                    _path_origin(
                        node.value,
                        names=tainted,
                        modules=modules,
                        symbols=symbols,
                        constants=constants,
                        temp_controlled=temp_controlled,
                        controlled_transports=controlled_transports,
                    )
                    & _BAD_ORIGINS
                )
                if origins:
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        for name in _assigned_names(target):
                            previous = tainted.get(name, frozenset())
                            expanded = previous | frozenset(origins)
                            if expanded != previous:
                                tainted[name] = expanded
                                changed = True
        if not changed:
            break
    return tainted


def _owned_statements(statements: list[ast.stmt]) -> tuple[ast.stmt, ...]:
    """Keep nested scopes separate so a local name cannot taint another function."""
    return tuple(
        statement
        for statement in statements
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )


def _scan_scope(
    relative: str,
    statements: tuple[ast.stmt, ...],
    *,
    initial: dict[str, frozenset[str]],
    modules: dict[str, str],
    symbols: dict[str, str],
    constants: dict[str, str],
    temp_controlled: bool,
    controlled_transports: frozenset[str],
) -> tuple[tuple[str, ...], dict[str, frozenset[str]]]:
    names = _local_tainted_names(
        statements,
        initial=initial,
        modules=modules,
        symbols=symbols,
        constants=constants,
        temp_controlled=temp_controlled,
        controlled_transports=controlled_transports,
    )
    findings: set[str] = set()
    for statement in statements:
        for call in (node for node in ast.walk(statement) if isinstance(node, ast.Call)):
            for target in _write_targets(call, modules, symbols, constants):
                origins = (
                    _path_origin(
                        target,
                        names=names,
                        modules=modules,
                        symbols=symbols,
                        constants=constants,
                        temp_controlled=temp_controlled,
                        controlled_transports=controlled_transports,
                    )
                    & _BAD_ORIGINS
                )
                if origins:
                    findings.add(f"{relative}:{call.lineno} ({', '.join(sorted(origins))})")
    return tuple(sorted(findings)), names


def _scan_source(relative: str, source: str, *, temp_controlled: bool) -> tuple[str, ...]:
    tree = _parse(source)
    modules, symbols, constants = _module_aliases(tree)
    module_statements = _owned_statements(tree.body)
    controlled_transports = _INTERNAL_PATH_TRANSPORTS.get(relative, frozenset())
    findings, module_names = _scan_scope(
        relative,
        module_statements,
        initial={},
        modules=modules,
        symbols=symbols,
        constants=constants,
        temp_controlled=temp_controlled,
        controlled_transports=controlled_transports,
    )
    all_findings = set(findings)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_findings, _ = _scan_scope(
                relative,
                _owned_statements(node.body),
                initial=module_names,
                modules=modules,
                symbols=symbols,
                constants=constants,
                temp_controlled=temp_controlled,
                controlled_transports=controlled_transports,
            )
            all_findings.update(class_findings)
            continue
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        statements = _owned_statements(node.body)
        locally_assigned = {
            name
            for statement in statements
            for child in ast.walk(statement)
            if isinstance(child, (ast.Assign, ast.AnnAssign))
            for target in (child.targets if isinstance(child, ast.Assign) else [child.target])
            for name in _assigned_names(target)
        }
        globals_visible = {name: origin for name, origin in module_names.items() if name not in locally_assigned}
        scope_findings, _ = _scan_scope(
            relative,
            statements,
            initial=globals_visible,
            modules=modules,
            symbols=symbols,
            constants=constants,
            temp_controlled=temp_controlled,
            controlled_transports=controlled_transports,
        )
        all_findings.update(scope_findings)
    return tuple(sorted(all_findings))


def _first_temp_use(tree: ast.Module) -> int | None:
    modules, symbols = _imports(tree)
    constants = _string_constants(tree)
    calls = [
        node.lineno
        for statement in tree.body
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
        for node in ast.walk(statement)
        if isinstance(node, ast.Call)
        and (_call_path(node, modules, symbols)[-1:] or (None,))[0] in _TEMP_APIS | _TEMP_READS
    ]
    loads = [
        node.lineno
        for statement in tree.body
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
        for node in ast.walk(statement)
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "tempdir"
            and isinstance(node.ctx, ast.Load)
            and modules.get(_attribute_path(node)[0], _attribute_path(node)[0]) == "tempfile"
        )
        or _environment_key(node, constants, modules, symbols) in _TEMP_ENV
    ]
    uses = (*calls, *loads)
    return min(uses) if uses else None


def _assigned_names_for_statement(statement: ast.stmt) -> tuple[str, ...]:
    if isinstance(statement, ast.Assign):
        return tuple(name for target in statement.targets for name in _assigned_names(target))
    if isinstance(statement, ast.AnnAssign):
        return _assigned_names(statement.target)
    return ()


def _storage_pinner_is_rooted(tree: ast.Module, modules: dict[str, str], symbols: dict[str, str]) -> bool:
    base_is_canonical = any(
        isinstance(statement, (ast.Assign, ast.AnnAssign))
        and "_BASE_STORAGE_ROOT" in _assigned_names_for_statement(statement)
        and isinstance(statement.value, ast.Call)
        and _call_path(statement.value, modules, symbols)[-1:] == ("configured_storage_root",)
        for statement in tree.body
    )
    pinner = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_pin_storage_override"),
        None,
    )
    if not base_is_canonical or pinner is None:
        return False
    rooted_values = {
        name
        for statement in pinner.body
        if isinstance(statement, (ast.Assign, ast.AnnAssign))
        and isinstance(statement.value, ast.Call)
        and _call_path(statement.value, modules, symbols)[-1:] == ("storage_directory",)
        and any(
            keyword.arg == "root" and isinstance(keyword.value, ast.Name) and keyword.value.id == "_BASE_STORAGE_ROOT"
            for keyword in statement.value.keywords
        )
        for name in _assigned_names_for_statement(statement)
    }
    return any(
        isinstance(statement, ast.Return)
        and isinstance(statement.value, ast.Name)
        and statement.value.id in rooted_values
        for statement in pinner.body
    )


def _pytest_temp_bootstrap(root: Path) -> bool:
    """Prove conftest pins OS and stdlib temp before its first temp lookup."""
    try:
        tree = _parse((root / "conftest.py").read_text(encoding=UTF_8))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return False
    modules, symbols = _imports(tree)
    constants = _string_constants(tree)
    pinner_is_rooted = _storage_pinner_is_rooted(tree, modules, symbols)
    roots: set[str] = set()
    root_lines: list[int] = []
    configured_env: set[str] = set()
    configured_lines: list[int] = []
    tempfile_is_configured = False

    def uses_temp_root(value: ast.AST) -> bool:
        return any(isinstance(part, ast.Name) and part.id in roots for part in ast.walk(value))

    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            value = statement.value
            targets = statement.targets
        elif isinstance(statement, ast.AnnAssign):
            value = statement.value
            targets = [statement.target]
        elif isinstance(statement, ast.Expr):
            value = statement.value
            targets = []
        else:
            continue
        if value is None:
            continue
        if isinstance(value, ast.Call):
            call = _call_path(value, modules, symbols)
            if call[-1:] in {("_pin_storage_override",), ("storage_directory",)} and value.args:
                if _literal(value.args[0], constants) == "CADRUMO_TEMP_DIR" and (
                    call[-1:] != ("_pin_storage_override",) or pinner_is_rooted
                ):
                    roots.update(name for target in targets for name in _assigned_names(target))
                    root_lines.append(statement.lineno)
            elif call[-1:] == ("prepare_temporary_directory",):
                roots.update(name for target in targets for name in _assigned_names(target))
                root_lines.append(statement.lineno)

            if call[-1:] == ("update",) and isinstance(value.func, ast.Attribute) and value.args:
                receiver = value.func.value
                is_environ = (
                    isinstance(receiver, ast.Attribute)
                    and receiver.attr == "environ"
                    and isinstance(receiver.value, ast.Name)
                    and modules.get(receiver.value.id, receiver.value.id) == "os"
                )
                mapping = value.args[0]
                if is_environ and isinstance(mapping, ast.Dict):
                    for key, item_value in zip(mapping.keys, mapping.values, strict=False):
                        name = _literal(key, constants)
                        if name in _TEMP_ENV and uses_temp_root(item_value):
                            configured_env.add(name)
                            configured_lines.append(statement.lineno)

        for target in targets:
            target_path = _attribute_path(target) if isinstance(target, ast.expr) else ()
            if (
                target_path
                and modules.get(target_path[0], target_path[0]) == "tempfile"
                and target_path[-1:] == ("tempdir",)
                and uses_temp_root(value)
            ):
                tempfile_is_configured = True
                configured_lines.append(statement.lineno)

    first_temp_use = _first_temp_use(tree)
    last_binding = max((*root_lines, *configured_lines), default=0)
    return (
        bool(roots)
        and _TEMP_ENV.issubset(configured_env)
        and tempfile_is_configured
        and first_temp_use is not None
        and last_binding < first_temp_use
    )


def _controlled_temp_bootstrap(relative: str, pytest_bootstrap: bool) -> bool:
    if relative == "conftest.py":
        return pytest_bootstrap
    if "tests" in relative.split("/") or relative.split("/")[-1].startswith("test_"):
        return pytest_bootstrap
    return False


@cache
def _python_sources() -> tuple[str, ...]:
    return tuple(path for path in repository_files() if path.endswith(".py"))


@cache
def _live_scan() -> tuple[tuple[str, ...], int, tuple[str, ...]]:
    findings: list[str] = []
    unreadable: list[str] = []
    examined = 0
    pytest_bootstrap = _pytest_temp_bootstrap(REPO_ROOT)
    for relative in _python_sources():
        try:
            source = (REPO_ROOT / relative).read_text(encoding=UTF_8)
            findings.extend(
                _scan_source(
                    relative,
                    source,
                    temp_controlled=_controlled_temp_bootstrap(relative, pytest_bootstrap),
                )
            )
        except (OSError, UnicodeDecodeError, SyntaxError) as refusal:
            unreadable.append(f"{relative} ({type(refusal).__name__})")
            continue
        examined += 1
    return tuple(sorted(set(findings))), examined, tuple(unreadable)


def test_every_first_party_python_source_is_readable() -> None:
    """A source the gate could not parse must not silently shrink the scan."""
    _, examined, unreadable = _live_scan()

    assert examined > 100, "no first-party Python source was discovered; this gate is asserting nothing"
    assert unreadable == (), "these sources were not checked:\n  " + "\n  ".join(unreadable)


def test_no_filesystem_write_uses_an_uncontrolled_external_root() -> None:
    """Home/platform roots and ambient temp must not reach a filesystem mutation."""
    findings, examined, unreadable = _live_scan()

    assert examined > 100 and not unreadable, "the source scan was incomplete"
    assert findings == (), (
        "route writes through CADRUMO_STORAGE_ROOT / a refined storage variable, "
        "or initialize CADRUMO_TEMP_DIR before using process temp:\n  " + "\n  ".join(findings)
    )


def _fixture_scan(
    tmp_path: Path, source: str, *, relative: str = "fixture.py", temp_controlled: bool = False
) -> tuple[str, ...]:
    (tmp_path / "fixture.py").write_text(source, encoding=UTF_8)
    return _scan_source(relative, source, temp_controlled=temp_controlled)


def test_a_platform_storage_path_is_reported(tmp_path: Path) -> None:
    """Renaming the folder beneath LOCALAPPDATA does not control its location."""
    findings = _fixture_scan(
        tmp_path,
        "import os\nfrom pathlib import Path\n"
        "target = Path(os.environ['LOCALAPPDATA']) / 'cadrumo' / 'data'\n"
        "target.mkdir(parents=True, exist_ok=True)\n",
    )

    assert findings == ("fixture.py:4 (platform-data)",)


def test_an_undocumented_environment_path_is_not_a_storage_override(tmp_path: Path) -> None:
    """Only path controls published in env/.env.example count as configured."""
    findings = _fixture_scan(
        tmp_path,
        "import os\nfrom pathlib import Path\n"
        "target = Path(os.environ['CADRUMO_UNDOCUMENTED_ROOT']) / 'data'\n"
        "target.mkdir(parents=True, exist_ok=True)\n",
    )

    assert findings == ("fixture.py:4 (uncontrolled-environment)",)


def test_a_home_path_is_reported_through_a_local_alias(tmp_path: Path) -> None:
    """The path origin survives the ordinary local variable used by a writer."""
    findings = _fixture_scan(
        tmp_path,
        "from pathlib import Path\n"
        "storage = Path.home() / 'renamed-cadrumo'\n"
        "(storage / 'storage').mkdir(parents=True)\n",
    )

    assert findings == ("fixture.py:3 (home)",)


def test_an_unqualified_temp_constructor_is_reported(tmp_path: Path) -> None:
    """The stdlib default follows the host, not the configured Cadrumo root."""
    findings = _fixture_scan(
        tmp_path,
        "import tempfile\nwith tempfile.TemporaryDirectory(prefix='cadrumo-'):\n    pass\n",
    )

    assert findings == ("fixture.py:2 (ambient-temp)",)


def test_an_explicit_none_temp_directory_is_still_unqualified(tmp_path: Path) -> None:
    """Spelling ``dir=None`` does not bind stdlib temp to Cadrumo storage."""
    findings = _fixture_scan(
        tmp_path,
        "import tempfile\nwith tempfile.TemporaryDirectory(dir=None):\n    pass\n",
    )

    assert findings == ("fixture.py:2 (ambient-temp)",)


def test_an_explicit_hard_coded_temp_directory_is_reported(tmp_path: Path) -> None:
    """An explicit ``dir`` is only controlled when it follows Cadrumo config."""
    findings = _fixture_scan(
        tmp_path,
        "import tempfile\nwith tempfile.TemporaryDirectory(dir='/tmp/cadrumo'):\n    pass\n",
    )

    assert findings == ("fixture.py:2 (hardcoded-external)",)


def test_documented_storage_roots_include_canonical_and_refined_temp_controls() -> None:
    """The gate follows the operator-facing names rather than suffix guesses."""
    assert {
        "CADRUMO_STORAGE_ROOT",
        "CADRUMO_LOCAL_STORAGE_ROOT",
        "CADRUMO_TEMP_DIR",
        "CADRUMO_SCRATCH_BASE",
    }.issubset(_documented_storage_overrides())


@pytest.mark.parametrize(
    ("relative", "variable"),
    (
        ("dev/test_runs/logging.py", "CADRUMO_TEST_RUN_ROOT"),
        ("dev/test_runs/tests/path_probe.py", "CADRUMO_PYTEST_PATH_PROBE"),
        ("dev/test_runs/tests/worker_basetemp_probe.py", "CADRUMO_WORKER_BASETEMP_PROBE"),
    ),
)
def test_only_named_test_run_transport_sources_can_write_to_handoff_paths(
    tmp_path: Path, relative: str, variable: str
) -> None:
    """Internal subprocess path handoffs are scoped to their rooted producers."""
    source = f"import os\nfrom pathlib import Path\nPath(os.environ[{variable!r}]).write_text('probe')\n"
    assert _fixture_scan(tmp_path, source) == ("fixture.py:3 (uncontrolled-environment)",)
    assert _fixture_scan(tmp_path, source, relative=relative) == ()


@pytest.mark.parametrize(
    "source",
    (
        "from pathlib import Path\nPath('/tmp/cadrumo').mkdir()\n",
        "from pathlib import Path\nPath('C:/Users/Neve/AppData/Local/cadrumo/storage').mkdir()\n",
        "from pathlib import Path\nSCRATCH = '/var/tmp/cadrumo'\nPath(SCRATCH).mkdir()\n",
    ),
)
def test_known_absolute_user_and_scratch_paths_are_reported(tmp_path: Path, source: str) -> None:
    """Hard-coded OS user and scratch roots bypass operator storage controls."""
    findings = _fixture_scan(tmp_path, source)

    assert findings == (f"fixture.py:{source.count(chr(10))} (hardcoded-external)",)


def test_path_separators_in_a_generated_filename_are_not_path_roots(tmp_path: Path) -> None:
    """A slash passed to replace/strip is a token, not a storage location."""
    source = (
        "from pathlib import Path\n"
        "name = 'nested/file'.replace('/', '-')\n"
        "target = Path('artifacts') / f'{name}.log'\n"
        "target.write_text('generated')\n"
    )
    findings = _fixture_scan(tmp_path, source)

    assert findings == ()


def test_a_source_paths_basename_does_not_taint_a_controlled_copy_destination(tmp_path: Path) -> None:
    """Copying a home-sourced file by basename still writes under the destination root."""
    source = (
        "import os\nimport shutil\nfrom pathlib import Path\n"
        "descriptor = Path(os.environ['HOME']) / 'authority.sqlite'\n"
        "destination = Path('var/storage/authority') / descriptor.name\n"
        "shutil.copy2(descriptor, destination)\n"
    )
    findings = _fixture_scan(tmp_path, source)

    assert findings == ()


@pytest.mark.parametrize("device", ("/dev/null", "/dev/tty", "NUL", "CONOUT$"))
def test_console_and_null_devices_are_not_storage_paths(tmp_path: Path, device: str) -> None:
    """Intentional terminal output does not create application storage."""
    source = f"open({device!r}, 'w', encoding='utf-8').write('probe')\n"
    findings = _fixture_scan(tmp_path, source)

    assert findings == ()


def test_expanding_a_tilde_path_is_reported_as_home_storage(tmp_path: Path) -> None:
    """Path.expanduser turns a lexical tilde path into an OS user path."""
    source = "from pathlib import Path\nPath('~/cadrumo/storage').expanduser().mkdir()\n"
    findings = _fixture_scan(tmp_path, source)

    assert findings == ("fixture.py:2 (home)",)


def test_storage_roots_and_explicit_temp_directory_are_accepted(tmp_path: Path) -> None:
    """Cadrumo root variables and explicit temp locations are operator-controlled."""
    findings = _fixture_scan(
        tmp_path,
        "import os\nimport tempfile\nfrom pathlib import Path\n"
        "storage = Path(os.environ['CADRUMO_STORAGE_ROOT']) / 'profiles'\n"
        "storage.mkdir(parents=True, exist_ok=True)\n"
        "with tempfile.TemporaryDirectory(dir=os.environ['CADRUMO_TEMP_DIR']):\n    pass\n",
    )

    assert findings == ()


def test_an_unscoped_temp_constructor_is_allowed_only_after_bootstrap(tmp_path: Path) -> None:
    """The test process may use stdlib temp after conftest pins it to Cadrumo."""
    source = "import tempfile\nwith tempfile.TemporaryDirectory():\n    pass\n"
    assert _fixture_scan(tmp_path, source) == ("fixture.py:2 (ambient-temp)",)
    assert _fixture_scan(tmp_path, source, temp_controlled=True) == ()


def test_pytest_temp_bootstrap_requires_rooted_and_early_os_and_stdlib_bindings(tmp_path: Path) -> None:
    """A test-only allowance cannot be copied without the real root assignments."""
    base = (
        "import os\nimport tempfile\n"
        "from cadrumo.core.storage_environment import configured_storage_root, storage_directory\n"
        "_BASE_STORAGE_ROOT = configured_storage_root()\n"
        "def _pin_storage_override(name, default):\n"
        "    resolved = storage_directory(name, default, root=_BASE_STORAGE_ROOT)\n"
        "    os.environ[name] = str(resolved)\n"
        "    return resolved\n"
        "_TEMP_BASE = _pin_storage_override('CADRUMO_TEMP_DIR', 'tmp')\n"
    )
    bindings = (
        "os.environ.update({'TEMP': str(_TEMP_BASE), 'TMP': str(_TEMP_BASE), 'TMPDIR': str(_TEMP_BASE)})\n"
        "tempfile.tempdir = str(_TEMP_BASE)\n"
        "tempfile.gettempdir()\n"
    )
    (tmp_path / "conftest.py").write_text(base + bindings, encoding=UTF_8)
    assert _pytest_temp_bootstrap(tmp_path)

    (tmp_path / "conftest.py").write_text(base + bindings.replace(", 'TMPDIR': str(_TEMP_BASE)", ""), encoding=UTF_8)
    assert not _pytest_temp_bootstrap(tmp_path)

    late_binding = base + "tempfile.gettempdir()\n" + bindings.replace("tempfile.gettempdir()\n", "")
    (tmp_path / "conftest.py").write_text(late_binding, encoding=UTF_8)
    assert not _pytest_temp_bootstrap(tmp_path)

    unrooted = base.replace(
        "resolved = storage_directory(name, default, root=_BASE_STORAGE_ROOT)",
        "resolved = Path.home() / default",
    )
    (tmp_path / "conftest.py").write_text(unrooted + bindings, encoding=UTF_8)
    assert not _pytest_temp_bootstrap(tmp_path)


def test_reading_a_platform_setting_without_writing_is_not_reported(tmp_path: Path) -> None:
    """The gate follows sources to effects instead of banning harmless probes."""
    findings = _fixture_scan(
        tmp_path,
        "import os\nvalue = os.environ.get('LOCALAPPDATA')\nprint(value)\n",
    )

    assert findings == ()
