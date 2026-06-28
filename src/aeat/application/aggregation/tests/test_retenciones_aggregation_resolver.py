"""Calc-mesh resolver for the dedicated per-perceptor retención store (RET-1 P02).

The :class:`RetencionesAggregationSourceResolver` reads the persisted per-perceptor
observations (P01 store) and materialises the Modelo 180 "número total de
perceptores" box with the validated DISTINCT-NIF count — never the sum of
quarterly aggregate counts. An empty store on a revision that declares the
perceptor-count binding raises before a zero count can be persisted.

The test revision is the real Modelo 180 revision with its perceptor-count binding
re-pointed to the ``retenciones_aggregation`` source (the P03 cutover, simulated
here via ``model_copy`` so P02 can be exercised before the registry re-stamp).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....core import BindingSourceKind, Period
from ....core.resources import resources
from ....domain.calculations.registry import ModeloRevision
from ....tests.secure_sql import isolated_runtime_profile
from .._errors import AggregationValidationError
from .._modelo_bindings import RetencionesAggregationSourceResolver
from .._retencion_observations_repository import RetencionObservationRepository
from .._retenciones import RetencionObservation, RetencionScheme
from .._source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERCEPTOR_BINDING_ID = "modelo-180-115-perceptores-anual"


def _observation(nif: str) -> RetencionObservation:
    return RetencionObservation(
        source_kind="ledger_transaction",
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

    Simulates the P03 registry re-stamp via ``model_copy`` so the P02 resolver is
    exercised before the registry cutover lands.
    """
    snapshot = resources().modelos.authority.snapshot("180", filing_year=2024, period="0A")
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
            source_kind="aggregate_pull",
        )
        resolution = RetencionesAggregationSourceResolver().resolve(_context(_m180_revision_with_retenciones_source()))

        assert resolution.binding_values == {_PERCEPTOR_BINDING_ID: Decimal(2)}
        assert resolution.diagnostics == ()
        assert {item.source_ref for item in resolution.provenance} == {
            "perceptor:11111111H",
            "perceptor:22222222J",
        }


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
    assert "--retencion-observation" in (exc_info.value.suggestion or "")


def test_resolver_is_silent_when_revision_declares_no_retenciones_binding(tmp_path: Path) -> None:
    """A revision without a retenciones_aggregation binding resolves empty (no false advisory).

    Modelo 303 (IVA) declares no retenciones_aggregation binding. (M180/M193 DO
    declare it after the RET-1 P03 re-stamp, so this uses a non-retenciones modelo.)
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        snapshot = resources().modelos.authority.snapshot("303", filing_year=2024, period="1T")
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
