"""Independent guard: retenciones count source refuses an empty perceptor store.

Modelo 180's current registry revision declares its perceptor-count binding as
``source = "retenciones_aggregation"``. With an empty encrypted retención
observation store, the live resolver must raise before a zero count can be
materialised. This keeps the guard on the real registry + real resolver path and
away from hand-built resolver payloads.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core import Period
from ....core.resources import resources
from ....tests.secure_sql import isolated_runtime_profile
from .._errors import AggregationValidationError
from .._modelo_bindings import RetencionesAggregationSourceResolver
from .._source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_real_resolver_empty_store_fails_before_silent_zero(tmp_path: Path) -> None:
    with (
        isolated_runtime_profile(tmp_path=tmp_path),
        pytest.raises(AggregationValidationError) as exc_info,
    ):
        snapshot = resources().modelos.authority.snapshot("180", filing_year=2024, period="0A")
        RetencionesAggregationSourceResolver().resolve(
            CalculationSourceContext(
                bucket_id="operator",
                modelo="180",
                filing_year=2024,
                period=Period.from_year_and_code(2024, "0A"),
                revision=snapshot.revision,
            ),
        )

    assert exc_info.value.translated_message == "aggregation.retenciones.errors.perceptor_observations_missing"
    assert exc_info.value.context == {
        "modelo": "180",
        "filing_year": "2024",
        "period": "0A",
        "source_kind": "retenciones_aggregation",
    }
    assert "--retencion-observation" in (exc_info.value.suggestion or "")
