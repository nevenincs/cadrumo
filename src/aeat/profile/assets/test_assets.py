"""Tests for actividad economica asset amortization ledgers."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from ...errors import get_registered_error_code
from ...formulas import LIS_ART_12_LINEAL_TABLE, AssetClass
from ...storage import EphemeralMasterKeyProvider, override_master_key_provider
from ..errors import BasisCapExceededError
from . import (
    AmortizationEntry,
    AmortizationLedger,
    AssetRecord,
    LibertadAmortizacionElection,
    compute_amortization_for_year,
    compute_anexo_d_amortization_aggregate,
    load_amortization_ledger,
    load_assets,
    record_amortization,
    save_assets,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


@pytest.fixture(autouse=True)
def _ephemeral_master_key() -> Iterator[None]:
    override_master_key_provider(EphemeralMasterKeyProvider())
    try:
        yield
    finally:
        override_master_key_provider(None)


def _asset(
    identifier: str,
    asset_class: AssetClass,
    cost_basis: str = "10000.00",
    actividad_id: str | None = "consulting",
) -> AssetRecord:
    return AssetRecord(
        identifier=identifier,
        description=f"asset {identifier}",
        asset_class=asset_class,
        acquisition_date=date(2025, 1, 1),
        cost_basis=Decimal(cost_basis),
        actividad_id=actividad_id,
    )


def test_representative_lis_art_12_coefficients_match_boe() -> None:
    """BOE LIS art. 12.1.a representative coefficient lock."""

    table = {row.asset_class: row for row in LIS_ART_12_LINEAL_TABLE}
    assert len(table) == 33
    assert table[AssetClass.EDIFICIOS_INDUSTRIALES].coef_max_pct == Decimal("3.00")
    assert table[AssetClass.EDIFICIOS_INDUSTRIALES].period_max_years == 68
    assert table[AssetClass.TRANSPORTE_EXTERNO].coef_max_pct == Decimal("16.00")
    assert table[AssetClass.ELECTRONICA_INFORMATICA].coef_max_pct == Decimal("25.00")


@pytest.mark.parametrize(
    ("asset_class", "expected"),
    [
        (AssetClass.EDIFICIOS_INDUSTRIALES, Decimal("300.00")),
        (AssetClass.TRANSPORTE_EXTERNO, Decimal("1600.00")),
        (AssetClass.ELECTRONICA_INFORMATICA, Decimal("2500.00")),
    ],
)
def test_amortization_uses_lis_coefficient(asset_class: AssetClass, expected: Decimal) -> None:
    asset = _asset("a1", asset_class)

    assert compute_amortization_for_year(asset, 2025, AmortizationLedger()) == expected


def test_amortization_prorates_first_year_days() -> None:
    asset = AssetRecord(
        identifier="laptop",
        description="laptop",
        asset_class=AssetClass.ELECTRONICA_INFORMATICA,
        acquisition_date=date(2025, 7, 1),
        cost_basis=Decimal("10000.00"),
    )

    assert compute_amortization_for_year(asset, 2025, AmortizationLedger()) == Decimal("1260.27")


def test_basis_cap_returns_zero_when_fully_amortized() -> None:
    asset = _asset("van", AssetClass.TRANSPORTE_EXTERNO)
    ledger = AmortizationLedger(entries=(AmortizationEntry(asset_id="van", year=2021, amount=Decimal("10000.00")),))

    assert compute_amortization_for_year(asset, 2025, ledger) == Decimal("0.00")


def test_basis_cap_raises_when_existing_ledger_exceeds_cost() -> None:
    asset = _asset("van", AssetClass.TRANSPORTE_EXTERNO)
    ledger = AmortizationLedger(entries=(AmortizationEntry(asset_id="van", year=2021, amount=Decimal("10000.01")),))

    with pytest.raises(BasisCapExceededError):
        compute_amortization_for_year(asset, 2025, ledger)


def test_libertad_amortizacion_opt_in_is_capped_to_basis() -> None:
    asset = AssetRecord(
        identifier="robot",
        description="robot",
        asset_class=AssetClass.MAQUINARIA_GENERAL,
        acquisition_date=date(2025, 1, 1),
        cost_basis=Decimal("12000.00"),
        libertad_amortizacion=LibertadAmortizacionElection(enabled=True, legal_basis="LIS art. 12.5"),
    )

    assert compute_amortization_for_year(asset, 2025, AmortizationLedger()) == Decimal("12000.00")
    assert compute_amortization_for_year(
        asset,
        2026,
        AmortizationLedger(entries=(AmortizationEntry(asset_id="robot", year=2025, amount=Decimal("12000.00")),)),
    ) == Decimal("0.00")


def test_asset_persistence_round_trip(tmp_path) -> None:
    asset = _asset("pc", AssetClass.ELECTRONICA_INFORMATICA)

    save_assets((asset,), storage_dir=tmp_path)
    loaded = load_assets(storage_dir=tmp_path)

    assert loaded == (asset,)


def test_asset_persistence_is_encrypted_financial_envelope(tmp_path) -> None:
    asset = AssetRecord(
        identifier="nas",
        description="LEAK-CANARY-NAS",
        asset_class=AssetClass.ELECTRONICA_INFORMATICA,
        acquisition_date=date(2025, 1, 1),
        taxable_base=Decimal("1000.00"),
        vat_rate=Decimal("21.00"),
        vat_amount=Decimal("210.00"),
        deductible_vat_ratio=Decimal("0.50"),
        gross_total=Decimal("1210.00"),
        cost_basis=Decimal("1105.00"),
    )

    path = save_assets((asset,), storage_dir=tmp_path)
    text = path.read_text(encoding="utf-8")

    assert '"classification":"financial"' in text
    assert '"encryption":' in text
    assert "LEAK-CANARY-NAS" not in text


def test_future_year_amortization_entries_do_not_reduce_prior_year_recompute() -> None:
    asset = _asset("pc", AssetClass.ELECTRONICA_INFORMATICA)
    ledger = AmortizationLedger(entries=(AmortizationEntry(asset_id="pc", year=2026, amount=Decimal("2500.00")),))

    assert compute_amortization_for_year(asset, 2025, ledger) == Decimal("2500.00")


def test_useful_life_override_cannot_exceed_lis_maximum_rate() -> None:
    asset = AssetRecord(
        identifier="fast-pc",
        description="fast pc",
        asset_class=AssetClass.ELECTRONICA_INFORMATICA,
        acquisition_date=date(2025, 1, 1),
        cost_basis=Decimal("1000.00"),
        useful_life_years=2,
    )

    with pytest.raises(Exception, match=r"LIS art\. 12\.1\.a"):
        compute_amortization_for_year(asset, 2025, AmortizationLedger())


def test_useful_life_override_cannot_exceed_lis_maximum_period() -> None:
    asset = AssetRecord(
        identifier="slow-pc",
        description="slow pc",
        asset_class=AssetClass.ELECTRONICA_INFORMATICA,
        acquisition_date=date(2025, 1, 1),
        cost_basis=Decimal("1000.00"),
        useful_life_years=9,
    )

    with pytest.raises(Exception, match=r"LIS art\. 12\.1\.a"):
        compute_amortization_for_year(asset, 2025, AmortizationLedger())


def test_record_amortization_persists_real_ledger(tmp_path) -> None:
    asset = _asset("pc", AssetClass.ELECTRONICA_INFORMATICA)

    record_amortization(asset, 2025, storage_dir=tmp_path)
    ledger = load_amortization_ledger(storage_dir=tmp_path)

    assert ledger.entries == (AmortizationEntry(asset_id="pc", year=2025, amount=Decimal("2500.00")),)


def test_record_amortization_is_idempotent_for_existing_year(tmp_path) -> None:
    asset = AssetRecord(
        identifier="robot",
        description="robot",
        asset_class=AssetClass.MAQUINARIA_GENERAL,
        acquisition_date=date(2025, 1, 1),
        cost_basis=Decimal("12000.00"),
        libertad_amortizacion=LibertadAmortizacionElection(enabled=True, legal_basis="LIS art. 12.5"),
    )

    record_amortization(asset, 2025, storage_dir=tmp_path)
    record_amortization(asset, 2025, storage_dir=tmp_path)
    ledger = load_amortization_ledger(storage_dir=tmp_path)

    assert ledger.entries == (AmortizationEntry(asset_id="robot", year=2025, amount=Decimal("12000.00")),)


def test_multi_actividad_aggregate_filters_and_allocates() -> None:
    assets = (
        _asset("pc", AssetClass.ELECTRONICA_INFORMATICA, actividad_id="consulting"),
        _asset("van", AssetClass.TRANSPORTE_EXTERNO, actividad_id="retail"),
        AssetRecord(
            identifier="shared",
            description="shared printer",
            asset_class=AssetClass.ELECTRONICA_INFORMATICA,
            acquisition_date=date(2025, 1, 1),
            cost_basis=Decimal("1000.00"),
            actividad_id=None,
            allocation_ratio=Decimal("0.50"),
        ),
    )

    assert compute_anexo_d_amortization_aggregate(2025, assets=assets, actividad_id="consulting") == Decimal("2625.00")


def test_new_errors_are_registered() -> None:
    assert get_registered_error_code(BasisCapExceededError).code == "INTEGRITY_PROFILE_AMORTIZATION_BASIS_CAP"
