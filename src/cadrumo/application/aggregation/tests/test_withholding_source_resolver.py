"""The WithholdingSourceResolver materialises the M190 percepciones count.

Drives the REAL encrypted store plus a typed registry-shaped revision:
the resolver reads persisted per-perceptor-clave
:class:`WithholdingObservation` records and materialises the DISTINCT
(perceptor, clave, subclave) count for a ``percepcion_count`` binding. Empty
store -> zero count + a non-blocking advisory (a nil filer must still
calculate), never a hard refusal.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal

import pytest

from ....core.aggregation import (
    AggregationCaptureKind,
    BindingAggregation,
    BindingAggregationOp,
    RetencionClave,
)
from ....core.period import Period
from ....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_references import PeriodSelector
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ..percepciones_observations_repository import PercepcionObservationPorts
from ..source_mesh import CalculationSourceContext
from ..withholding_source import WithholdingSourceResolver

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


class _InMemoryPercepcionObservationRepository:
    """Protocol-conforming inward fake for resolver behavior tests."""

    def __init__(self) -> None:
        self._windows: dict[tuple[str, int, str], tuple[WithholdingObservation, ...]] = {}

    def replace_observations(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observations: Sequence[WithholdingObservation],
        source_kind: AggregationCaptureKind,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        del source_kind, captured_at, source_metadata
        self._windows[(modelo, filing_year, period.registry_token)] = tuple(observations)

    def load_observations(self, modelo: str, period: Period) -> tuple[WithholdingObservation, ...]:
        return self._windows.get((modelo, period.filing_year, period.registry_token), ())


def _revision_with(*bindings: BindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id="2024-y-siguientes",
        localization_key="test.schema.revision.2024-y-siguientes.label",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(year_from=2024, periods=("0A",)),
        legal_refs=_M190_WITHHOLDING_LEGAL_REFS,
        source_refs=_M190_WITHHOLDING_SOURCE_REFS,
        bindings=bindings,
    )


def _percepcion_binding() -> BindingDefinition:
    return BindingDefinition(
        id=_PERCEPCION_BINDING_ID,
        provider={"kind": "withholding", **{"fact": "percepcion_count"}},
        value={"data_type": "money", "channel": "decimal"},
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
        incapacity_cash_perception=Decimal("0"),
        incapacity_cash_withholding=Decimal("0"),
        incapacity_kind_value=Decimal("0"),
        incapacity_kind_ingreso_a_cuenta=Decimal("0"),
        incapacity_kind_repercutido=Decimal("0"),
        foral_retention_estatal=Decimal("0"),
        foral_retention_navarra=Decimal("0"),
        foral_retention_araba=Decimal("0"),
        foral_retention_gipuzkoa=Decimal("0"),
        foral_retention_bizkaia=Decimal("0"),
        base_retenciones=Decimal("0"),
    )


def test_resolver_materialises_distinct_percepcion_count() -> None:
    """One perceptor under two claves -> percepciones count of 2 from the store."""
    binding = _percepcion_binding()
    period = Period.from_year_and_code(2024, "0A")
    repository = _InMemoryPercepcionObservationRepository()
    repository.replace_observations(
        modelo="190",
        filing_year=2024,
        period=period,
        observations=[
            _obs("11111111H", RetencionClave.from_registry("A")),
            _obs("11111111H", RetencionClave.from_registry("G")),
            _obs("22222222J", RetencionClave.from_registry("A")),
        ],
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )
    resolution = WithholdingSourceResolver(ports=PercepcionObservationPorts(repository=repository)).resolve(
        _context(_revision_with(binding)),
    )

    assert resolution.binding_values == {binding.id: Decimal(3)}
    assert resolution.diagnostics == ()


def test_resolver_materialises_zero_with_advisory_on_empty_store() -> None:
    """Empty store -> zero count materialised + a non-blocking advisory (not a refusal)."""
    binding = _percepcion_binding()
    ports = PercepcionObservationPorts(repository=_InMemoryPercepcionObservationRepository())
    resolution = WithholdingSourceResolver(ports=ports).resolve(_context(_revision_with(binding)))

    assert resolution.binding_values == {binding.id: Decimal(0)}
    assert len(resolution.diagnostics) == 1
    assert resolution.diagnostics[0].source_kind == "withholding"
    assert "materialised as zero" in resolution.diagnostics[0].message


def test_resolver_silent_when_revision_declares_no_withholding_binding() -> None:
    """A revision with no withholding binding resolves empty (no false advisory)."""
    ports = PercepcionObservationPorts(repository=_InMemoryPercepcionObservationRepository())
    resolution = WithholdingSourceResolver(ports=ports).resolve(
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
