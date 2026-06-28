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
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_AEAT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SRC_AEAT.parents[1]
_TEST_MODULE_ROOTS = (
    _SRC_AEAT,
    _REPO_ROOT / "docs",
)
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
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
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
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return set()
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
    source = path.read_text(encoding="utf-8")
    ranges = _docstring_ranges(path)
    violations: list[str] = []
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    for token in tokens:
        inspect_token = token.type == tokenize.COMMENT or (
            token.type == tokenize.STRING and any(start <= token.start[0] <= end for start, end in ranges)
        )
        if not inspect_token:
            continue
        for pattern in _CAMPAIGN_METADATA_PATTERNS:
            if pattern.search(token.string):
                relative = path.relative_to(_REPO_ROOT)
                violations.append(f"{relative}:{token.start[0]}: {token.string.strip()[:160]}")
                break
    return violations


def _process_symbol_metadata_violations(path: Path) -> list[str]:
    """Return process identifiers found in test symbols or pytest case ids."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []
    relative = path.relative_to(_REPO_ROOT)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and any(
            pattern.search(node.name) for pattern in _PROCESS_SYMBOL_METADATA_PATTERNS
        ):
            violations.append(f"{relative}:{node.lineno}: {node.name}")
        if isinstance(node, ast.Call):
            violations.extend(_process_pytest_id_violations(path, node))
    return violations


def _process_pytest_id_violations(path: Path, node: ast.Call) -> list[str]:
    violations: list[str] = []
    func_text = ast.unparse(node.func)
    relative = path.relative_to(_REPO_ROOT)
    for keyword in node.keywords:
        if keyword.arg == "id" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            value = keyword.value.value
            if any(pattern.search(value) for pattern in _PROCESS_SYMBOL_METADATA_PATTERNS):
                violations.append(f"{relative}:{keyword.value.lineno}: {value}")
        if (
            "parametrize" not in func_text
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
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
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


def _placement_error(path: Path) -> str | None:
    """Validate that module-level ``pytestmark`` is the first test statement."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
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
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        for decorator in node.decorator_list:
            name = _pytest_mark_name(decorator)
            if name in _EXECUTION_MARKERS or (name is not None and name.startswith("hex_")):
                violations.append(f"{path.relative_to(_REPO_ROOT)}:{decorator.lineno}: @{name}")
    return violations


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
    if "access_gate" in path.parts:
        return True
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        if node.module.endswith("core.access_gate") or ".core.access_gate" in node.module:
            return True
    return False


def _live_env_runtime_violations(path: Path) -> list[str]:
    """Return live-test env runtime accesses outside live tests or gate tests."""
    names, error = _extract_pytestmark_names(path)
    if error is not None:
        return []
    execution = names & _EXECUTION_MARKERS
    if execution & {"aeat_live"}:
        return []
    if _imports_access_gate(path):
        return []

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if _is_live_env_runtime_access(node):
            violations.append(f"{path.relative_to(_REPO_ROOT)}:{getattr(node, 'lineno', '?')}")
    return violations


def _requires_live_gate_helper(path: Path) -> bool:
    """Return True when a test module calls the shared live-test gate helper."""
    source = path.read_text(encoding="utf-8")
    if "requires_live_enabled" not in source:
        return False
    tree = ast.parse(source, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "requires_live_enabled":
            return True
    return False


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


@pytest.mark.parametrize(
    "module_path",
    _MODULES,
    ids=[str(p.relative_to(_REPO_ROOT)).replace("\\", "/") for p in _MODULES],
)
def test_module_carries_valid_pytestmark(module_path: Path) -> None:
    """Every test module must declare a valid hexagonal ``pytestmark``."""
    marker_sequence, error = _extract_pytestmark_sequence(module_path)
    names = set(marker_sequence)
    relative = module_path.relative_to(_REPO_ROOT)
    assert error is None, f"{relative}: {error}"
    duplicates = sorted({name for name in marker_sequence if marker_sequence.count(name) > 1})
    assert not duplicates, f"{relative}: duplicate pytestmark marker(s) {duplicates}"

    execution = names & _EXECUTION_MARKERS
    assert len(execution) == 1, (
        f"{relative}: must carry exactly one of {sorted(_EXECUTION_MARKERS)}; found {sorted(execution)}"
    )

    hex_markers = {name for name in names if name.startswith("hex_")}
    assert len(hex_markers) == 1, f"{relative}: must carry exactly one `hex_*` marker; found {sorted(hex_markers)}"
    assert hex_markers <= _HEX_MARKERS, f"{relative}: unknown hex marker(s) {sorted(hex_markers - _HEX_MARKERS)}"

    forbidden = names & _FORBIDDEN_MARKERS
    assert not forbidden, f"{relative}: forbidden legacy marker(s) {sorted(forbidden)}"


@pytest.mark.parametrize(
    "module_path",
    _MODULES,
    ids=[str(p.relative_to(_REPO_ROOT)).replace("\\", "/") for p in _MODULES],
)
def test_module_hex_marker_matches_owning_architecture_root(module_path: Path) -> None:
    """Tests under clear architecture roots must carry that root's hex marker."""
    expected = _expected_hex_marker_for_path(module_path)
    if expected is None:
        return
    names, error = _extract_pytestmark_names(module_path)
    assert error is None, f"{module_path.relative_to(_REPO_ROOT)}: {error}"
    hex_markers = {name for name in names if name.startswith("hex_")}
    assert hex_markers == {expected}, (
        f"{module_path.relative_to(_REPO_ROOT)}: expected {expected}; found {sorted(hex_markers)}"
    )


@pytest.mark.parametrize(
    "module_path",
    _MODULES,
    ids=[str(p.relative_to(_REPO_ROOT)).replace("\\", "/") for p in _MODULES],
)
def test_module_pytestmark_is_first_test_statement(module_path: Path) -> None:
    """The module marker declaration must precede constants, fixtures, and tests."""
    error = _placement_error(module_path)
    assert error is None, f"{module_path.relative_to(_REPO_ROOT)}: {error}"


def test_no_function_level_access_or_domain_markers() -> None:
    """Execution and hex markers are module-level only."""
    violations: list[str] = []
    for module_path in _MODULES:
        violations.extend(_function_level_marker_violations(module_path))
    assert not violations, "function-level execution/hex markers are forbidden:\n" + "\n".join(violations)


def test_live_test_env_runtime_access_is_live_or_gate_scoped() -> None:
    """Ordinary unit/domain tests must not depend on the live-test opt-in env var."""
    violations: list[str] = []
    for module_path in _MODULES:
        violations.extend(_live_env_runtime_violations(module_path))
    assert not violations, (
        "runtime AEAT_LIVE_TESTS_ENABLED access is only allowed in aeat_live tests "
        "or focused access-gate tests:\n" + "\n".join(violations)
    )


def test_live_gate_helper_usage_is_aeat_live_marked() -> None:
    """Tests that call the shared live gate helper must be ``aeat_live`` modules."""
    violations: list[str] = []
    for module_path in _MODULES:
        names, error = _extract_pytestmark_names(module_path)
        if error is not None or "aeat_live" in names:
            continue
        if _requires_live_gate_helper(module_path):
            violations.append(str(module_path.relative_to(_REPO_ROOT)))
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
        for root in _TEST_MODULE_ROOTS
        for path in root.rglob("test_*.py")
        if "tests" not in path.relative_to(_REPO_ROOT).parts
    ]
    underscore_prefixed = [
        str(path.relative_to(_REPO_ROOT)) for root in _TEST_MODULE_ROOTS for path in root.rglob("_test_*.py")
    ]
    suffix_style = [
        str(path.relative_to(_REPO_ROOT)) for root in _TEST_MODULE_ROOTS for path in root.rglob("*_test.py")
    ]
    assert not misplaced, "test-prefixed files outside tests directories:\n" + "\n".join(misplaced)
    assert not underscore_prefixed, "underscore-prefixed test files are forbidden:\n" + "\n".join(underscore_prefixed)
    assert not suffix_style, "suffix-style test files are forbidden:\n" + "\n".join(suffix_style)


def test_source_tests_do_not_reference_retired_marker_names() -> None:
    """Retired marker names must not remain in durable source test surfaces."""
    violations: list[str] = []
    for module_path in _MODULES:
        text = module_path.read_text(encoding="utf-8")
        for marker in sorted(_FORBIDDEN_MARKERS):
            if f"pytest.mark.{marker}" in text:
                violations.append(f"{module_path.relative_to(_REPO_ROOT)}: pytest.mark.{marker}")
    assert not violations, "retired marker usage remains:\n" + "\n".join(violations)


def test_source_test_comments_and_docstrings_do_not_reference_campaign_metadata() -> None:
    """Durable test comments and docstrings must not carry process metadata."""
    violations: list[str] = []
    for module_path in _MODULES:
        violations.extend(_campaign_metadata_violations(module_path))
    assert not violations, "campaign metadata remains in comments/docstrings:\n" + "\n".join(violations)


def test_source_test_symbol_names_and_ids_do_not_reference_process_metadata() -> None:
    """Durable test names and pytest ids must not carry process metadata."""
    violations: list[str] = []
    for module_path in _MODULES:
        violations.extend(_process_symbol_metadata_violations(module_path))
    assert not violations, "process metadata remains in test symbols/ids:\n" + "\n".join(violations)


def test_discovery_found_modules() -> None:
    """Guardrail: the walker must discover at least one test module."""
    assert _MODULES, "no test modules discovered - glob roots or layout changed"
