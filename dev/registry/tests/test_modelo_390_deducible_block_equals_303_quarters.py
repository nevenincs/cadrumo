"""Modelo 390 apartado 5 IVA deducible equals the sum of the year's Modelo 303 boxes.

The four quarterly Modelo 303 autoliquidaciones of each supported year are
calculated from ledger rows of every deducible kind through the compiled
registry, and the annual Modelo 390 is calculated from the same rows and those
four filings. Each annual deducible total must equal the sum of the quarterly
box it restates, which is also what the blocking reconciliation of [64] against
the filed 303s relies on:

    390 [48]/[49]   = 303 [28]/[29]   operaciones interiores corrientes
    390 [50]/[51]   = 303 [30]/[31]   operaciones interiores, bienes de inversion
    390 [52]/[53]   = 303 [32]/[33]   importaciones de bienes corrientes
    390 [54]/[55]   = 303 [34]/[35]   importaciones de bienes de inversion
    390 [56]+[597]  = 303 [36]        adquisiciones intracomunitarias corrientes
    390 [57]+[598]  = 303 [37]          (bienes and servicios apart on the 390)
    390 [58]/[59]   = 303 [38]/[39]   adquisiciones intracomunitarias, inversion
    390 [639]/[62]  = 303 [40]/[41]   rectificacion de deducciones
    390 [61]        = 303 [42]        compensaciones REAGP (operator input)
    390 [64]        = 303 [45]        suma de deducciones
    390 [47]        = 303 [27]        total cuota devengada (the semantic total on 2022)
    390 [65]        = 303 [46]        resultado regimen general

Beyond parity, the annual boxes are held to figures worked by hand from the
fixture rows, so a routing error that both modelos shared would still fail.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import RegistryCalculationResult
from cadrumo.domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
)
from cadrumo.domain.calculations.registry.rate_box_partition import (
    derive_rate_box_partitions,
    rate_box_coverage_shortfalls,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.iva.schema import IvaLedgerObservationRole
from dev.registry.compiler.authority import compiled_bundled_authority

from ..compiler.loader import load_modelo_directory
from ..compiler.validate_bindings import validate_binding_registration_section
from .ledger_iva_aggregation_support import (
    _calculate_303_from_observations,
    _calculate_390_from_observations_and_303_filings,
    _category,
    _deduction_kind,
    _deduction_provenance,
    _flow,
    _rate_kind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_SURFACE = "test_modelo_390_deducible_block_equals_303_quarters"
_SUPPORTED_YEARS = (2022, 2023, 2024, 2025)
_QUARTER_MONTH = {"1T": 2, "2T": 5, "3T": 8, "4T": 11}
_GENERAL = Decimal("0.21")
_REDUCED = Decimal("0.10")


def _casilla(raw: str) -> CasillaId:
    return validated_casilla_id(raw, surface=_SURFACE)


@dataclass(frozen=True, slots=True)
class _Row:
    """One ledger row of the fixture: what it is, when, and how much."""

    key: str
    category: str
    flow: str
    kind: str | None
    base: str
    cuota: str
    rate: Decimal
    periods: tuple[str, ...] = ("1T", "2T", "3T", "4T")
    rectifies: str | None = None
    """For a rectification, the key of the row it corrects (its first-quarter booking)."""


_ROWS = (
    _Row("venta", "domestic_general", "repercutido", None, "10000.00", "2100.00", _GENERAL),
    _Row("compra-21", "domestic_general", "soportado", "domestic_current", "1000.00", "210.00", _GENERAL),
    _Row("compra-10", "domestic_reduced", "soportado", "domestic_current", "300.00", "30.00", _REDUCED),
    _Row("ordenador", "domestic_general", "soportado", "domestic_investment", "4000.00", "840.00", _GENERAL, ("2T",)),
    _Row(
        "isp-corriente",
        "domestic_reverse_charge",
        "inversion_sujeto_pasivo",
        "domestic_current",
        "500.00",
        "105.00",
        _GENERAL,
    ),
    _Row(
        "isp-inversion",
        "domestic_reverse_charge",
        "inversion_sujeto_pasivo",
        "domestic_investment",
        "2000.00",
        "420.00",
        _GENERAL,
        ("3T",),
    ),
    _Row("importacion-21", "import_third_country", "soportado", "import_current", "800.00", "168.00", _GENERAL),
    _Row("importacion-10", "import_third_country", "soportado", "import_current", "200.00", "20.00", _REDUCED),
    _Row(
        "importacion-inversion",
        "import_third_country",
        "soportado",
        "import_investment",
        "3000.00",
        "630.00",
        _GENERAL,
        ("4T",),
    ),
    _Row(
        "aic-bienes-21",
        "intra_community_acquisition_reverse_charge",
        "inversion_sujeto_pasivo",
        "intra_eu_current",
        "600.00",
        "126.00",
        _GENERAL,
    ),
    _Row(
        "aic-bienes-10",
        "intra_community_acquisition_reverse_charge",
        "inversion_sujeto_pasivo",
        "intra_eu_current",
        "400.00",
        "40.00",
        _REDUCED,
    ),
    _Row(
        "aic-servicios",
        "intra_community_service_acquisition_reverse_charge",
        "inversion_sujeto_pasivo",
        "intra_eu_current",
        "700.00",
        "147.00",
        _GENERAL,
    ),
    _Row(
        "aic-maquina",
        "intra_community_acquisition_reverse_charge",
        "inversion_sujeto_pasivo",
        "intra_eu_investment",
        "5000.00",
        "1050.00",
        _GENERAL,
        ("1T",),
    ),
    _Row(
        "rect-interior",
        "domestic_general",
        "soportado",
        "rectification",
        "-100.00",
        "-21.00",
        _GENERAL,
        ("2T",),
        "compra-21",
    ),
    _Row(
        "rect-importacion",
        "import_third_country",
        "soportado",
        "rectification",
        "-50.00",
        "-10.50",
        _GENERAL,
        ("3T",),
        "importacion-21",
    ),
    _Row(
        "rect-aic",
        "intra_community_acquisition_reverse_charge",
        "inversion_sujeto_pasivo",
        "rectification",
        "-200.00",
        "-42.00",
        _GENERAL,
        ("4T",),
        "aic-bienes-21",
    ),
    _Row(
        "rect-isp",
        "domestic_reverse_charge",
        "inversion_sujeto_pasivo",
        "rectification",
        "-30.00",
        "-6.30",
        _GENERAL,
        ("1T",),
        "isp-corriente",
    ),
)

#: 303 box [42] is operator input: the ledger does not carry the compensacion
#: a tanto alzado paid to a REAGP farmer.
_REAGP_BY_QUARTER = {"1T": "12.00", "2T": "0.00", "3T": "30.00", "4T": "0.00"}


_INVESTMENT_KINDS = frozenset({"domestic_investment", "import_investment", "intra_eu_investment"})


def _ledger_row(row: _Row, *, ledger_id: str, on: date, applied_rate: Decimal | None) -> IvaLedgerObservation:
    """Build one row as the ledger projection emits it, asset id included for a bien de inversion."""
    kind = None if row.kind is None else _deduction_kind(row.kind, effective_date=on)
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=on,
        category=_category(row.category, effective_date=on),
        rate_kind=_rate_kind("general" if row.rate == _GENERAL else "reduced", effective_date=on),
        flow_direction=_flow(row.flow, effective_date=on),
        base_amount=Decimal(row.base),
        iva_amount=Decimal(row.cuota),
        applied_rate=applied_rate,
        deduction_fact_kind=kind,
        deduction_provenance=(
            None if kind is None else _deduction_provenance(kind, source_locator=f"test-ledger:{ledger_id}")
        ),
        investment_asset_id=f"BI-{ledger_id}" if row.kind in _INVESTMENT_KINDS else None,
        rectifies_ledger_id=(None if row.rectifies is None else f"{on.year}-1T-{row.rectifies}"),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _rows_for(year: int, period: str) -> tuple[IvaLedgerObservation, ...]:
    on = date(year, _QUARTER_MONTH[period], 10)
    return tuple(
        _ledger_row(row, ledger_id=f"{year}-{period}-{row.key}", on=on, applied_rate=row.rate)
        for row in _ROWS
        if period in row.periods
    )


@dataclass(frozen=True, slots=True)
class _Year:
    quarters: Mapping[str, RegistryCalculationResult]
    annual: RegistryCalculationResult


@cache
def _file_year(year: int) -> _Year:
    quarters: dict[str, RegistryCalculationResult] = {}
    rows: tuple[IvaLedgerObservation, ...] = ()
    for period in _QUARTER_MONTH:
        quarter_rows = _rows_for(year, period)
        rows += quarter_rows
        quarters[period] = _calculate_303_from_observations(
            filing_year=year,
            period=period,
            observations=quarter_rows,
            operator_inputs={_casilla("42"): Decimal(_REAGP_BY_QUARTER[period])},
        )
    annual = _calculate_390_from_observations_and_303_filings(
        filing_year=year,
        observations=rows,
        quarterly_results=quarters,
    )
    return _Year(quarters=quarters, annual=annual)


def _quarter_sum(year: _Year, box: str) -> Decimal:
    return sum((result.values[_casilla(box)] for result in year.quarters.values()), Decimal("0"))


def _annual(year: _Year, casilla_id: str) -> Decimal:
    return year.annual.values[_casilla(casilla_id)]


#: 390 casilla(s) whose sum restates each 303 box.
_ANNUAL_FOR_QUARTERLY_BOX = {
    "28": ("iva.anual.soportado.interiores.base",),
    "29": ("iva.anual.soportado.interiores",),
    "30": ("iva.anual.deducible.interiores-inversion.total.base",),
    "31": ("iva.anual.deducible.interiores-inversion.total.cuota",),
    "32": ("iva.anual.deducible.importaciones-corrientes.total.base",),
    "33": ("iva.anual.soportado.importaciones",),
    "34": ("iva.anual.deducible.importaciones-inversion.total.base",),
    "35": ("iva.anual.deducible.importaciones-inversion.total.cuota",),
    "36": ("iva.anual.deducible.aic-corrientes.total.base", "iva.anual.deducible.aic-servicios.total.base"),
    "37": ("iva.anual.deducible.aic-corrientes.total.cuota", "iva.anual.deducible.aic-servicios.total.cuota"),
    "38": ("iva.anual.deducible.aic-inversion.total.base",),
    "39": ("iva.anual.deducible.aic-inversion.total.cuota",),
    "40": ("iva.anual.deducible.rectificacion.base",),
    "41": ("iva.anual.deducible.rectificacion.cuota",),
    "42": ("iva.anual.deducible.compensaciones-reagp.cuota",),
    "45": ("iva.anual.cuota-deducible-total",),
    "iva.cuota-devengada-total": ("iva.anual.cuota-devengada-total",),
    "iva.resultado-regimen-general": ("iva.anual.resultado-regimen-general",),
}


@pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
@pytest.mark.parametrize("quarterly_box", tuple(_ANNUAL_FOR_QUARTERLY_BOX))
def test_each_annual_deducible_box_is_the_sum_of_its_quarterly_box(filing_year: int, quarterly_box: str) -> None:
    year = _file_year(filing_year)

    annual = sum((_annual(year, casilla_id) for casilla_id in _ANNUAL_FOR_QUARTERLY_BOX[quarterly_box]), Decimal("0"))

    assert annual == _quarter_sum(year, quarterly_box)


# Worked by hand from _ROWS: the four-quarter rows times four, the one-quarter
# rows once, the domestic inversion del sujeto pasivo inside the interiores
# boxes, every rectification in [639]/[62] and nowhere else.
_HAND_WORKED = {
    # 4 x (1000 + 300) soportado + 4 x 500 inversion del sujeto pasivo
    "iva.anual.soportado.interiores.base": "7200.00",
    # 4 x (210 + 30) + 4 x 105
    "iva.anual.soportado.interiores": "1380.00",
    # ordenador + isp-inversion
    "iva.anual.deducible.interiores-inversion.total.base": "6000.00",
    "iva.anual.deducible.interiores-inversion.total.cuota": "1260.00",
    # 4 x (800 + 200)
    "iva.anual.deducible.importaciones-corrientes.total.base": "4000.00",
    "iva.anual.soportado.importaciones": "752.00",
    "iva.anual.deducible.importaciones-inversion.total.base": "3000.00",
    "iva.anual.deducible.importaciones-inversion.total.cuota": "630.00",
    # 4 x (600 + 400) and 4 x (126 + 40)
    "iva.anual.deducible.aic-corrientes.total.base": "4000.00",
    "iva.anual.deducible.aic-corrientes.total.cuota": "664.00",
    "iva.anual.deducible.aic-corrientes.tipo-21.base": "2400.00",
    "iva.anual.deducible.aic-corrientes.tipo-21.cuota": "504.00",
    "iva.anual.deducible.aic-corrientes.tipo-10.base": "1600.00",
    "iva.anual.deducible.aic-corrientes.tipo-10.cuota": "160.00",
    "iva.anual.deducible.aic-corrientes.tipo-4.cuota": "0",
    "iva.anual.deducible.aic-inversion.total.base": "5000.00",
    "iva.anual.deducible.aic-inversion.total.cuota": "1050.00",
    "iva.anual.deducible.aic-inversion.tipo-21.cuota": "1050.00",
    "iva.anual.deducible.aic-servicios.total.base": "2800.00",
    "iva.anual.deducible.aic-servicios.total.cuota": "588.00",
    "iva.anual.deducible.aic-servicios.tipo-21.base": "2800.00",
    "iva.anual.deducible.aic-servicios.tipo-21.cuota": "588.00",
    # -100 - 50 - 200 - 30 and -21 - 10.50 - 42 - 6.30
    "iva.anual.deducible.rectificacion.base": "-380.00",
    "iva.anual.deducible.rectificacion.cuota": "-79.80",
    "iva.anual.deducible.compensaciones-reagp.cuota": "42.00",
    # 1380 + 1260 + 752 + 630 + 664 + 1050 + 588 + 42 - 79.80
    "iva.anual.cuota-deducible-total": "6286.20",
}


@pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
def test_the_annual_deducible_boxes_hold_the_hand_worked_figures(filing_year: int) -> None:
    year = _file_year(filing_year)

    assert {casilla_id: _annual(year, casilla_id) for casilla_id in _HAND_WORKED} == {
        casilla_id: Decimal(value) for casilla_id, value in _HAND_WORKED.items()
    }


@pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
def test_the_reconciliations_against_the_filed_303s_close(filing_year: int) -> None:
    """The blocking rules compare these pairs; the fixture carries every deducible kind."""
    annual = _file_year(filing_year).annual.values

    assert (
        annual[_casilla("iva.anual.cuota-deducible-total")]
        == annual[_casilla("iva.anual.reconciliacion.deducible-303")]
    )
    assert (
        annual[_casilla("iva.anual.cuota-devengada-total")]
        == annual[_casilla("iva.anual.reconciliacion.devengada-303")]
    )
    assert (
        annual[_casilla("iva.anual.resultado-regimen-general")]
        == annual[_casilla("iva.anual.reconciliacion.resultado-303")]
    )


@pytest.mark.parametrize("filing_year", (2024, 2025))
def test_the_2024_rate_boxes_of_the_aic_block_are_bound(filing_year: int) -> None:
    """The 2 % and 7,5 % boxes the 2024 design adds read only their own rate."""
    revision = compiled_bundled_authority().snapshot("390", filing_year=filing_year, period="0A").revision
    on = date(filing_year, 11, 10)
    aceite = _Row(
        "aceite-7-5",
        "intra_community_acquisition_reverse_charge",
        "inversion_sujeto_pasivo",
        "intra_eu_current",
        "1000.00",
        "75.00",
        _REDUCED,
    )
    rows = (_ledger_row(aceite, ledger_id="aceite-7-5", on=on, applied_rate=Decimal("0.075")),)
    values = resolve_ledger_iva_aggregation_binding_values(revision, rows)
    casillas = {casilla.id: casilla for casilla in revision.casillas}

    assert casillas[_casilla("iva.anual.deducible.aic-corrientes.tipo-7-5.cuota")].binding == (
        "modelo-390-iva-deducible-aic-corrientes-tipo-7-5-cuota"
    )
    assert values["modelo-390-iva-deducible-aic-corrientes-tipo-7-5-cuota"] == Decimal("75.00")
    assert values["modelo-390-iva-deducible-aic-corrientes-tipo-10-cuota"] == Decimal("0")
    assert values["modelo-390-iva-deducible-aic-corrientes-cuota"] == Decimal("75.00")


def test_a_rate_unrecorded_aic_row_reaches_the_total_and_is_reported() -> None:
    """The rate-blind layer keeps the row in [57]; the rate boxes cannot, and say so."""
    revision = compiled_bundled_authority().snapshot("390", filing_year=2025, period="0A").revision
    on = date(2025, 5, 10)
    aic_goods = next(row for row in _ROWS if row.key == "aic-bienes-21")
    unrated = _ledger_row(aic_goods, ledger_id="aic-sin-tipo", on=on, applied_rate=None)
    values = resolve_ledger_iva_aggregation_binding_values(revision, (unrated,))
    by_casilla = {
        _casilla("iva.anual.deducible.aic-corrientes.todos-tipos.cuota"): values[
            "modelo-390-iva-deducible-aic-corrientes-cuota"
        ],
        _casilla("iva.anual.deducible.aic-corrientes.tipo-21.cuota"): values[
            "modelo-390-iva-deducible-aic-corrientes-tipo-21-cuota"
        ],
    }
    partitions = {partition.total_casilla_id: partition for partition in derive_rate_box_partitions(revision)}
    partition = partitions[_casilla("iva.anual.deducible.aic-corrientes.todos-tipos.cuota")]

    shortfalls = rate_box_coverage_shortfalls((partition,), by_casilla)

    assert values["modelo-390-iva-deducible-aic-corrientes-cuota"] == Decimal(aic_goods.cuota)
    assert values["modelo-390-iva-deducible-aic-corrientes-tipo-21-cuota"] == Decimal("0")
    assert _casilla("iva.anual.deducible.aic-corrientes.tipo-21.cuota") in partition.box_casilla_ids
    assert [shortfall.shortfall for shortfall in shortfalls] == [Decimal(aic_goods.cuota)]


_MODELOS_ROOT = Path(__file__).resolve().parents[3] / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"
_FRAGMENT = Path("revisions") / "2022" / "bindings" / "0001-declarations.toml"


def test_a_390_corrientes_selector_that_claims_every_kind_is_refused(tmp_path: Path) -> None:
    """Dropping the interior corrientes kind puts investments and rectifications in [49] too."""
    tree = tmp_path / "390"
    shutil.copytree(_MODELOS_ROOT / "390", tree)
    fragment = tree / _FRAGMENT
    text = fragment.read_text(encoding="utf-8")
    anchor = 'flow_direction = "soportado", fact = "iva_amount_sum", deduction_fact_kinds = ["domestic_current"], '
    lines = [line for line in text.splitlines() if anchor in line and '"domestic_general"' in line]
    assert len(lines) == 1, lines
    fragment.write_text(
        text.replace(lines[0], lines[0].replace('deduction_fact_kinds = ["domestic_current"], ', "")),
        encoding="utf-8",
    )
    clean = load_modelo_directory(_MODELOS_ROOT / "390").revisions["2025"]
    planted = load_modelo_directory(tree).revisions["2025"]

    def overlaps(revision: ModeloRevision) -> list[str]:
        return [
            failure
            for failure in validate_binding_registration_section(prefix="modelo 390 revision 2025", revision=revision)
            if "deduction kind" in failure
        ]

    assert overlaps(clean) == []
    failures = overlaps(planted)
    assert len(failures) == 2, failures
    assert all("modelo-390-iva-soportado-interiores-cuota" in failure for failure in failures)
    assert any("modelo-390-iva-soportado-interiores-bienes-inversion-cuota" in failure for failure in failures)
    assert any("modelo-390-iva-rectificacion-deducciones-interiores-cuota" in failure for failure in failures)
