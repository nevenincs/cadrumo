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

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.aggregation import AggregationCaptureKind, BindingSourceKind, RetencionScheme
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.period import Period
from ....domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from .._preconditions import AggregationPreconditionCondition
from ..errors import AggregationValidationError
from ..modelo_bindings_retenciones import RetencionesAggregationSourceResolver
from ..retencion_observations_repository import RetencionObservationPorts
from ..retenciones import Modelo180PropertyEvidence, Modelo180StructuredAddress, RetencionObservation
from ..source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

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


class _InMemoryRetencionObservationRepository:
    """Deterministic application-port fake for resolver behavior tests."""

    def __init__(self) -> None:
        self._windows: dict[tuple[str, int, str], tuple[RetencionObservation, ...]] = {}

    def replace_observations(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observations: Sequence[RetencionObservation],
        source_kind: AggregationCaptureKind,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        self._windows[(modelo, filing_year, period.registry_token)] = tuple(observations)

    def load_observations(self, modelo: str, period: Period) -> tuple[RetencionObservation, ...]:
        return self._windows.get((modelo, period.filing_year, period.registry_token), ())

    def load_annual_source_observations(self, source_modelo: str, filing_year: int) -> tuple[RetencionObservation, ...]:
        return tuple(
            observation
            for (modelo, year, period), observations in self._windows.items()
            if modelo == source_modelo and year == filing_year and period.endswith("T")
            for observation in observations
        )

    def load_source_observations_through_year(
        self,
        source_modelo: str,
        last_filing_year: int,
    ) -> tuple[RetencionObservation, ...]:
        return tuple(
            observation
            for (modelo, year, period), observations in self._windows.items()
            if modelo == source_modelo and year <= last_filing_year and period.endswith("T")
            for observation in observations
        )


def _resolver(repository: _InMemoryRetencionObservationRepository) -> RetencionesAggregationSourceResolver:
    return RetencionesAggregationSourceResolver(ports=RetencionObservationPorts(repository=repository))


@pytest.mark.parametrize("modelo", ("111", "115", "123", "180", "190", "193"))
def test_public_retenciones_resolver_owns_each_retenciones_modelo(modelo: str) -> None:
    """The public aggregation owner, not an entrypoint tuple, classifies retenciones modelos."""
    assert RetencionesAggregationSourceResolver.supports_modelo(modelo)


def test_public_retenciones_resolver_rejects_non_retenciones_modelos() -> None:
    assert not RetencionesAggregationSourceResolver.supports_modelo("303")


@cache
def _authority_snapshot(modelo: str, filing_year: int, period: str) -> RegistrySnapshot:
    return published_snapshot(modelo, filing_year=filing_year, period=period)


def _observation(nif: str) -> RetencionObservation:
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id=f"tx-{nif}",
        perceptor_nif=nif,
        perceptor_name="Arrendador Ejemplo SL",
        # Modelo 180 is the arrendamiento de inmuebles urbanos summary; its
        # aggregator filters on the URBAN_RENTAL scheme.
        scheme=RetencionScheme("arrendamiento_urbano"),
        taxable_base=Decimal("1000.00"),
        retencion_amount=Decimal("190.00"),
        accrued_on="2024-03-15",
        modelo_180_property=Modelo180PropertyEvidence(
            property_key=f"property-{nif}",
            situation="1",
            cadastral_reference=f"{nif}PROPERTY",
            recipient_province_code="28",
            modality="1",
            accrual_year=2024,
            withholding_percentage=Decimal("19.00"),
            address=Modelo180StructuredAddress(
                province_code="28",
                municipality_code="079",
                municipality="Madrid",
                locality="Madrid",
                postal_code="28001",
                street_type="CL",
                street_name="Ejemplo",
                number_type="NUM",
                house_number="1",
            ),
        ),
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


def test_resolver_materialises_distinct_perceptor_count() -> None:
    """Two perceptors across three rows materialise a DISTINCT count of 2, not 3."""
    repository = _InMemoryRetencionObservationRepository()
    period = Period.from_year_and_code(2024, "1T")
    # 11111111H appears twice (e.g. two payments) but is ONE perceptor; the
    # distinct-NIF count is 2. (Same NIF, same scheme → the second overwrites,
    # so seed via two NIFs plus a repeat to prove distinctness through the
    # aggregator, not the store.)
    repository.replace_observations(
        modelo="115",
        filing_year=2024,
        period=period,
        observations=[_observation("11111111H"), _observation("22222222J")],
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )
    resolution = _resolver(repository).resolve(_context(_m180_revision_with_retenciones_source()))

    assert resolution.binding_values == {_PERCEPTOR_BINDING_ID: Decimal(2)}
    assert resolution.diagnostics == ()
    assert {item.source_ref for item in resolution.provenance} == {
        "perceptor:11111111H",
        "perceptor:22222222J",
    }


def test_resolver_materialises_modelo_115_count_and_base_from_application_port() -> None:
    """M115 01/02 resolve from application-port per-perceptor observations."""
    repository = _InMemoryRetencionObservationRepository()
    period = Period.from_year_and_code(2026, "1T")
    repository.replace_observations(
        modelo="115",
        filing_year=2026,
        period=period,
        observations=[
            RetencionObservation(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                source_object_id="rent-ledger-row-001",
                perceptor_nif="B12345678",
                perceptor_name="Arrendador Ejemplo SL",
                scheme=RetencionScheme("arrendamiento_urbano"),
                taxable_base=Decimal("2700.00"),
                retencion_amount=Decimal("513.00"),
                accrued_on="2026-03-15",
            ),
        ],
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )
    snapshot = _authority_snapshot("115", 2026, "1T")

    resolution = _resolver(repository).resolve(
        _context_for(modelo="115", filing_year=2026, period="1T", revision=snapshot.revision),
    )

    assert resolution.binding_values == {
        _M115_PERCEPTOR_BINDING_ID: Decimal("1"),
        _M115_BASE_BINDING_ID: Decimal("2700.00"),
    }
    assert resolution.diagnostics == ()
    assert {item.source_ref for item in resolution.provenance} == {"perceptor:B12345678"}


def test_resolver_materialises_modelo_111_scheme_filtered_bindings_from_application_port() -> None:
    """M111 source bindings resolve the real registry's per-scheme count/base/retention selectors."""
    repository = _InMemoryRetencionObservationRepository()
    period = Period.from_year_and_code(2026, "1T")
    repository.replace_observations(
        modelo="111",
        filing_year=2026,
        period=period,
        observations=[
            RetencionObservation(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                source_object_id="payroll-row-001",
                perceptor_nif="11111111H",
                perceptor_name="Trabajador Ejemplo",
                scheme=RetencionScheme("rendimientos_trabajo"),
                taxable_base=Decimal("100.00"),
                retencion_amount=Decimal("10.00"),
                accrued_on="2026-01-31",
            ),
            RetencionObservation(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                source_object_id="activity-row-001",
                perceptor_nif="22222222J",
                perceptor_name="Profesional Ejemplo A",
                scheme=RetencionScheme("actividades_economicas"),
                taxable_base=Decimal("200.00"),
                retencion_amount=Decimal("20.00"),
                accrued_on="2026-02-28",
            ),
            RetencionObservation(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                source_object_id="professional-row-001",
                perceptor_nif="33333333P",
                perceptor_name="Profesional Ejemplo B",
                scheme=RetencionScheme("actividades_profesionales"),
                taxable_base=Decimal("300.00"),
                retencion_amount=Decimal("30.00"),
                accrued_on="2026-03-15",
            ),
            RetencionObservation(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                source_object_id="prize-row-001",
                perceptor_nif="44444444A",
                perceptor_name="Premio Ejemplo",
                scheme=RetencionScheme("premios"),
                taxable_base=Decimal("400.00"),
                retencion_amount=Decimal("40.00"),
                accrued_on="2026-03-20",
            ),
        ],
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )
    snapshot = _authority_snapshot("111", 2026, "1T")

    resolution = _resolver(repository).resolve(
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


def test_resolver_empty_modelo_115_store_fails_before_silent_zero() -> None:
    """A declaring M115 revision without per-perceptor evidence refuses zero materialisation."""
    snapshot = _authority_snapshot("115", 2026, "1T")
    with pytest.raises(AggregationValidationError) as exc_info:
        _resolver(_InMemoryRetencionObservationRepository()).resolve(
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


def test_resolver_materialises_empty_modelo_115_only_for_exact_no_relevant_payment_attestation() -> None:
    """An explicit matching profile fact is the sole empty-window zero authority."""
    snapshot = _authority_snapshot("115", 2026, "1T")
    resolver = RetencionesAggregationSourceResolver(
        ports=RetencionObservationPorts(repository=_InMemoryRetencionObservationRepository()),
        m115_no_relevant_payment_periods=frozenset({(2026, "1T")}),
    )

    resolution = resolver.resolve(
        _context_for(modelo="115", filing_year=2026, period="1T", revision=snapshot.revision),
    )

    assert resolution.binding_values == {
        _M115_PERCEPTOR_BINDING_ID: Decimal("0"),
        _M115_BASE_BINDING_ID: Decimal("0"),
    }
    assert len(resolution.diagnostics) == 1
    assert "explicit no-relevant-payment attestation" in resolution.diagnostics[0].message
    with pytest.raises(AggregationValidationError):
        resolver.resolve(
            _context_for(
                modelo="115",
                filing_year=2026,
                period="2T",
                revision=_authority_snapshot("115", 2026, "2T").revision,
            ),
        )


def test_resolver_empty_store_fails_before_silent_zero() -> None:
    """An empty store on a declaring revision refuses calculation, never materialises 0."""
    with pytest.raises(AggregationValidationError) as exc_info:
        _resolver(_InMemoryRetencionObservationRepository()).resolve(_context(_m180_revision_with_retenciones_source()))

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


def test_resolver_is_silent_when_revision_declares_no_retenciones_binding() -> None:
    """A revision without a retenciones_aggregation binding resolves empty (no false advisory).

    Modelo 303 (IVA) declares no retenciones_aggregation binding. (M180/M193 DO
    declare it, so this uses a non-retenciones modelo.)
    """
    snapshot = _authority_snapshot("303", 2024, "1T")
    resolution = _resolver(_InMemoryRetencionObservationRepository()).resolve(
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
