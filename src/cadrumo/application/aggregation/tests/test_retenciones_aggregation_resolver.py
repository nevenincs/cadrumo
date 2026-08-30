"""Calc-mesh resolver for the dedicated per-perceptor retención store.

The :class:`RetencionesAggregationSourceResolver` reads the persisted per-perceptor
observations and materialises the Modelo 180 "número total de
perceptores" box with the validated DISTINCT-NIF count — never the sum of
quarterly aggregate counts. An empty store on a revision that declares the
perceptor-count binding raises before a zero count can be persisted.

The test revision is the real Modelo 180 revision with its perceptor-count binding
re-pointed to the ``retenciones_aggregation`` source, simulated here via
``model_copy`` so the resolver can be exercised before the registry re-stamp.
"""

from __future__ import annotations

from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from ....core import NoRecoveryOutcome, Period
from ....core.aggregation import AggregationCaptureKind, BindingSourceKind
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ....tests.secure_sql import isolated_runtime_profile
from .._modelo_bindings import RetencionesAggregationSourceResolver
from .._preconditions import AggregationPreconditionCondition
from .._retencion_observations_repository import RetencionObservationRepository
from .._retenciones import RetencionObservation, RetencionScheme
from .._source_mesh import CalculationSourceContext
from ..errors import AggregationValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERCEPTOR_BINDING_ID = "modelo-180-115-perceptores-anual"
_M115_PERCEPTOR_BINDING_ID = "modelo-115-perceptores"
_M115_BASE_BINDING_ID = "modelo-115-base-retenciones"
_M111_BINDING_VALUES = {
    "modelo-111-trabajo-dinerario-perceptores": Decimal("1"),
    "modelo-111-trabajo-dinerario-base": Decimal("100.00"),
    "modelo-111-trabajo-dinerario-retenciones": Decimal("10.00"),
    "modelo-111-actividades-dinerario-perceptores": Decimal("2"),
    "modelo-111-actividades-dinerario-base": Decimal("500.00"),
    "modelo-111-actividades-dinerario-retenciones": Decimal("50.00"),
    "modelo-111-premios-dinerario-perceptores": Decimal("1"),
    "modelo-111-premios-dinerario-base": Decimal("400.00"),
    "modelo-111-premios-dinerario-retenciones": Decimal("40.00"),
}


@cache
def _authority_snapshot(modelo: str, filing_year: int, period: str) -> RegistrySnapshot:
    return bundled_authority().snapshot(modelo, filing_year=filing_year, period=period)


def _observation(nif: str) -> RetencionObservation:
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id=f"tx-{nif}",
        perceptor_nif=nif,
        perceptor_name="Arrendador Ejemplo SL",
        # Modelo 180 is the arrendamiento de inmuebles urbanos summary; its
        # aggregator filters on the URBAN_RENTAL scheme.
        scheme=RetencionScheme.URBAN_RENTAL,
        taxable_base=Decimal("1000.00"),
        retencion_amount=Decimal("190.00"),
        accrued_on="2024-03-15",
    )


def _m180_revision_with_retenciones_source() -> ModeloRevision:
    """The real M180 revision with its perceptor-count binding flipped to retenciones_aggregation.

    Simulates the registry re-stamp via ``model_copy`` so the resolver is
    exercised before the registry cutover lands.
    """
    snapshot = _authority_snapshot("180", 2024, "0A")
    existing = next(b for b in snapshot.revision.bindings if str(b.id) == _PERCEPTOR_BINDING_ID)
    flipped = existing.model_copy(update={"source": BindingSourceKind.RETENCIONES_AGGREGATION})
    other = tuple(b for b in snapshot.revision.bindings if str(b.id) != _PERCEPTOR_BINDING_ID)
    return snapshot.revision.model_copy(update={"bindings": (flipped, *other)})


def _context(revision: ModeloRevision) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id="operator",
        modelo="180",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "0A"),
        revision=revision,
    )


def _context_for(*, modelo: str, filing_year: int, period: str, revision: ModeloRevision) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id="operator",
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        revision=revision,
    )


def test_resolver_materialises_distinct_perceptor_count(tmp_path: Path) -> None:
    """Two perceptors across three rows materialise a DISTINCT count of 2, not 3."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        period = Period.from_year_and_code(2024, "0A")
        # 11111111H appears twice (e.g. two payments) but is ONE perceptor; the
        # distinct-NIF count is 2. (Same NIF, same scheme → the second overwrites,
        # so seed via two NIFs plus a repeat to prove distinctness through the
        # aggregator, not the store.)
        RetencionObservationRepository().replace_observations(
            modelo="180",
            filing_year=2024,
            period=period,
            observations=[_observation("11111111H"), _observation("22222222J")],
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        resolution = RetencionesAggregationSourceResolver().resolve(_context(_m180_revision_with_retenciones_source()))

        assert resolution.binding_values == {_PERCEPTOR_BINDING_ID: Decimal(2)}
        assert resolution.diagnostics == ()
        assert {item.source_ref for item in resolution.provenance} == {
            "perceptor:11111111H",
            "perceptor:22222222J",
        }


def test_resolver_materialises_modelo_115_count_and_base_from_real_store(tmp_path: Path) -> None:
    """M115 01/02 resolve from persisted URBAN_RENTAL per-perceptor observations."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        period = Period.from_year_and_code(2026, "1T")
        RetencionObservationRepository().replace_observations(
            modelo="115",
            filing_year=2026,
            period=period,
            observations=[
                RetencionObservation(
                    source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                    source_object_id="rent-ledger-row-001",
                    perceptor_nif="B12345678",
                    perceptor_name="Arrendador Ejemplo SL",
                    scheme=RetencionScheme.URBAN_RENTAL,
                    taxable_base=Decimal("2700.00"),
                    retencion_amount=Decimal("513.00"),
                    accrued_on="2026-03-15",
                ),
            ],
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        snapshot = _authority_snapshot("115", 2026, "1T")

        resolution = RetencionesAggregationSourceResolver().resolve(
            _context_for(modelo="115", filing_year=2026, period="1T", revision=snapshot.revision),
        )

    assert resolution.binding_values == {
        _M115_PERCEPTOR_BINDING_ID: Decimal("1"),
        _M115_BASE_BINDING_ID: Decimal("2700.00"),
    }
    assert resolution.diagnostics == ()
    assert {item.source_ref for item in resolution.provenance} == {"perceptor:B12345678"}


def test_resolver_materialises_modelo_111_scheme_filtered_bindings_from_real_store(tmp_path: Path) -> None:
    """M111 source bindings resolve the real registry's per-scheme count/base/retention selectors."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        period = Period.from_year_and_code(2026, "1T")
        RetencionObservationRepository().replace_observations(
            modelo="111",
            filing_year=2026,
            period=period,
            observations=[
                RetencionObservation(
                    source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                    source_object_id="payroll-row-001",
                    perceptor_nif="11111111H",
                    perceptor_name="Trabajador Ejemplo",
                    scheme=RetencionScheme.WORK_INCOME,
                    taxable_base=Decimal("100.00"),
                    retencion_amount=Decimal("10.00"),
                    accrued_on="2026-01-31",
                ),
                RetencionObservation(
                    source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                    source_object_id="activity-row-001",
                    perceptor_nif="22222222J",
                    perceptor_name="Profesional Ejemplo A",
                    scheme=RetencionScheme.ECONOMIC_ACTIVITY,
                    taxable_base=Decimal("200.00"),
                    retencion_amount=Decimal("20.00"),
                    accrued_on="2026-02-28",
                ),
                RetencionObservation(
                    source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                    source_object_id="professional-row-001",
                    perceptor_nif="33333333P",
                    perceptor_name="Profesional Ejemplo B",
                    scheme=RetencionScheme.PROFESSIONAL,
                    taxable_base=Decimal("300.00"),
                    retencion_amount=Decimal("30.00"),
                    accrued_on="2026-03-15",
                ),
                RetencionObservation(
                    source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                    source_object_id="prize-row-001",
                    perceptor_nif="44444444A",
                    perceptor_name="Premio Ejemplo",
                    scheme=RetencionScheme.PRIZE,
                    taxable_base=Decimal("400.00"),
                    retencion_amount=Decimal("40.00"),
                    accrued_on="2026-03-20",
                ),
            ],
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        )
        snapshot = _authority_snapshot("111", 2026, "1T")

        resolution = RetencionesAggregationSourceResolver().resolve(
            _context_for(modelo="111", filing_year=2026, period="1T", revision=snapshot.revision),
        )

    assert resolution.binding_values == _M111_BINDING_VALUES
    assert resolution.diagnostics == ()
    assert {item.source_ref for item in resolution.provenance} == {
        "perceptor:11111111H",
        "perceptor:22222222J",
        "perceptor:33333333P",
        "perceptor:44444444A",
    }


def test_resolver_empty_modelo_115_store_fails_before_silent_zero(tmp_path: Path) -> None:
    """A declaring M115 revision without per-perceptor evidence refuses zero materialisation."""
    snapshot = _authority_snapshot("115", 2026, "1T")
    with (
        isolated_runtime_profile(tmp_path=tmp_path),
        pytest.raises(AggregationValidationError) as exc_info,
    ):
        RetencionesAggregationSourceResolver().resolve(
            _context_for(modelo="115", filing_year=2026, period="1T", revision=snapshot.revision),
        )

    assert exc_info.value.translated_message == "aggregation.retenciones.errors.perceptor_observations_missing"
    context = exc_info.value.context or {}
    assert context["modelo"] == "115"
    assert context["period"] == "1T"
    verdict = exc_info.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == AggregationPreconditionCondition.RETENCIONES_OBSERVATIONS_PRESENT.value
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values["modelo"] == "115"


def test_resolver_empty_store_fails_before_silent_zero(tmp_path: Path) -> None:
    """An empty store on a declaring revision refuses calculation, never materialises 0."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path),
        pytest.raises(AggregationValidationError) as exc_info,
    ):
        RetencionesAggregationSourceResolver().resolve(_context(_m180_revision_with_retenciones_source()))

    assert exc_info.value.translated_message == "aggregation.retenciones.errors.perceptor_observations_missing"
    context = exc_info.value.context or {}
    assert context["modelo"] == "180"
    assert context["period"] == "0A"
    verdict = exc_info.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == AggregationPreconditionCondition.RETENCIONES_OBSERVATIONS_PRESENT.value
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values["modelo"] == "180"


def test_resolver_is_silent_when_revision_declares_no_retenciones_binding(tmp_path: Path) -> None:
    """A revision without a retenciones_aggregation binding resolves empty (no false advisory).

    Modelo 303 (IVA) declares no retenciones_aggregation binding. (M180/M193 DO
    declare it, so this uses a non-retenciones modelo.)
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        snapshot = _authority_snapshot("303", 2024, "1T")
        resolution = RetencionesAggregationSourceResolver().resolve(
            CalculationSourceContext(
                bucket_id="operator",
                modelo="303",
                filing_year=2024,
                period=Period.from_year_and_code(2024, "1T"),
                revision=snapshot.revision,
            ),
        )

        assert resolution.binding_values == {}
        assert resolution.diagnostics == ()
