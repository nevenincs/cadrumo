"""Aggregate closure test for W21.P53 (S646-S650).

Verifies that all marker tokens landed in the correct files (S646-S648),
the parameter-Any ratchet (S649) is importable and passes, and prior-wave
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
_ADAPTERS_GOOGLE = _SRC_ROOT / "adapters" / "outbound" / "google"

_AST_CACHE: Mapping[pathlib.Path, ast.AST] | None = None


def _build_ast_cache() -> Mapping[pathlib.Path, ast.AST]:
    """Mirror the conftest ``source_tree_ast`` fixture for imperative callers."""
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


# ---------------------------------------------------------------------------
# S646 — core/setup_answers.py markers
# ---------------------------------------------------------------------------


def test_s646_kwargs_any_rationale_profile_wizard_flow_circular() -> None:
    """KWARGS-ANY-RATIONALE-PROFILE-WIZARD-FLOW-CIRCULAR must appear in core/setup_answers.py."""
    target = _SRC_ROOT / "core" / "setup_answers.py"
    text = target.read_text(encoding="utf-8")
    assert "KWARGS-ANY-RATIONALE-PROFILE-WIZARD-FLOW-CIRCULAR" in text, (
        f"Expected marker token not found in {target.relative_to(_SRC_ROOT)}"
    )


# ---------------------------------------------------------------------------
# S647 — core/wizard_catalogue.py marker
# ---------------------------------------------------------------------------


def test_s647_kwargs_any_rationale_catalogue_wizard_flow_circular() -> None:
    """KWARGS-ANY-RATIONALE-CATALOGUE-WIZARD-FLOW-CIRCULAR must appear in core/wizard_catalogue.py."""
    target = _SRC_ROOT / "core" / "wizard_catalogue.py"
    text = target.read_text(encoding="utf-8")
    assert "KWARGS-ANY-RATIONALE-CATALOGUE-WIZARD-FLOW-CIRCULAR" in text, (
        f"Expected marker token not found in {target.relative_to(_SRC_ROOT)}"
    )


# ---------------------------------------------------------------------------
# S648 — Google adapter markers
# ---------------------------------------------------------------------------


def test_s648_adapter_internal_alias_rationale_google_resource_apply() -> None:
    """ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE must appear in _calc_sheets_apply.py."""
    target = _ADAPTERS_GOOGLE / "_calc_sheets_apply.py"
    text = target.read_text(encoding="utf-8")
    assert "ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE" in text, (
        f"Expected marker token not found in {target.relative_to(_SRC_ROOT)}"
    )


def test_s648_adapter_internal_alias_rationale_google_resource_pull() -> None:
    """ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE must appear in _calc_sheets_pull.py."""
    target = _ADAPTERS_GOOGLE / "_calc_sheets_pull.py"
    text = target.read_text(encoding="utf-8")
    assert "ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE" in text, (
        f"Expected marker token not found in {target.relative_to(_SRC_ROOT)}"
    )


# ---------------------------------------------------------------------------
# S649 — parameter-Any ratchet importable and passes
# ---------------------------------------------------------------------------


def test_s649_any_param_rationale_inventory_importable_and_passes() -> None:
    """test_any_param_rationale_inventory must import cleanly and its ratchet must pass."""
    mod = importlib.import_module("aeat.test_any_param_rationale_inventory")
    assert hasattr(mod, "test_no_new_any_param_without_rationale"), (
        "Expected ratchet function not found in test_any_param_rationale_inventory"
    )
    # Run the ratchet directly — if it raises AssertionError the Step failed.
    _invoke_test_fn(mod.test_no_new_any_param_without_rationale)


# ---------------------------------------------------------------------------
# Prior-wave inventory ratchets — must remain green
# ---------------------------------------------------------------------------


def _run_ratchet_module(module_name: str, func_name: str) -> None:
    """Import *module_name* and call *func_name*, re-raising any AssertionError."""
    mod = importlib.import_module(module_name)
    fn = getattr(mod, func_name, None)
    assert fn is not None, f"{func_name} not found in {module_name}"
    fn()


def test_prior_wave_utf8_enrollment_inventory() -> None:
    """W11 UTF-8 enrollment ratchet must remain green."""
    _run_ratchet_module(
        "aeat.test_utf8_enrollment_inventory",
        "test_no_bare_utf8_literals_in_production_files",
    )


def test_prior_wave_cast_rationale_inventory() -> None:
    """Cast-rationale ratchet must remain green."""
    mod = importlib.import_module("aeat.test_cast_rationale_inventory")
    # Find the single test function — name may vary across campaigns.
    test_fns = [v for k, v in vars(mod).items() if k.startswith("test_") and callable(v)]
    assert test_fns, "No test_ function found in test_cast_rationale_inventory"
    for fn in test_fns:
        _invoke_test_fn(fn)


def test_prior_wave_latin1_encoding_constant_enrollment() -> None:
    """Latin-1 encoding constant enrollment ratchet must remain green."""
    mod = importlib.import_module("aeat.test_latin1_encoding_constant_enrollment")
    test_fns = [v for k, v in vars(mod).items() if k.startswith("test_") and callable(v)]
    assert test_fns, "No test_ function found in test_latin1_encoding_constant_enrollment"
    for fn in test_fns:
        _invoke_test_fn(fn)


def test_prior_wave_enum_constant_extraction_inventory() -> None:
    """Enum constant extraction ratchet must remain green."""
    mod = importlib.import_module("aeat.test_enum_constant_extraction_inventory")
    test_fns = [v for k, v in vars(mod).items() if k.startswith("test_") and callable(v)]
    assert test_fns, "No test_ function found in test_enum_constant_extraction_inventory"
    for fn in test_fns:
        _invoke_test_fn(fn)


def test_prior_wave_mock_inventory() -> None:
    """Mock inventory ratchet must remain green."""
    mod = importlib.import_module("aeat.test_mock_inventory")
    test_fns = [v for k, v in vars(mod).items() if k.startswith("test_") and callable(v)]
    assert test_fns, "No test_ function found in test_mock_inventory"
    for fn in test_fns:
        _invoke_test_fn(fn)


def test_prior_wave_no_skip_xfail() -> None:
    """No-skip/xfail ratchet must remain green."""
    mod = importlib.import_module("aeat.test_no_skip_xfail")
    test_fns = [v for k, v in vars(mod).items() if k.startswith("test_") and callable(v)]
    assert test_fns, "No test_ function found in test_no_skip_xfail"
    for fn in test_fns:
        _invoke_test_fn(fn)
