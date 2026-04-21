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


def test_load_invalid_schema_surfaces_pydantic_detail(tmp_path: Path) -> None:
    """JSON that fails pydantic validation surfaces with the offending path.

    Hand-edit errors (the primary cause of invalid profile files) must name
    the field and reason, not just ``invalid usage-ratio profile JSON``.
    """
    target = tmp_path / "invalid-schema.json"
    target.write_text('{"ratios": {"telefonia_turbo": "0.5"}}', encoding="utf-8")
    with pytest.raises(UsageRatioPersistenceError) as excinfo:
        load_usage_ratios(target)
    # The field path and at least a pydantic reason fragment must appear.
    message = str(excinfo.value)
    assert "ratios" in message
    assert "telefonia_turbo" in message


def test_load_out_of_range_surfaces_pydantic_detail(tmp_path: Path) -> None:
    """Hand-edited out-of-range ratio surfaces the offending category."""
    target = tmp_path / "out-of-range.json"
    target.write_text(
        '{"ratios": {"suministros_home_office_luz": "1.5"}}',
        encoding="utf-8",
    )
    with pytest.raises(UsageRatioPersistenceError) as excinfo:
        load_usage_ratios(target)
    message = str(excinfo.value)
    assert "suministros_home_office_luz" in message
    assert "[0, 1]" in message


def test_load_unknown_key_names_only_eligible_categories(tmp_path: Path) -> None:
    """Hand-edited unknown key must surface the twelve eligible categories,
    NOT pydantic's default 38-entry ``SpendingCategory`` dump."""
    target = tmp_path / "unknown-key.json"
    target.write_text('{"ratios": {"foo": "0.5"}}', encoding="utf-8")
    with pytest.raises(UsageRatioPersistenceError) as excinfo:
        load_usage_ratios(target)
    message = str(excinfo.value)
    assert "unknown ratio key" in message
    assert "eligible categories are:" in message
    # Eligible categories must be listed; ineligible ones must not.
    assert "suministros_home_office_luz" in message
    assert "material_oficina" not in message
    assert "cuotas_colegiales" not in message


def test_load_tolerates_utf8_bom(tmp_path: Path) -> None:
    """Files saved with a UTF-8 BOM (Windows Notepad default) must load cleanly."""
    target = tmp_path / "with-bom.json"
    target.write_bytes(b"\xef\xbb\xbf" + b'{"ratios": {"suministros_home_office_luz": "0.21"}}')
    profile = load_usage_ratios(target)
    assert profile.ratios[SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ] == Decimal("0.21")


def test_load_ineligible_category_surfaces_pydantic_detail(tmp_path: Path) -> None:
    """Hand-smuggled ineligible category surfaces as a named error."""
    target = tmp_path / "ineligible.json"
    target.write_text(
        '{"ratios": {"material_oficina": "0.3"}}',
        encoding="utf-8",
    )
    with pytest.raises(UsageRatioPersistenceError) as excinfo:
        load_usage_ratios(target)
    message = str(excinfo.value)
    assert "material_oficina" in message
    assert "USAGE_RATIO" in message


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


def test_save_preserves_prior_target_on_mid_write_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Atomicity: if ``os.replace`` fails, the existing target is unchanged.

    Pins the safety property that a mid-save crash cannot truncate Kent's
    existing ratios, and that the temp file is cleaned up.
    """
    target = tmp_path / "ratios.json"
    initial = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    save_usage_ratios(initial, target)
    original_bytes = target.read_bytes()

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated mid-write failure")

    monkeypatch.setattr("aeat.financial.usage_ratios._service.os.replace", _boom)

    replacement = initial.with_ratio(SpendingCategory.TELEFONIA_MOVIL, Decimal("0.6"))
    with pytest.raises(UsageRatioPersistenceError):
        save_usage_ratios(replacement, target)

    assert target.read_bytes() == original_bytes, "target was corrupted mid-save"
    assert list(tmp_path.glob("*.tmp")) == [], "temp file leaked after failure"


def test_save_payload_is_indented_for_git_diff_readability(tmp_path: Path) -> None:
    """Pin the two-space-indented JSON shape Kent relies on for diffing."""
    target = tmp_path / "ratios.json"
    profile = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    save_usage_ratios(profile, target)
    payload = target.read_text(encoding="utf-8")
    # Indent=2 means the ratios dict opens on a new line with two-space prefix.
    assert "\n  " in payload, f"payload is not indented: {payload!r}"


def test_save_writes_pure_utf8_bytes(tmp_path: Path) -> None:
    """The on-disk bytes must decode cleanly as UTF-8 for portable editing."""
    target = tmp_path / "ratios.json"
    profile = UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: Decimal("0.21")})
    save_usage_ratios(profile, target)
    # Round-trip via explicit utf-8 decode without the BOM-strip helper.
    raw_bytes = target.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "we must not write a BOM"
    raw_bytes.decode("utf-8")  # raises on non-utf-8


def test_load_value_error_prefix_is_stripped_from_summary(tmp_path: Path) -> None:
    """Pydantic's ``Value error, `` prefix must not leak into Kent's output."""
    target = tmp_path / "out-of-range.json"
    target.write_text(
        '{"ratios": {"suministros_home_office_luz": "1.5"}}',
        encoding="utf-8",
    )
    with pytest.raises(UsageRatioPersistenceError) as excinfo:
        load_usage_ratios(target)
    message = str(excinfo.value)
    assert "Value error, " not in message
    # But the substantive reason is preserved.
    assert "must be in [0, 1]" in message


def test_save_to_unwritable_parent_surfaces_os_detail(tmp_path: Path) -> None:
    """Target whose parent is a file triggers :class:`UsageRatioPersistenceError`
    and includes the OSError class name so Kent can diagnose."""
    parent_as_file = tmp_path / "not-a-dir"
    parent_as_file.write_text("", encoding="utf-8")
    target = parent_as_file / "ratios.json"
    profile = UsageRatioProfile()
    with pytest.raises(UsageRatioPersistenceError) as excinfo:
        save_usage_ratios(profile, target)
    # The wrapped OSError class name must appear in the message.
    message = str(excinfo.value)
    assert "Error" in message  # e.g. FileExistsError, NotADirectoryError
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_target_is_existing_directory_raises(tmp_path: Path) -> None:
    """Pointing ``target`` at an existing directory surfaces cleanly.

    On POSIX ``os.replace`` raises ``IsADirectoryError`` and on Windows
    ``PermissionError`` — both subclasses of ``OSError``, wrapped into
    :class:`UsageRatioPersistenceError`.
    """
    target = tmp_path / "ratios-as-dir"
    target.mkdir()
    profile = UsageRatioProfile()
    with pytest.raises(UsageRatioPersistenceError):
        save_usage_ratios(profile, target)
    assert list(tmp_path.glob("*.tmp")) == []
