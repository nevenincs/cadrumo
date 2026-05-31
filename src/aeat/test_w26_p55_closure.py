"""Aggregate closure test for W26.P55 (S654-S656).

Verifies that:
- The type-ignore rationale ratchet (S654) is importable and passes.
- The ratchet module docstring documents the ``TYPE-IGNORE-RATIONALE-*`` convention (S655).
- Prior-wave inventory ratchets remain green.
"""

from __future__ import annotations

import importlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


# ---------------------------------------------------------------------------
# S654 / S655 — type-ignore ratchet importable, convention documented, passes
# ---------------------------------------------------------------------------


def test_s654_type_ignore_rationale_inventory_importable() -> None:
    """test_type_ignore_rationale_inventory must import cleanly."""
    mod = importlib.import_module("aeat.test_type_ignore_rationale_inventory")
    assert hasattr(mod, "test_no_new_type_ignore_without_rationale"), (
        "Expected ratchet function not found in test_type_ignore_rationale_inventory"
    )


def test_s655_docstring_documents_convention() -> None:
    """The ratchet module docstring must contain the TYPE-IGNORE-RATIONALE- token (S655)."""
    mod = importlib.import_module("aeat.test_type_ignore_rationale_inventory")
    doc = mod.__doc__ or ""
    assert "TYPE-IGNORE-RATIONALE-" in doc, (
        "test_type_ignore_rationale_inventory.__doc__ must document the "
        "TYPE-IGNORE-RATIONALE-* convention per S655 mandate."
    )


def test_s654_ratchet_passes() -> None:
    """The type-ignore ratchet must pass (no new drift beyond the enrolled allowlist)."""
    mod = importlib.import_module("aeat.test_type_ignore_rationale_inventory")
    mod.test_no_new_type_ignore_without_rationale()


# ---------------------------------------------------------------------------
# Prior-wave inventory ratchets — must remain green
# ---------------------------------------------------------------------------


def _run_all_test_fns(module_name: str) -> None:
    """Import *module_name* and invoke every ``test_*`` callable."""
    mod = importlib.import_module(module_name)
    test_fns = [v for k, v in vars(mod).items() if k.startswith("test_") and callable(v)]
    assert test_fns, f"No test_ function found in {module_name}"
    for fn in test_fns:
        fn()


def test_prior_wave_utf8_enrollment_inventory() -> None:
    """W11 UTF-8 enrollment ratchet must remain green."""
    _run_all_test_fns("aeat.test_utf8_enrollment_inventory")


def test_prior_wave_cast_rationale_inventory() -> None:
    """Cast-rationale ratchet must remain green."""
    _run_all_test_fns("aeat.test_cast_rationale_inventory")


def test_prior_wave_latin1_encoding_constant_enrollment() -> None:
    """Latin-1 encoding constant enrollment ratchet must remain green."""
    _run_all_test_fns("aeat.test_latin1_encoding_constant_enrollment")


def test_prior_wave_enum_constant_extraction_inventory() -> None:
    """Enum constant extraction ratchet must remain green."""
    _run_all_test_fns("aeat.test_enum_constant_extraction_inventory")


def test_prior_wave_any_param_rationale_inventory() -> None:
    """Parameter-Any rationale ratchet (W21) must remain green."""
    _run_all_test_fns("aeat.test_any_param_rationale_inventory")


def test_prior_wave_mock_inventory() -> None:
    """Mock inventory ratchet must remain green."""
    _run_all_test_fns("aeat.test_mock_inventory")
