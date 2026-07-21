"""AST-backed integrity audit for the hexagonal test-marker taxonomy.

Walks every source-controlled test module under ``src/aeat/`` and ``docs/`` and asserts that each
carries a single top-level ``pytestmark = [...]`` assignment containing
exactly one execution-scope marker (``unit`` / ``integration`` /
``aeat_live``) and exactly one ``hex_*`` marker.

The walker uses :mod:`ast` only; it does not import the test modules.
The file self-validates because the discovery glob includes itself.

See charter ``#116`` and ``src/aeat/tests/README.md`` for the taxonomy
contract.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
import tomllib
from functools import cache
from pathlib import Path
from typing import NamedTuple

import pytest

from ._inventory import PROJECT_TEST_ROOTS, ast_for_path, project_test_modules, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_AEAT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SRC_AEAT.parents[1]
_TEST_MODULE_ROOTS = (
    _SRC_AEAT,
    _REPO_ROOT / "docs",
)
_TEST_TOPOLOGY_ROOTS = (_SRC_AEAT, *PROJECT_TEST_ROOTS)
_EXECUTION_MARKERS = frozenset({"unit", "integration", "aeat_live"})
_HEX_MARKERS = frozenset(
    {
        "hex_application",
        "hex_core",
        "hex_domain",
        "hex_entrypoint",
        "hex_inbound_adapter",
        "hex_outbound_adapter",
        "hex_persistence_adapter",
    },
)
_EXPECTED_CONFIGURED_MARKERS = _EXECUTION_MARKERS | _HEX_MARKERS | {"docs"}
_LEGACY_READ_MARKER = "live_" + "read"
_LEGACY_WRITE_MARKER = "live_" + "write"
_LEGACY_DOMAIN_MARKERS = frozenset(
    "domain_" + suffix
    for suffix in (
        "application",
        "core",
        "export",
        "inbound",
        "model",
        "outbound",
        "persistence",
    )
)
_LEGACY_FIXTURE_TIER_MARKER = "fixture_" + "tier_" + "l" + "3"
_CAMPAIGN_METADATA_PATTERNS = (
    re.compile(r"\btest_w\d+_p\d+", re.IGNORECASE),
    re.compile(r"\bW\d{1,3}(?:\.P\d{1,3})?(?:\.S\d{1,4})?\b"),
    re.compile(r"\bP\d{1,3}\.S\d{1,4}\b"),
    re.compile(r"\bS\d{2,4}\b"),
    re.compile(r"\blegacy-(?:plan|step)"),
    re.compile(r"\baccepted contract\b", re.IGNORECASE),
    re.compile(r"\bhistory-step\b", re.IGNORECASE),
    re.compile(r"\bfollow-up step\b", re.IGNORECASE),
    re.compile(r"\bplan Step\b"),
    re.compile(r"\bSte" + r"p\s+\d+\b"),
    re.compile(r"\bstep by step\b", re.IGNORECASE),
    re.compile(r"\bPla" + r"n\s+[A-Z]\b"),
    re.compile(r"\bwave\b", re.IGNORECASE),
    re.compile(r"\bAD" + r"R\b"),
    re.compile(r"\bP" + r"R\b"),
    re.compile(r"\b[Pp]hase[- ][A-Za-z0-9]"),
    re.compile(r"\.vault/ad" + r"r", re.IGNORECASE),
    re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[-_a-z0-9]*ad" + r"r", re.IGNORECASE),
)
_NOQA_LINT_CODE_PATTERN = re.compile(r"(#\s*noqa(?::\s*)?)([A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*)")
_PROCESS_SYMBOL_METADATA_PATTERNS = (
    re.compile(r"(^|[_-])ad" + r"r($|[_-])", re.IGNORECASE),
    re.compile(r"(^|[_-])pha" + r"se($|[_-])", re.IGNORECASE),
    re.compile(r"(^|[_-])wa" + r"ve($|[_-])", re.IGNORECASE),
    re.compile(r"pa" + r"ln", re.IGNORECASE),
    re.compile(r"(^|[_-])p" + r"r($|[_-])", re.IGNORECASE),
)
_FORBIDDEN_MARKERS = (
    frozenset(
        {
            _LEGACY_FIXTURE_TIER_MARKER,
            "flaky",
            "inventory",
            _LEGACY_READ_MARKER,
            _LEGACY_WRITE_MARKER,
            "slow",
            "workbook_" + "parity",
        },
    )
    | _LEGACY_DOMAIN_MARKERS
)
_LIVE_ENV_NAME = "AEAT_LIVE_TESTS_ENABLED"
_LIVE_TEST_OPT_IN_TOKENS = ("AEAT_LIVE_TESTS_ENABLED", "aeat_live_tests_enabled")
_LIVE_TEST_OPT_IN_AUTHORITY_FILES = frozenset(
    {
        Path("src/aeat/core/_config_live_tests.py"),
        Path("src/aeat/core/config.py"),
        Path("src/aeat/core/access_gate/__init__.py"),
        Path("src/aeat/core/access_gate/_errors.py"),
    },
)
_LIVE_TEST_OPT_IN_SCAN_ROOTS = (
    _SRC_AEAT / "adapters",
    _SRC_AEAT / "application",
    _SRC_AEAT / "core",
    _SRC_AEAT / "entrypoints",
)


class _MarkerModuleInventory(NamedTuple):
    campaign_metadata_violations: list[str]
    process_symbol_metadata_violations: list[str]
    function_level_marker_violations: list[str]
    live_env_runtime_violations: list[str]
    requires_live_gate_helper: bool
    retired_marker_violations: list[str]


class _MarkerPolicyInventory(NamedTuple):
    campaign_metadata_violations: list[str]
    process_symbol_metadata_violations: list[str]
    function_level_marker_violations: list[str]
    live_env_runtime_violations: list[str]
    live_gate_helper_violations: list[str]
    retired_marker_violations: list[str]


@cache
def _source_for_path(path: Path) -> str:
    """Return source text for a path inspected repeatedly by this ratchet."""
    return path.read_text(encoding="utf-8")


@cache
def _tree_for_path(path: Path) -> ast.Module:
    """Return the parsed AST for a path inspected repeatedly by this ratchet."""
    tree = ast_for_path(path)
    if isinstance(tree, ast.Module):
        return tree
    return ast.parse(_source_for_path(path), filename=str(path))


def _discover_test_modules() -> list[Path]:
    """Return every source-controlled ``test_*.py`` module.

    Excludes ``__init__.py`` and helper modules that do not define test
    functions or test classes.
    """
    collected: set[Path] = set()
    for root in _TEST_MODULE_ROOTS:
        for path in root.glob("**/test_*.py"):
            if path.name == "__init__.py":
                continue
            if _module_defines_test_functions(path):
                collected.add(path)
    return sorted(collected)


def _module_defines_test_functions(path: Path) -> bool:
    """Return True if ``path`` declares any ``def test_*`` function at module level.

    This filter keeps the marker-integrity gate honest by scoping it to
    actual test modules.
    """
    try:
        tree = _tree_for_path(path)
    except (SyntaxError, OSError):
        return True
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_"):
            return True
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            return True
    return False


def _docstring_ranges(path: Path) -> set[tuple[int, int]]:
    """Return source-line ranges for module, class, and function docstrings."""
    try:
        tree = _tree_for_path(path)
    except SyntaxError:
        return set()
    return _docstring_ranges_for_tree(tree)


def _docstring_ranges_for_tree(tree: ast.AST) -> set[tuple[int, int]]:
    ranges: set[tuple[int, int]] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            ranges.add((first.lineno, getattr(first, "end_lineno", first.lineno)))
    return ranges


def _campaign_metadata_violations(path: Path) -> list[str]:
    """Return campaign identifiers found in comments or docstrings."""
    return _marker_module_inventory(path).campaign_metadata_violations


def _campaign_metadata_violations_for_ranges(
    path: Path,
    source: str,
    ranges: set[tuple[int, int]],
) -> list[str]:
    violations: list[str] = []
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    for token in tokens:
        inspect_token = token.type == tokenize.COMMENT or (
            token.type == tokenize.STRING and any(start <= token.start[0] <= end for start, end in ranges)
        )
        if not inspect_token:
            continue
        token_text = _campaign_metadata_scan_text(token.string)
        for pattern in _CAMPAIGN_METADATA_PATTERNS:
            if pattern.search(token_text):
                relative = path.relative_to(_REPO_ROOT)
                violations.append(f"{relative}:{token.start[0]}: {token.string.strip()[:160]}")
                break
    return violations


def _campaign_metadata_scan_text(token_string: str) -> str:
    """Return token text with ordinary lint suppression codes removed."""
    return _NOQA_LINT_CODE_PATTERN.sub(lambda match: match.group(1), token_string)


def _process_symbol_metadata_violations(path: Path) -> list[str]:
    """Return process identifiers found in test symbols or pytest case ids."""
    return _marker_module_inventory(path).process_symbol_metadata_violations


@cache
def _marker_module_inventory(path: Path) -> _MarkerModuleInventory:
    source = _source_for_path(path)
    tree = _tree_for_path(path)
    relative = path.relative_to(_REPO_ROOT)
    names, error = _extract_pytestmark_names(path)
    execution = names & _EXECUTION_MARKERS if error is None else set()
    skip_live_env_scan = (
        error is not None
        or bool(execution & {"aeat_live"})
        or _imports_access_gate_from_tree(
            path,
            tree,
        )
    )
    source_has_live_gate_helper = "requires_live_enabled" in source

    docstring_ranges: set[tuple[int, int]] = set()
    process_symbol_violations: list[str] = []
    function_level_marker_violations: list[str] = []
    live_env_runtime_violations: list[str] = []
    requires_live_gate_helper = False

    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body:
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                docstring_ranges.add((first.lineno, getattr(first, "end_lineno", first.lineno)))

        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if any(pattern.search(node.name) for pattern in _PROCESS_SYMBOL_METADATA_PATTERNS):
                process_symbol_violations.append(f"{relative}:{node.lineno}: {node.name}")
            for decorator in node.decorator_list:
                name = _pytest_mark_name(decorator)
                if name in _EXECUTION_MARKERS or (name is not None and name.startswith("hex_")):
                    function_level_marker_violations.append(f"{relative}:{decorator.lineno}: @{name}")

        if isinstance(node, ast.Call):
            process_symbol_violations.extend(_process_pytest_id_violations(path, node))
            if (
                source_has_live_gate_helper
                and isinstance(node.func, ast.Name)
                and node.func.id == "requires_live_enabled"
            ):
                requires_live_gate_helper = True

        if not skip_live_env_scan and _is_live_env_runtime_access(node):
            live_env_runtime_violations.append(f"{relative}:{getattr(node, 'lineno', '?')}")

    retired_marker_violations = [
        f"{relative}: pytest.mark.{marker}"
        for marker in sorted(_FORBIDDEN_MARKERS)
        if f"pytest.mark.{marker}" in source
    ]
    return _MarkerModuleInventory(
        campaign_metadata_violations=_campaign_metadata_violations_for_ranges(path, source, docstring_ranges),
        process_symbol_metadata_violations=process_symbol_violations,
        function_level_marker_violations=function_level_marker_violations,
        live_env_runtime_violations=live_env_runtime_violations,
        requires_live_gate_helper=requires_live_gate_helper,
        retired_marker_violations=retired_marker_violations,
    )


def _process_pytest_id_violations(path: Path, node: ast.Call) -> list[str]:
    violations: list[str] = []
    func_name = _qualified_name(node.func)
    relative = path.relative_to(_REPO_ROOT)
    for keyword in node.keywords:
        if keyword.arg == "id" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            value = keyword.value.value
            if any(pattern.search(value) for pattern in _PROCESS_SYMBOL_METADATA_PATTERNS):
                violations.append(f"{relative}:{keyword.value.lineno}: {value}")
        if (
            "parametrize" not in func_name
            or keyword.arg != "ids"
            or not isinstance(keyword.value, ast.List | ast.Tuple)
        ):
            continue
        for element in keyword.value.elts:
            if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
                continue
            if any(pattern.search(element.value) for pattern in _PROCESS_SYMBOL_METADATA_PATTERNS):
                violations.append(f"{relative}:{element.lineno}: {element.value}")
    return violations


def _qualified_name(node: ast.AST) -> str:
    """Return a dotted name for simple call/name/attribute AST shapes."""
    if isinstance(node, ast.Call):
        return _qualified_name(node.func)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


@cache
def _extract_pytestmark_sequence(path: Path) -> tuple[tuple[str, ...], str | None]:
    """Parse ``path`` and return the marker-name sequence declared at module level.

    Args:
        path: Path to the test module.

    Returns:
        A tuple ``(names, error)``. ``names`` contains every marker name
        extracted from the module-level ``pytestmark`` assignment in declaration
        order, preserving duplicates for audit rules.
        ``error`` is a human-readable string describing any structural
        problem (missing assignment, wrong shape, etc.), or ``None`` on
        success.
    """
    try:
        tree = _tree_for_path(path)
    except SyntaxError as exc:  # pragma: no cover - defensive
        return (), f"SyntaxError: {exc}"
    assign_node = _find_pytestmark_assign(tree)
    if assign_node is None:
        return (), "missing top-level `pytestmark = [...]` assignment"
    value = assign_node.value
    if not isinstance(value, ast.List | ast.Tuple):
        return (), "`pytestmark` must be assigned a list or tuple literal"
    names: list[str] = []
    for element in value.elts:
        marker_name, error = _marker_name_from_pytestmark_element(element)
        if error is not None:
            return (), error
        assert marker_name is not None  # narrowed by error=None branch
        names.append(marker_name)
    return tuple(names), None


def _extract_pytestmark_names(path: Path) -> tuple[set[str], str | None]:
    """Parse ``path`` and return the marker-name set declared at module level."""
    names, error = _extract_pytestmark_sequence(path)
    return set(names), error


def _find_pytestmark_assign(tree: ast.Module) -> ast.Assign | None:
    """Return the module-level ``pytestmark = ...`` assignment node, or ``None``."""
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "pytestmark":
            return node
    return None


def _marker_name_from_pytestmark_element(element: ast.expr) -> tuple[str | None, str | None]:
    """Resolve one ``pytestmark`` list/tuple element to its marker name.

    Accepts either ``pytest.mark.<name>`` (attribute chain, used for
    access + domain markers) or ``pytest.mark.<name>(...)`` (call
    expression, used for conditional markers like
    ``pytest.mark.skipif(cond, reason=...)``). Names from the latter
    shape are recorded but do not participate in access/domain
    validation because those are always attribute-chained.

    Returns ``(name, None)`` on success and ``(None, error)`` on any
    structural mismatch so the caller can short-circuit with the same
    error envelope it was emitting inline.
    """
    attr_chain = element.func if isinstance(element, ast.Call) else element
    if not isinstance(attr_chain, ast.Attribute):
        return None, f"unexpected element type {type(element).__name__} in pytestmark"
    mark_attr = attr_chain.value
    if not isinstance(mark_attr, ast.Attribute) or mark_attr.attr != "mark":
        return None, "element is not a `pytest.mark.<name>` attribute chain"
    mark_root = mark_attr.value
    if not isinstance(mark_root, ast.Name) or mark_root.id != "pytest":
        return None, "element is not rooted at `pytest`"
    return attr_chain.attr, None


def _pytest_mark_name(node: ast.AST) -> str | None:
    """Return the marker name for ``pytest.mark.<name>`` decorators."""
    attr_chain = node.func if isinstance(node, ast.Call) else node
    if not isinstance(attr_chain, ast.Attribute):
        return None
    mark_attr = attr_chain.value
    if not isinstance(mark_attr, ast.Attribute) or mark_attr.attr != "mark":
        return None
    mark_root = mark_attr.value
    if not isinstance(mark_root, ast.Name) or mark_root.id != "pytest":
        return None
    return attr_chain.attr


def _decorator_marker_names(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for decorator in node.decorator_list:
        name = _pytest_mark_name(decorator)
        if name is not None:
            names.add(name)
    return names


def _project_module_marker_names(path: Path) -> tuple[set[str], str | None]:
    tree = _tree_for_path(path)
    if _find_pytestmark_assign(tree) is None:
        return set(), None
    marker_sequence, error = _extract_pytestmark_sequence(path)
    return set(marker_sequence), error


def _project_test_item_marker_violations(path: Path) -> list[str]:
    tree = _tree_for_path(path)
    relative = repo_relative(path)
    module_markers, error = _project_module_marker_names(path)
    if error is not None:
        assign_node = _find_pytestmark_assign(tree)
        lineno = assign_node.lineno if assign_node is not None else 1
        return [f"{relative}:{lineno}: {error}"]

    violations: list[str] = []

    def check_item(lineno: int, name: str, marker_names: set[str]) -> None:
        execution = marker_names & _EXECUTION_MARKERS
        hex_markers = {marker for marker in marker_names if marker.startswith("hex_")}
        if len(execution) != 1 or len(hex_markers) != 1 or not hex_markers <= _HEX_MARKERS:
            violations.append(
                f"{relative}:{lineno}: {name}: execution={sorted(execution)} hex={sorted(hex_markers)}",
            )

    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_"):
            check_item(node.lineno, node.name, module_markers | _decorator_marker_names(node))
            continue
        if not isinstance(node, ast.ClassDef) or not node.name.startswith("Test"):
            continue
        class_markers = module_markers | _decorator_marker_names(node)
        for child in node.body:
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and child.name.startswith("test_"):
                check_item(child.lineno, f"{node.name}.{child.name}", class_markers | _decorator_marker_names(child))

    return violations


@cache
def _placement_error(path: Path) -> str | None:
    """Validate that module-level ``pytestmark`` is the first test statement."""
    tree = _tree_for_path(path)
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, ast.Import | ast.ImportFrom):
            continue
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets
        ):
            return None
        return f"`pytestmark` must appear before {type(node).__name__} at line {node.lineno}"
    return "missing top-level `pytestmark = [...]` assignment"


def _function_level_marker_violations(path: Path) -> list[str]:
    """Return function/class decorators that misuse execution or hex markers."""
    return _marker_module_inventory(path).function_level_marker_violations


def _is_live_env_runtime_access(node: ast.AST) -> bool:
    """Return True for executable reads/writes of the live-test opt-in env var."""
    if isinstance(node, ast.Subscript):
        if not _is_os_environ(node.value):
            return False
        return _literal_string(node.slice) == _LIVE_ENV_NAME
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if _is_os_environ(node.func.value) and node.func.attr in {"get", "pop", "setdefault"}:
            return bool(node.args) and _literal_string(node.args[0]) == _LIVE_ENV_NAME
        if node.func.attr in {"setenv", "delenv"}:
            return bool(node.args) and _literal_string(node.args[0]) == _LIVE_ENV_NAME
    return False


def _is_os_environ(node: ast.AST) -> bool:
    """Return True for the AST shape `os.environ`."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _literal_string(node: ast.AST) -> str | None:
    """Return the string literal value represented by `node`, when static."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _imports_access_gate(path: Path) -> bool:
    """Return True when a unit test is directly testing the live access gate."""
    return _imports_access_gate_from_tree(path, _tree_for_path(path))


def _imports_access_gate_from_tree(path: Path, tree: ast.Module) -> bool:
    if "access_gate" in path.parts:
        return True
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        if node.module.endswith("core.access_gate") or ".core.access_gate" in node.module:
            return True
    return False


def _live_env_runtime_violations(path: Path) -> list[str]:
    """Return live-test env runtime accesses outside live tests or gate tests."""
    return _marker_module_inventory(path).live_env_runtime_violations


def _requires_live_gate_helper(path: Path) -> bool:
    """Return True when a test module calls the shared live-test gate helper."""
    return _marker_module_inventory(path).requires_live_gate_helper


def _expected_hex_marker_for_path(path: Path) -> str | None:
    """Return the owning hex marker for paths with unambiguous architecture roots."""
    relative = path.relative_to(_REPO_ROOT)
    parts = relative.parts
    path_text = relative.as_posix()

    if path_text.startswith("docs/tools/tests/test_cli_reference"):
        return "hex_entrypoint"
    if path_text.startswith("docs/"):
        return "hex_core"
    if parts[:3] == ("src", "aeat", "entrypoints"):
        return "hex_entrypoint"
    if parts[:3] == ("src", "aeat", "application"):
        return "hex_application"
    if parts[:3] == ("src", "aeat", "domain"):
        return "hex_domain"
    if parts[:4] == ("src", "aeat", "adapters", "inbound"):
        return "hex_inbound_adapter"
    if parts[:4] == ("src", "aeat", "adapters", "outbound"):
        return "hex_outbound_adapter"
    if parts[:4] == ("src", "aeat", "adapters", "persistence"):
        return "hex_persistence_adapter"
    if parts[:3] == ("src", "aeat", "core"):
        return "hex_core"
    if parts[:3] == ("src", "aeat", "_data"):
        return "hex_domain"
    if path_text.startswith("src/aeat/tests/fixtures/"):
        return "hex_inbound_adapter"
    return None


def _configured_marker_names() -> list[str]:
    """Return marker names declared in ``pyproject.toml``."""
    data = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    marker_rows = data["tool"]["pytest"]["ini_options"]["markers"]
    return [row.split(":", 1)[0] for row in marker_rows]


def _is_test_infrastructure_path(path: Path) -> bool:
    """Return True for test modules and shared pytest infrastructure."""
    parts = path.relative_to(_REPO_ROOT).parts
    return "tests" in parts or path.name == "conftest.py" or path.name.startswith("test_")


def _production_live_test_opt_in_violations() -> list[str]:
    """Return production modules that mention the pytest live-test opt-in token."""
    violations: list[str] = []
    for root in _LIVE_TEST_OPT_IN_SCAN_ROOTS:
        for path in root.rglob("*.py"):
            relative = path.relative_to(_REPO_ROOT)
            if relative in _LIVE_TEST_OPT_IN_AUTHORITY_FILES or _is_test_infrastructure_path(path):
                continue
            source = path.read_text(encoding="utf-8")
            hits = [token for token in _LIVE_TEST_OPT_IN_TOKENS if token in source]
            if hits:
                violations.append(f"{relative}: {', '.join(hits)}")
    return violations


_MODULES = _discover_test_modules()


@pytest.fixture(scope="module")
def marker_policy_inventory() -> _MarkerPolicyInventory:
    campaign_metadata_violations: list[str] = []
    process_symbol_metadata_violations: list[str] = []
    function_level_marker_violations: list[str] = []
    live_env_runtime_violations: list[str] = []
    live_gate_helper_violations: list[str] = []
    retired_marker_violations: list[str] = []

    for module_path in _MODULES:
        inventory = _marker_module_inventory(module_path)
        campaign_metadata_violations.extend(inventory.campaign_metadata_violations)
        process_symbol_metadata_violations.extend(inventory.process_symbol_metadata_violations)
        function_level_marker_violations.extend(inventory.function_level_marker_violations)
        live_env_runtime_violations.extend(inventory.live_env_runtime_violations)
        retired_marker_violations.extend(inventory.retired_marker_violations)
        names, error = _extract_pytestmark_names(module_path)
        if error is None and "aeat_live" not in names and inventory.requires_live_gate_helper:
            live_gate_helper_violations.append(str(module_path.relative_to(_REPO_ROOT)))

    return _MarkerPolicyInventory(
        campaign_metadata_violations=campaign_metadata_violations,
        process_symbol_metadata_violations=process_symbol_metadata_violations,
        function_level_marker_violations=function_level_marker_violations,
        live_env_runtime_violations=live_env_runtime_violations,
        live_gate_helper_violations=live_gate_helper_violations,
        retired_marker_violations=retired_marker_violations,
    )


def test_module_carries_valid_pytestmark() -> None:
    """Every test module must declare a valid hexagonal ``pytestmark``."""
    violations: list[str] = []
    for module_path in _MODULES:
        marker_sequence, error = _extract_pytestmark_sequence(module_path)
        names = set(marker_sequence)
        relative = module_path.relative_to(_REPO_ROOT)
        if error is not None:
            violations.append(f"{relative}: {error}")
            continue
        duplicates = sorted({name for name in marker_sequence if marker_sequence.count(name) > 1})
        if duplicates:
            violations.append(f"{relative}: duplicate pytestmark marker(s) {duplicates}")

        execution = names & _EXECUTION_MARKERS
        if len(execution) != 1:
            violations.append(
                f"{relative}: must carry exactly one of {sorted(_EXECUTION_MARKERS)}; found {sorted(execution)}",
            )

        hex_markers = {name for name in names if name.startswith("hex_")}
        if len(hex_markers) != 1:
            violations.append(f"{relative}: must carry exactly one `hex_*` marker; found {sorted(hex_markers)}")
        unknown_hex_markers = hex_markers - _HEX_MARKERS
        if unknown_hex_markers:
            violations.append(f"{relative}: unknown hex marker(s) {sorted(unknown_hex_markers)}")

        forbidden = names & _FORBIDDEN_MARKERS
        if forbidden:
            violations.append(f"{relative}: forbidden legacy marker(s) {sorted(forbidden)}")

    assert not violations, "module pytestmark violations:\n" + "\n".join(violations)


def test_module_hex_marker_matches_owning_architecture_root() -> None:
    """Tests under clear architecture roots must carry that root's hex marker."""
    violations: list[str] = []
    for module_path in _MODULES:
        expected = _expected_hex_marker_for_path(module_path)
        if expected is None:
            continue
        names, error = _extract_pytestmark_names(module_path)
        relative = module_path.relative_to(_REPO_ROOT)
        if error is not None:
            violations.append(f"{relative}: {error}")
            continue
        hex_markers = {name for name in names if name.startswith("hex_")}
        if hex_markers != {expected}:
            violations.append(f"{relative}: expected {expected}; found {sorted(hex_markers)}")

    assert not violations, "module architecture marker violations:\n" + "\n".join(violations)


def test_module_pytestmark_is_first_test_statement() -> None:
    """The module marker declaration must precede constants, fixtures, and tests."""
    violations: list[str] = []
    for module_path in _MODULES:
        error = _placement_error(module_path)
        if error is not None:
            violations.append(f"{module_path.relative_to(_REPO_ROOT)}: {error}")
    assert not violations, "module pytestmark placement violations:\n" + "\n".join(violations)


def test_project_test_items_resolve_to_single_execution_and_hex_marker() -> None:
    violations: list[str] = []
    for module_path in project_test_modules():
        violations.extend(_project_test_item_marker_violations(module_path))
    assert not violations, "project test item marker violations:\n" + "\n".join(violations)


def test_no_function_level_access_or_domain_markers(marker_policy_inventory: _MarkerPolicyInventory) -> None:
    """Execution and hex markers are module-level only."""
    violations = marker_policy_inventory.function_level_marker_violations
    assert not violations, "function-level execution/hex markers are forbidden:\n" + "\n".join(violations)


def test_live_test_env_runtime_access_is_live_or_gate_scoped(marker_policy_inventory: _MarkerPolicyInventory) -> None:
    """Ordinary unit/domain tests must not depend on the live-test opt-in env var."""
    violations = marker_policy_inventory.live_env_runtime_violations
    assert not violations, (
        "runtime AEAT_LIVE_TESTS_ENABLED access is only allowed in aeat_live tests "
        "or focused access-gate tests:\n" + "\n".join(violations)
    )


def test_live_gate_helper_usage_is_aeat_live_marked(marker_policy_inventory: _MarkerPolicyInventory) -> None:
    """Tests that call the shared live gate helper must be ``aeat_live`` modules."""
    violations = marker_policy_inventory.live_gate_helper_violations
    assert not violations, "requires_live_enabled() used outside aeat_live tests:\n" + "\n".join(violations)


def test_pyproject_marker_registry_is_pruned_and_unique() -> None:
    """Configured markers must be unique and match the active taxonomy."""
    configured = _configured_marker_names()
    duplicates = sorted({name for name in configured if configured.count(name) > 1})
    assert not duplicates, f"duplicate pytest marker declarations: {duplicates}"
    assert set(configured) == _EXPECTED_CONFIGURED_MARKERS


def test_live_test_opt_in_token_is_not_used_by_production_aeat_live_paths() -> None:
    """The live-test opt-in env var must remain test/core-gate infrastructure only."""
    violations = _production_live_test_opt_in_violations()
    assert not violations, "production modules must not gate live reads on the pytest opt-in:\n" + "\n".join(violations)


def test_test_modules_live_under_tests_directories_and_use_test_prefix() -> None:
    """Every test module must live below a ``tests`` directory and use ``test_``."""
    misplaced = [
        str(path.relative_to(_REPO_ROOT))
        for root in _TEST_TOPOLOGY_ROOTS
        for path in root.rglob("test_*.py")
        if "tests" not in path.relative_to(_REPO_ROOT).parts
    ]
    underscore_prefixed = [
        str(path.relative_to(_REPO_ROOT)) for root in _TEST_TOPOLOGY_ROOTS for path in root.rglob("_test_*.py")
    ]
    suffix_style = [
        str(path.relative_to(_REPO_ROOT)) for root in _TEST_TOPOLOGY_ROOTS for path in root.rglob("*_test.py")
    ]
    assert not misplaced, "test-prefixed files outside tests directories:\n" + "\n".join(misplaced)
    assert not underscore_prefixed, "underscore-prefixed test files are forbidden:\n" + "\n".join(underscore_prefixed)
    assert not suffix_style, "suffix-style test files are forbidden:\n" + "\n".join(suffix_style)


def test_source_tests_do_not_reference_retired_marker_names(marker_policy_inventory: _MarkerPolicyInventory) -> None:
    """Retired marker names must not remain in durable source test surfaces."""
    violations = marker_policy_inventory.retired_marker_violations
    assert not violations, "retired marker usage remains:\n" + "\n".join(violations)


def test_campaign_metadata_scan_ignores_noqa_lint_codes() -> None:
    """Lint suppression codes are not campaign process identifiers."""
    lint_comment = "# noqa: " + "S" + "603 - subprocess invocation is intentional"
    campaign_comment = "# carried campaign step " + "S" + "603"

    lint_scan_text = _campaign_metadata_scan_text(lint_comment)
    campaign_scan_text = _campaign_metadata_scan_text(campaign_comment)

    assert not any(pattern.search(lint_scan_text) for pattern in _CAMPAIGN_METADATA_PATTERNS)
    assert any(pattern.search(campaign_scan_text) for pattern in _CAMPAIGN_METADATA_PATTERNS)


def test_qualified_name_handles_parametrize_call_shape() -> None:
    """The process-metadata scan should not need source unparsing."""
    call_expr = ast.parse("pytest.mark.parametrize('value', [1], ids=['case'])").body[0]
    assert isinstance(call_expr, ast.Expr)

    call = call_expr.value
    assert isinstance(call, ast.Call)
    assert _qualified_name(call.func) == "pytest.mark.parametrize"


def test_source_test_comments_and_docstrings_do_not_reference_campaign_metadata(
    marker_policy_inventory: _MarkerPolicyInventory,
) -> None:
    """Durable test comments and docstrings must not carry process metadata."""
    violations = marker_policy_inventory.campaign_metadata_violations
    assert not violations, "campaign metadata remains in comments/docstrings:\n" + "\n".join(violations)


def test_source_test_symbol_names_and_ids_do_not_reference_process_metadata(
    marker_policy_inventory: _MarkerPolicyInventory,
) -> None:
    """Durable test names and pytest ids must not carry process metadata."""
    violations = marker_policy_inventory.process_symbol_metadata_violations
    assert not violations, "process metadata remains in test symbols/ids:\n" + "\n".join(violations)


def test_discovery_found_modules() -> None:
    """Guardrail: the walker must discover at least one test module."""
    assert _MODULES, "no test modules discovered - glob roots or layout changed"
