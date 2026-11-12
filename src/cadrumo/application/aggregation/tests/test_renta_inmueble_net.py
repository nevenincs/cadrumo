"""The net chain of a let property: amortisation, the interest-and-repair limit, the net yield, the reduction.

The expected figures are the Manual práctico de Renta's own worked examples
(the 2025 edition: the inherited dwelling of page 279 and the dwelling let
under two contracts of pages 298 to 300), or are derived by hand from the rule
the test names; none is read back from the function under test. Rates are the
ones the manual prints: 3 per 100 for the building, 60 per 100 for a contract
before 26 May 2023 and 50 per 100 for a later one meeting no higher tier.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pytest

from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.gasto_capital_inmobiliario import (
    GastoCapitalInmobiliarioCatalogue,
    resolve_gasto_capital_inmobiliario_catalogue,
)
from ....domain.calculations.registry.tests.authored_editions import (
    newest_authored_edition,
    revision_selected_for,
    supported_exercises_with_projection,
)
from ....domain.contribuyente.arrendamiento_record import ArrendamientoRecord
from ....domain.contribuyente.inmueble_record import AdquisicionTitulo, InmuebleRecord, ValorCatastral
from ....domain.renta.retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord
from ....domain.transactions.models import Transaction
from ..renta_inmueble_findings import RentaInmuebleCause
from ..renta_inmueble_net import RentaInmuebleNet, RentaInmuebleNetInputs, RentaInmuebleTerms, renta_inmueble_net
from ..renta_inmueble_resolver import resolve_renta_inmueble_terms
from ..renta_inmueble_source import (
    RentaInmuebleOccurrence,
    RentaInmuebleOccurrences,
    RentaInmuebleRowField,
    renta_inmueble_occurrences,
)
from .renta_inmueble_support import (
    TENANT_NIF,
    expense,
    inmueble,
    lease,
    monthly_rent,
    profile_facts,
    with_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_RATE_BUILDING = Decimal("0.03")
_RATE_LEGACY = Decimal("0.60")
_RATE_RESIDUAL_TIER = Decimal("0.50")
_RENT = Decimal("950.00")


def _cents(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _days(first: date, last: date) -> int:
    return (last - first).days + 1


def _concepts(year: int) -> GastoCapitalInmobiliarioCatalogue:
    return resolve_gasto_capital_inmobiliario_catalogue(effective_date=date(year, 12, 31))


def _terms(year: int) -> RentaInmuebleTerms:
    with bundled_indexed_authority().operation() as operation:
        return resolve_renta_inmueble_terms(
            modelo="100",
            revision_id=revision_selected_for("100", year, "0A").id,
            devengo=date(year, 12, 31),
            operation=operation,
        )


def _build(
    year: int,
    inmuebles: list[InmuebleRecord],
    leases: list[ArrendamientoRecord],
    rows: tuple[Transaction, ...],
    withholding: tuple[RetencionSoportadaRecord, ...] = (),
) -> RentaInmuebleOccurrences:
    return renta_inmueble_occurrences(
        path_values=profile_facts(tuple(inmuebles), tuple(leases)),
        transactions=rows,
        ejercicio=year,
        concepts=_concepts(year),
        terms=_terms(year),
        withholding=withholding,
    )


def _causes(built: RentaInmuebleOccurrences) -> set[RentaInmuebleCause]:
    return {finding.cause for finding in built.findings}


def _only(built: RentaInmuebleOccurrences) -> RentaInmuebleOccurrence:
    assert len(built.occurrences) == 1
    return built.occurrences[0]


def _inherited(year: int, **fields: object) -> InmuebleRecord:
    """The manual's inherited dwelling: ISD value 100.000, expenses 2.000, cadastral value 80.000, land 20 %."""
    payload: dict[str, object] = {
        "adquisicion_titulo": AdquisicionTitulo.LUCRATIVA,
        "importe_adquisicion": Decimal(100000),
        "gastos_tributos_adquisicion": Decimal(2000),
        "valores_catastrales": (ValorCatastral(year=year, total=Decimal(80000), construccion=Decimal(64000)),),
    }
    return with_fields(inmueble(ejercicio=year), {**payload, **fields})


def test_every_supported_year_amortises_the_inherited_dwelling_on_its_acquisition_cost() -> None:
    for year in supported_exercises_with_projection("100"):
        built = _build(year, [_inherited(year)], [lease(start=date(year - 1, 9, 1))], monthly_rent(year, amount=_RENT))
        occurrence = _only(built)

        assert occurrence.column(RentaInmuebleRowField.PORCENTAJE_CONSTRUCCION) == Decimal("80.00"), year
        assert occurrence.column(RentaInmuebleRowField.IMPORTE_ADQUISICION) == Decimal(100000), year
        assert occurrence.column(RentaInmuebleRowField.GASTOS_ADQUISICION) == Decimal(2000), year
        assert occurrence.column(RentaInmuebleRowField.VALOR_CATASTRAL) == Decimal(80000), year
        assert occurrence.column(RentaInmuebleRowField.VALOR_CATASTRAL_CONSTRUCCION) == Decimal(64000), year
        # Manual, page 279: the greater of 80 % of (100.000 + 2.000) and 80 % of 80.000, at 3 per 100.
        assert occurrence.column(RentaInmuebleRowField.BASE_AMORTIZACION) == Decimal("81600.00"), year
        assert occurrence.column(RentaInmuebleRowField.AMORTIZACION) == Decimal("2448.00"), year


def test_what_earlier_years_left_pending_is_never_inferred() -> None:
    year = newest_authored_edition("100")
    built = _build(year, [_inherited(year)], [lease(start=date(year - 1, 9, 1))], monthly_rent(year, amount=_RENT))
    occurrence = _only(built)

    assert RentaInmuebleCause.PENDING_EXPENSES_UNSTATED in _causes(built)
    assert occurrence.column(RentaInmuebleRowField.RENDIMIENTO_NETO) is None
    assert occurrence.column(RentaInmuebleRowField.RENDIMIENTO_NETO_REDUCIDO) is None
    assert occurrence.column(RentaInmuebleRowField.INTERESES_REPARACION_APLICADOS) is None


def _two_contracts(year: int) -> tuple[list[InmuebleRecord], list[ArrendamientoRecord], tuple[Transaction, ...]]:
    """The manual's dwelling in a zone not tensioned, let under a 2021 contract and from 1 June under a new one."""
    record = inmueble(
        ejercicio=year,
        fecha_adquisicion=date(year - 25, 3, 1),
        importe_adquisicion=Decimal(120000),
        gastos_tributos_adquisicion=Decimal(9000),
        valores_catastrales=(ValorCatastral(year=year, total=Decimal(76200), construccion=Decimal(39120)),),
    )
    leases = [
        lease(0, start=date(year - 4, 1, 1), end=date(year, 5, 31)),
        lease(1, start=date(year, 6, 1), zona_tensionada=False),
    ]
    rows = (
        *monthly_rent(year, amount=Decimal(900), lease_clave=0, months=range(1, 6)),
        *monthly_rent(year, amount=Decimal(1000), lease_clave=1, months=range(6, 13)),
        expense("intereses", concept="interes_financiacion", amount=Decimal(400), booked=date(year, 6, 30)),
        expense("fachada", concept="reparacion_conservacion", amount=Decimal(500), booked=date(year, 4, 2)),
        expense("ibi", concept="tributos", amount=Decimal(320), booked=date(year, 9, 1)),
        expense("comunidad", concept="comunidad", amount=Decimal(900), booked=date(year, 2, 1)),
    )
    return [record], leases, rows


def test_the_two_contract_dwelling_states_the_manual_amortisation_figures() -> None:
    year = newest_authored_edition("100")
    built = _build(year, *_two_contracts(year))
    occurrence = _only(built)

    assert occurrence.column(RentaInmuebleRowField.INGRESOS_INTEGROS) == Decimal(11500)
    assert occurrence.gasto("interes_financiacion") == Decimal(400)
    assert occurrence.gasto("reparacion_conservacion") == Decimal(500)
    # Manual, page 300, note (2): 39.120 / 76.200 = 51,34 %; 129.000 x 51,34 % = 66.228,60; 3 % = 1.986,86.
    assert occurrence.column(RentaInmuebleRowField.PORCENTAJE_CONSTRUCCION) == Decimal("51.34")
    assert occurrence.column(RentaInmuebleRowField.BASE_AMORTIZACION) == Decimal("66228.60")
    assert occurrence.column(RentaInmuebleRowField.AMORTIZACION) == Decimal("1986.86")
    assert RentaInmuebleCause.SEVERAL_LEASES in _causes(built)


def _inputs(occurrence: RentaInmuebleOccurrence, *, pendiente: Decimal, year: int) -> RentaInmuebleNetInputs:
    """Restate the occurrence as the chain's inputs, the earlier ejercicios' pending amount stated by the test."""
    first, last = date(year, 1, 1), date(year, 12, 31)
    lease_days = {
        item.clave: _days(max(first, item.fecha_inicio), min(last, item.fecha_fin or last))
        for item in occurrence.leases
    }
    lease_rent = {0: Decimal(4500), 1: Decimal(7000)}
    assert occurrence.ingresos is not None
    return RentaInmuebleNetInputs(
        record=occurrence.inmueble,
        leases=occurrence.leases,
        ejercicio_first=first,
        ejercicio_last=last,
        days_let=occurrence.dias_arrendado,
        lease_days=lease_days,
        ingresos=occurrence.ingresos,
        lease_ingresos={clave: lease_rent[clave] for clave in lease_days},
        gastos=occurrence.gastos,
        improvements_before=Decimal(0),
        improvements_in=Decimal(0),
        withholding=(),
        pendiente=pendiente,
    )


def _chain(year: int, pendiente: Decimal) -> RentaInmuebleNet:
    occurrence = _only(_build(year, *_two_contracts(year)))
    return renta_inmueble_net(
        _inputs(occurrence, pendiente=pendiente, year=year), terms=_terms(year), concepts=_concepts(year)
    )


def test_stated_nothing_pending_the_two_contract_dwelling_reduces_each_contract_on_its_own_days() -> None:
    year = newest_authored_edition("100")
    net = _chain(year, Decimal(0))
    deductions = Decimal(900) + Decimal(320) + Decimal(900) + Decimal("1986.86")
    days = _days(date(year, 1, 1), date(year, 12, 31))
    first_days = _days(date(year, 1, 1), date(year, 5, 31))
    first_net = Decimal(4500) - deductions * first_days / days
    second_net = Decimal(7000) - deductions * (days - first_days) / days
    reduction = _cents(first_net * _RATE_LEGACY) + _cents(second_net * _RATE_RESIDUAL_TIER)

    # Manual, note (1): interest 400 plus repairs 500 are far below the income of 11.500.
    assert net.intereses_reparacion_aplicados == Decimal(900)
    assert net.intereses_reparacion_pendientes is None
    assert net.gastos_pendientes_aplicados is None
    assert net.rendimiento_neto == Decimal(11500) - deductions
    assert net.reduccion_aplicable is True
    assert net.reduccion == reduction
    assert net.rendimiento_neto_reducido == Decimal(11500) - deductions - reduction
    assert net.causes == []


def test_earlier_pending_amounts_take_the_room_first_and_the_rest_of_the_year_is_carried() -> None:
    year = newest_authored_edition("100")
    net = _chain(year, Decimal(11000))

    # LIRPF art. 23.1.a.1.º: the limit is the gross income of 11.500; 11.000 earlier, 500 of this year's 900.
    assert net.gastos_pendientes_aplicados == Decimal(11000)
    assert net.intereses_reparacion_aplicados == Decimal(500)
    assert net.intereses_reparacion_pendientes == Decimal(400)


def test_a_cap_that_can_bind_requires_the_attested_cumulative_amortisation() -> None:
    year = newest_authored_edition("100")
    old = _inherited(year, fecha_adquisicion=date(year - 40, 1, 1))
    built = _build(year, [old], [lease(start=date(year - 1, 9, 1))], monthly_rent(year, amount=_RENT))

    assert RentaInmuebleCause.CUMULATIVE_AMORTISATION_UNSTATED in _causes(built)
    assert _only(built).column(RentaInmuebleRowField.AMORTIZACION) is None

    attested = _inherited(
        year,
        fecha_adquisicion=date(year - 40, 1, 1),
        amortizacion_acumulada=Decimal(81000),
        amortizacion_acumulada_desde=date(year, 1, 1),
    )
    capped = _build(year, [attested], [lease(start=date(year - 1, 9, 1))], monthly_rent(year, amount=_RENT))
    # The acquisition value without the land is 81.600, so 600 remain of it.
    assert _only(capped).column(RentaInmuebleRowField.AMORTIZACION) == Decimal("600.00")
    assert RentaInmuebleCause.CUMULATIVE_AMORTISATION_UNSTATED not in _causes(capped)


def test_a_stated_land_value_is_excluded_before_the_cadastral_split() -> None:
    year = newest_authored_edition("100")
    record = _inherited(year, valor_suelo=Decimal(30000), valores_catastrales=())
    occurrence = _only(_build(year, [record], [lease(start=date(year - 1, 9, 1))], monthly_rent(year, amount=_RENT)))

    # RIRPF art. 14.2.a: (100.000 + 2.000) x 70.000 / 100.000 = 71.400, at 3 per 100.
    assert occurrence.column(RentaInmuebleRowField.BASE_AMORTIZACION) == Decimal("71400.00")
    assert occurrence.column(RentaInmuebleRowField.AMORTIZACION) == Decimal("2142.00")
    assert occurrence.column(RentaInmuebleRowField.PORCENTAJE_CONSTRUCCION) is None


def test_each_unstated_fact_of_the_chain_is_a_blocking_finding_with_its_door() -> None:
    year = newest_authored_edition("100")
    start = date(year - 1, 9, 1)
    cases = {
        RentaInmuebleCause.ACQUISITION_COST_UNSTATED: _inherited(year, importe_adquisicion=None),
        RentaInmuebleCause.CADASTRAL_VALUES_UNSTATED: _inherited(year, valores_catastrales=()),
    }
    for cause, record in cases.items():
        built = _build(year, [record], [lease(start=start)], monthly_rent(year, amount=_RENT))
        (finding,) = (finding for finding in built.findings if finding.cause is cause)
        assert not built.refused, cause
        assert finding.door is not None, cause
        assert _only(built).column(RentaInmuebleRowField.AMORTIZACION) is None, cause

    tiered = lease(start=date(year, 1, 1))
    built = _build(year, [_inherited(year)], [tiered], monthly_rent(year, amount=_RENT))
    assert RentaInmuebleCause.REDUCTION_FACT_UNSTATED in _causes(built)


def _withholding(payer: str, retencion: str, year: int) -> RetencionSoportadaRecord:
    return RetencionSoportadaRecord.model_validate(
        {
            "ejercicio": year,
            "payer_tax_id": payer,
            "payer_ref": "c" * 64,
            "income_class": RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO,
            "importe_integro_dinerario": _RENT * 12,
            "valoracion_especie": Decimal("0.00"),
            "retencion": Decimal(retencion),
            "ingreso_a_cuenta": Decimal("0.00"),
            "ingreso_a_cuenta_repercutido": Decimal("0.00"),
            "origin": RetencionSoportadaOrigen.OPERATOR_DECLARATION,
            "captured_at": datetime(year + 1, 2, 1, 9, tzinfo=UTC),
        }
    )


def test_a_tenant_s_withholding_is_placed_on_the_property_its_lease_names() -> None:
    year = newest_authored_edition("100")
    start = date(year - 1, 9, 1)
    placed = _build(
        year,
        [_inherited(year)],
        [lease(start=start)],
        monthly_rent(year, amount=_RENT),
        (_withholding(TENANT_NIF, "2052.00", year),),
    )
    assert _only(placed).column(RentaInmuebleRowField.RETENCIONES) == Decimal("2052.00")

    stranger = _build(
        year,
        [_inherited(year)],
        [lease(start=start)],
        monthly_rent(year, amount=_RENT),
        (_withholding("12345678Z", "2052.00", year),),
    )
    assert RentaInmuebleCause.WITHHOLDING_PAYER_NO_TENANT in _causes(stranger)
    assert _only(stranger).column(RentaInmuebleRowField.RETENCIONES) == Decimal(0)

    two = _build(
        year,
        [_inherited(year), _inherited(year, clave=1)],
        [lease(start=start), lease(1, inmueble_clave=1, start=start)],
        (*monthly_rent(year, amount=_RENT), *monthly_rent(year, amount=_RENT, lease_clave=1)),
        (_withholding(TENANT_NIF, "2052.00", year),),
    )
    assert RentaInmuebleCause.WITHHOLDING_PAYER_SEVERAL_PROPERTIES in _causes(two)


def test_rent_of_a_property_acquired_on_the_first_day_reaches_its_reduced_net_yield() -> None:
    year = newest_authored_edition("100")
    record = _inherited(year, fecha_adquisicion=date(year, 1, 1))
    built = _build(
        year,
        [record],
        [lease(start=date(year, 1, 1), zona_tensionada=False)],
        monthly_rent(year, amount=_RENT),
    )
    occurrence = _only(built)
    net = _RENT * 12 - Decimal("2448.00")

    assert RentaInmuebleCause.PENDING_EXPENSES_UNSTATED not in _causes(built)
    assert occurrence.column(RentaInmuebleRowField.RENDIMIENTO_NETO) == net
    assert occurrence.column(RentaInmuebleRowField.REDUCCION) == _cents(net * _RATE_RESIDUAL_TIER)
    assert occurrence.column(RentaInmuebleRowField.RENDIMIENTO_NETO_REDUCIDO) == net - _cents(net * _RATE_RESIDUAL_TIER)
    assert occurrence.column(RentaInmuebleRowField.REDUCCION_APLICABLE) is True


def _one_lease_net(year: int, contract: date, **lease_fields: object) -> tuple[RentaInmuebleNet, Decimal]:
    """Run the chain over the inherited dwelling let from ``contract`` to the end of ``year``, nothing pending.

    Returns the chain and its net yield, derived here: the rent less the
    building amortisation for the days let (RIRPF art. 14).
    """
    first, last = date(year, 1, 1), date(year, 12, 31)
    record = _inherited(year)
    let = with_fields(lease(start=contract), lease_fields)
    days = _days(max(first, contract), last)
    ingresos = _RENT * 12
    inputs = RentaInmuebleNetInputs(
        record=record,
        leases=(let,),
        ejercicio_first=first,
        ejercicio_last=last,
        days_let=days,
        lease_days={let.clave: days},
        ingresos=ingresos,
        lease_ingresos={let.clave: ingresos},
        gastos={},
        improvements_before=Decimal(0),
        improvements_in=Decimal(0),
        withholding=(),
        pendiente=Decimal(0),
    )
    net = renta_inmueble_net(inputs, terms=_terms(year), concepts=_concepts(year))
    amortizacion = _cents(Decimal("81600.00") * _RATE_BUILDING * days / _days(first, last))
    return net, ingresos - amortizacion


def test_every_supported_year_reduces_a_contract_from_the_cut_off_by_its_regime() -> None:
    for year in supported_exercises_with_projection("100"):
        rules = _terms(year).reduction_rules
        contract = rules.contract_cut_off if rules.contract_cut_off <= date(year, 12, 31) else date(year, 1, 1)
        net, expected_net = _one_lease_net(year, contract, zona_tensionada=False)
        legacy = date(year, 12, 31) < rules.regime_start or contract < rules.contract_cut_off
        rate = _RATE_LEGACY if legacy else _RATE_RESIDUAL_TIER

        assert net.rendimiento_neto == expected_net, year
        assert net.reduccion_aplicable is True, year
        assert net.reduccion == _cents(expected_net * rate), year
        assert net.causes == [], year


def test_every_supported_year_keeps_sixty_per_cent_for_a_contract_before_the_cut_off() -> None:
    for year in supported_exercises_with_projection("100"):
        rules = _terms(year).reduction_rules
        net, expected_net = _one_lease_net(year, min(rules.contract_cut_off - timedelta(days=1), date(year, 1, 1)))

        assert net.reduccion == _cents(expected_net * _RATE_LEGACY), year


def test_a_lau_breach_reduces_nothing_and_an_unstated_zone_fact_leaves_the_yield_open() -> None:
    year = newest_authored_edition("100")
    cut_off = _terms(year).reduction_rules.contract_cut_off
    breach, expected_net = _one_lease_net(year, cut_off, zona_tensionada=True, incumple_lau_17_6=True)
    unstated, _ = _one_lease_net(year, cut_off, zona_tensionada=True)

    assert breach.reduccion is None
    assert breach.rendimiento_neto_reducido == expected_net
    assert unstated.rendimiento_neto_reducido is None
    assert unstated.causes == [RentaInmuebleCause.REDUCTION_FACT_UNSTATED]
