"""AST-backed integrity audit for the hexagonal test-marker taxonomy.

Walks every test module present on disk under ``src/cadrumo/`` and ``docs/``
— the scan is a filesystem glob and does not consult git, so an untracked
module is in scope (see :func:`_discover_test_modules`) — and asserts that each
carries a single top-level ``pytestmark = [...]`` assignment containing
exactly one execution-scope marker (``unit`` / ``integration`` /
``aeat_live``) and exactly one ``hex_*`` marker.

The walker uses :mod:`ast` only; it does not import the test modules.
The file self-validates because the discovery glob includes itself.

See charter ``#116`` and ``src/cadrumo/tests/README.md`` for the taxonomy
contract.
"""

from __future__ import annotations

import ast
import io
import re
import subprocess
import sys
import tempfile
import tokenize
import tomllib
from functools import cache
from pathlib import Path
from typing import NamedTuple

import pytest

from cadrumo.core import scan_directory
from cadrumo.tests._inventory import ast_for_path, qualified_name, repo_relative
from dev._paths import REPO_ROOT

from ._marker_metadata_patterns import CAMPAIGN_METADATA_CASES as _CAMPAIGN_METADATA_CASES
from ._marker_metadata_patterns import CAMPAIGN_METADATA_PATTERNS as _CAMPAIGN_METADATA_PATTERNS
from ._marker_metadata_patterns import PROCESS_PLAN_CASE as _PROCESS_PLAN_CASE
from ._marker_metadata_patterns import PROCESS_SYMBOL_METADATA_CASES as _PROCESS_SYMBOL_METADATA_CASES
from ._marker_metadata_patterns import PROCESS_SYMBOL_METADATA_PATTERNS as _PROCESS_SYMBOL_METADATA_PATTERNS
from ._marker_metadata_patterns import PRODUCTION_SCOPED_CAMPAIGN_METADATA_CASES as _PRODUCTION_SCOPED_CASES
from ._marker_metadata_patterns import PRODUCTION_SCOPED_CAMPAIGN_METADATA_PATTERNS as _PRODUCTION_SCOPED_PATTERNS
from ._marker_metadata_patterns import RETIRED_SCRAMBLED_PLAN_PATTERN as _RETIRED_SCRAMBLED_PLAN_PATTERN
from ._marker_metadata_patterns import MarkerScanScope as _MarkerScanScope
from ._marker_metadata_patterns import PatternCase as _PatternCase
from ._marker_metadata_patterns import assert_cases_discriminate as _assert_cases_discriminate
from ._marker_metadata_patterns import campaign_metadata_scan_text as _campaign_metadata_scan_text
from ._project_inventory import PROJECT_TEST_ROOTS, project_test_modules

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_CADRUMO = REPO_ROOT / "src" / "cadrumo"
_REPO_ROOT = REPO_ROOT
#: Roots the module-level marker checks read. ``dev`` is included so the two
#: inventories in this gate cover the same trees: ``project_test_modules()``
#: (the unioned per-item check) already reaches ``dev`` and ``docs``, and this
#: one reaches ``src/cadrumo`` and ``docs``. Leaving ``dev`` out here meant each
#: inventory had a hole the other only partly filled, so a ``dev`` module could
#: carry no module-level execution marker and no check would say so.
#:
#: ``packaging`` was the same hole one tree over. A gate that cannot see part
#: of the tree is not passing on it; it is silent about it, and the two are
#: indistinguishable from the outside.
_TEST_MODULE_ROOTS = (
    _SRC_CADRUMO,
    _REPO_ROOT / "docs",
    _REPO_ROOT / "dev",
    _REPO_ROOT / "packaging",
)
_TEST_TOPOLOGY_ROOTS = (_SRC_CADRUMO, *PROJECT_TEST_ROOTS)
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
# ``perf`` is a supplementary label, not an execution marker: the benchmark
# module carries it alongside ``integration`` + ``serial`` so the broad serial
# passes can exclude it (``-m "integration and serial and not perf"``) and the
# dispatch-only ci-full lane can enrol it explicitly. Its placement policy is
# pinned by dev/ci/tests/test_perf_gate_policy.py.
# ``external_tool`` follows the same supplementary-label pattern: the workbook
# parity module carries it alongside ``unit`` so the default lane can exclude it
# (``-m "unit and not external_tool"``) while ``just test-workbook-parity``
# enrols it explicitly. It marks tests needing an external binary the dependency
# set does not install (LibreOffice), so the marker rather than a path
# ``--ignore`` is what holds them out of the default lane.
# ``os_keychain`` follows the same supplementary-label pattern for a capability
# of the LOGON SESSION rather than of the dependency set: the OS credential
# store answers only an interactive desktop session, so a headless CI runner and
# an agent's SSH network logon both reach a real backend that refuses every
# credential call. Tests whose assertion subject IS that custody carry the label
# alongside their execution marker, every lane excludes it, and
# ``just test-os-keychain`` enrols it. Everything provable without custody stays
# in the default lanes.
# ``resident_service`` is the same supplementary-label pattern for a precondition
# of a RUNNING LOCAL SERVICE rather than of the dependency set; enrolled by
# ``just test-resident-service``. Full rationale on the pyproject registration.
# There is deliberately NO marker for the outer-serial harness members. Their
# cost is multiplicative inside another lane's xdist pool, so they are held out
# of every parallel lane -- but by explicit path, never by a runtime-cost label
# competing with this taxonomy. The exclusion and the enrolling recipe's member
# list are proven exactly equal by dev/ci/tests/test_machine_aware_load.py.
_EXPECTED_CONFIGURED_MARKERS = (
    _EXECUTION_MARKERS | _HEX_MARKERS | {"docs", "serial", "perf", "external_tool", "os_keychain", "resident_service"}
)
_OS_KEYCHAIN_MARKER = "os_keychain"
_LIVE_POLICY_SUBPROCESS_TIMEOUT_SECONDS = 60
#: Every test whose assertion subject IS the OS credential store, by node id.
#:
#: This membership is PINNED rather than counted, because ``os_keychain`` removes a
#: test from every lane including the default ``addopts`` selection. Unpinned, it is
#: a mute button: any agent meeting a red custody test could add the label and the
#: test would silently leave the automated lanes with nothing to notice — the same
#: hazard the locale honesty allowlist is guarded against, and here it sits in front
#: of a security-critical fail-closed path. A count is not sufficient: it cannot say
#: WHICH test drifted, and one enrolled plus one dropped nets to zero.
#:
#: Adding an entry is a deliberate claim that the case cannot be proven at all
#: without a credential store. Anything provable without custody stays in the lanes
#: — see the boundary drawn in the user_profile tests conftest.
_EXPECTED_OS_KEYCHAIN_TEST_IDS = frozenset(
    {
        "src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py"
        "::TestSilentResume::test_valid_session_resumes_with_no_authentication",
        "src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py"
        "::TestSilentResume::test_resume_advances_the_idle_deadline",
        # The destroy-path reaps. Each asserts on the KEYCHAIN half of the
        # split-knowledge session specifically — that the UUID-paired
        # keychain receipt is absent once the profile is gone — so a host
        # with no credential store cannot mint the key whose
        # absence is the subject, and the case would pass vacuously. The
        # on-disk half of the same contract is deliberately left in the
        # default lane (``test_tombstone_removes_the_persisted_record``), so
        # the reap stays covered everywhere; only the custody-bound halves
        # carry the marker.
        # The acceleration-receipt and DEK-wipe custody suites. Each mints, reads or
        # revokes a real profile-session receipt in the OS credential store, so the
        # store IS the subject: on a host without one every case fails at
        # KeyringUnavailableError before reaching its assertion.
        "src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py"
        "::TestProfileSessionAcceleration::test_custody_rotation_revokes_old_receipt",
        "src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py"
        "::TestProfileSessionAcceleration::test_expired_receipt_removes_only_its_own_keychain_entry",
        "src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py"
        "::TestProfileSessionAcceleration::test_mint_then_resume_binds_exact_current_envelope_metadata",
        "src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py"
        "::TestProfileSessionAcceleration::test_mint_uses_random_session_id_and_exact_keychain_account",
        "src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py"
        "::TestProfileSessionAcceleration::test_nonpositive_windows_refuse_before_keychain_write",
        "src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py"
        "::TestProfileSessionAcceleration::test_receipt_never_writes_plaintext_dek",
        "src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py"
        "::TestProfileSessionAcceleration::test_tampered_aad_record_is_refused_and_cleaned",
        "src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py"
        "::test_revocation_refuses_when_the_receipt_survives_the_clear",
        "src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py"
        "::test_revocation_returns_normally_when_the_receipt_is_cleared",
        "src/cadrumo/adapters/persistence/storage/custody/tests/test_unwrapped_dek_is_wipeable.py"
        "::test_the_resumed_key_is_a_buffer_whose_wipe_reaches_the_material",
        # Reaps a discovered bucket key from the credential store; the absence it
        # asserts cannot be established where the key could never be minted.
        "src/cadrumo/adapters/persistence/storage/tests/test_test_support_runtime_context_lifecycle.py"
        "::test_isolated_profile_storage_root_reaps_a_discovered_bucket_key",
        # Owner-receipt durability across the custody transaction journal. The
        # receipts are credential-store records, so the journal's resume and
        # idempotence contracts are unprovable without custody.
        "src/cadrumo/application/user_profile/tests/test_custody_transactions.py"
        "::test_create_orchestration_journals_stages_verifies_and_publishes_pointer_last",
        "src/cadrumo/application/user_profile/tests/test_custody_transactions.py"
        "::test_delete_owner_receipts_are_durable_and_idempotent",
        "src/cadrumo/application/user_profile/tests/test_custody_transactions.py"
        "::test_owner_receipts_resume_after_owner_effect_precedes_journal_state",
        # Fail-closed CLI refusals reached through a REAL profile session: the
        # absent/expired states under test are states OF the keychain-backed
        # session half, so establishing them needs a store to have held one.
        "src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py"
        "::TestFailClosedRefusals::test_absent_session_login_action_keeps_the_executable_profile_label",
        "src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py"
        "::TestFailClosedRefusals::test_absent_session_refuses_naming_login",
        "src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py"
        "::TestFailClosedRefusals::test_absent_session_root_refusal_carries_the_login_action",
        "src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py"
        "::TestFailClosedRefusals::test_absolute_cap_refuses",
        "src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py"
        "::TestFailClosedRefusals::test_explicit_history_reads_the_requested_profile_repository",
        "src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py"
        "::TestFailClosedRefusals::test_explicit_validate_is_not_preempted_by_the_active_profile_gate",
        "src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py"
        "::TestFailClosedRefusals::test_idle_expiry_refuses",
        "src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py"
        "::TestFailClosedRefusals::test_unnamed_history_reads_the_authenticated_active_profile",
        "src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py"
        "::TestFailClosedRefusals::test_unnamed_validate_is_gated_as_an_active_profile_read",
    },
)
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
#: Campaign- and process-metadata scan pattern tables and their positive-control
#: helper live in :mod:`._marker_metadata_patterns` — pure declarative scan data,
#: separable from this module's AST walk. See that module for the pattern/
#: target/near-miss rationale.
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
_LIVE_ENV_NAME = "CADRUMO_LIVE_TESTS_ENABLED"
_LIVE_TEST_OPT_IN_TOKENS = ("CADRUMO_LIVE_TESTS_ENABLED", "cadrumo_live_tests_enabled")
_LIVE_TEST_OPT_IN_AUTHORITY_FILES = frozenset(
    {
        Path("src/cadrumo/core/_config_live_tests.py"),
        Path("src/cadrumo/core/config.py"),
        Path("src/cadrumo/core/access_gate/__init__.py"),
        Path("src/cadrumo/core/access_gate/_errors.py"),
    },
)
_LIVE_TEST_OPT_IN_SCAN_ROOTS = (
    _SRC_CADRUMO / "adapters",
    _SRC_CADRUMO / "application",
    _SRC_CADRUMO / "core",
    _SRC_CADRUMO / "entrypoints",
)
#: Test modules whose declared subject is the vault authoring pipeline itself.


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
    """Return every ``test_*.py`` module present on disk.

    Excludes ``__init__.py`` and helper modules that do not define test
    functions or test classes.

    The scan is a filesystem glob and deliberately does not consult git, so
    an untracked module is in scope. That is the useful behaviour in a
    worktree where several agents hold uncommitted work at once: a
    misplaced ``pytestmark`` is caught before it is committed rather than
    after. The cost is that a red here may name a file that does not exist
    at HEAD, so triage starts with ``git status --short -- <file>`` — an
    untracked path is a peer's work in progress, not a regression.
    """
    collected: set[Path] = set()
    for root in _TEST_MODULE_ROOTS:
        for path in scan_directory(root, pattern="test_*.py", recursive=True):
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
    patterns: tuple[re.Pattern[str], ...] = _CAMPAIGN_METADATA_PATTERNS,
) -> list[str]:
    """Return process-metadata hits in the comments and docstrings of one module.

    The single scan mechanism for both module populations. ``patterns`` is the
    caller's scope selection — the whole table for a test module, the
    production-scoped subset for ordinary source — so widening a family's reach
    is a declaration on the pattern rather than a second walk over the tree. A
    parallel production scanner would be free to drift in its tokenisation, its
    docstring-range derivation and its noqa handling, and every such drift is
    invisible from the outside because both shapes report an empty list.
    """
    violations: list[str] = []
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    for token in tokens:
        inspect_token = token.type == tokenize.COMMENT or (
            token.type == tokenize.STRING and any(start <= token.start[0] <= end for start, end in ranges)
        )
        if not inspect_token:
            continue
        token_text = _campaign_metadata_scan_text(token.string)
        for pattern in patterns:
            if pattern.search(token_text):
                relative = path.relative_to(_REPO_ROOT)
                violations.append(f"{relative}:{token.start[0]}: {token.string.strip()[:160]}")
                break
    return violations


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
    marker_aliases = _module_marker_aliases(tree)

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
                name = _pytest_mark_name(decorator) or _aliased_marker_name(decorator, marker_aliases)
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


def _module_marker_aliases(tree: ast.Module) -> dict[str, str]:
    """Return module-level ``NAME = pytest.mark.<marker>`` bindings.

    A marker bound to a constant and applied as a bare ``@NAME`` decorator is
    invisible to :func:`_pytest_mark_name`, which only recognises the literal
    attribute chain. The runtime collection hook sees the real marker either
    way, so an unresolved alias lets a module declare one execution lane at
    module level and a conflicting one per test — a combination that raises
    :class:`pytest.UsageError` during collection and aborts the entire run
    rather than failing this gate. Resolving the binding keeps the static gate
    and the runtime hook looking at the same marker set.
    """
    aliases: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        marker = _pytest_mark_name(node.value)
        if marker is not None:
            aliases[target.id] = marker
    return aliases


def _decorator_marker_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    aliases: dict[str, str] | None = None,
) -> set[str]:
    names: set[str] = set()
    for decorator in node.decorator_list:
        name = _pytest_mark_name(decorator)
        if name is None:
            name = _aliased_marker_name(decorator, aliases or {})
        if name is not None:
            names.add(name)
    return names


def _aliased_marker_name(decorator: ast.expr, aliases: dict[str, str]) -> str | None:
    """Return the marker a bare ``@NAME`` decorator resolves to, if any."""
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(target, ast.Name):
        return aliases.get(target.id)
    return None


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
    aliases = _module_marker_aliases(tree)

    def check_item(lineno: int, name: str, marker_names: set[str]) -> None:
        execution = marker_names & _EXECUTION_MARKERS
        hex_markers = {marker for marker in marker_names if marker.startswith("hex_")}
        if len(execution) != 1 or len(hex_markers) != 1 or not hex_markers <= _HEX_MARKERS:
            violations.append(
                f"{relative}:{lineno}: {name}: execution={sorted(execution)} hex={sorted(hex_markers)}",
            )

    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_"):
            check_item(node.lineno, node.name, module_markers | _decorator_marker_names(node, aliases))
            continue
        if not isinstance(node, ast.ClassDef) or not node.name.startswith("Test"):
            continue
        class_markers = module_markers | _decorator_marker_names(node, aliases)
        for child in node.body:
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and child.name.startswith("test_"):
                check_item(
                    child.lineno,
                    f"{node.name}.{child.name}",
                    class_markers | _decorator_marker_names(child, aliases),
                )

    return violations


def _os_keychain_ids_for_tree(tree: ast.Module, relative: str, module_markers: set[str]) -> list[str]:
    """Return node ids of tests resolving to ``os_keychain`` in one module tree.

    Reads the same union pytest resolves — the module-level ``pytestmark`` plus the
    class and function decorators, alias bindings included — so a label applied by
    any of those routes is seen. Taking only one route would leave the others as
    unwatched ways to mute a test.
    """
    found: list[str] = []
    aliases = _module_marker_aliases(tree)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_"):
            if _OS_KEYCHAIN_MARKER in module_markers | _decorator_marker_names(node, aliases):
                found.append(f"{relative}::{node.name}")
            continue
        if not isinstance(node, ast.ClassDef) or not node.name.startswith("Test"):
            continue
        class_markers = module_markers | _decorator_marker_names(node, aliases)
        for child in node.body:
            if not isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) or not child.name.startswith("test_"):
                continue
            if _OS_KEYCHAIN_MARKER in class_markers | _decorator_marker_names(child, aliases):
                found.append(f"{relative}::{node.name}::{child.name}")
    return found


def _os_keychain_marked_test_ids() -> list[str]:
    """Return the node id of every test in the tree carrying ``os_keychain``."""
    found: list[str] = []
    for module_path in _unioned_marker_item_modules():
        module_markers, error = _project_module_marker_names(module_path)
        if error is not None:
            continue
        found.extend(
            _os_keychain_ids_for_tree(
                _tree_for_path(module_path),
                module_path.relative_to(_REPO_ROOT).as_posix(),
                module_markers,
            ),
        )
    return found


def _is_fixture_reexport(node: ast.stmt) -> bool:
    """Return True for an ``__all__`` assignment: import wiring, not a test statement.

    A fixture imported solely for pytest to discover it is re-exported so the
    unused-import lint stays honest.
    """
    return isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)


def _is_type_checking_import_guard(node: ast.stmt) -> bool:
    """Return True for an ``if TYPE_CHECKING:`` block holding only imports.

    The guard defers an import to type-check time, so it belongs on the import
    side of ``pytestmark``. The body is checked so no unrelated branch rides in.
    """
    if not isinstance(node, ast.If) or node.orelse:
        return False
    test = node.test
    if not (
        (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING")
        or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")
    ):
        return False
    return all(isinstance(stmt, ast.Import | ast.ImportFrom) for stmt in node.body)


@cache
def _placement_error(path: Path) -> str | None:
    """Validate that module-level ``pytestmark`` is the first test statement."""
    tree = _tree_for_path(path)
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, ast.Import | ast.ImportFrom):
            continue
        if _is_fixture_reexport(node) or _is_type_checking_import_guard(node):
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
    if parts[:3] == ("src", "cadrumo", "entrypoints"):
        return "hex_entrypoint"
    if parts[:3] == ("src", "cadrumo", "application"):
        return "hex_application"
    if parts[:3] == ("src", "cadrumo", "domain"):
        return "hex_domain"
    if parts[:4] == ("src", "cadrumo", "adapters", "inbound"):
        return "hex_inbound_adapter"
    if parts[:4] == ("src", "cadrumo", "adapters", "outbound"):
        return "hex_outbound_adapter"
    if parts[:4] == ("src", "cadrumo", "adapters", "persistence"):
        return "hex_persistence_adapter"
    if parts[:3] == ("src", "cadrumo", "core"):
        return "hex_core"
    if parts[:3] == ("src", "cadrumo", "_data"):
        return "hex_domain"
    if path_text.startswith("src/cadrumo/tests/fixtures/"):
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
    scanned = 0
    for root in _LIVE_TEST_OPT_IN_SCAN_ROOTS:
        for path in scan_directory(root, pattern="*.py", recursive=True):
            relative = path.relative_to(_REPO_ROOT)
            if relative in _LIVE_TEST_OPT_IN_AUTHORITY_FILES or _is_test_infrastructure_path(path):
                continue
            scanned += 1
            source = path.read_text(encoding="utf-8")
            hits = [token for token in _LIVE_TEST_OPT_IN_TOKENS if token in source]
            if hits:
                violations.append(f"{relative}: {', '.join(hits)}")
    # Floor the production-source scan: a relocation of any scan root would empty
    # this walk and pass identically to a clean tree, so the opt-in-leak guard would
    # be silently vacuous.
    assert scanned > 200, (
        f"scanned only {scanned} production modules under the live-test-opt-in scan roots; the "
        "scan corpus collapsed (a package relocation or rename), so an empty violation list "
        "would mean 'nothing was checked' rather than 'nothing is wrong'"
    )
    return violations


def _discover_production_modules() -> list[Path]:
    """Return every shipped non-test module under ``src/cadrumo``.

    The production half of the metadata scan's corpus. Test infrastructure is
    excluded by :func:`_is_test_infrastructure_path`, which is also what keeps
    :mod:`._marker_metadata_patterns` out: that module is the pattern table
    itself, so its own literals are scan DATA rather than a leak, and it splits
    every token across a concatenation for exactly that reason.

    Scoped to the shipped package rather than the whole repository. ``dev``,
    ``docs`` and ``packaging`` are development scaffolding whose own subject is
    frequently the authoring pipeline; the "Code Stands Alone" mandate is about
    what ships.
    """
    return sorted(
        path
        for path in scan_directory(_SRC_CADRUMO, pattern="*.py", recursive=True)
        if not _is_test_infrastructure_path(path)
    )


def _production_campaign_metadata_violations() -> list[str]:
    """Return production-scoped process-metadata hits across the shipped package."""
    violations: list[str] = []
    scanned = 0
    for path in _discover_production_modules():
        scanned += 1
        try:
            source = _source_for_path(path)
            ranges = _docstring_ranges(path)
            violations.extend(
                _campaign_metadata_violations_for_ranges(path, source, ranges, _PRODUCTION_SCOPED_PATTERNS),
            )
        except (SyntaxError, tokenize.TokenError):  # pragma: no cover - defensive
            continue
    # Floor the walk for the same reason the live-test-opt-in scan floors its
    # own: a package relocation would empty this corpus, and an empty corpus
    # reports precisely what a clean one reports.
    assert scanned > 1000, (
        f"scanned only {scanned} production modules; the production scan corpus collapsed, so an "
        "empty violation list would mean 'nothing was checked' rather than 'nothing is wrong'"
    )
    return violations


@cache
def _modules() -> tuple[Path, ...]:
    """Return the discovered test-module corpus, built once per process on first use.

    Not a module-level constant: :func:`_discover_test_modules` reads and
    ``ast.parse``s every ``test_*.py`` under all four roots, and a module-level
    binding pays that at import — which pytest does during collection, once per
    xdist worker, even for runs that deselect every test here. The cache keeps
    the corpus built exactly once, so every gate reads one consistent snapshot.
    """
    return tuple(_discover_test_modules())


def _unioned_marker_item_modules() -> tuple[Path, ...]:
    """Return every test module whose per-item marker union must be asserted.

    The per-item union is the marker set pytest actually resolves for a test:
    the module-level ``pytestmark`` combined with the test's own decorators. It
    is the only view that sees a module declaring one execution lane while a
    decorator supplies another — the collision the runtime collection hook
    rejects with a session-aborting :class:`pytest.UsageError`.

    That view previously covered only :func:`project_test_modules`
    (``dev`` and ``docs``), leaving every ``src/cadrumo`` test guaranteed only
    *emergently*: the module-level check plus the function-level ban together
    imply one lane per item, but only while both remain sighted. One of them
    went blind to alias-bound decorators, which is how a two-lane module
    reached main and aborted every collection. Asserting the union directly
    over the whole tree does not depend on that composition holding.
    """
    return tuple(sorted({*project_test_modules(), *_modules()}))


@pytest.fixture(scope="module")
def marker_policy_inventory() -> _MarkerPolicyInventory:
    campaign_metadata_violations: list[str] = []
    process_symbol_metadata_violations: list[str] = []
    function_level_marker_violations: list[str] = []
    live_env_runtime_violations: list[str] = []
    live_gate_helper_violations: list[str] = []
    retired_marker_violations: list[str] = []

    for module_path in _modules():
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
    for module_path in _modules():
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
    for module_path in _modules():
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
    for module_path in _modules():
        error = _placement_error(module_path)
        if error is not None:
            violations.append(f"{module_path.relative_to(_REPO_ROOT)}: {error}")
    assert not violations, "module pytestmark placement violations:\n" + "\n".join(violations)


def test_unioned_marker_item_inventory_covers_the_package_tree() -> None:
    """The per-item union is asserted over ``src/cadrumo``, not just ``dev``/``docs``.

    Proves the widening is not vacuous. The module that aborted every
    collection lived under ``src/cadrumo``, which the previous
    :func:`project_test_modules` inventory did not reach, so the check that
    would have caught it never ran on it.
    """
    inventory = _unioned_marker_item_modules()
    package_modules = [path for path in inventory if _SRC_CADRUMO in path.parents]

    assert package_modules, "the per-item union must reach the src/cadrumo tree"
    # The dev/docs coverage the check started with is retained, not traded away.
    assert set(project_test_modules()) <= set(inventory)


def test_every_test_item_resolves_to_single_execution_and_hex_marker() -> None:
    """Every test's resolved marker union carries exactly one execution lane.

    Asserted directly over the whole tree rather than inferred from the
    module-level and function-level checks agreeing; see
    :func:`_unioned_marker_item_modules` for why the emergent form was not
    enough.
    """
    violations: list[str] = []
    for module_path in _unioned_marker_item_modules():
        violations.extend(_project_test_item_marker_violations(module_path))
    assert not violations, "test item marker violations:\n" + "\n".join(violations)


def test_os_keychain_marker_membership_is_pinned() -> None:
    """The set of credential-store-bound tests is enumerated, not merely counted.

    Fails in BOTH directions. A test that gained the label without being enrolled
    here has left every automated lane unannounced, which is how the label becomes
    a way to silence a red custody test. A test enrolled here that no longer carries
    it has either been renamed or genuinely returned to the lanes, and the pin must
    be updated to say so rather than quietly describing a test that is gone.
    """
    found = frozenset(_os_keychain_marked_test_ids())
    unenrolled = sorted(found - _EXPECTED_OS_KEYCHAIN_TEST_IDS)
    absent = sorted(_EXPECTED_OS_KEYCHAIN_TEST_IDS - found)

    assert not unenrolled, (
        "these tests carry `os_keychain` without being enrolled in "
        "_EXPECTED_OS_KEYCHAIN_TEST_IDS, so they left every lane unannounced. "
        "Enrol them only if they genuinely cannot be proven without a credential "
        "store; otherwise remove the label:\n" + "\n".join(unenrolled)
    )
    assert not absent, (
        "these enrolled tests no longer carry `os_keychain` (renamed, removed, or "
        "returned to the default lanes) - update the pin to match:\n" + "\n".join(absent)
    )


def test_os_keychain_scan_sees_every_route_a_label_can_arrive_by() -> None:
    """Proves the membership scan is not vacuous.

    A pin backed by a blind scanner reports an empty set forever and silently
    permits the muting it exists to prevent. Each route below is asserted against a
    synthetic module, including the alias binding the execution-marker detector was
    once blind to.
    """
    tree = ast.parse(
        "import pytest\n"
        "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]\n"
        "_CUSTODY = pytest.mark.os_keychain\n"
        "@pytest.mark.os_keychain\n"
        "def test_function_level() -> None: ...\n"
        "@_CUSTODY\n"
        "def test_alias_bound() -> None: ...\n"
        "@pytest.mark.os_keychain\n"
        "class TestClassLevel:\n"
        "    def test_inherits_from_class() -> None: ...\n"
        "class TestPlain:\n"
        "    @pytest.mark.os_keychain\n"
        "    def test_method_level() -> None: ...\n"
        "    def test_unmarked() -> None: ...\n",
    )

    found = set(_os_keychain_ids_for_tree(tree, "synthetic.py", {"unit", "hex_core"}))

    assert found == {
        "synthetic.py::test_function_level",
        "synthetic.py::test_alias_bound",
        "synthetic.py::TestClassLevel::test_inherits_from_class",
        "synthetic.py::TestPlain::test_method_level",
    }
    # An unlabelled sibling must not be swept in, or the pin would demand entries
    # for tests that never left the lanes.
    assert "synthetic.py::TestPlain::test_unmarked" not in found
    # A module-level label reaches every test in the module.
    module_wide = set(_os_keychain_ids_for_tree(tree, "synthetic.py", {"unit", "hex_core", _OS_KEYCHAIN_MARKER}))
    assert "synthetic.py::TestPlain::test_unmarked" in module_wide


def test_no_function_level_access_or_domain_markers(marker_policy_inventory: _MarkerPolicyInventory) -> None:
    """Execution and hex markers are module-level only."""
    violations = marker_policy_inventory.function_level_marker_violations
    assert not violations, "function-level execution/hex markers are forbidden:\n" + "\n".join(violations)


def test_live_test_env_runtime_access_is_live_or_gate_scoped(marker_policy_inventory: _MarkerPolicyInventory) -> None:
    """Ordinary unit/domain tests must not depend on the live-test opt-in env var."""
    violations = marker_policy_inventory.live_env_runtime_violations
    assert not violations, (
        "runtime CADRUMO_LIVE_TESTS_ENABLED access is only allowed in aeat_live tests "
        "or focused access-gate tests:\n" + "\n".join(violations)
    )


def test_live_gate_helper_usage_is_aeat_live_marked(marker_policy_inventory: _MarkerPolicyInventory) -> None:
    """Tests that call the shared live gate helper must be ``aeat_live`` modules."""
    violations = marker_policy_inventory.live_gate_helper_violations
    assert not violations, "requires_live_enabled() used outside aeat_live tests:\n" + "\n".join(violations)


def test_root_policy_rejects_domain_local_banned_live_import_before_unit_deselection() -> None:
    """A domain-local live module cannot hide a banned import behind ``-m unit``.

    The generated module lives under ``src/cadrumo`` but outside the central
    harness, so this runs the installed repository-root conftest through the
    same discovery route a domain owner uses. ``-m unit`` would ordinarily
    deselect its ``aeat_live`` item; exit code 2 from the banned-import policy
    proves the root hook inspects it before marker selection can remove it.
    """
    with tempfile.TemporaryDirectory(prefix="s74-live-policy-", dir=_SRC_CADRUMO) as temporary_directory:
        module = _write_domain_local_live_module(
            Path(temporary_directory),
            "test_banned_live_import.py",
            "import unittest.mock\n"
            "import pytest\n\n"
            "pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_domain]\n\n\n"
            "def test_banned_import_never_executes() -> None:\n"
            "    raise AssertionError('collection policy should exit before this test can run')\n",
        )

        completed = _run_root_policy_subprocess("unit", module)
        output = completed.stdout + completed.stderr

    assert completed.returncode == 2, _subprocess_diagnostics(completed)
    assert "Banned import in live-marked file" in output, _subprocess_diagnostics(completed)
    assert "unittest.mock" in output, _subprocess_diagnostics(completed)


def test_root_policy_accepts_clean_domain_local_live_module_with_one_conftest_traversal() -> None:
    """A clean domain-local live module collects and sees one root policy hook.

    The child test interrogates pytest's installed hook registry from the real
    process. It therefore proves both that a clean live module remains
    executable and that exactly one conftest-owned collection traversal is
    installed: the repository-root owner, rather than a child duplicate.
    """
    root_policy_owner = _REPO_ROOT / "conftest.py"
    module_source = (
        "from pathlib import Path\n\n"
        "import pytest\n\n"
        "pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_domain]\n"
        f"EXPECTED_POLICY_OWNER = Path({str(root_policy_owner)!r})\n\n\n"
        "def test_clean_domain_local_live_control() -> None:\n"
        "    assert True\n\n\n"
        "def test_root_collection_policy_has_one_conftest_owner(pytestconfig: pytest.Config) -> None:\n"
        "    conftest_collection_hooks = [\n"
        "        Path(hook.function.__code__.co_filename).resolve()\n"
        "        for hook in pytestconfig.pluginmanager.hook.pytest_collection_modifyitems.get_hookimpls()\n"
        "        if Path(hook.function.__code__.co_filename).name == 'conftest.py'\n"
        "    ]\n"
        "    assert conftest_collection_hooks == [EXPECTED_POLICY_OWNER.resolve()]\n"
    )
    with tempfile.TemporaryDirectory(prefix="s74-live-policy-", dir=_SRC_CADRUMO) as temporary_directory:
        module = _write_domain_local_live_module(Path(temporary_directory), "test_clean_live_control.py", module_source)

        completed = _run_root_policy_subprocess("aeat_live", module)
        output = completed.stdout + completed.stderr

    assert completed.returncode == 0, _subprocess_diagnostics(completed)
    assert "2 passed" in output, "the clean live control did not execute both non-vacuity probes:\n" + output


def _write_domain_local_live_module(temporary_root: Path, filename: str, source: str) -> Path:
    """Create one temporary domain-local live module beneath the real source root."""
    module = temporary_root / "domain_local" / "tests" / filename
    module.parent.mkdir(parents=True)
    module.write_text(source, encoding="utf-8")
    return module


def _run_root_policy_subprocess(marker_expression: str, module: Path) -> subprocess.CompletedProcess[str]:
    """Collect one generated source module through the installed root policy."""
    return subprocess.run(  # noqa: S603 - fixed interpreter argv; marker expressions are local literals.
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-n0",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "-m",
            marker_expression,
            str(module),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_LIVE_POLICY_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _subprocess_diagnostics(completed: subprocess.CompletedProcess[str]) -> str:
    """Render child-process evidence when a policy expectation fails."""
    return f"returncode={completed.returncode}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"


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


#: Tests naming a live-transport ECB door that provably never issues a request,
#: keyed by ``(module path, enclosing function)`` rather than by line number so a
#: reordering cannot silently move the exemption onto a different test. Every
#: entry states why the door it opens cannot reach the network.
_LIVE_ECB_DOOR_EXEMPTIONS: dict[tuple[str, str], str] = {
    (
        "src/cadrumo/adapters/outbound/fx/tests/test_ecb_provider.py",
        "test_default_provider_is_cached",
    ): (
        "asserts the lru_cache identity contract of default_ecb_rate_provider only; it "
        "constructs the provider and never calls a lookup, so no transport is reached. The "
        "cached accessor takes no fetch argument, so injection cannot close this door."
    ),
}


def _live_ecb_door_violations() -> tuple[list[str], int]:
    """Return deterministic tests opening a default-transport ECB door, and the door count.

    A door is ``EcbReferenceRateProvider(...)`` built without an injected
    ``fetch=`` transport, or any call to ``default_ecb_rate_provider``. Both bind
    the live European Central Bank host, so a test opening one either declares
    ``aeat_live`` -- selected by the live lane alone -- or states in
    :data:`_LIVE_ECB_DOOR_EXEMPTIONS` why it cannot reach the network.
    """
    violations: list[str] = []
    doors = 0
    for path in _modules():
        tree = ast_for_path(path)
        if tree is None:
            continue
        relative = repo_relative(path)
        enclosing: dict[ast.AST, str] = {}
        for function in ast.walk(tree):
            if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                for descendant in ast.walk(function):
                    enclosing.setdefault(descendant, function.name)
        module_markers, _error = _extract_pytestmark_names(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = (qualified_name(node.func) or "").rsplit(".", 1)[-1]
            if callee == "EcbReferenceRateProvider":
                if any(keyword.arg == "fetch" for keyword in node.keywords):
                    continue
            elif callee != "default_ecb_rate_provider":
                continue
            doors += 1
            if "aeat_live" in module_markers:
                continue
            owner = enclosing.get(node, "<module level>")
            if _LIVE_ECB_DOOR_EXEMPTIONS.get((relative, owner)):
                continue
            violations.append(
                f"{relative}::{owner}:{node.lineno}: opens a default-transport ECB door "
                f"({callee}) without the `aeat_live` marker; inject a RateFetch transport "
                "(tests.ecb_stub.ecb_csv_fetch) or declare the test live"
            )
    return violations, doors


def test_deterministic_tests_do_not_open_a_live_ecb_transport_door() -> None:
    """Reaching the live ECB host is an ``aeat_live`` concern, not a production branch.

    The provider carries no test-awareness: its default transport reaches the
    European Central Bank unconditionally, because that is what the adapter is
    for. What holds a deterministic suite off that host is this marker contract
    plus the injectable ``RateFetch`` boundary.
    """
    violations, doors = _live_ecb_door_violations()

    assert doors, (
        "no ECB transport door was found in any test module; the provider was renamed or "
        "relocated, so an empty violation list would mean 'nothing was checked'"
    )
    assert not violations, "deterministic tests open a live ECB transport door:\n" + "\n".join(violations)


def test_every_live_ecb_door_exemption_still_names_a_real_test() -> None:
    """A stale exemption must fail rather than silently excusing nothing."""
    known = {
        (repo_relative(path), node.name)
        for path in _modules()
        if (tree := ast_for_path(path)) is not None
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    stale = sorted(entry for entry in _LIVE_ECB_DOOR_EXEMPTIONS if entry not in known)

    assert not stale, f"live-ECB door exemptions naming no such test: {stale}"
    assert all(_LIVE_ECB_DOOR_EXEMPTIONS.values()), "every live-ECB door exemption must state its reason"


def test_test_modules_live_under_tests_directories_and_use_test_prefix() -> None:
    """Every test module must live below a ``tests`` directory and use ``test_``."""
    scanned = [
        path for root in _TEST_TOPOLOGY_ROOTS for path in scan_directory(root, pattern="test_*.py", recursive=True)
    ]
    assert scanned, "the topology walk found no test modules; misplacement cannot be detected in an empty scan"
    misplaced = [
        str(path.relative_to(_REPO_ROOT))
        for root in _TEST_TOPOLOGY_ROOTS
        for path in scan_directory(root, pattern="test_*.py", recursive=True)
        if "tests" not in path.relative_to(_REPO_ROOT).parts
    ]
    underscore_prefixed = [
        str(path.relative_to(_REPO_ROOT))
        for root in _TEST_TOPOLOGY_ROOTS
        for path in scan_directory(root, pattern="_test_*.py", recursive=True)
    ]
    suffix_style = [
        str(path.relative_to(_REPO_ROOT))
        for root in _TEST_TOPOLOGY_ROOTS
        for path in scan_directory(root, pattern="*_test.py", recursive=True)
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


def test_campaign_metadata_patterns_discriminate() -> None:
    """Positive control: every campaign pattern matches its target and rejects a near-miss.

    Asserted against the compiled pattern directly rather than through the token
    walk, so a pattern that can no longer match is a failure here instead of a
    quiet clean result from the scan.
    """
    _assert_cases_discriminate(_CAMPAIGN_METADATA_CASES)


def test_process_symbol_patterns_discriminate() -> None:
    """Positive control: every process-symbol pattern matches and rejects its controls."""
    _assert_cases_discriminate(_PROCESS_SYMBOL_METADATA_CASES)


def test_retired_scrambled_plan_pattern_fails_the_replacement_controls() -> None:
    """The replaced pattern must fail the controls its replacement passes.

    Without this the repair is unfalsifiable: a control suite that both the old
    and the new pattern satisfy would prove only that the probes are weak. The
    transposed token matches none of the shapes the live pattern is required to
    catch, which is the measurement showing the entry was inert rather than
    merely differently spelled.
    """
    assert _PROCESS_PLAN_CASE in _PROCESS_SYMBOL_METADATA_CASES, (
        "the live plan case left the scanned table, so this control now compares "
        "the retired pattern against nothing the gate actually runs"
    )
    matched_by_retired = [
        probe for probe in _PROCESS_PLAN_CASE.must_match if _RETIRED_SCRAMBLED_PLAN_PATTERN.search(probe)
    ]

    assert not matched_by_retired, (
        "the retired pattern matched a control its replacement catches, so the "
        f"replacement is not a repair: {matched_by_retired}"
    )


def test_alias_bound_execution_marker_resolves_to_its_marker_name() -> None:
    """A marker bound to a constant is recognised through the bare decorator.

    Proves the detector is not vacuous. An alias-applied execution marker
    combines with the module-level ``pytestmark`` to give a test two execution
    markers, which the runtime collection hook rejects with a
    :class:`pytest.UsageError` that aborts the whole run before any test
    executes. This gate has to see the same marker set the hook does, so the
    resolution is asserted against the shape that caused that abort.
    """
    tree = ast.parse(
        "import pytest\n"
        "pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]\n"
        "_CLASSIFICATION = pytest.mark.unit\n"
        "@_CLASSIFICATION\n"
        "def test_case() -> None: ...\n",
    )
    aliases = _module_marker_aliases(tree)
    assert aliases == {"_CLASSIFICATION": "unit"}

    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
    assert _decorator_marker_names(function, aliases) == {"unit"}
    # Without the alias map the decorator is invisible: that blindness is what
    # let a two-lane module reach main and abort every collection.
    assert _decorator_marker_names(function) == set()


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


def test_production_source_does_not_cite_dated_vault_documents() -> None:
    """Shipped source must not name a dated record from this repo's own vault.

    The citation direction is one-way: a vault document cites code by locator,
    and code never cites the vault. Every other pattern in the table stays
    test-scoped; this check is the dated-document-stem family only, because
    that is the only shape measured at a zero false-positive rate over real
    production source.
    """
    violations = _production_campaign_metadata_violations()
    assert not violations, "production modules must not name a dated vault document:\n" + "\n".join(violations)


def test_production_scan_corpus_reaches_the_shipped_package() -> None:
    """Proves the production walk is a real corpus, not an empty one.

    An empty walk and a clean walk both report no violations, so the corpus is
    asserted directly: it must be large, it must exclude test infrastructure,
    and it must contain modules from the layers the mandate is about.
    """
    corpus = _discover_production_modules()

    assert len(corpus) > 1000, f"the production corpus collapsed to {len(corpus)} modules"
    assert not [path for path in corpus if _is_test_infrastructure_path(path)]
    # The pattern table is scan DATA, and its deliberately split literals would
    # otherwise read as leaks. It is excluded by being test infrastructure.
    assert _SRC_CADRUMO / "tests" / "_marker_metadata_patterns.py" not in corpus
    relative_parts = {path.relative_to(_SRC_CADRUMO).parts[0] for path in corpus}
    assert {"adapters", "application", "core", "domain", "entrypoints"} <= relative_parts


@pytest.mark.parametrize(
    ("citation", "expected_fragment"),
    [
        (
            "Governed by 2026-05-27-schema-hardening-casilla-continuity-contract-adr.",
            "continuity-contract-adr",
        ),
        ("Governed by .vault/adr/2026-05-27-schema-hardening-adr.md.", ".vault/adr/"),
        ("Rationale recorded under .vault/research/x.md.", ".vault/research/"),
    ],
)
def test_production_scan_detects_a_document_citation_in_production_source(
    citation: str,
    expected_fragment: str,
) -> None:
    """The widened scope detects in production what it previously could not see.

    Each case is a module docstring of exactly the shape that shipped in
    production source before this scope existed, run through the real scanner
    against a synthetic in-memory source rather than a planted file — a file
    written under ``src`` is capturable by a landing sweep even when it is new,
    and a probe that ships is worse than one that proves nothing.

    The same source scanned with an empty pattern selection is the negative
    control: the detection is the scope's doing, not the walker's.
    """
    probe_path = _SRC_CADRUMO / "domain" / "_scope_probe.py"
    source = f'"""Ledger binding contract.\n\n{citation}\n"""\n\nVALUE = 1\n'
    ranges = _docstring_ranges_for_tree(ast.parse(source))

    detected = _campaign_metadata_violations_for_ranges(probe_path, source, ranges, _PRODUCTION_SCOPED_PATTERNS)
    undetected = _campaign_metadata_violations_for_ranges(probe_path, source, ranges, ())

    assert len(detected) == 1, f"the production-scoped scan missed the citation: {detected}"
    assert expected_fragment in detected[0]
    assert not undetected, "the walker alone reported the citation, so the scope proves nothing"


def test_the_vault_path_family_is_load_bearing_in_the_production_scope() -> None:
    """A vault PATH with no dated stem is caught only because that family was widened.

    The isolating control. Most real citations carry both shapes at once — a
    vault directory path AND a dated document stem inside it — so such a probe
    is caught by the dated-stem family alone and proves nothing about this one.
    Stripping the date is what leaves the vault-path family as the only pattern
    that can fire.
    """
    probe_path = _SRC_CADRUMO / "domain" / "_scope_probe.py"
    source = '"""Invoice kind resolution.\n\nRationale under .vault/research/invoice-kind-notes.md.\n"""\n\nVALUE = 1\n'
    ranges = _docstring_ranges_for_tree(ast.parse(source))
    dated_stem_only = tuple(case.pattern for case in _PRODUCTION_SCOPED_CASES if ".vault/" not in case.pattern.pattern)

    detected = _campaign_metadata_violations_for_ranges(probe_path, source, ranges, _PRODUCTION_SCOPED_PATTERNS)
    without_the_family = _campaign_metadata_violations_for_ranges(probe_path, source, ranges, dated_stem_only)

    assert dated_stem_only, "the comparison subset is empty, so it cannot show the vault family carrying the catch"
    assert len(detected) == 1, f"the widened scope missed a bare vault-path citation: {detected}"
    assert not without_the_family, "the dated-stem family already caught it, so this probe isolates nothing"


def test_production_scan_ignores_prose_that_names_no_vault_document() -> None:
    """The vault-path family's reach stops at prose that cites nothing.

    Its near-misses are the whole reason the family is safe in production: a
    module may say a decision lives in the vault, or name a reference
    implementation, without naming a document. Asserted through the real
    scanner rather than against the bare pattern, so the noqa stripping and the
    docstring-range walk are in the path too.
    """
    probe_path = _SRC_CADRUMO / "domain" / "_scope_probe.py"
    source = (
        '"""Invoice kind resolution.\n'
        "\n"
        "This follows an open decision recorded in the vault; the reference\n"
        "implementation lives there too, and the audit trail explains why.\n"
        '"""\n'
        "\n"
        "VALUE = 1\n"
    )
    ranges = _docstring_ranges_for_tree(ast.parse(source))

    assert not _campaign_metadata_violations_for_ranges(probe_path, source, ranges, _PRODUCTION_SCOPED_PATTERNS)


def test_production_scope_excludes_the_families_that_false_fire_on_domain_prose() -> None:
    """The noisy families stayed test-scoped, and stayed live in tests.

    Each probe is asserted BOTH ways. Absent from production proves the
    widening was per-family rather than global; present in the full table
    proves the exclusion is a scope decision rather than a pattern that has
    quietly stopped matching anything at all.
    """
    test_scoped_only = (
        "the second wave landed",
        "phase-2 rollout",
        "landed in PR",
        "recorded in the ADR",
        "Ste" + "p 4 of the campaign",
        "carried in W01.P02.S03",
    )
    for probe in test_scoped_only:
        assert any(pattern.search(probe) for pattern in _CAMPAIGN_METADATA_PATTERNS), (
            f"{probe!r} is matched by no pattern at all, so its exclusion from production measures nothing"
        )
        assert not any(pattern.search(probe) for pattern in _PRODUCTION_SCOPED_PATTERNS), (
            f"{probe!r} reached the production scope; only the document-naming families were widened"
        )

    # Real domain prose from the shipped tree that the noisy families flag and
    # the production scope must never see: a Spanish tax-law citation, a
    # custody protocol describing itself as two-phase, and a bare constraint
    # statement naming no document.
    domain_prose = (
        "RD-ley 4/2024 phase-out",
        "Two-phase like :func:`recovery_create`",
        "needs a superseding ADR",
    )
    for probe in domain_prose:
        assert not any(pattern.search(probe) for pattern in _PRODUCTION_SCOPED_PATTERNS), (
            f"legitimate domain prose {probe!r} would be reported against production source"
        )


def test_production_scoped_cases_are_derived_from_the_declared_scope() -> None:
    """The production subset is the table filtered by its own scope field.

    A hand-maintained second list is the drift this derivation removes, and
    the drift is silent in the direction that matters: a case widened at its
    declaration but missing from the subset is never applied to production and
    reports a clean tree.
    """
    assert _PRODUCTION_SCOPED_CASES, "no case is production-scoped, so the production scan is vacuous"
    assert set(_PRODUCTION_SCOPED_CASES) <= set(_CAMPAIGN_METADATA_CASES)
    assert set(_PRODUCTION_SCOPED_CASES) == {
        case for case in _CAMPAIGN_METADATA_CASES if case.scope is _MarkerScanScope.TEST_AND_PRODUCTION_MODULES
    }
    # A new case arrives at the narrower reach unless its author says otherwise.
    assert _PatternCase(re.compile("x"), ("x",), ("y",)).scope is _MarkerScanScope.TEST_MODULES


def test_discovery_found_modules() -> None:
    """Guardrail: the walker must discover at least one test module."""
    assert _modules(), "no test modules discovered - glob roots or layout changed"
