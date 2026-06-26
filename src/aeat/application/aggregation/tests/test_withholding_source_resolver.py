"""The WithholdingSourceResolver materialises the M190 percepciones count (#28 P03).

Drives the REAL encrypted store + the real registry authority (no mocks): the
resolver reads the persisted per-perceptor-clave :class:`WithholdingObservation`
records and materialises the DISTINCT (perceptor, clave, subclave) count for a
``percepcion_count`` binding. Empty store -> zero count + a non-blocking advisory
(the RET-1 ruling: a nil filer must still calculate), never a hard refusal.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....core.aggregation import BindingAggregation, BindingAggregationOp, RowSetGroupingKind
from ....core.resources import resources
from ....domain.calculations.registry import DataBindingDefinition, ModeloRevision, WithholdingObservation
from ....tests.secure_sql import isolated_runtime_profile
from .._source_mesh import CalculationSourceContext
from .._withholding_observations_repository import WithholdingObservationRepository
from .._withholding_source import WithholdingSourceResolver

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERCEPCION_BINDING_ID = "modelo-190-123-percepciones-anual-test"


def _m190_revision() -> ModeloRevision:
    return resources().modelos.authority.snapshot("190", filing_year=2024, period="0A").revision


def _percepcion_binding() -> DataBindingDefinition:
    base = next(b for b in _m190_revision().bindings if b.source == RowSetGroupingKind.WITHHOLDING)
    return base.model_copy(
        update={
            "source": RowSetGroupingKind.WITHHOLDING,
            "selector": {"fact": "percepcion_count"},
            "aggregation": BindingAggregation(op=BindingAggregationOp.COUNT_DISTINCT),
        },
    )


def _revision_with(binding: DataBindingDefinition) -> ModeloRevision:
    return _m190_revision().model_copy(update={"bindings": (binding,)})


def _context(revision: ModeloRevision) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id="operator",
        modelo="190",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "0A"),
        revision=revision,
    )


def _obs(nif: str, clave: str) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=f"row-{nif}-{clave}",
        perceptor_tax_id=nif,
        transaction_date=date(2024, 6, 1),
        clave=clave,
        percibido_dinerario=Decimal("1000"),
        retencion_practicada=Decimal("190"),
    )


def test_resolver_materialises_distinct_percepcion_count(tmp_path: Path) -> None:
    """One perceptor under two claves -> percepciones count of 2 from the store."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        binding = _percepcion_binding()
        period = Period.from_year_and_code(2024, "0A")
        WithholdingObservationRepository().replace_observations(
            modelo="190",
            filing_year=2024,
            period=period,
            observations=[_obs("11111111H", "A"), _obs("11111111H", "G"), _obs("22222222J", "A")],
            source_kind="aggregate_pull",
        )
        resolution = WithholdingSourceResolver().resolve(_context(_revision_with(binding)))

        assert resolution.binding_values == {binding.id: Decimal(3)}
        assert resolution.diagnostics == ()


def test_resolver_materialises_zero_with_advisory_on_empty_store(tmp_path: Path) -> None:
    """Empty store -> zero count materialised + a non-blocking advisory (not a refusal)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        binding = _percepcion_binding()
        resolution = WithholdingSourceResolver().resolve(_context(_revision_with(binding)))

        assert resolution.binding_values == {binding.id: Decimal(0)}
        assert len(resolution.diagnostics) == 1
        assert resolution.diagnostics[0].source_kind == "withholding"
        assert "materialised as zero" in resolution.diagnostics[0].message


def test_resolver_silent_when_revision_declares_no_withholding_binding(tmp_path: Path) -> None:
    """A revision with no withholding binding resolves empty (no false advisory)."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        snapshot = resources().modelos.authority.snapshot("303", filing_year=2024, period="1T")
        resolution = WithholdingSourceResolver().resolve(
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
