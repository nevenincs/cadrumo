"""Activity-asset amortization authority in every year of the support envelope.

The amortization tables and method admissions are authored once, at the first
supported edition the law admits them, and keyed forward only where the law
changes. Each year's expectation is read from that year's bundled AEAT Renta
manual rather than restated here: a table row or an incentive is expected in
exactly the exercises whose manual prints it. A projected year beyond the
newest manual carries the tables forward but admits no incentive whose own
enactment is annual.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.application.calculations.actividad_asset_schedule import forecast_activity_asset_charge
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.actividad_asset_bindings import resolve_activity_asset_schedule_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.tests.authored_editions import manual_editions_printing
from cadrumo.domain.renta.actividad_asset.election import (
    AmortizationMethod,
    ChargingInfrastructureEvidence,
)
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetUnsupportedError
from cadrumo.domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from cadrumo.domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge
from cadrumo.domain.user_profile.plantilla_media import PlantillaMediaState, PlantillaMediaYear

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_shared_catalogues
from .test_activity_asset_schedule_authority_resolution import (
    _asset,
    _election,
    _linear,
    _renewable,
    _renewable_evidence,
    _workforce,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# LIS art. 12.1.a table row the manual reprints, maximum linear coefficient 12%.
_MACHINERY_ROW = "Maquinaria 12 por 100 18 años"
_MACHINERY_RATE = Decimal("0.12")
# The heading each manual gives the free-depreciation regimes of LIS DA 17 and DA 18.
_RENEWABLE_HEADING = "Libertad de amortización en inversiones que utilicen energía"
_VEHICLE_HEADING = "Libertad de amortización en determinados vehículos"


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


def _edition(year: int) -> ModeloRevision:
    return compiled_bundled_authority().snapshot("100", filing_year=year, period="0A").revision


def _charge(
    asset: ActivityAssetRevision,
    year: int,
    *,
    free_amount: str | None = None,
    workforce: tuple[PlantillaMediaYear, ...] = (),
) -> ScheduledAmortizationCharge:
    return forecast_activity_asset_charge(
        asset,
        modelo_100_revision=_edition(year),
        authority_generation="candidate-source",
        covered_from=date(year, 1, 1),
        covered_until=date(year + 1, 1, 1),
        history=AssetScheduleHistory(),
        taxpayer_workforce=lambda: workforce,
        requested_free_amount=Decimal(free_amount) if free_amount is not None else None,
    )


def _kept_workforce(year: int) -> tuple[PlantillaMediaYear, ...]:
    return _workforce(
        (year - 1, "10.00", PlantillaMediaState.OBSERVED),
        (year, "10.00", PlantillaMediaState.OBSERVED),
        (year + 1, "10.00", PlantillaMediaState.COMMITTED),
    )


def test_every_authored_supported_year_prints_the_machinery_row() -> None:
    printed = set(manual_editions_printing("renta", _MACHINERY_ROW))
    authored = {year for year in _supported_years() if _edition(year).valid_from.year == year}
    assert authored <= printed, sorted(authored - printed)


@pytest.mark.parametrize("year", _supported_years())
def test_a_full_year_of_linear_machinery_charges_the_table_maximum(year: int) -> None:
    basis = Decimal("10000")
    asset = _asset(_linear("maquinaria"), basis=str(basis), in_service=date(year, 1, 1))

    assert _charge(asset, year).amount == basis * _MACHINERY_RATE


@pytest.mark.parametrize("year", _supported_years())
def test_renewable_free_depreciation_is_admitted_exactly_where_the_manual_prints_it(year: int) -> None:
    admitted = year in manual_editions_printing("renta", _RENEWABLE_HEADING)
    evidence = _renewable_evidence(made_available=date(year, 1, 10))
    panels = _asset(_renewable(evidence), basis="40000", in_service=date(year, 2, 1))

    if admitted:
        assert _charge(panels, year, free_amount="40000", workforce=_kept_workforce(year)).amount == Decimal("40000.00")
    else:
        with pytest.raises(ActividadAssetUnsupportedError):
            _charge(panels, year, free_amount="40000", workforce=_kept_workforce(year))


@pytest.mark.parametrize("year", _supported_years())
def test_charging_point_free_depreciation_is_admitted_exactly_where_the_manual_prints_it(year: int) -> None:
    admitted = year in manual_editions_printing("renta", _VEHICLE_HEADING)
    charger = _asset(
        _election(
            AmortizationMethod.CHARGING_INFRASTRUCTURE_FREE,
            authority_class_key="instalacion-resto",
            charging_infrastructure=ChargingInfrastructureEvidence(
                technical_documentation_reference="rebt-memoria",
                installation_certificate_reference="ccaa-certificate",
            ),
        ),
        basis="2500",
        in_service=date(year, 3, 1),
    )

    if admitted:
        assert _charge(charger, year, free_amount="2500").amount == Decimal("2500.00")
    else:
        with pytest.raises(ActividadAssetUnsupportedError):
            _charge(charger, year, free_amount="2500")


def test_an_edition_that_begins_after_the_tax_year_is_refused() -> None:
    """Canonical selection may serve a later year from an earlier edition, never the reverse."""
    later = max(_supported_years(), key=lambda year: _edition(year).valid_from)
    edition = _edition(later)
    earlier_year = edition.valid_from.year - 1
    asset = _asset(_linear("maquinaria"), basis="10000", in_service=date(earlier_year, 1, 1))

    with pytest.raises(ActividadAssetUnsupportedError, match="begins after tax year"):
        resolve_activity_asset_schedule_authority(
            edition,
            tax_year=earlier_year,
            asset_revision=asset,
            authority_generation="candidate-source",
            workforce=(),
        )
