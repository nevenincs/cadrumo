"""The WithholdingSourceResolver materialises the M190 percepciones count.

Drives the REAL encrypted store plus a typed registry-shaped revision:
the resolver reads persisted per-perceptor-clave
:class:`WithholdingObservation` records and materialises the DISTINCT
(perceptor, clave, subclave) count for a ``percepcion_count`` binding. Empty
store -> zero count + a non-blocking advisory (a nil filer must still
calculate), never a hard refusal.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema import DataBindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingObservation

from ....core import AggregationCaptureKind, Period
from ....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind, RetencionClave
from ....tests.secure_sql import isolated_runtime_profile
from .._percepciones_observations_repository import PercepcionObservationRepository
from .._source_mesh import CalculationSourceContext
from .._withholding_source import WithholdingSourceResolver

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PERCEPCION_BINDING_ID = "modelo-190-percepciones-anual"
_M190_WITHHOLDING_LEGAL_REFS = (
    "ley-35-2006:art-99",
    "orden-eha-3127-2009:art-1",
    "orden-hac-1431-2025:art-2",
    "rd-439-2007:art-108",
    "rd-439-2007:art-80",
    "ley-35-2006:art-101",
    "rd-439-2007:art-86",
    "ley-58-2003:art-93",
)
_M190_WITHHOLDING_SOURCE_REFS = (
    "aeat-dr-190-2025",
    "aeat-modelo-190-instructions-2025",
    "boe-modelo-190-2025-form",
)


def _revision_with(*bindings: DataBindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id="2024-y-siguientes",
        localization_key="test.schema.revision.2024-y-siguientes.label",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(year_from=2024, periods=("0A",)),
        legal_refs=_M190_WITHHOLDING_LEGAL_REFS,
        source_refs=_M190_WITHHOLDING_SOURCE_REFS,
        bindings=bindings,
    )


def _percepcion_binding() -> DataBindingDefinition:
    return DataBindingDefinition(
        id=_PERCEPCION_BINDING_ID,
        source=BindingSourceKind.WITHHOLDING,
        selector={"fact": "percepcion_count"},
        aggregation=BindingAggregation(op=BindingAggregationOp.COUNT_DISTINCT),
        legal_refs=_M190_WITHHOLDING_LEGAL_REFS,
        source_refs=_M190_WITHHOLDING_SOURCE_REFS,
    )


def _non_withholding_revision() -> ModeloRevision:
    return ModeloRevision(
        id="303-no-withholding-test",
        localization_key="test.schema.revision.303-no-withholding-test.label",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(years=(2024,), periods=("1T",)),
        legal_refs=("ley-37-1992:art-1",),
        source_refs=("test-no-withholding-binding",),
    )


def _context(revision: ModeloRevision) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id="operator",
        modelo="190",
        filing_year=2024,
        period=Period.from_year_and_code(2024, "0A"),
        revision=revision,
    )


def _obs(nif: str, clave: RetencionClave) -> WithholdingObservation:
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
        PercepcionObservationRepository().replace_observations(
            modelo="190",
            filing_year=2024,
            period=period,
            observations=[
                _obs("11111111H", RetencionClave.A),
                _obs("11111111H", RetencionClave.G),
                _obs("22222222J", RetencionClave.A),
            ],
            source_kind=AggregationCaptureKind.AGGREGATE_PULL,
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
        resolution = WithholdingSourceResolver().resolve(
            CalculationSourceContext(
                bucket_id="operator",
                modelo="303",
                filing_year=2024,
                period=Period.from_year_and_code(2024, "1T"),
                revision=_non_withholding_revision(),
            ),
        )

        assert resolution.binding_values == {}
        assert resolution.diagnostics == ()
