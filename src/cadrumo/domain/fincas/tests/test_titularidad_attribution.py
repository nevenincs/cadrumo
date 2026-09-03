"""Titularidad attribution against the official AEAT worked examples.

Every expected figure below is taken from the *Manual práctico de Renta
2025*, Parte 1 — the bundled official manual — and not from this
engine's own output:

* Capítulo 4, "Rendimiento neto reducido", págs. 291-292: the "Vivienda
  1" column of Don S.P.T.'s worked example.
* Capítulo 4, "Individualización de los rendimientos del capital
  inmobiliario", págs. 292-293 (Art. 11.3 Ley IRPF): the cotitular and
  usufructo rules for the rendimiento.
* Capítulo 10, "Individualización de las rentas inmobiliarias" and its
  worked example, págs. 805-806: the same rules for the art. 85
  imputación, and Don J.V.C.'s "apartamento en la playa" figure.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import ExitStack
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ....adapters.persistence.profile.fincas import (
    ArrendamientoRepository,
    FincaAmortizacionLedgerRepository,
    FincaGastoRepository,
    FincaRendimientoRepository,
    FincaRepository,
)
from ....adapters.persistence.storage.sql.engine import get_engine
from ....adapters.persistence.storage.sql.session import session_scope
from ....tests.secure_sql import isolated_runtime_profile
from ..aggregates import FincaAggregates, compute_finca_aggregates
from ..enums import (
    ExpenseCategory,
    ReduccionTier,
    TitularContribuyente,
    TitularidadRegime,
    UseType,
)
from ..errors import FincaAggregationError, FincaValidationError
from ..models import Arrendamiento, Finca, FincaGasto, FincaRendimientoRecord
from ..titularidad import Titularidad, not_declared

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

PERIOD = 2025

# --- Manual, Capítulo 4, págs. 291-292, "Vivienda 1" column ------------------
MANUAL_INGRESOS_INTEGROS = Decimal("6865.00")
MANUAL_REPARACION_Y_CONSERVACION = Decimal("2150.00")
MANUAL_IBI = Decimal("500.00")
MANUAL_COMUNIDAD = Decimal("580.00")
MANUAL_AMORTIZACION = Decimal("200.00")
MANUAL_RENDIMIENTO_NETO = Decimal("3435.00")
MANUAL_REDUCCION = Decimal("1717.50")

#: The manual's note to the example states the amortización figures were
#: "calculad[as] aplicando el 3% del valor catastral de los inmuebles",
#: so the valor catastral de la construcción that yields the manual's
#: 200 euros is 200 / 0,03.
MANUAL_VALOR_CATASTRAL_CONSTRUCCION = Decimal("6666.67")

# --- Manual, Capítulo 10, pág. 806, "apartamento en la playa" ----------------
MANUAL_IMPUTACION_VALOR_CATASTRAL = Decimal("40800.00")
MANUAL_IMPUTACION_REVISION_YEAR = 2015
MANUAL_IMPUTACION = Decimal("448.80")


@pytest.fixture
def make_engine(tmp_path: Path) -> Iterator[Callable[[str], Engine]]:
    """Yield a factory for independent profile databases within one test.

    Two registers modelling the same property from two taxpayers' sides
    must not share a database, so scenarios take a named profile each.
    """
    with ExitStack() as stack:

        def factory(name: str) -> Engine:
            profile = stack.enter_context(isolated_runtime_profile(tmp_path=tmp_path / name))
            return get_engine(profile.settings)

        yield factory


@pytest.fixture
def engine(make_engine: Callable[[str], Engine]) -> Engine:
    return make_engine("default")


def _pleno_dominio(porcentaje: str) -> Titularidad:
    return Titularidad(
        regime=TitularidadRegime.PLENO_DOMINIO,
        contribuyente=TitularContribuyente.PRIMER_DECLARANTE,
        porcentaje_propiedad=Decimal(porcentaje),
    )


def _nuda_propiedad(porcentaje: str) -> Titularidad:
    return Titularidad(
        regime=TitularidadRegime.NUDA_PROPIEDAD,
        contribuyente=TitularContribuyente.PRIMER_DECLARANTE,
        porcentaje_propiedad=Decimal(porcentaje),
    )


def _usufructo(porcentaje: str) -> Titularidad:
    return Titularidad(
        regime=TitularidadRegime.USUFRUCTO,
        contribuyente=TitularContribuyente.CONYUGE,
        porcentaje_usufructo=Decimal(porcentaje),
    )


def _let_vivienda(titularidad: Titularidad) -> Finca:
    """Build the manual's "Vivienda 1", let for the whole of 2025."""
    return Finca(
        identifier="manual-vivienda-1",
        address="Calle de ejemplo 1, Madrid",
        valor_catastral_total=Decimal("10000.00"),
        valor_catastral_construccion=MANUAL_VALOR_CATASTRAL_CONSTRUCCION,
        valor_catastral_revision_year=None,
        coste_adquisicion=Decimal("6666.67"),
        coste_adquisicion_construccion=MANUAL_VALOR_CATASTRAL_CONSTRUCCION,
        acquisition_date=date(2010, 1, 1),
        use_type=UseType.VIVIENDA_ARRENDADA,
        is_stressed_area=False,
        titularidad=titularidad,
    )


def _non_let_apartamento(titularidad: Titularidad) -> Finca:
    """Build the manual's "apartamento en la playa" under the art. 85 regime."""
    return Finca(
        identifier="manual-apartamento-playa",
        address="Paseo de ejemplo 2, Cádiz",
        valor_catastral_total=MANUAL_IMPUTACION_VALOR_CATASTRAL,
        valor_catastral_construccion=Decimal("30000.00"),
        valor_catastral_revision_year=MANUAL_IMPUTACION_REVISION_YEAR,
        coste_adquisicion=Decimal("120000.00"),
        coste_adquisicion_construccion=Decimal("90000.00"),
        acquisition_date=date(2005, 6, 1),
        use_type=UseType.VIVIENDA_DESOCUPADA,
        is_stressed_area=False,
        titularidad=titularidad,
    )


def _register_let_vivienda(session: Session, titularidad: Titularidad) -> None:
    """Persist the manual's Vivienda 1 with its contract, rent and gastos."""
    finca = FincaRepository(session).upsert(_let_vivienda(titularidad))
    assert finca.id is not None
    contract = ArrendamientoRepository(session).upsert(
        Arrendamiento(
            finca_id=finca.id,
            # The manual states the contracts were celebrated on 1 September 2023,
            # after 26 May 2023 and meeting none of the 90/70/60 conditions.
            contract_celebration_date=date(2023, 9, 1),
            tenant_count=1,
            initial_rent=Decimal("572.08"),
        ),
    )
    assert contract.id is not None
    FincaRendimientoRepository(session).upsert(
        FincaRendimientoRecord(
            contract_id=contract.id,
            period_year=PERIOD,
            gross_rent_received=MANUAL_INGRESOS_INTEGROS,
            dias_alquilados=365,
        ),
    )
    gasto_repo = FincaGastoRepository(session)
    for category, amount in (
        (ExpenseCategory.CONSERVACION_REPARACION, MANUAL_REPARACION_Y_CONSERVACION),
        (ExpenseCategory.IBI_TRIBUTOS_NO_ESTATALES, MANUAL_IBI),
        (ExpenseCategory.COMUNIDAD, MANUAL_COMUNIDAD),
    ):
        gasto_repo.upsert(
            FincaGasto(finca_id=finca.id, period_year=PERIOD, category=category, amount=amount),
        )


def _aggregate(session: Session) -> FincaAggregates:
    return compute_finca_aggregates(
        period_year=PERIOD,
        finca_repo=FincaRepository(session),
        contract_repo=ArrendamientoRepository(session),
        income_repo=FincaRendimientoRepository(session),
        expense_repo=FincaGastoRepository(session),
        ledger_repo=FincaAmortizacionLedgerRepository(session),
    )


def test_sole_full_ownership_reproduces_the_manual_worked_example(engine: Engine) -> None:
    """A 100 % pleno propietario declares the manual's own Vivienda 1 figures."""
    with session_scope(engine) as session:
        _register_let_vivienda(session, _pleno_dominio("100.00"))
        aggregates = _aggregate(session)

    assert aggregates.ingresos_integros == MANUAL_INGRESOS_INTEGROS
    assert aggregates.gastos_deducibles == (
        MANUAL_REPARACION_Y_CONSERVACION + MANUAL_IBI + MANUAL_COMUNIDAD
    )
    assert aggregates.amortizacion == MANUAL_AMORTIZACION
    assert aggregates.reduccion_arrendamiento_vivienda == MANUAL_REDUCCION

    (contract_attrib,) = aggregates.per_contract_tier.values()
    assert contract_attrib.tier.tier is ReduccionTier.TIER_50
    assert contract_attrib.rendimiento_neto_positivo == MANUAL_RENDIMIENTO_NETO

    (finca_attrib,) = aggregates.per_finca_attribution.values()
    assert finca_attrib.titularidad_share == Decimal("1")


def test_two_owner_split_halves_every_figure_of_the_manual_example(engine: Engine) -> None:
    """A 50 % cotitular declares half of every whole-property figure.

    Manual, Capítulo 4, pág. 292: "cada uno de los cotitulares deberá
    declarar como rendimiento la cantidad que resulte de aplicar al
    rendimiento total producido por el inmueble o derecho el porcentaje
    que represente su participación en la titularidad del mismo".
    """
    with session_scope(engine) as session:
        _register_let_vivienda(session, _pleno_dominio("50.00"))
        aggregates = _aggregate(session)

    half = Decimal("2")
    assert aggregates.ingresos_integros == MANUAL_INGRESOS_INTEGROS / half
    assert aggregates.gastos_deducibles == (
        MANUAL_REPARACION_Y_CONSERVACION + MANUAL_IBI + MANUAL_COMUNIDAD
    ) / half
    assert aggregates.amortizacion == MANUAL_AMORTIZACION / half
    assert aggregates.reduccion_arrendamiento_vivienda == MANUAL_REDUCCION / half

    (finca_attrib,) = aggregates.per_finca_attribution.values()
    assert finca_attrib.titularidad_share == Decimal("0.5")


def test_bare_ownership_and_usufruct_attribute_to_different_parties(
    make_engine: Callable[[str], Engine],
) -> None:
    """The usufructuario declares both regimes; the nudo propietario declares neither.

    Manual, Capítulo 4, pág. 292: "si existe un usufructo, el rendimiento
    íntegro debe declararlo el usufructuario y no el nudo propietario".
    Manual, Capítulo 10, pág. 805: the imputación is charged to the
    titular del derecho "sin que este último [el nudo propietario] deba
    incluir cantidad alguna en su declaración en concepto de imputación
    de rentas inmobiliarias".
    """
    with session_scope(make_engine("nudo-propietario")) as session:
        _register_let_vivienda(session, _nuda_propiedad("100.00"))
        FincaRepository(session).upsert(_non_let_apartamento(_nuda_propiedad("100.00")))
        nudo_propietario = _aggregate(session)

    assert nudo_propietario.ingresos_integros == Decimal("0.00")
    assert nudo_propietario.reduccion_arrendamiento_vivienda == Decimal("0.00")
    assert nudo_propietario.imputacion_rentas_inmobiliarias == Decimal("0.00")

    with session_scope(make_engine("usufructuario")) as session:
        _register_let_vivienda(session, _usufructo("100.00"))
        FincaRepository(session).upsert(_non_let_apartamento(_usufructo("100.00")))
        usufructuario = _aggregate(session)

    assert usufructuario.ingresos_integros == MANUAL_INGRESOS_INTEGROS
    assert usufructuario.reduccion_arrendamiento_vivienda == MANUAL_REDUCCION
    # Manual, Capítulo 10, pág. 806: 1,1 por 100 s/40.800 = 448,80.
    assert usufructuario.imputacion_rentas_inmobiliarias == MANUAL_IMPUTACION


def test_undeclared_titularidad_refuses_instead_of_attributing_the_whole(
    make_engine: Callable[[str], Engine],
) -> None:
    """An absent share is a refusal, not an implicit 100 %."""
    with session_scope(make_engine("undeclared")) as session:
        _register_let_vivienda(session, not_declared())
        with pytest.raises(FincaAggregationError) as refusal:
            _aggregate(session)

    message = str(refusal.value)
    assert "manual-vivienda-1" in message
    assert "never declared" in message
    # The identical register with a declared full title does produce the
    # figures, so the refusal above is the titularidad's doing and not an
    # empty or otherwise unusable register.
    with session_scope(make_engine("declared")) as session:
        _register_let_vivienda(session, _pleno_dominio("100.00"))
        assert _aggregate(session).ingresos_integros == MANUAL_INGRESOS_INTEGROS


def test_incoherent_shares_refuse_rather_than_normalising() -> None:
    """A porcentaje set summing beyond 100 is refused, not scaled back to 100."""
    with pytest.raises(FincaValidationError) as refusal:
        Titularidad(
            regime=TitularidadRegime.PLENO_DOMINIO_Y_USUFRUCTO,
            contribuyente=TitularContribuyente.PRIMER_DECLARANTE,
            porcentaje_propiedad=Decimal("60.00"),
            porcentaje_usufructo=Decimal("50.00"),
        )
    assert "must not exceed 100" in str(refusal.value)


def test_mixed_pleno_dominio_and_usufructo_is_refused_not_approximated(engine: Engine) -> None:
    """A coherent mixed holding is recordable but produces no attributed total.

    Manual, Capítulo 4, pág. 281, "Plena propiedad y usufructo sobre un
    inmueble": the amortización "se calculará de forma diferente para la
    parte del inmueble del que es pleno propietario y la parte del que es
    usufructuario". The register carries no cost or duration for the
    usufruct, so the split cannot be computed and is not guessed.
    """
    mixed = Titularidad(
        regime=TitularidadRegime.PLENO_DOMINIO_Y_USUFRUCTO,
        contribuyente=TitularContribuyente.PRIMER_DECLARANTE,
        porcentaje_propiedad=Decimal("50.00"),
        porcentaje_usufructo=Decimal("50.00"),
    )
    with session_scope(engine) as session:
        _register_let_vivienda(session, mixed)
        with pytest.raises(FincaAggregationError) as refusal:
            _aggregate(session)
    assert "amortización" in str(refusal.value)


def test_not_declared_and_unsupported_mixed_holding_stay_distinguishable() -> None:
    """The two non-filing-grade states report different reasons."""
    undeclared = not_declared()
    mixed = Titularidad(
        regime=TitularidadRegime.PLENO_DOMINIO_Y_USUFRUCTO,
        contribuyente=TitularContribuyente.COMUN,
        porcentaje_propiedad=Decimal("50.00"),
        porcentaje_usufructo=Decimal("50.00"),
    )
    assert not undeclared.is_filing_grade
    assert not mixed.is_filing_grade
    assert undeclared.refusal_reason != mixed.refusal_reason


def test_declared_percentage_carrying_more_than_two_decimals_is_refused() -> None:
    """Casillas [0063] and [0064] take two decimals; a third is not rounded away."""
    with pytest.raises(FincaValidationError) as refusal:
        _pleno_dominio("33.333")
    assert "[0063]" in str(refusal.value)


def test_titularidad_survives_the_persistence_round_trip(engine: Engine) -> None:
    """The three declared facts reload from the profile database unchanged."""
    declared = Titularidad(
        regime=TitularidadRegime.USUFRUCTO,
        contribuyente=TitularContribuyente.HIJO,
        hijo_ordinal=2,
        porcentaje_usufructo=Decimal("33.33"),
    )
    with session_scope(engine) as session:
        stored = FincaRepository(session).upsert(_let_vivienda(declared))
        assert stored.id is not None
        reloaded = FincaRepository(session).get(stored.id)

    assert reloaded.titularidad == declared
    assert reloaded.titularidad.attribution_share() == Decimal("33.33") / Decimal("100")
