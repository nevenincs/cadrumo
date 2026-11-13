"""Three let properties of one filer, carried by the real resolver from the records to boxes 0149 to 0156.

The expected figures are derived by hand in this file from the rules each step
names, never read back from the code under test. The texts are the bundled
corpus copies:

* LIRPF art. 23.1.a.1.º (``normatives/html/ley-35-2006.html.extracted.md``
  line 372) and RIRPF art. 13.a (``rd-439-2007.html.extracted.md`` lines 391
  and 392): financing interest and repairs, together with what earlier years
  left pending, are limited per property to its gross income; earlier pending
  amounts are applied in the years that follow.
* LIRPF art. 23.1.a.2.º (line 373), RIRPF art. 13.b and 13.g (lines 393 and
  401): taxes and community fees are deductible without that limit.
* LIRPF art. 23.1.b (line 376) and RIRPF art. 14.2.a (lines 409 and 410): the
  building is amortised at 3 per 100 of the greater of the acquisition cost and
  the cadastral value, the land excluded; without a stated land value the cost
  is split by the year's cadastral values.
* Manual práctico de Renta 2024, parte 1 (``manuals/renta/2024/part1/
  source.pdf.extracted.md`` lines 11312 to 11314): for a property let part of
  the year, the yield is determined in proportion to the days it was let.
* LIRPF art. 11.3 (line 154): a co-owner declares the yield of the share the
  title gives.
* LIRPF art. 23.2 as worded at 31 December 2021
  (``ley-35-2006-art-23-2021.html.extracted.md`` line 11), kept for contracts
  made before Ley 12/2023 came into force by disposición transitoria
  trigésima octava (``ley-35-2006.html.extracted.md`` line 3918): the positive
  net yield of a dwelling lease is reduced by 60 per 100.

Every lease here was made before that law, so the 60 per 100 holds in every
year of the support envelope. Properties one and three were first let when
they were acquired, five years before the ejercicio, and property two in it.
Property one states 300.00 left pending by the ejercicio before and nothing by
the others of the carry window; property three states that no origin year left
anything pending, and property two, first let in the ejercicio, needs no
statement.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pytest

from ....core.period import Period
from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.renta_inmueble_bindings import (
    RentaInmuebleOriginPart,
    renta_inmueble_columns,
    renta_inmueble_origin_columns,
    renta_inmueble_totals,
)
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, revision_selected_for
from ....domain.contribuyente.arrendamiento_record import Inquilino, InquilinoEdad
from ....domain.contribuyente.inmueble_record import (
    ImportesMovimientos,
    InmuebleTitularidad,
    TitularidadRegimen,
    TitularRole,
    ValorCatastral,
)
from ....domain.modelos.calculation_revision_operator_layer import ATTESTED_ZERO, RowCarryAttestation
from ....domain.renta.retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord
from ....domain.transactions.models import TransactionCatalogue
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...modelo.work_profile import ModeloWorkProfile
from ..renta_inmueble_findings import RentaInmuebleCause
from ..renta_inmueble_resolver import RentaInmuebleSourceResolver, resolve_renta_inmueble_terms
from ..renta_inmueble_source import RentaInmuebleRowField
from ..retencion_soportada_repository import RetencionSoportadaPorts
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .ledger_source_mesh_support import BUCKET_ID, InMemoryTransactionCatalogueRepository, m100_revision
from .renta_inmueble_support import TENANT_NIF, expense, inmueble, lease, monthly_rent, profile_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_SECOND_TENANT = "12345678Z"
_THIRD_TENANT = "87654321X"
_BUILDING_RATE = Decimal("0.03")
_REDUCTION_RATE = Decimal("0.60")
_PENDING_ON_ONE = Decimal("300.00")
_WITHHELD_ON_ONE = Decimal("2052.00")


def _cents(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _year_days(year: int) -> int:
    return (date(year, 12, 31) - date(year, 1, 1)).days + 1


def _contract_before_the_law(year: int) -> date:
    """A contract date before Ley 12/2023, on or before the year's first day, read from the registry's cut-off."""
    with bundled_indexed_authority().operation() as operation:
        rules = resolve_renta_inmueble_terms(
            modelo="100",
            revision_id=revision_selected_for("100", year, "0A").id,
            devengo=date(year, 12, 31),
            operation=operation,
        ).reduction_rules
    return min(rules.contract_cut_off - timedelta(days=1), date(year, 1, 1))


def _acquired(year: int) -> date:
    """The day the support acquires a property, five years before ``year``; properties one and three were let then."""
    return date(year - 5, 6, 1)


def _statements(revision: ModeloRevision) -> tuple[RowCarryAttestation, ...]:
    """State each origin year's opening: 300.00 on property one from the year before, nothing otherwise."""
    statements: list[RowCarryAttestation] = []
    for back, binding in renta_inmueble_origin_columns(revision)[RentaInmuebleOriginPart.OPENING].items():
        for row in ("inmueble:0", "inmueble:2"):
            if row == "inmueble:0" and back == 1:
                statements.append(RowCarryAttestation(binding_id=binding.id, source_row_identity=row, amount="300"))
            else:
                statements.append(
                    RowCarryAttestation(
                        binding_id=binding.id, source_row_identity=row, amount=ATTESTED_ZERO, absent=True
                    )
                )
    return tuple(statements)


def _tenant(nif: str) -> tuple[Inquilino, ...]:
    return (Inquilino(nif=nif, franja_edad=InquilinoEdad.OTRA, extranjero=False),)


def _records(year: int) -> dict[str, str]:
    contract = _contract_before_the_law(year)
    whole_year = inmueble(
        0,
        ejercicio=year,
        importe_adquisicion=Decimal(150000),
        gastos_tributos_adquisicion=Decimal(10000),
        valores_catastrales=(ValorCatastral(year=year, total=Decimal(100000), construccion=Decimal(60000)),),
        arrendado_desde=_acquired(year),
    )
    half_year = inmueble(
        1,
        ejercicio=year,
        fecha_adquisicion=date(year - 10, 3, 1),
        importe_adquisicion=Decimal(80000),
        gastos_tributos_adquisicion=Decimal(4000),
        valores_catastrales=(ValorCatastral(year=year, total=Decimal(50000), construccion=Decimal(25000)),),
        arrendado_desde=date(year, 7, 1),
    )
    shared = inmueble(
        2,
        ejercicio=year,
        importe_adquisicion=Decimal(200000),
        gastos_tributos_adquisicion=Decimal(12000),
        valores_catastrales=(ValorCatastral(year=year, total=Decimal(120000), construccion=Decimal(84000)),),
        titularidad=InmuebleTitularidad(
            regimen=TitularidadRegimen.PLENO_DOMINIO,
            titular=TitularRole.PRIMER_DECLARANTE,
            porcentaje_propiedad=Decimal(50),
        ),
        importes_movimientos=ImportesMovimientos.INMUEBLE_COMPLETO,
        arrendado_desde=_acquired(year),
    )
    leases = (
        lease(0, inmueble_clave=0, start=contract),
        lease(
            1,
            inmueble_clave=1,
            start=date(year, 7, 1),
            fecha_contrato=contract,
            zona_tensionada=False,
            inquilinos=_tenant(_SECOND_TENANT),
        ),
        lease(2, inmueble_clave=2, start=contract, inquilinos=_tenant(_THIRD_TENANT)),
    )
    return profile_facts((whole_year, half_year, shared), leases)


def _rows(year: int) -> TransactionCatalogue:
    return TransactionCatalogue.from_transactions(
        (
            *monthly_rent(year, amount=Decimal(900), lease_clave=0),
            expense("a-comunidad", concept="comunidad", inmueble_clave=0, amount=Decimal(600), booked=date(year, 2, 1)),
            expense("a-ibi", concept="tributos", inmueble_clave=0, amount=Decimal(400), booked=date(year, 9, 1)),
            expense(
                "a-intereses",
                concept="interes_financiacion",
                inmueble_clave=0,
                amount=Decimal(1000),
                booked=date(year, 6, 30),
            ),
            expense(
                "a-pintura",
                concept="reparacion_conservacion",
                inmueble_clave=0,
                amount=Decimal(500),
                booked=date(year, 4, 2),
            ),
            *monthly_rent(year, amount=Decimal(1000), lease_clave=1, months=range(7, 13)),
            expense("b-ibi", concept="tributos", inmueble_clave=1, amount=Decimal(365), booked=date(year, 9, 1)),
            expense("b-comunidad", concept="comunidad", inmueble_clave=1, amount=Decimal(730), booked=date(year, 2, 1)),
            *monthly_rent(year, amount=Decimal(800), lease_clave=2),
            expense(
                "c-comunidad", concept="comunidad", inmueble_clave=2, amount=Decimal(1200), booked=date(year, 2, 1)
            ),
            expense(
                "c-intereses",
                concept="interes_financiacion",
                inmueble_clave=2,
                amount=Decimal(2000),
                booked=date(year, 6, 30),
            ),
        )
    )


class _Withholding:
    """The suffered-withholding store: the first tenant withheld on the rent of property one."""

    def load_records(self, ejercicio: int) -> tuple[RetencionSoportadaRecord, ...]:
        return (
            RetencionSoportadaRecord.model_validate(
                {
                    "ejercicio": ejercicio,
                    "payer_tax_id": TENANT_NIF,
                    "payer_ref": "d" * 64,
                    "income_class": RetencionSoportadaClase.ARRENDAMIENTO_INMUEBLE_URBANO,
                    "importe_integro_dinerario": Decimal(10800),
                    "valoracion_especie": Decimal("0.00"),
                    "retencion": _WITHHELD_ON_ONE,
                    "ingreso_a_cuenta": Decimal("0.00"),
                    "ingreso_a_cuenta_repercutido": Decimal("0.00"),
                    "origin": RetencionSoportadaOrigen.OPERATOR_DECLARATION,
                    "captured_at": datetime(ejercicio + 1, 2, 1, 9, tzinfo=UTC),
                }
            ),
        )


def _column(revision: ModeloRevision, field: RentaInmuebleRowField) -> BindingId:
    return next(
        binding.id for binding, provider in renta_inmueble_columns(revision) if provider.row_field == field.value
    )


def _total(revision: ModeloRevision, field: RentaInmuebleRowField) -> BindingId:
    return next(
        binding.id for binding, provider in renta_inmueble_totals(revision) if provider.row_field == field.value
    )


def _resolve(year: int) -> CalculationSourceResolution:
    operation = governed_facts_in_scope()
    assert isinstance(operation, PinnedAuthorityOperation)
    revision = m100_revision(year)
    profile = ModeloWorkProfile(
        record=create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="X0001500M"),
                *(UserProfileFact(path=path, value=value) for path, value in _records(year).items()),
            ),
            context=operation.profile_create_context(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(_rows(year))
    return RentaInmuebleSourceResolver(
        transaction_repository=repository,
        retencion_soportada_ports=RetencionSoportadaPorts(repository=_Withholding()),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=year,
            period=Period.from_year_and_code(year, "0A"),
            revision=revision,
            profile=profile,
            caller_row_attestations=_statements(revision),
        )
    )


def _expected(year: int) -> dict[int, dict[str, Decimal]]:
    """Derive each property's boxes by hand, row by row, for ``year``."""
    days = Decimal(_year_days(year))
    expected: dict[int, dict[str, Decimal]] = {}

    # Property one, let all year. Construction share 60.000 / 100.000 = 60.00 %; cost side
    # (150.000 + 10.000) x 60 % = 96.000 beats the cadastral 60.000; 3 % is 2.880.
    # The 300 pending and the year's 1.500 of interest and repairs fit inside the 10.800 of rent.
    rent_one = Decimal(900) * 12
    net_one = rent_one - _PENDING_ON_ONE - Decimal(1500) - Decimal(600) - Decimal(400) - Decimal("2880.00")
    expected[1] = {"0149": net_one, "0153": _WITHHELD_ON_ONE}

    # Property two, held all year and let from 1 July: 184 days. Its expenses and amortisation count for
    # those days only. Construction share 25.000 / 50.000 = 50.00 %; cost side 84.000 x 50 % = 42.000.
    let = Decimal(184)
    net_two = (
        Decimal(1000) * 6
        - _cents(Decimal(365) * let / days)
        - _cents(Decimal(730) * let / days)
        - _cents(Decimal(42000) * _BUILDING_RATE * let / days)
    )
    expected[2] = {"0149": net_two, "0153": Decimal("0.00")}

    # Property three, half owned, its ledger rows whole-property amounts. Construction share
    # 84.000 / 120.000 = 70.00 %; cost side 212.000 x 70 % = 148.400, half 74.200, beats half the
    # cadastral 84.000; 3 % is 2.226. Half the interest, 1.000, fits inside half the rent, 4.800.
    net_three = Decimal(800) * 12 / 2 - Decimal(1000) - Decimal(600) - Decimal("2226.00")
    expected[3] = {"0149": net_three, "0153": Decimal("0.00")}

    for boxes in expected.values():
        boxes["0150"] = _cents(boxes["0149"] * _REDUCTION_RATE)
        boxes["0154"] = boxes["0149"] - boxes["0150"]
    return expected


def test_the_hand_derivation_holds_for_a_year_of_365_days() -> None:
    year = next(year for year in filing_year_envelope().years if _year_days(year) == 365)
    expected = _expected(year)

    assert expected[1] == {
        "0149": Decimal("5120.00"),
        "0153": _WITHHELD_ON_ONE,
        "0150": Decimal("3072.00"),
        "0154": Decimal("2048.00"),
    }
    assert expected[2]["0149"] == Decimal("4812.82")
    assert expected[3] == {
        "0149": Decimal("974.00"),
        "0153": Decimal("0.00"),
        "0150": Decimal("584.40"),
        "0154": Decimal("389.60"),
    }


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_three_let_properties_reach_their_hand_derived_boxes(year: int) -> None:
    revision = m100_revision(year)
    resolution = _resolve(year)
    values = resolution.row_binding_values
    expected = _expected(year)
    fields = {
        "0149": RentaInmuebleRowField.RENDIMIENTO_NETO,
        "0150": RentaInmuebleRowField.REDUCCION,
        "0153": RentaInmuebleRowField.RETENCIONES,
        "0154": RentaInmuebleRowField.RENDIMIENTO_NETO_REDUCIDO,
    }

    for row, boxes in expected.items():
        for box, field in fields.items():
            assert values[(_column(revision, field), row)] == boxes[box], (year, row, box)
    pending = _column(revision, RentaInmuebleRowField.GASTOS_PENDIENTES_ANTERIORES)
    applied = _column(revision, RentaInmuebleRowField.GASTOS_PENDIENTES_APLICADOS)
    assert values[(pending, 1)] == _PENDING_ON_ONE, year
    assert values[(applied, 1)] == _PENDING_ON_ONE, year
    # Anexo C.1 follows the 300.00 by its origin year: opened and applied whole, nothing carried on.
    origin = renta_inmueble_origin_columns(revision)
    assert values[(origin[RentaInmuebleOriginPart.OPENING][1].id, 1)] == _PENDING_ON_ONE, year
    assert values[(origin[RentaInmuebleOriginPart.APPLIED][1].id, 1)] == _PENDING_ON_ONE, year
    assert (origin[RentaInmuebleOriginPart.CARRIED][1].id, 1) not in values, year
    assert (pending, 2) not in values and (pending, 3) not in values, year

    # Box 0156 takes the sum of the reduced net yields; 0153 totals the withholding.
    total_reduced = sum((boxes["0154"] for boxes in expected.values()), Decimal(0))
    assert resolution.binding_values[_total(revision, RentaInmuebleRowField.RENDIMIENTO_NETO_REDUCIDO)] == total_reduced
    assert resolution.binding_values[_total(revision, RentaInmuebleRowField.RETENCIONES)] == _WITHHELD_ON_ONE

    # The days property two stood empty have no stated use, so their imputed income stays open, and it says so.
    facts = {diagnostic.fact for diagnostic in resolution.diagnostics if diagnostic.fact is not None}
    sentences = {(fact.sentence.value, fact.row_refs) for fact in facts}
    assert (f"renta_inmueble_{RentaInmuebleCause.DAYS_UNACCOUNTED.value}", ("inmueble:1",)) in sentences, year
    assert not any(
        fact.sentence.value == f"renta_inmueble_{RentaInmuebleCause.PENDING_EXPENSES_UNSTATED.value}" for fact in facts
    ), year
