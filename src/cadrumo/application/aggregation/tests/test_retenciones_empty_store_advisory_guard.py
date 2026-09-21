"""Independent guard: retenciones count source refuses an empty perceptor store.

Modelo 180's perceptor-count binding declares
``source = "retenciones_aggregation"``. With an empty observation capability,
the application resolver must raise before a zero count can be materialised.
The concrete encrypted adapter is covered at its persistence seam; this test
keeps the guard on the real resolver with an inward empty-port fake.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime

import pytest

from ....core.aggregation import AggregationCaptureKind
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.period import Period
from ....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_references import PeriodSelector
from .._preconditions import AggregationPreconditionCondition
from ..errors import AggregationValidationError
from ..modelo_bindings_retenciones import RetencionesAggregationSourceResolver
from ..retencion_observations_repository import RetencionObservationPorts
from ..retenciones import RetencionObservation
from ..source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M180_BINDING_ID = "modelo-180-115-perceptores-anual"
_M180_RETENCIONES_LEGAL_REFS = (
    "ley-35-2006:art-99",
    "rd-439-2007:art-100",
    "orden-hap-1732-2014:art-2",
    "orden-hfp-1284-2023:art-7",
    "rd-439-2007:art-108",
    "ley-35-2006:art-101",
    "ley-58-2003:art-93",
)
_M180_RETENCIONES_SOURCE_REFS = (
    "aeat-modelo-180-ayuda-resumen-datos",
    "aeat-modelo-180-ayuda-presentacion",
    "boe-modelo-180-2014-form",
    "boe-modelo-180-2023-form",
)


class _EmptyRetencionObservationRepository:
    """Application-port fake representing an empty observation window."""

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
        del modelo, filing_year, period, observations, source_kind, captured_at, source_metadata

    def load_observations(self, modelo: str, period: Period) -> tuple[RetencionObservation, ...]:
        return ()

    def load_annual_source_observations(self, source_modelo: str, filing_year: int) -> tuple[RetencionObservation, ...]:
        return ()


def _m180_retenciones_revision() -> ModeloRevision:
    return ModeloRevision(
        id="2023-y-siguientes",
        localization_key="test.schema.revision.2023-y-siguientes.label",
        valid_from=date(2023, 1, 1),
        period_selector=PeriodSelector(year_from=2023, periods=("0A",)),
        legal_refs=_M180_RETENCIONES_LEGAL_REFS,
        source_refs=_M180_RETENCIONES_SOURCE_REFS,
        bindings=(
            BindingDefinition(
                id=_M180_BINDING_ID,
                provider={
                    "kind": "retenciones_aggregation",
                    **{
                        "target_casilla_id": "decl.total-perceptores",
                        "fact": "perceptor_count_distinct",
                    },
                },
                value={"data_type": "money", "channel": "decimal"},
                legal_refs=_M180_RETENCIONES_LEGAL_REFS,
                source_refs=_M180_RETENCIONES_SOURCE_REFS,
            ),
        ),
    )


def test_resolver_empty_application_port_fails_before_silent_zero() -> None:
    with (
        pytest.raises(AggregationValidationError) as exc_info,
    ):
        RetencionesAggregationSourceResolver(
            ports=RetencionObservationPorts(repository=_EmptyRetencionObservationRepository()),
        ).resolve(
            CalculationSourceContext(
                bucket_id="operator",
                modelo="180",
                filing_year=2024,
                period=Period.from_year_and_code(2024, "0A"),
                revision=_m180_retenciones_revision(),
            ),
        )

    assert exc_info.value.translated_message == "aggregation.retenciones.errors.perceptor_observations_missing"
    assert exc_info.value.context == {
        "modelo": "180",
        "filing_year": "2024",
        "period": "0A",
        "source_kind": "retenciones_aggregation",
    }
    verdict = exc_info.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == AggregationPreconditionCondition.RETENCIONES_OBSERVATIONS_PRESENT.value
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values["modelo"] == "180"
