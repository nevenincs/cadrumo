"""Independent guard: retenciones count source refuses an empty perceptor store.

Modelo 180's perceptor-count binding declares
``source = "retenciones_aggregation"``. With an empty encrypted retención
observation store, the live resolver must raise before a zero count can be
materialised. The test keeps the guard on the real resolver and store path while
building only the typed binding surface it consumes.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema import DataBindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector

from ....core import NoRecoveryOutcome, Period
from ....core.aggregation import BindingSourceKind
from ....tests.secure_sql import isolated_runtime_profile
from .._modelo_bindings import RetencionesAggregationSourceResolver
from .._preconditions import AggregationPreconditionCondition
from .._source_mesh import CalculationSourceContext
from ..errors import AggregationValidationError

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


def _m180_retenciones_revision() -> ModeloRevision:
    return ModeloRevision(
        id="2023-y-siguientes",
        localization_key="test.schema.revision.2023-y-siguientes.label",
        valid_from=date(2023, 1, 1),
        period_selector=PeriodSelector(year_from=2023, periods=("0A",)),
        legal_refs=_M180_RETENCIONES_LEGAL_REFS,
        source_refs=_M180_RETENCIONES_SOURCE_REFS,
        bindings=(
            DataBindingDefinition(
                id=_M180_BINDING_ID,
                source=BindingSourceKind.RETENCIONES_AGGREGATION,
                selector={
                    "target_casilla_id": "decl.total-perceptores",
                    "fact": "perceptor_count_distinct",
                },
                legal_refs=_M180_RETENCIONES_LEGAL_REFS,
                source_refs=_M180_RETENCIONES_SOURCE_REFS,
            ),
        ),
    )


def test_real_resolver_empty_store_fails_before_silent_zero(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path),
        pytest.raises(AggregationValidationError) as exc_info,
    ):
        RetencionesAggregationSourceResolver().resolve(
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
