"""The imputed income of LIRPF art. 85 for a property at its owner's disposal, casillas 0083 to 0089.

The expected amounts are the manuals' worked examples, recomputed by hand: the
2022 to 2025 Renta manuals impute "1,1 por 100 s/40.800 = 448,80" for a whole
year at disposal with a recently revised value, and the 2025 manual imputes
"1,1% (46.200 x (90/365)) = 125,31" for a flat at disposal from January to
March and let from April. The rates and the 365 divisor below are the manuals'
figures, written here independently of the registry the resolver reads.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.gasto_capital_inmobiliario import resolve_gasto_capital_inmobiliario_catalogue
from ....domain.calculations.registry.tests.authored_editions import (
    revision_selected_for,
    supported_exercises_with_projection,
)
from ....domain.contribuyente.inmueble_record import (
    ImportesMovimientos,
    InmuebleNaturaleza,
    InmuebleRecord,
    InmuebleTitularidad,
    TitularidadRegimen,
    TitularRole,
    UsoInmueble,
    UsoInmuebleTipo,
    ValorCatastral,
)
from ..renta_inmueble_findings import RentaInmuebleCause, RentaInmuebleFindingKind
from ..renta_inmueble_imputacion import RentaInmuebleImputacion
from ..renta_inmueble_net import RentaInmuebleTerms
from ..renta_inmueble_resolver import resolve_renta_inmueble_terms
from ..renta_inmueble_source import RentaInmuebleOccurrences, RentaInmuebleRowField, renta_inmueble_occurrences
from .renta_inmueble_support import inmueble, lease, monthly_rent, profile_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_REDUCED = Decimal("0.011")
_GENERAL = Decimal("0.02")
_YEAR_DAYS = 365
_LOOK_BACK = 10
"""The periods before the ejercicio in which a collective valuation still gives the reduced rate (art. 85.1)."""
_MANUAL_VALUE = Decimal("40800")
_GRANOLLERS_VALUE = Decimal("46200")
_RENT = Decimal("700.00")
_IMPUTACION_CAUSES = frozenset(
    {
        RentaInmuebleCause.IMPUTACION_VALOR_CATASTRAL_UNSTATED,
        RentaInmuebleCause.IMPUTACION_VIGOR_UNSTATED,
        RentaInmuebleCause.IMPUTACION_USO_SIMULTANEO,
        RentaInmuebleCause.IMPUTACION_RUSTICA,
    }
)


def _years() -> tuple[int, ...]:
    return tuple(supported_exercises_with_projection("100"))


def _terms(year: int) -> RentaInmuebleTerms:
    with bundled_indexed_authority().operation() as operation:
        return resolve_renta_inmueble_terms(
            modelo="100",
            revision_id=revision_selected_for("100", year, "0A").id,
            devengo=date(year, 12, 31),
            operation=operation,
        )


def _build(year: int, record: InmuebleRecord, leases=(), rows=()) -> RentaInmuebleOccurrences:
    return renta_inmueble_occurrences(
        path_values=profile_facts((record,), tuple(leases)),
        transactions=tuple(rows),
        ejercicio=year,
        concepts=resolve_gasto_capital_inmobiliario_catalogue(effective_date=date(year, 12, 31)),
        terms=_terms(year),
    )


def _imputacion(built: RentaInmuebleOccurrences) -> RentaInmuebleImputacion | None:
    assert not built.refused
    assert len(built.occurrences) == 1
    return built.occurrences[0].imputacion


def _causes(built: RentaInmuebleOccurrences) -> set[RentaInmuebleCause]:
    return {finding.cause for finding in built.findings}


def _cents(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _at_disposal(
    year: int,
    value: Decimal | None,
    *,
    vigor: int | None,
    desde: date | None = None,
    hasta: date | None = None,
    **fields,
) -> InmuebleRecord:
    valores = () if value is None else (ValorCatastral(year=year, total=value, construccion=value / 2, vigor=vigor),)
    uso = UsoInmueble(tipo=UsoInmuebleTipo.DISPOSICION_PROPIETARIO, desde=desde or date(year - 3, 1, 1), hasta=hasta)
    return inmueble(ejercicio=year, valores_catastrales=valores, usos=(uso,), **fields)


def test_a_whole_year_at_disposal_with_a_recent_valuation_imputes_the_manual_448_80() -> None:
    for year in _years():
        built = _build(year, _at_disposal(year, _MANUAL_VALUE, vigor=year - 1))
        boxes = _imputacion(built)

        assert boxes is not None, year
        assert boxes.importe == Decimal("448.80"), year
        assert boxes.dias == _YEAR_DAYS, year
        assert boxes.valor_catastral == _MANUAL_VALUE, year
        assert boxes.revisado is True, year
        assert boxes.porcentaje == Decimal(100), year
        assert not _causes(built) & _IMPUTACION_CAUSES, year
        occurrence = built.occurrences[0]
        assert occurrence.column(RentaInmuebleRowField.RENTA_IMPUTADA) == Decimal("448.80"), year
        assert occurrence.column(RentaInmuebleRowField.DISPOSICION) is True, year
        assert occurrence.column(RentaInmuebleRowField.IMPUTACION_VALOR_CATASTRAL_REVISADO) is True, year


def test_the_granollers_flat_imputes_its_days_before_the_lease_at_the_rate_its_valuation_earns() -> None:
    for year in _years():
        terms = _terms(year).imputacion
        # The 2025 manual's flat was revised in a year the ten-period look-back no longer reaches; where an
        # edition declares a qualifying first year, that year keeps the reduced rate, otherwise the general one.
        vigor = year - _LOOK_BACK - 1 if terms.revision_from_year is None else terms.revision_from_year
        rate = _GENERAL if terms.revision_from_year is None else _REDUCED
        let_from = date(year, 4, 1)
        record = _at_disposal(year, _GRANOLLERS_VALUE, vigor=vigor, hasta=date(year, 3, 31))
        built = _build(year, record, (lease(start=let_from),), monthly_rent(year, amount=_RENT, months=range(4, 13)))
        boxes = _imputacion(built)
        days = (date(year, 3, 31) - date(year, 1, 1)).days + 1

        assert boxes is not None, year
        assert boxes.dias == days, year
        assert boxes.revisado is (rate == _REDUCED), year
        assert boxes.importe == _cents(_GRANOLLERS_VALUE * rate * days / _YEAR_DAYS), year
        if days == 90 and rate == _REDUCED:
            assert boxes.importe == Decimal("125.31"), year
        assert not _causes(built) & (_IMPUTACION_CAUSES | {RentaInmuebleCause.DAYS_UNACCOUNTED}), year


def test_a_co_owner_imputes_his_share_of_the_value() -> None:
    for year in _years():
        half = InmuebleTitularidad(
            regimen=TitularidadRegimen.PLENO_DOMINIO,
            titular=TitularRole.PRIMER_DECLARANTE,
            porcentaje_propiedad=Decimal(50),
        )
        boxes = _imputacion(
            _build(
                year,
                _at_disposal(
                    year,
                    _MANUAL_VALUE,
                    vigor=year,
                    titularidad=half,
                    importes_movimientos=ImportesMovimientos.PARTE_PROPIA,
                ),
            )
        )

        assert boxes is not None, year
        assert boxes.importe == Decimal("224.40"), year


def test_days_at_disposal_without_a_cadastral_value_block_the_amount_and_keep_the_days() -> None:
    for year in _years():
        built = _build(year, _at_disposal(year, None, vigor=None, desde=date(year, 10, 31)), ())
        boxes = _imputacion(built)

        assert boxes is not None, year
        assert boxes.dias == 62, year
        assert boxes.importe is None, year
        assert boxes.valor_catastral is None, year
        blocking = {finding.cause for finding in built.findings if finding.kind is RentaInmuebleFindingKind.BLOCKING}
        assert RentaInmuebleCause.IMPUTACION_VALOR_CATASTRAL_UNSTATED in blocking, year


def test_an_unstated_valuation_year_blocks_the_rate_and_the_amount() -> None:
    for year in _years():
        built = _build(year, _at_disposal(year, _MANUAL_VALUE, vigor=None))
        boxes = _imputacion(built)

        assert boxes is not None, year
        assert boxes.revisado is None, year
        assert boxes.importe is None, year
        assert RentaInmuebleCause.IMPUTACION_VIGOR_UNSTATED in _causes(built), year


def test_a_day_at_disposal_shared_with_a_lease_blocks_the_amount() -> None:
    for year in _years():
        let_from = date(year, 7, 1)
        record = _at_disposal(year, _MANUAL_VALUE, vigor=year)
        built = _build(year, record, (lease(start=let_from),), monthly_rent(year, amount=_RENT, months=range(7, 13)))
        boxes = _imputacion(built)

        assert boxes is not None, year
        assert boxes.porcentaje is None, year
        assert boxes.importe is None, year
        assert RentaInmuebleCause.IMPUTACION_USO_SIMULTANEO in _causes(built), year


def test_a_rustic_property_at_disposal_blocks_the_amount() -> None:
    for year in _years():
        built = _build(year, _at_disposal(year, _MANUAL_VALUE, vigor=year, naturaleza=InmuebleNaturaleza.RUSTICA))
        boxes = _imputacion(built)

        assert boxes is not None, year
        assert boxes.importe is None, year
        assert RentaInmuebleCause.IMPUTACION_RUSTICA in _causes(built), year


def test_a_property_let_all_year_imputes_nothing_and_raises_nothing() -> None:
    for year in _years():
        record = inmueble(ejercicio=year)
        built = _build(year, record, (lease(start=date(year - 1, 9, 1)),), monthly_rent(year, amount=_RENT))

        assert _imputacion(built) is None, year
        assert built.occurrences[0].column(RentaInmuebleRowField.RENTA_IMPUTADA) is None, year
        assert not _causes(built) & (_IMPUTACION_CAUSES | {RentaInmuebleCause.DAYS_UNACCOUNTED}), year


def test_the_habitual_dwelling_before_a_lease_imputes_nothing_and_accounts_for_its_days() -> None:
    for year in _years():
        let_from = date(year, 7, 1)
        dwelling = UsoInmueble(
            tipo=UsoInmuebleTipo.VIVIENDA_HABITUAL, desde=date(year - 4, 1, 1), hasta=date(year, 6, 30)
        )
        record = inmueble(ejercicio=year, usos=(dwelling,))
        built = _build(year, record, (lease(start=let_from),), monthly_rent(year, amount=_RENT, months=range(7, 13)))

        assert _imputacion(built) is None, year
        assert not _causes(built) & (_IMPUTACION_CAUSES | {RentaInmuebleCause.DAYS_UNACCOUNTED}), year


def test_days_in_no_stated_use_block_as_unaccounted() -> None:
    for year in _years():
        built = _build(
            year,
            inmueble(ejercicio=year),
            (lease(start=date(year, 7, 1)),),
            monthly_rent(year, amount=_RENT, months=range(7, 13)),
        )

        assert _imputacion(built) is None, year
        assert RentaInmuebleCause.DAYS_UNACCOUNTED in _causes(built), year
