"""Detector teeth for production development-metastate declarations."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..production_metastate import SHIPPED_ROOT, production_metastate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _module(root: Path, source: str) -> Path:
    path = root / "policy.py"
    path.write_text(source, encoding="utf-8")
    return root


def test_shipped_production_has_no_development_metastate() -> None:
    assert production_metastate(SHIPPED_ROOT) == []


def test_detector_catches_the_removed_stub_census(tmp_path: Path) -> None:
    root = _module(
        tmp_path,
        "STUB_MODELO_LOCALE_KEYS = {'210': 'refused'}\n"
        "STUB_ONLY_MODELOS = frozenset(STUB_MODELO_LOCALE_KEYS)\n",
    )

    assert production_metastate(root) == [
        "policy.py:1: progress census STUB_MODELO_LOCALE_KEYS",
        "policy.py:2: progress census STUB_ONLY_MODELOS",
    ]


def test_detector_catches_the_removed_engine_live_switch(tmp_path: Path) -> None:
    root = _module(
        tmp_path,
        "class Settings:\n"
        "    cadrumo_m210_engine_live: bool = False\n",
    )

    assert production_metastate(root) == [
        "policy.py:2: engine rollout switch cadrumo_m210_engine_live",
    ]


def test_domain_lifecycle_state_is_not_development_progress(tmp_path: Path) -> None:
    root = _module(tmp_path, "TRANSACTION_LIFECYCLE_STATES = ('active', 'archived')\n")

    assert production_metastate(root) == []


def test_detector_catches_review_residue_attached_to_product_authority(tmp_path: Path) -> None:
    root = _module(
        tmp_path,
        "class ValidatedRegistryAuthority:\n"
        "    _supported_filing_year_gaps: tuple[object, ...]\n",
    )

    assert production_metastate(root) == [
        "policy.py:2: authority review residue _supported_filing_year_gaps",
    ]


def test_detector_catches_development_status_on_executable_declaration(tmp_path: Path) -> None:
    root = _module(
        tmp_path,
        "def staged_classifier() -> bool:\n"
        '    \"\"\"DECLARED, NOT YET REACHED. No product path calls this.\"\"\"\n'
        "    return False\n",
    )

    assert production_metastate(root) == [
        "policy.py:1: development-status declaration staged_classifier (DECLARED, NOT YET REACHED)",
    ]


def test_detector_ignores_product_language_that_is_not_a_development_status(tmp_path: Path) -> None:
    root = _module(
        tmp_path,
        "def declared_amount() -> int:\n"
        '    \"\"\"Return the amount declared by the operator.\"\"\"\n'
        "    return 0\n",
    )

    assert production_metastate(root) == []


def test_detector_catches_module_and_nested_development_statuses(tmp_path: Path) -> None:
    root = _module(
        tmp_path,
        '\"\"\"IMPLEMENTED, NOT YET REACHED. Module staging note.\"\"\"\n'
        "class Policy:\n"
        "    def staged_method(self) -> bool:\n"
        '        \"\"\"DECLARED, NOT YET REACHED. Method staging note.\"\"\"\n'
        "        return False\n",
    )

    assert production_metastate(root) == [
        "policy.py:1: development-status declaration <module> (IMPLEMENTED, NOT YET REACHED)",
        "policy.py:3: development-status declaration staged_method (DECLARED, NOT YET REACHED)",
    ]
