"""End-to-end coverage check for the seven detail-record modelos.

Catches binding-vs-resolver mismatches and Detalle-tab dead bindings:
each modelo that declares row-producer bindings must (a) be visible
to the engine's `collect_row_sets` walker so the Sheets Detalle
tab gets headers + reserved data rows, and (b) point at a
binding source kind a resolver actually consumes. A binding
declared with no matching resolver is dead weight; one that
collects empty is silently broken.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from .....application.storage.calc_sheets import collect_row_sets
from ..schema import ModeloDefinition
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# Source kind → number of row-producer binding cohorts the engine should
# collect per modelo (not every revision; the spec is per declared
# revision-id below).
_DETAIL_RECORD_MODELOS: tuple[tuple[str, str, str, int], ...] = (
    # (modelo, revision_id, source_kind, expected_cohort_count)
    ("190", "2025-y-siguientes", "withholding", 1),
    ("193", "2025-y-siguientes", "withholding", 2),
    ("232", "2018-y-siguientes", "related_party_operation", 1),
    ("720", "2013-y-siguientes", "foreign_asset", 1),
    ("184", "2025-y-siguientes", "atribucion_member", 1),
    ("360", "2010-y-siguientes", "refund_operation", 1),
    ("349", "2020-y-siguientes", "collectible_invoice", 2),
    ("182", "2025", "donativo_donor", 1),
)


@pytest.fixture(scope="module")
def _modelos_by_id() -> Mapping[str, ModeloDefinition]:
    modelos, _catalogues = _committed_registry_tree()
    return {modelo.id: modelo for modelo in modelos}


@pytest.mark.parametrize(("modelo_id", "revision_id", "source_kind", "expected_cohorts"), _DETAIL_RECORD_MODELOS)
def test_detail_record_modelo_emits_row_sets_with_localized_headers(
    _modelos_by_id: Mapping[str, ModeloDefinition],
    modelo_id: str,
    revision_id: str,
    source_kind: str,
    expected_cohorts: int,
) -> None:
    """Each detail-record modelo's row-producer bindings produce localized row-sets."""

    revision = _modelos_by_id[modelo_id].revisions[revision_id]
    declared = [
        b
        for b in revision.bindings
        if b.source == source_kind and b.aggregation is not None and b.aggregation.op == "rows"
    ]
    assert declared, f"modelo {modelo_id!r} declares no {source_kind!r} row-producer bindings"
    # The column-completeness universe is every row-producer binding the
    # revision declares, whatever its source: modelo 193 emits two cohorts
    # (perceptor and gastos rows) and both must produce localized columns.
    row_producer_ids = {b.id for b in revision.bindings if b.aggregation is not None and b.aggregation.op == "rows"}

    row_sets = collect_row_sets(revision)

    assert len(row_sets) == expected_cohorts, (
        f"modelo {modelo_id!r} expected {expected_cohorts} row-set cohort(s), got {len(row_sets)}"
    )
    declared_ids = {b.id for b in declared}
    column_binding_ids = {col.binding for rs in row_sets for col in rs.columns}
    missing_columns = declared_ids - column_binding_ids
    assert not missing_columns, (
        f"modelo {modelo_id!r} row-set columns missing declared bindings: {sorted(missing_columns)}"
    )
    spurious_columns = column_binding_ids - row_producer_ids
    assert not spurious_columns, (
        f"modelo {modelo_id!r} row-set columns include unknown bindings: {sorted(spurious_columns)}"
    )

    # `_row_set_column_label` falls back to `binding.id` when the locale
    # catalogue lacks an entry for the row_field. A binding-id label would
    # surface to the operator instead of the translated header.
    for row_set in row_sets:
        for column in row_set.columns:
            assert column.header_label != column.binding, (
                f"modelo {modelo_id!r} column {column.binding!r} header label fell back to "
                f"the binding id (missing sheets.detalle.headers.<row_field> locale entry?)"
            )
            assert column.header_label.strip(), f"modelo {modelo_id!r} column {column.binding!r} has blank header label"
