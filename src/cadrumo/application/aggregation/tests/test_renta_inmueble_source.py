"""The ``Inmueble`` occurrence: one per property held, joined from profile rows and linked ledger rows.

Prorated expenses follow the manual's rule that a let property's expenses are
deductible "proporcional al número de días" of the ejercicio it is let; the
expected figures below are derived from the lease dates by hand, not read back
from the function under test.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest

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
from ....domain.contribuyente.arrendamiento_record import Inquilino, InquilinoEdad
from ....domain.contribuyente.inmueble_record import (
    ImportesMovimientos,
    InmuebleSituacion,
    InmuebleTitularidad,
    TitularidadRegimen,
    TitularRole,
)
from ....domain.transactions.enums import TransactionDirection
from ..renta_inmueble_findings import RentaInmuebleCause, RentaInmuebleFindingKind
from ..renta_inmueble_net import RentaInmuebleTerms
from ..renta_inmueble_resolver import resolve_renta_inmueble_terms
from ..renta_inmueble_source import (
    RentaInmuebleOccurrence,
    RentaInmuebleOccurrences,
    RentaInmuebleRowField,
    renta_inmueble_occurrences,
)
from .renta_inmueble_support import (
    TENANT_NIF,
    co_owned,
    expense,
    inmueble,
    lease,
    ledger_row,
    monthly_rent,
    profile_facts,
    rent,
    with_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_RENT = Decimal("950.00")
_COMUNIDAD = Decimal("540.00")
_TRIBUTOS = Decimal("412.00")


def _year() -> int:
    return newest_authored_edition("100")


def _days(first: date, last: date) -> int:
    return (last - first).days + 1


def _cents(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


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


def _build(year: int, inmuebles, leases, rows) -> RentaInmuebleOccurrences:
    return renta_inmueble_occurrences(
        path_values=profile_facts(tuple(inmuebles), tuple(leases)),
        transactions=tuple(rows),
        ejercicio=year,
        concepts=_concepts(year),
        terms=_terms(year),
    )


def _causes(built: RentaInmuebleOccurrences) -> set[RentaInmuebleCause]:
    return {finding.cause for finding in built.findings}


def _full_year(year: int) -> RentaInmuebleOccurrences:
    return _build(
        year,
        [inmueble(ejercicio=year)],
        [lease(start=date(year - 1, 9, 1))],
        (
            *monthly_rent(year, amount=_RENT),
            expense("comunidad", concept="comunidad", amount=_COMUNIDAD, booked=date(year, 3, 10)),
            expense("ibi", concept="tributos", amount=_TRIBUTOS, booked=date(year, 10, 5)),
        ),
    )


def _only(built: RentaInmuebleOccurrences) -> RentaInmuebleOccurrence:
    assert len(built.occurrences) == 1
    return built.occurrences[0]


def test_one_property_let_all_year_states_its_rent_expenses_and_days() -> None:
    year = _year()
    built = _full_year(year)
    occurrence = _only(built)

    assert not built.refused
    assert occurrence.index == 1
    assert occurrence.source_identity == "inmueble:0"
    assert occurrence.column(RentaInmuebleRowField.INGRESOS_INTEGROS) == _RENT * 12
    assert occurrence.gasto("comunidad") == _COMUNIDAD
    assert occurrence.gasto("tributos") == _TRIBUTOS
    assert occurrence.gasto("suministros") is None
    assert occurrence.column(RentaInmuebleRowField.DIAS_ARRENDADO) == _days(date(year, 1, 1), date(year, 12, 31))
    assert occurrence.column(RentaInmuebleRowField.ARRENDADO) is True
    assert occurrence.column(RentaInmuebleRowField.INQUILINO_1_NIF) == TENANT_NIF
    assert occurrence.column(RentaInmuebleRowField.INQUILINO_1_NIF_EXTRANJERO) is None
    assert occurrence.column(RentaInmuebleRowField.INQUILINO_2_NIF) is None
    assert occurrence.column(RentaInmuebleRowField.FECHA_CONTRATO) == date(year - 1, 9, 1).isoformat()
    assert occurrence.column(RentaInmuebleRowField.SITUACION) == InmuebleSituacion.CATASTRAL_COMUN.value
    assert occurrence.column(RentaInmuebleRowField.URBANA) is True
    assert occurrence.column(RentaInmuebleRowField.RUSTICA) is None
    assert occurrence.column(RentaInmuebleRowField.PORCENTAJE_PROPIEDAD) == Decimal(100)
    assert occurrence.column(RentaInmuebleRowField.FECHA_TRANSMISION) is None
    # The fixture states no acquisition cost, nothing about what earlier years left pending, and
    # not whether its contract signed after May 2023 lies in a stressed-market zone; each withholds
    # the net chain.
    assert _causes(built) == {
        RentaInmuebleCause.BOXES_NOT_OFFERED,
        RentaInmuebleCause.ACQUISITION_COST_UNSTATED,
        RentaInmuebleCause.PENDING_EXPENSES_UNSTATED,
        RentaInmuebleCause.REDUCTION_FACT_UNSTATED,
    }
    assert occurrence.column(RentaInmuebleRowField.RENDIMIENTO_NETO) is None


def test_a_part_year_lease_counts_its_days_and_prorates_the_expenses_by_them() -> None:
    year = _year()
    start = date(year, 7, 1)
    built = _build(
        year,
        [inmueble(ejercicio=year)],
        [lease(start=start)],
        (
            *monthly_rent(year, amount=_RENT, months=range(7, 13)),
            expense("comunidad", concept="comunidad", amount=_COMUNIDAD, booked=date(year, 3, 10)),
        ),
    )
    occurrence = _only(built)
    let = _days(start, date(year, 12, 31))
    in_year = _days(date(year, 1, 1), date(year, 12, 31))

    assert occurrence.dias_arrendado == let
    assert occurrence.ingresos == _RENT * 6
    assert occurrence.gasto("comunidad") == _cents(_COMUNIDAD * let / in_year)
    assert RentaInmuebleCause.DAYS_NOT_LET in _causes(built)
    assert not built.refused


@pytest.mark.parametrize(
    ("scope", "share"),
    [(ImportesMovimientos.INMUEBLE_COMPLETO, Decimal("0.5")), (ImportesMovimientos.PARTE_PROPIA, Decimal(1))],
)
def test_a_co_owner_declares_his_share_applied_last(scope: ImportesMovimientos, share: Decimal) -> None:
    year = _year()
    built = _build(
        year,
        [co_owned(ejercicio=year, scope=scope)],
        [lease(start=date(year - 1, 9, 1))],
        (
            *monthly_rent(year, amount=Decimal("1000.01")),
            expense("comunidad", concept="comunidad", amount=Decimal("333.33"), booked=date(year, 3, 10)),
        ),
    )
    occurrence = _only(built)

    assert occurrence.ingresos == _cents(Decimal("1000.01") * 12 * share)
    assert occurrence.gasto("comunidad") == _cents(Decimal("333.33") * share)
    assert occurrence.column(RentaInmuebleRowField.PORCENTAJE_PROPIEDAD) == Decimal(50)
    assert not built.refused


def test_the_taxable_base_excluding_iva_is_the_income_where_the_row_states_it() -> None:
    year = _year()
    built = _build(
        year,
        [inmueble(ejercicio=year)],
        [lease(start=date(year - 1, 9, 1))],
        [
            rent(
                "local",
                amount=Decimal("1210.00"),
                booked=date(year, 2, 1),
                taxable_base=Decimal("1000.00"),
                iva_amount=Decimal("210.00"),
                iva_rate=Decimal("0.21"),
            )
        ],
    )

    assert _only(built).ingresos == Decimal("1000.00")


def test_rent_falls_in_the_year_it_accrues_not_the_year_it_was_booked() -> None:
    year = _year()
    late = rent("late", amount=_RENT, booked=date(year + 1, 1, 10), accrual_date=date(year, 12, 1))
    early = rent("early", amount=_RENT, booked=date(year, 1, 10), accrual_date=date(year - 1, 12, 1))
    built = _build(year, [inmueble(ejercicio=year)], [lease(start=date(year - 1, 9, 1))], [late, early])

    assert _only(built).ingresos == _RENT


def test_properties_are_ordered_by_row_key_and_one_not_held_is_absent() -> None:
    year = _year()
    built = _build(
        year,
        [
            inmueble(2, ejercicio=year),
            inmueble(0, ejercicio=year),
            inmueble(1, ejercicio=year, fecha_adquisicion=date(year + 1, 2, 1)),
        ],
        [
            lease(0, inmueble_clave=0, start=date(year - 1, 1, 1)),
            lease(1, inmueble_clave=2, start=date(year - 1, 1, 1)),
        ],
        (*monthly_rent(year, amount=_RENT, lease_clave=0), *monthly_rent(year, amount=_RENT, lease_clave=1)),
    )

    assert [occurrence.source_identity for occurrence in built.occurrences] == ["inmueble:0", "inmueble:2"]
    assert [occurrence.index for occurrence in built.occurrences] == [1, 2]


def _fields(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return {str(key): item for key, item in value.items()}


def _refusal(year: int, **changes: object) -> set[RentaInmuebleCause]:
    property_fields = changes.pop("inmueble_fields", {})
    lease_fields = changes.pop("lease_fields", {})
    rows = changes.pop("rows", monthly_rent(year, amount=_RENT))
    built = _build(
        year,
        [with_fields(inmueble(ejercicio=year), _fields(property_fields))],
        [with_fields(lease(start=date(year - 1, 9, 1)), _fields(lease_fields))],
        rows,
    )
    assert built.refused
    assert all(
        finding.door is not None for finding in built.findings if finding.kind is RentaInmuebleFindingKind.REFUSAL
    )
    return _causes(built)


def test_each_unsettled_join_or_fact_refuses_the_occurrences() -> None:
    year = _year()
    rows = monthly_rent(year, amount=_RENT)
    booked = date(year, 4, 1)
    cases: dict[RentaInmuebleCause, dict[str, object]] = {
        RentaInmuebleCause.TITULARIDAD_UNSTATED: {"inmueble_fields": {"titularidad": None}},
        RentaInmuebleCause.NATURALEZA_UNSTATED: {"inmueble_fields": {"naturaleza": None}},
        RentaInmuebleCause.LEASE_WITHOUT_INCOME: {"rows": ()},
        RentaInmuebleCause.RELATIVE_FACT_UNSTATED: {"lease_fields": {"arrendatario_pariente_art24": None}},
        RentaInmuebleCause.ROW_NAMES_NO_LEASE: {
            "rows": (*rows, rent("stray", lease_clave=7, amount=_RENT, booked=booked))
        },
        RentaInmuebleCause.ROW_NAMES_NO_PROPERTY: {
            "rows": (*rows, expense("stray", concept="comunidad", inmueble_clave=7, amount=_RENT, booked=booked))
        },
        RentaInmuebleCause.EXPENSE_ROW_ON_LEASE: {
            "rows": (
                *rows,
                ledger_row(
                    "wrong", amount=_RENT, direction=TransactionDirection.OUTGOING, booked=booked, arrendamiento_ref="0"
                ),
            )
        },
        RentaInmuebleCause.INCOME_ROW_ON_PROPERTY: {
            "rows": (
                *rows,
                ledger_row(
                    "wrong", amount=_RENT, direction=TransactionDirection.INCOMING, booked=booked, inmueble_ref="0"
                ),
            )
        },
        RentaInmuebleCause.EXPENSE_ROW_WITHOUT_CONCEPT: {
            "rows": (
                *rows,
                ledger_row(
                    "bare", amount=_RENT, direction=TransactionDirection.OUTGOING, booked=booked, inmueble_ref="0"
                ),
            )
        },
        RentaInmuebleCause.INCOME_OUTSIDE_LEASE: {
            "lease_fields": {"fecha_fin": date(year, 6, 30)},
        },
        RentaInmuebleCause.CURRENCY_UNCONVERTED: {
            "rows": (*rows, rent("usd", amount=_RENT, booked=booked, currency="USD")),
        },
    }
    for cause, changes in cases.items():
        assert cause in _refusal(year, **changes), cause


def test_a_lease_naming_no_held_property_refuses() -> None:
    year = _year()
    built = _build(
        year,
        [inmueble(ejercicio=year)],
        [lease(start=date(year - 1, 9, 1)), lease(1, inmueble_clave=5, start=date(year - 1, 9, 1))],
        monthly_rent(year, amount=_RENT),
    )

    assert RentaInmuebleCause.LEASE_NAMES_NO_PROPERTY in _causes(built)
    assert built.refused


def test_an_unreadable_property_row_refuses_without_echoing_its_value() -> None:
    year = _year()
    facts = profile_facts((inmueble(ejercicio=year),), (lease(start=date(year - 1, 9, 1)),))
    facts["renta_inmueble.0.fecha_adquisicion"] = "not-a-date"
    built = renta_inmueble_occurrences(
        path_values=facts,
        transactions=monthly_rent(year, amount=_RENT),
        ejercicio=year,
        concepts=_concepts(year),
        terms=_terms(year),
    )

    assert built.refused
    assert [finding.message for finding in built.findings if finding.cause is RentaInmuebleCause.RECORD_UNREADABLE] == [
        "renta_inmueble:0: a property or lease record of the profile cannot be read"
    ]


def _blocking(year: int, inmuebles, leases, rows) -> set[RentaInmuebleCause]:
    built = _build(year, inmuebles, leases, rows)
    assert not built.refused
    return {finding.cause for finding in built.findings if finding.kind is RentaInmuebleFindingKind.BLOCKING}


def test_each_deferred_case_keeps_its_rows_and_blocks_filing() -> None:
    year = _year()
    rows = monthly_rent(year, amount=_RENT)
    start = date(year - 1, 9, 1)
    held_by_spouse = InmuebleTitularidad(
        regimen=TitularidadRegimen.PLENO_DOMINIO, titular=TitularRole.CONYUGE, porcentaje_propiedad=Decimal(100)
    )
    usufruct = InmuebleTitularidad(
        regimen=TitularidadRegimen.USUFRUCTO, titular=TitularRole.PRIMER_DECLARANTE, porcentaje_usufructo=Decimal(100)
    )
    four_tenants = tuple(
        Inquilino(nif=f"X000000{digit}T", franja_edad=InquilinoEdad.OTRA, extranjero=False) for digit in range(4)
    )
    cases = {
        RentaInmuebleCause.TITULAR_NOT_DECLARANT: (
            [inmueble(ejercicio=year, titularidad=held_by_spouse)],
            [lease(start=start)],
            rows,
        ),
        RentaInmuebleCause.REGIME_NOT_PLENO_DOMINIO: (
            [inmueble(ejercicio=year, titularidad=usufruct)],
            [lease(start=start)],
            rows,
        ),
        RentaInmuebleCause.PROPERTY_ABROAD_LET: (
            [inmueble(ejercicio=year, situacion=InmuebleSituacion.EXTRANJERO, referencia_catastral=None)],
            [lease(start=start)],
            rows,
        ),
        RentaInmuebleCause.ACCESSORY_PROPERTY: (
            [inmueble(ejercicio=year), inmueble(1, ejercicio=year, inmueble_principal=0)],
            [lease(start=start), lease(1, inmueble_clave=1, start=start)],
            (*rows, *monthly_rent(year, amount=Decimal(50), lease_clave=1)),
        ),
        RentaInmuebleCause.TENANTS_BEYOND_NUMBERED: (
            [inmueble(ejercicio=year)],
            [lease(start=start, inquilinos=four_tenants)],
            rows,
        ),
        RentaInmuebleCause.RELATIVE_TENANT: (
            [inmueble(ejercicio=year)],
            [lease(start=start, arrendatario_pariente_art24=True)],
            rows,
        ),
        RentaInmuebleCause.IMPROVEMENT_IN_EJERCICIO: (
            [inmueble(ejercicio=year)],
            [lease(start=start)],
            (*rows, expense("obra", concept="mejora", amount=Decimal(9000), booked=date(year, 5, 2))),
        ),
        RentaInmuebleCause.HELD_PART_OF_EJERCICIO: (
            [inmueble(ejercicio=year, fecha_adquisicion=date(year, 1, 1), fecha_transmision=date(year, 10, 31))],
            [lease(start=start, fecha_fin=date(year, 10, 31))],
            monthly_rent(year, amount=_RENT, months=range(1, 11)),
        ),
        RentaInmuebleCause.SEVERAL_LEASES: (
            [inmueble(ejercicio=year)],
            [lease(start=start, fecha_fin=date(year, 5, 31)), lease(1, start=date(year, 6, 1))],
            (
                *monthly_rent(year, amount=_RENT, months=range(1, 6)),
                *monthly_rent(year, amount=_RENT, lease_clave=1, months=range(6, 13)),
            ),
        ),
        RentaInmuebleCause.CONCURRENT_LEASES: (
            [inmueble(ejercicio=year)],
            [lease(start=start), lease(1, start=date(year, 6, 1))],
            (*rows, *monthly_rent(year, amount=_RENT, lease_clave=1, months=range(6, 13))),
        ),
        RentaInmuebleCause.DAYS_NOT_LET: ([inmueble(ejercicio=year)], [], ()),
    }
    for cause, (inmuebles, leases, case_rows) in cases.items():
        assert cause in _blocking(year, inmuebles, leases, case_rows), cause


def test_a_property_held_but_not_let_states_no_rent_and_no_days() -> None:
    year = _year()
    built = _build(year, [inmueble(ejercicio=year)], [], ())
    occurrence = _only(built)

    assert occurrence.ingresos is None
    assert occurrence.column(RentaInmuebleRowField.DIAS_ARRENDADO) is None
    assert occurrence.column(RentaInmuebleRowField.ARRENDADO) is None
    assert occurrence.net is None
    assert RentaInmuebleCause.PENDING_EXPENSES_UNSTATED not in _causes(built)


def test_every_supported_year_counts_its_own_days() -> None:
    for year in supported_exercises_with_projection("100"):
        occurrence = _only(_full_year(year))
        assert occurrence.dias_arrendado == _days(date(year, 1, 1), date(year, 12, 31)), year
        assert occurrence.ingresos == _RENT * 12, year
