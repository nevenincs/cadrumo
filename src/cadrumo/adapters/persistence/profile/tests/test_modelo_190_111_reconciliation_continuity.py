"""Modelo 190 resumen sources against the Modelo 111 quarters the same retenedor files.

Modelo 111 is the quarterly retencion autoliquidacion (Orden EHA/586/2011, RD
439/2007 arts. 80, 86 and 108.1); Modelo 190 is the annual resumen (RD 439/2007
art. 108.2, Orden EHA/3127/2009). The Modelo 190 record design defines its three
declarante totals over the declaration's own type-2 perceptor records, in every
edition from the 2020 design onward and in the 2025 instrucciones for casillas
01 to 03, and no official text defines them from Modelo 111:

- ``decl.total-percepciones`` = distinct (perceptor, clave, subclave) records
- ``decl.percepciones-total`` = sum of the records' percepciones
- ``decl.retenciones-total`` = sum of the records' retenciones e ingresos a cuenta

This module drives the REAL backend (encrypted-SQLite observation store, the
registry authority, the calculation engine and the relation resolver, no mocks).
It files the four Modelo 111 quarters into the same store and proves that the
Modelo 190 resolver takes no relation from them in any supported exercise, and
that two distinct exercises total their own withholding records only. The 111
quarterly amounts deliberately differ from the 190 record amounts, so a total
drawn from Modelo 111 fails loudly.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.aggregation.retenciones import (
    RetencionObservation,
    aggregate_retenciones_111,
)
from .....application.calculations.relation_prefill import resolve_relations_from_local_store
from .....core.aggregation import (
    BindingSourceKind,
    RetencionScheme,
)
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.period import Period
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.calculations.registry.bindings import (
    RegistryModeloObservation,
    resolve_available_bound_inputs_by_casilla_id,
)
from .....domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from .....domain.calculations.registry.retenciones_bindings import resolve_retenciones_aggregation_binding_values
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.calculations.registry.tests.registry_observations import (
    registry_grounded_modelo_observation,
    revision_id_for_observation,
)
from .....domain.calculations.registry.withholding_bindings import (
    WithholdingObservation,
    resolve_withholding_binding_values,
)
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..calculation_observations import CalculationObservationRepository
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo ids this module exercises.
_MODELO_111 = "111"
_MODELO_190 = "190"

#: Two distinct exercises, the newest the support envelope admits.
_YEAR_N, _YEAR_N_PLUS_1 = filing_year_envelope().years[-2:]

_CLOCK = datetime(_YEAR_N_PLUS_1 + 1, 1, 20, 9, 0, 0, tzinfo=UTC)


_M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("01")
_M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: CasillaId = validated_casilla_id("02")
_M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("03")
_M111_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id("28")
_M190_TOTAL_PERCEPCIONES_CASILLA: CasillaId = validated_casilla_id("decl.total-percepciones")
_M190_PERCEPCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.percepciones-total")
_M190_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.retenciones-total")
_M190_PERCEPCIONES_BINDING = "modelo-190-percepciones-anual"
# ---------------------------------------------------------------------------
# 111 quarterly scenarios — a trabajo-dinerario-only filer.
#
# Casilla 01 = trabajo dinerario: número de perceptores (integer, manual, no
# longer consumed by Modelo 190's annual count)
# Casilla 02 = trabajo dinerario: importe dinerario (money, manual)
# Casilla 03 = trabajo dinerario: retenciones dinerario (money, manual)
# Casillas 04-27 = eight remaining categories, all zero.
# Casilla 28 = total retenciones (computed: sum of sub-total retenciones).
#
# Zeroing all other monetary categories keeps the scenario minimal.
# ---------------------------------------------------------------------------

# All 111 manual-input casillas not driven by the scenario are zero.
_ZERO_CASILLAS: list[CasillaId] = list(
    validated_casilla_id(_v)
    for _v in (
        "04",
        "05",
        "06",  # trabajo especie
        "07",
        "08",
        "09",  # actividades econ dinerario
        "10",
        "11",
        "12",  # actividades econ especie
        "13",
        "14",
        "15",  # premios dinerario
        "16",
        "17",
        "18",  # premios especie
        "19",
        "20",
        "21",  # ganancias forestales dinerario
        "22",
        "23",
        "24",  # ganancias forestales especie
        "25",
        "26",
        "27",  # cesión derechos imagen
        "29",
    )
)

_YEAR_N_QUARTERS: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("5"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("12000.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("2280.00"),
    },
    "2T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("6"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("14000.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("2660.00"),
    },
    "3T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("4"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("10500.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("1995.00"),
    },
    "4T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("5"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("13000.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("2470.00"),
    },
}

_YEAR_N_PLUS_1_QUARTERS: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("3"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("9000.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("1710.00"),
    },
    "2T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("4"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("11000.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("2090.00"),
    },
    "3T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("5"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("15000.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("2850.00"),
    },
    "4T": {
        _M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA: Decimal("4"),
        _M111_TRABAJO_DINERARIO_IMPORTE_CASILLA: Decimal("12500.00"),
        _M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA: Decimal("2375.00"),
    },
}


#: Each 190 record's percepcion and retencion, chosen apart from every 111 quarterly amount.
_RECORD_PERCEPCION = Decimal("1000.00")
_RECORD_RETENCION = Decimal("190.00")


def _withholding_obs(source_id: str, nif: str, clave: str, *, filing_year: int) -> WithholdingObservation:
    return WithholdingObservation.model_validate(
        {
            "source_id": source_id,
            "perceptor_tax_id": nif,
            "transaction_date": date(filing_year, 6, 1),
            "clave": clave,
            "percibido_dinerario": _RECORD_PERCEPCION,
            "retencion_practicada": _RECORD_RETENCION,
            "incapacity_cash_perception": Decimal("0"),
            "incapacity_cash_withholding": Decimal("0"),
            "incapacity_kind_value": Decimal("0"),
            "incapacity_kind_ingreso_a_cuenta": Decimal("0"),
            "incapacity_kind_repercutido": Decimal("0"),
            "foral_retention_estatal": Decimal("0"),
            "foral_retention_navarra": Decimal("0"),
            "foral_retention_araba": Decimal("0"),
            "foral_retention_gipuzkoa": Decimal("0"),
            "foral_retention_bizkaia": Decimal("0"),
            "base_retenciones": Decimal("0"),
        }
    )


def _year_n_withholding_observations() -> tuple[WithholdingObservation, ...]:
    return (
        _withholding_obs("yN-a-q1", "00001500M", "A", filing_year=_YEAR_N),
        _withholding_obs("yN-a-q2", "00001500M", "A", filing_year=_YEAR_N),
        _withholding_obs("yN-g-q3", "00001500M", "G", filing_year=_YEAR_N),
        _withholding_obs("yN-a-q4", "00001501Y", "A", filing_year=_YEAR_N),
    )


_YEAR_N_WITHHOLDING_PERCEPCIONES = Decimal("3")


def _year_n_plus_1_withholding_observations() -> tuple[WithholdingObservation, ...]:
    return (
        _withholding_obs("yN1-a-q1", "00001502F", "A", filing_year=_YEAR_N_PLUS_1),
        _withholding_obs("yN1-b-q2", "00001502F", "B", filing_year=_YEAR_N_PLUS_1),
    )


_YEAR_N_PLUS_1_WITHHOLDING_PERCEPCIONES = Decimal("2")
_PERIOD_ACCRUAL_DATES = {
    "1T": "03-31",
    "2T": "06-30",
    "3T": "09-30",
    "4T": "12-31",
}


def _split_amount(amount: Decimal, parts: int) -> tuple[Decimal, ...]:
    if parts <= 0:
        if amount != Decimal("0"):
            raise AssertionError(f"cannot spread non-zero retenciones fixture amount {amount} over zero perceptors")
        return ()
    unit = (amount / Decimal(parts)).quantize(Decimal("0.01"))
    values = [unit for _ in range(parts - 1)]
    values.append(amount - sum(values, Decimal("0")))
    return tuple(values)


def _retencion_observations_for_111_inputs(
    *,
    filing_year: int,
    period: str,
    casilla_inputs: dict[CasillaId, Decimal],
) -> tuple[RetencionObservation, ...]:
    perceptor_count = casilla_inputs[_M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA]
    if perceptor_count != perceptor_count.to_integral_value():
        raise AssertionError(f"Modelo 111 perceptores fixture must be integral, got {perceptor_count}")
    count = int(perceptor_count)
    bases = _split_amount(casilla_inputs[_M111_TRABAJO_DINERARIO_IMPORTE_CASILLA], count)
    retenciones = _split_amount(casilla_inputs[_M111_TRABAJO_DINERARIO_RETENCIONES_CASILLA], count)
    accrued_on = f"{filing_year}-{_PERIOD_ACCRUAL_DATES[period]}"
    return tuple(
        RetencionObservation(
            source_kind=BindingSourceKind.LEDGER_TRANSACTION,
            source_object_id=f"m111-{filing_year}-{period}-work-{index:02d}",
            perceptor_nif=f"{index:08d}H",
            perceptor_name=f"Trabajador {index:02d}",
            scheme=RetencionScheme("rendimientos_trabajo"),
            taxable_base=base,
            retencion_amount=retencion,
            accrued_on=accrued_on,
        )
        for index, (base, retencion) in enumerate(zip(bases, retenciones, strict=True), start=1)
    )


def _calculate_111(
    *,
    filing_year: int,
    period: str,
    casilla_inputs: dict[CasillaId, Decimal],
    operation: PinnedAuthorityOperation,
) -> RegistryCalculationResult:
    """Run the REAL 111 quarterly calculation and return the engine result."""
    snapshot = published_authority_operation().snapshot(_MODELO_111, filing_year=filing_year, period=period)
    retenciones = aggregate_retenciones_111(
        _retencion_observations_for_111_inputs(
            filing_year=filing_year,
            period=period,
            casilla_inputs=casilla_inputs,
        ),
        period=Period.from_year_and_code(filing_year, period),
        operation=operation,
    )
    binding_values = resolve_retenciones_aggregation_binding_values(snapshot.revision, retenciones)
    bound_inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    # Supply all remaining manual-input zero casillas plus the scenario inputs.
    zero_inputs = {cid: Decimal("0") for cid in _ZERO_CASILLAS if cid not in bound_inputs}
    manual_inputs = {cid: value for cid, value in casilla_inputs.items() if cid not in bound_inputs}
    inputs = {
        **bound_inputs,
        **zero_inputs,
        **manual_inputs,
    }
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(filing_year, 12, 31)},
    )


def _111_observation(*, filing_year: int, period: str, result: RegistryCalculationResult) -> RegistryModeloObservation:
    return registry_grounded_modelo_observation(
        modelo=_MODELO_111,
        filing_year=filing_year,
        period=period,
        casilla_values=result.values,
    )


def _calculate_190(
    *,
    filing_year: int,
    withholding_observations: tuple[WithholdingObservation, ...],
) -> RegistryCalculationResult:
    """Run the REAL 190 annual calculation from its withholding records alone."""
    snapshot = published_authority_operation().snapshot(_MODELO_190, filing_year=filing_year, period="0A")
    binding_values = resolve_withholding_binding_values(snapshot.revision, withholding_observations)
    return calculate_registry_snapshot(
        snapshot,
        inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        binding_values=binding_values,
        date_context={"filing_period": date(filing_year, 12, 31)},
    )


def _file_111_quarters(
    quarters: dict[str, dict[CasillaId, Decimal]],
    *,
    filing_year: int,
    obs_repo: CalculationObservationRepository,
    operation: PinnedAuthorityOperation,
) -> Decimal:
    """Calculate all four 111 quarters, persist their observations, return the summed casilla 02."""
    importe = Decimal("0")
    for period, inputs in quarters.items():
        result = _calculate_111(filing_year=filing_year, period=period, casilla_inputs=inputs, operation=operation)
        observation = _111_observation(filing_year=filing_year, period=period, result=result)
        obs_repo.save(
            obs_repo.prepare_observation_envelope(
                observation,
                source_kind="app_filing",
                captured_at=_CLOCK,
                stamped_revision_id=revision_id_for_observation(observation),
            )
        )
        importe += result.values[_M111_TRABAJO_DINERARIO_IMPORTE_CASILLA]
    return importe


def test_modelo_111_quarterly_engine_produces_retenciones_casilla(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The 111 engine computes total retenciones (casilla 28) from sub-totals.

    The value is _produced by the real engine, never hand-computed. This is
    the seed fed to the 190 reconciliation for the retenciones relation.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result = _calculate_111(
            filing_year=_YEAR_N,
            period="1T",
            casilla_inputs=_YEAR_N_QUARTERS["1T"],
            operation=operation,
        )
    assert result.values[_M111_RETENCIONES_TOTAL_CASILLA] > Decimal("0")
    assert (
        result.values[_M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA]
        == _YEAR_N_QUARTERS["1T"][_M111_TRABAJO_DINERARIO_PERCEPTORES_CASILLA]
    )


@pytest.mark.parametrize("exercise", filing_year_envelope().years)
def test_modelo_190_takes_no_relation_from_filed_modelo_111_quarters(tmp_path: Path, exercise: int) -> None:
    """Filed Modelo 111 quarters reach no Modelo 190 total in any supported exercise."""
    with isolated_runtime_profile(tmp_path=tmp_path), bundled_indexed_authority().operation() as operation:
        obs_repo = CalculationObservationRepository()
        _file_111_quarters(_YEAR_N_QUARTERS, filing_year=exercise, obs_repo=obs_repo, operation=operation)
        snapshot_190 = published_authority_operation().snapshot(_MODELO_190, filing_year=exercise, period="0A")
        prefill = resolve_relations_from_local_store(snapshot_190, operation=operation, repository=obs_repo)

    relation_bindings = [
        binding.id for binding in snapshot_190.revision.bindings if binding.source is BindingSourceKind.RELATION_PREFILL
    ]
    assert not relation_bindings
    assert not [item.relation for item in prefill.values if item.value is not None]


def test_modelo_190_resumen_totals_each_exercise_own_withholding_records(tmp_path: Path) -> None:
    """Two exercises, both with filed 111 quarters, total only their own 190 records.

    The 111 trabajo-dinerario importe of each exercise is filed into the same
    store and differs from the 190 records' percepciones, so a total read from
    Modelo 111, or from the other exercise, fails the equalities below.
    """
    with isolated_runtime_profile(tmp_path=tmp_path), bundled_indexed_authority().operation() as operation:
        obs_repo = CalculationObservationRepository()
        filed_111_n = _file_111_quarters(_YEAR_N_QUARTERS, filing_year=_YEAR_N, obs_repo=obs_repo, operation=operation)
        filed_111_n1 = _file_111_quarters(
            _YEAR_N_PLUS_1_QUARTERS, filing_year=_YEAR_N_PLUS_1, obs_repo=obs_repo, operation=operation
        )
        result_n = _calculate_190(filing_year=_YEAR_N, withholding_observations=_year_n_withholding_observations())
        result_n1 = _calculate_190(
            filing_year=_YEAR_N_PLUS_1, withholding_observations=_year_n_plus_1_withholding_observations()
        )

    year_n_records = len(_year_n_withholding_observations())
    year_n1_records = len(_year_n_plus_1_withholding_observations())
    assert result_n.values[_M190_TOTAL_PERCEPCIONES_CASILLA] == _YEAR_N_WITHHOLDING_PERCEPCIONES
    assert result_n.values[_M190_PERCEPCIONES_TOTAL_CASILLA] == _RECORD_PERCEPCION * year_n_records
    assert result_n.values[_M190_RETENCIONES_TOTAL_CASILLA] == _RECORD_RETENCION * year_n_records
    assert result_n.values[_M190_PERCEPCIONES_TOTAL_CASILLA] != filed_111_n

    assert result_n1.values[_M190_TOTAL_PERCEPCIONES_CASILLA] == _YEAR_N_PLUS_1_WITHHOLDING_PERCEPCIONES
    assert result_n1.values[_M190_PERCEPCIONES_TOTAL_CASILLA] == _RECORD_PERCEPCION * year_n1_records
    assert result_n1.values[_M190_RETENCIONES_TOTAL_CASILLA] == _RECORD_RETENCION * year_n1_records
    assert result_n1.values[_M190_PERCEPCIONES_TOTAL_CASILLA] != filed_111_n1
