"""Unit tests for the usage-ratio persistence service (#259)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ..categories import SpendingCategory
from . import (
    UsageRatioPersistenceError,
    UsageRatioProfile,
    load_usage_ratios,
    save_usage_ratios,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]


def test_load_missing_returns_empty(tmp_path: Path) -> None:
    """A missing file yields an empty profile (the virgin state)."""
    target = tmp_path / "missing.json"
    assert not target.exists()
    assert load_usage_ratios(target) == UsageRatioProfile()


def test_load_malformed_raises_persistence_error(tmp_path: Path) -> None:
    """Invalid JSON surfaces as :class:`UsageRatioPersistenceError`."""
    target = tmp_path / "bad.json"
    target.write_text("{", encoding="utf-8")
    with pytest.raises(UsageRatioPersistenceError):
        load_usage_ratios(target)


def test_load_invalid_schema_raises_persistence_error(tmp_path: Path) -> None:
    """JSON that fails pydantic validation surfaces as the same error type."""
    target = tmp_path / "invalid-schema.json"
    target.write_text('{"ratios": {"telefonia_turbo": "0.5"}}', encoding="utf-8")
    with pytest.raises(UsageRatioPersistenceError):
        load_usage_ratios(target)


def test_load_directory_target_raises_persistence_error(tmp_path: Path) -> None:
    """Pointing the loader at a directory triggers an OSError path."""
    target = tmp_path / "ratios-dir"
    target.mkdir()
    with pytest.raises(UsageRatioPersistenceError):
        load_usage_ratios(target)


def test_save_creates_missing_parent_directory(tmp_path: Path) -> None:
    """``save_usage_ratios`` mkdirs parents when absent."""
    target = tmp_path / "a" / "b" / "ratios.json"
    profile = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    save_usage_ratios(profile, target)
    assert target.exists()


def test_save_round_trips(tmp_path: Path) -> None:
    """A saved profile reloads byte-for-byte identical."""
    target = tmp_path / "ratios.json"
    profile = UsageRatioProfile(
        ratios={
            SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21"),
            SpendingCategory.TELEFONIA_MOVIL: Decimal("0.6"),
        }
    )
    save_usage_ratios(profile, target)
    assert load_usage_ratios(target) == profile


def test_save_replaces_previous_payload(tmp_path: Path) -> None:
    """Successive saves replace the payload without leaving ``.tmp`` debris."""
    target = tmp_path / "ratios.json"
    first = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    second = first.with_ratio(SpendingCategory.TELEFONIA_MOVIL, Decimal("0.6"))
    save_usage_ratios(first, target)
    save_usage_ratios(second, target)
    assert load_usage_ratios(target) == second
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_to_unwritable_parent_raises(tmp_path: Path) -> None:
    """Target whose parent is a file triggers :class:`UsageRatioPersistenceError`."""
    parent_as_file = tmp_path / "not-a-dir"
    parent_as_file.write_text("", encoding="utf-8")
    target = parent_as_file / "ratios.json"
    profile = UsageRatioProfile()
    with pytest.raises(UsageRatioPersistenceError):
        save_usage_ratios(profile, target)
    assert list(tmp_path.glob("*.tmp")) == []
