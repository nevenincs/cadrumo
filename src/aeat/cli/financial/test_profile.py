"""Unit tests for the `aeat financial profile` command group (#259)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from .. import app as root_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]

_RUNNER = CliRunner()


@pytest.fixture(autouse=True)
def _isolate_usage_ratios_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point every test at a fresh tmp-path-backed usage-ratios file."""
    target = tmp_path / "usage-ratios.json"
    monkeypatch.setenv("AEAT_USAGE_RATIOS_PATH", str(target))
    yield target


def _invoke(*args: str):
    return _RUNNER.invoke(root_app, ["financial", "profile", *args])


def test_list_on_empty_profile_reports_no_ratios() -> None:
    result = _invoke("ratios", "list")
    assert result.exit_code == 0, result.output
    assert "No usage ratios configured." in result.output


def test_set_ratio_single_category_persists_and_lists() -> None:
    set_result = _invoke("set-ratio", "suministros_home_office_luz", "0.21")
    assert set_result.exit_code == 0, set_result.output
    assert "set suministros_home_office_luz = 0.21" in set_result.output

    list_result = _invoke("ratios", "list")
    assert list_result.exit_code == 0, list_result.output
    assert "suministros_home_office_luz" in list_result.output
    assert "usage_ratio_home_area" in list_result.output
    assert "0.21" in list_result.output
    assert "0.3" in list_result.output


def test_set_ratio_home_office_family_alias_sets_six_categories() -> None:
    result = _invoke("set-ratio", "home_office_area", "0.21")
    assert result.exit_code == 0, result.output
    for category in (
        "arrendamiento_vivienda_afecto",
        "suministros_home_office_luz",
        "suministros_home_office_agua",
        "suministros_home_office_gas",
        "suministros_home_office_internet",
        "telefonia_fija",
    ):
        assert f"set {category} = 0.21" in result.output

    list_result = _invoke("ratios", "list")
    assert list_result.exit_code == 0
    for category in (
        "arrendamiento_vivienda_afecto",
        "suministros_home_office_luz",
        "suministros_home_office_agua",
        "suministros_home_office_gas",
        "suministros_home_office_internet",
        "telefonia_fija",
    ):
        assert category in list_result.output


def test_set_ratio_mileage_business_alias_sets_five_vehicle_categories() -> None:
    result = _invoke("set-ratio", "mileage_business", "0.6")
    assert result.exit_code == 0, result.output
    for category in (
        "vehiculo_combustible",
        "vehiculo_mantenimiento",
        "vehiculo_seguro",
        "vehiculo_peaje",
        "vehiculo_parking",
    ):
        assert f"set {category} = 0.6" in result.output


def test_set_ratio_ineligible_category_rejected_with_hint() -> None:
    result = _invoke("set-ratio", "material_oficina", "0.5")
    assert result.exit_code == 2
    assert "does not accept a usage ratio" in result.output
    assert "suministros_home_office_luz" in result.output


def test_set_ratio_out_of_range_rejected() -> None:
    result = _invoke("set-ratio", "suministros_home_office_luz", "1.5")
    assert result.exit_code == 2
    assert "[0, 1]" in result.output


def test_set_ratio_nan_rejected() -> None:
    result = _invoke("set-ratio", "suministros_home_office_luz", "NaN")
    assert result.exit_code == 2
    assert "must be finite" in result.output


def test_set_ratio_infinity_rejected() -> None:
    result = _invoke("set-ratio", "suministros_home_office_luz", "Infinity")
    assert result.exit_code == 2
    assert "must be finite" in result.output


def test_set_ratio_non_numeric_rejected() -> None:
    result = _invoke("set-ratio", "suministros_home_office_luz", "not-a-number")
    assert result.exit_code == 2
    assert "invalid ratio" in result.output


def test_set_ratio_unknown_key_rejected_with_aliases() -> None:
    result = _invoke("set-ratio", "foo", "0.5")
    assert result.exit_code == 2
    assert "unknown key" in result.output
    assert "home_office_area" in result.output
    assert "mileage_business" in result.output
    assert "phone_fixed_business" in result.output


def test_unset_ratio_removes_persisted_entry() -> None:
    set_result = _invoke("set-ratio", "suministros_home_office_luz", "0.21")
    assert set_result.exit_code == 0
    unset_result = _invoke("unset-ratio", "suministros_home_office_luz")
    assert unset_result.exit_code == 0
    assert "unset suministros_home_office_luz" in unset_result.output

    second_unset = _invoke("unset-ratio", "suministros_home_office_luz")
    assert second_unset.exit_code == 0
    assert "no user ratio set for suministros_home_office_luz" in second_unset.output


def test_unset_ratio_family_alias_removes_all_members() -> None:
    _invoke("set-ratio", "home_office_area", "0.21")
    result = _invoke("unset-ratio", "home_office_area")
    assert result.exit_code == 0, result.output
    for category in (
        "arrendamiento_vivienda_afecto",
        "suministros_home_office_luz",
        "suministros_home_office_agua",
        "suministros_home_office_gas",
        "suministros_home_office_internet",
        "telefonia_fija",
    ):
        assert f"unset {category}" in result.output


def test_unset_ratio_family_alias_on_empty_profile_reports_no_entry() -> None:
    result = _invoke("unset-ratio", "home_office_area")
    assert result.exit_code == 0
    assert "no user ratio set for home_office_area" in result.output


def test_list_renders_missing_statutory_default_as_placeholder() -> None:
    set_result = _invoke("set-ratio", "telefonia_movil", "0.6")
    assert set_result.exit_code == 0
    list_result = _invoke("ratios", "list")
    assert list_result.exit_code == 0
    assert "telefonia_movil" in list_result.output
    assert "(none)" in list_result.output


def test_set_ratio_accepts_upper_bound_one() -> None:
    result = _invoke("set-ratio", "suministros_home_office_luz", "1")
    assert result.exit_code == 0, result.output
    assert "set suministros_home_office_luz = 1" in result.output


def test_set_ratio_accepts_lower_bound_zero() -> None:
    result = _invoke("set-ratio", "suministros_home_office_luz", "0")
    assert result.exit_code == 0, result.output
    assert "set suministros_home_office_luz = 0" in result.output


def test_set_ratio_rejects_spanish_locale_comma_decimal() -> None:
    """Kent in Málaga may type ``0,21`` out of habit; the CLI must refuse
    with a clear error rather than silently mis-parse."""
    result = _invoke("set-ratio", "suministros_home_office_luz", "0,21")
    assert result.exit_code == 2
    assert "invalid ratio" in result.output


def test_kent_success_moment_end_to_end(_isolate_usage_ratios_path: Path) -> None:
    """Replay Kent's issue-body narrative: set home-office ratio to 0.21,
    list, and confirm every home-office category now reports 0.21 beside
    the statutory default 0.3."""
    set_result = _invoke("set-ratio", "home_office_area", "0.21")
    assert set_result.exit_code == 0, set_result.output
    assert _isolate_usage_ratios_path.exists()

    list_result = _invoke("ratios", "list")
    assert list_result.exit_code == 0, list_result.output
    lines = list_result.output.splitlines()
    # One header + six data rows (the six USAGE_RATIO_HOME_AREA categories).
    data_rows = [line for line in lines if "\t" in line and "usage_ratio_home_area" in line]
    assert len(data_rows) == 6, list_result.output
    for row in data_rows:
        columns = row.split("\t")
        # category, kind, user_ratio, statutory_default
        assert len(columns) == 4
        assert columns[1] == "usage_ratio_home_area"
        assert columns[2] == "0.21"
        assert columns[3] == "0.3"


def test_successive_set_ratios_accumulate() -> None:
    """Two ``set-ratio`` calls for different categories must both persist;
    the second must not clobber the first."""
    first = _invoke("set-ratio", "suministros_home_office_luz", "0.21")
    assert first.exit_code == 0, first.output
    second = _invoke("set-ratio", "telefonia_movil", "0.6")
    assert second.exit_code == 0, second.output
    listing = _invoke("ratios", "list")
    assert "suministros_home_office_luz" in listing.output
    assert "telefonia_movil" in listing.output
    assert "0.21" in listing.output
    assert "0.6" in listing.output


def test_set_ratio_same_category_twice_replaces_value() -> None:
    """Setting the same category twice replaces the value rather than
    appending or erroring out."""
    _invoke("set-ratio", "suministros_home_office_luz", "0.21")
    second = _invoke("set-ratio", "suministros_home_office_luz", "0.5")
    assert second.exit_code == 0, second.output
    listing = _invoke("ratios", "list")
    assert "0.5" in listing.output
    # The replaced value must no longer appear as the user ratio for the
    # category — scan the row explicitly to avoid false matches elsewhere.
    data_rows = [line for line in listing.output.splitlines() if line.startswith("suministros_home_office_luz\t")]
    assert len(data_rows) == 1
    assert data_rows[0].split("\t")[2] == "0.5"
