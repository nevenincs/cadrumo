"""Contract test for `collect_row_sets`.

Exercises the engine-side helper that walks a `ModeloRevision`'s
row-producer bindings and emits per-grouping `SheetRowSet` records.
The pull adapter relies on this helper to compute the same row-set
layout the engine emitted, so the contract has to hold across
modelo 349 (the canonical row-producer modelo, with 13 bindings
split into operator_clave + operator_clave_period groupings).
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from .....core import BindingSourceKind
from .....core.aggregation import BindingAggregation, BindingAggregationOp
from .....domain.calculations.registry.authority import bundled_authority
from .....domain.calculations.registry.errors import RegistryValidationError
from .....domain.calculations.registry.schema import DataBindingDefinition
from .. import collect_row_sets

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _modelo_349_revision():
    return bundled_authority().modelo("349").revisions["2020-y-siguientes"]


def test_collect_row_sets_groups_modelo_349_bindings_by_grouping() -> None:
    revision = _modelo_349_revision()

    row_sets = collect_row_sets(revision)

    by_grouping = {rs.grouping: rs for rs in row_sets}
    assert "operator_clave" in by_grouping
    assert "operator_clave_period" in by_grouping
    assert len(by_grouping["operator_clave"].columns) == 5
    assert len(by_grouping["operator_clave_period"].columns) == 8
    for row_set in row_sets:
        assert row_set.legal_refs
        assert row_set.source_refs
        assert all(column.legal_refs for column in row_set.columns)


def test_collect_row_sets_suppresses_payable_acquisition_mirror_rows() -> None:
    revision = _modelo_349_revision()

    row_sets = collect_row_sets(revision)

    column_bindings = {str(column.binding) for row_set in row_sets for column in row_set.columns}
    assert "iva-349-operador-row-base" in column_bindings
    assert "iva-349-rectificacion-row-base-anterior" in column_bindings
    assert not any(binding_id.endswith("-adquisicion") for binding_id in column_bindings)


def test_collect_row_sets_assigns_distinct_header_rows_per_grouping() -> None:
    """Each grouping occupies a contiguous block; blocks stack vertically."""

    revision = _modelo_349_revision()

    row_sets = collect_row_sets(revision)

    header_rows = [rs.header_row for rs in row_sets]
    assert len(set(header_rows)) == len(row_sets), "row-sets must occupy distinct header rows"
    for prev, current in pairwise(sorted(header_rows)):
        assert current > prev, "header rows must be monotonically increasing"


def test_collect_row_sets_first_data_row_immediately_follows_header() -> None:
    revision = _modelo_349_revision()

    for rs in collect_row_sets(revision):
        assert rs.first_data_row == rs.header_row + 1


def test_collect_row_sets_columns_allocate_a_through_n_left_to_right() -> None:
    revision = _modelo_349_revision()

    for rs in collect_row_sets(revision):
        for column_index, column in enumerate(rs.columns, start=1):
            assert column.header_address.column == column_index, (
                f"row-set {rs.grouping!r} column {column.binding!r} expected column "
                f"index {column_index}, got {column.header_address.column}"
            )


def test_collect_row_sets_returns_empty_for_revision_without_row_producers() -> None:
    """Modelos without any `aggregation.op = "rows"` bindings emit no row-sets."""

    # Modelo 130 (IRPF pago fraccionado) has no row-producer bindings.
    revision = bundled_authority().modelo("130").revisions["2019-y-siguientes"]

    assert collect_row_sets(revision) == ()


def test_collect_row_sets_rejects_rows_binding_without_row_set_projection() -> None:
    revision = bundled_authority().modelo("130").revisions["2019-y-siguientes"]
    malformed_row_binding = DataBindingDefinition(
        id="synthetic-row-without-grouping",
        source=BindingSourceKind.COLLECTIBLE_INVOICE,
        selector={"fact": "row_field", "row_field": "country_code"},
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        legal_refs=("ley-37-1992:art-1",),
        source_refs=("aeat-dr-349",),
    )
    revision_with_malformed_row = revision.model_copy(update={"bindings": (malformed_row_binding,)})

    with pytest.raises(RegistryValidationError, match="missing grouping"):
        collect_row_sets(revision_with_malformed_row)
