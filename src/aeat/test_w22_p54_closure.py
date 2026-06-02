"""Aggregate closure test for W22.P54 (S651-S653).

Verifies that the LOGGING-STDLIB-RATIONALE-TYPE-CHECKING-ONLY marker
landed in the correct position (S651), zero unittest.mock.patch usage
remains in test_except_clause_narrowing.py (S652), the W21
parameter-Any ratchet remains green (S649 carry-forward), and prior-wave
inventory ratchets remain green.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pathlib
from collections.abc import Callable, Mapping

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_ROOT = pathlib.Path(__file__).parent

_AST_CACHE: Mapping[pathlib.Path, ast.AST] | None = None


def _build_ast_cache() -> Mapping[pathlib.Path, ast.AST]:
    """Mirror the conftest ``source_tree_ast`` fixture for imperative callers.

    Closure tests invoke ratchet functions via ``importlib + getattr`` and
    therefore bypass pytest's fixture injection. The S807 migration added a
    ``source_tree_ast`` parameter to several ratchet functions; this helper
    rebuilds the same cache once per process so imperative invocation still
    works.
    """
    global _AST_CACHE
    if _AST_CACHE is not None:
        return _AST_CACHE
    cache: dict[pathlib.Path, ast.AST] = {}
    for path in _SRC_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts or ".venv" in path.parts or "_data" in path.parts:
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            cache[path] = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError):
            continue
    _AST_CACHE = cache
    return cache


def _invoke_test_fn(fn: Callable[..., None]) -> None:
    """Invoke a ratchet test function, supplying ``source_tree_ast`` when required."""
    parameters = inspect.signature(fn).parameters
    if "source_tree_ast" in parameters:
        fn(_build_ast_cache())
    else:
        fn()


_BROWSER_STAGE = _SRC_ROOT / "adapters" / "outbound" / "aeat" / "sede" / "_browser_stage.py"
_NARROWING_TEST = _SRC_ROOT / "test_except_clause_narrowing.py"

_MARKER_TOKEN = "LOGGING-STDLIB-RATIONALE-TYPE-CHECKING-ONLY"


# ---------------------------------------------------------------------------
# S651 — marker token present within 3 lines preceding TYPE_CHECKING block
# ---------------------------------------------------------------------------


def test_s651_logging_rationale_marker_precedes_type_checking_block() -> None:
    """LOGGING-STDLIB-RATIONALE-TYPE-CHECKING-ONLY must appear within 3 lines before `if TYPE_CHECKING:`."""
    lines = _BROWSER_STAGE.read_text(encoding="utf-8").splitlines()
    type_checking_indices = [i for i, line in enumerate(lines) if line.strip().startswith("if TYPE_CHECKING:")]
    assert type_checking_indices, "No `if TYPE_CHECKING:` block found in _browser_stage.py"

    # For each TYPE_CHECKING block, check the 3 lines immediately preceding it.
    found = False
    for idx in type_checking_indices:
        window = lines[max(0, idx - 3) : idx]
        if any(_MARKER_TOKEN in line for line in window):
            found = True
            break

    assert found, f"Expected {_MARKER_TOKEN!r} within 3 lines before `if TYPE_CHECKING:` in _browser_stage.py"


# ---------------------------------------------------------------------------
# S652 — zero unittest.mock / patch.object usage in test_except_clause_narrowing.py
# ---------------------------------------------------------------------------


def test_s652_no_unittest_mock_in_narrowing_tests() -> None:
    """No `unittest.mock` or `patch.object(` must appear in test_except_clause_narrowing.py."""
    text = _NARROWING_TEST.read_text(encoding="utf-8")
    assert "unittest.mock" not in text, (
        "Found `unittest.mock` in test_except_clause_narrowing.py — mock import not fully removed"
    )
    assert "patch.object(" not in text, (
        "Found `patch.object(` in test_except_clause_narrowing.py — patch usage not fully removed"
    )


# ---------------------------------------------------------------------------
# W21 parameter-Any ratchet carry-forward (S649)
# ---------------------------------------------------------------------------


def test_w21_any_param_rationale_inventory_ratchet() -> None:
    """W21 parameter-Any ratchet must remain green."""
    mod = importlib.import_module("aeat.test_any_param_rationale_inventory")
    assert hasattr(mod, "test_no_new_any_param_without_rationale"), (
        "Expected ratchet function not found in test_any_param_rationale_inventory"
    )
    _invoke_test_fn(mod.test_no_new_any_param_without_rationale)


# ---------------------------------------------------------------------------
# Prior-wave inventory ratchets — must remain green
# ---------------------------------------------------------------------------


def _run_ratchet_module(module_name: str, func_name: str) -> None:
    """Import *module_name* and call *func_name*, re-raising any AssertionError."""
    mod = importlib.import_module(module_name)
    fn = getattr(mod, func_name, None)
    assert fn is not None, f"{func_name} not found in {module_name}"
    _invoke_test_fn(fn)


def _run_all_test_fns(module_name: str) -> None:
    """Import *module_name* and run every ``test_`` function in it."""
    mod = importlib.import_module(module_name)
    test_fns = [v for k, v in vars(mod).items() if k.startswith("test_") and callable(v)]
    assert test_fns, f"No test_ function found in {module_name}"
    for fn in test_fns:
        _invoke_test_fn(fn)


def test_prior_wave_utf8_enrollment_inventory() -> None:
    """W11 UTF-8 enrollment ratchet must remain green."""
    _run_ratchet_module(
        "aeat.test_utf8_enrollment_inventory",
        "test_no_bare_utf8_literals_in_production_files",
    )


def test_prior_wave_cast_rationale_inventory() -> None:
    """Cast-rationale ratchet must remain green."""
    _run_all_test_fns("aeat.test_cast_rationale_inventory")


def test_prior_wave_latin1_encoding_constant_enrollment() -> None:
    """Latin-1 encoding constant enrollment ratchet must remain green."""
    _run_all_test_fns("aeat.test_latin1_encoding_constant_enrollment")


def test_prior_wave_enum_constant_extraction_inventory() -> None:
    """Enum constant extraction ratchet must remain green."""
    _run_all_test_fns("aeat.test_enum_constant_extraction_inventory")


def test_prior_wave_mock_inventory() -> None:
    """Mock inventory ratchet must remain green."""
    _run_all_test_fns("aeat.test_mock_inventory")


def test_prior_wave_no_skip_xfail() -> None:
    """No-skip/xfail ratchet must remain green."""
    _run_all_test_fns("aeat.test_no_skip_xfail")
