"""The published annual Orden authority carries the tables each BOE Orden prints.

These figures are the fixed counts the annual Orden checks used to assert, and they
match the manifest rows extracted from each pinned BOE Orden. They were not recounted
by hand from the annexes for this test.
"""

from __future__ import annotations

import tomllib
from collections import Counter
from decimal import Decimal

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.modelo import Modelo
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.m303_orden_constants import validate_generated_source_counts
from cadrumo.domain.calculations.registry.m303_orden_projection_models import M303AnnualOrdenGeneratedSource

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_AGRICULTURAL_ROWS = {2022: 16, 2023: 16, 2024: 16, 2025: 17, 2026: 17}


def _source(**overrides: object) -> M303AnnualOrdenGeneratedSource:
    fields: dict[str, object] = {
        "ejercicio": 2025,
        "source_ref": "boe-orden-probe",
        "source_content_digest": "0" * 64,
        "activity_table_count": 3,
        "module_row_count": 5,
        "module_distribution": (2, 0, 1, 0, 0, 0, 0),
        "agricultural_index_row_count": 2,
        "agricultural_ingreso_a_cuenta_row_count": 2,
        "non_agricultural_ingreso_a_cuenta_row_count": 1,
        "seasonal_index_day_bands": ((1, 60), (61, 120), (121, 180)),
        "seasonal_index_coefficients": (Decimal("1.5"), Decimal("1.35"), Decimal("1.25")),
        "difficult_justification_pct": Decimal("1"),
    }
    return M303AnnualOrdenGeneratedSource.model_validate({**fields, **overrides})


@pytest.mark.parametrize("ejercicio", sorted(_AGRICULTURAL_ROWS))
def test_each_published_orden_carries_its_printed_table_counts(ejercicio: int) -> None:
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot(
            "303", filing_year=ejercicio, period="4T", grade=RegistryAuthorityGrade.CALCULATION
        )
    orden = snapshot.supplementary_ordenes[Modelo("303")].require_projection(
        ejercicio=ejercicio,
        registry_revision_id=snapshot.revision.id,
    )
    sizes = Counter(len(activity.modulos) for activity in orden.activities)
    assert len(orden.activities) == 49
    assert sum(sizes[size] * size for size in sizes) == 141
    assert tuple(sizes[size] for size in range(1, 8)) == (2, 25, 12, 4, 1, 3, 2)
    assert len(orden.non_agricultural_ingresos_a_cuenta) == 47


@pytest.mark.parametrize(("ejercicio", "rows"), sorted(_AGRICULTURAL_ROWS.items()))
def test_each_manifest_row_carries_the_printed_agricultural_axis(ejercicio: int, rows: int) -> None:
    manifest = tomllib.loads(bundled_path("registry", "aeat", "m303_orden_anual", "manifest.toml").read_text("utf-8"))
    row = next(item for item in manifest["sources"] if item["ejercicio"] == ejercicio)
    assert (row["agricultural_index_row_count"], row["agricultural_ingreso_a_cuenta_row_count"]) == (rows, rows)


def test_consistent_counts_are_accepted_for_any_year() -> None:
    validate_generated_source_counts(_source(ejercicio=2031))


@pytest.mark.parametrize(
    "defect",
    [
        pytest.param({"activity_table_count": 4}, id="activity-count"),
        pytest.param({"module_row_count": 6}, id="module-count"),
        pytest.param({"agricultural_ingreso_a_cuenta_row_count": 3}, id="agricultural-axes"),
    ],
)
def test_contradictory_counts_are_refused(defect: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="disagree"):
        _source(**defect)
