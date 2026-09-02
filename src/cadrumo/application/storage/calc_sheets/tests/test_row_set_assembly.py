"""Fail-closed worksheet row-set ingress tests.

These use the loaded registry snapshots and the public Google pull records; no
transport or calculation boundary is replaced with a test double.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....adapters.outbound.google.calc_sheets_pull_records import RowSetCellEdit, RowSetEdit
from .....domain.calculations.registry.authority import bundled_authority
from .....domain.calculations.registry.detail_record_bindings import Modelo720RowObservation
from .....domain.calculations.registry.errors import RegistryValidationError
from ..engine import collect_row_sets
from ..row_set_assembly import assemble_row_sets_for_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _snapshot(modelo: str, *, filing_year: int, period: str):
    return bundled_authority().snapshot(modelo, filing_year=filing_year, period=period)


def _foreign_asset_cells(*, row_index: int = 1, country: str | None = "CH") -> tuple[RowSetCellEdit, ...]:
    cells = [
        RowSetCellEdit(binding="modelo-720-asset-row-class", row_index=row_index, value="C"),
        RowSetCellEdit(binding="modelo-720-asset-row-currency", row_index=row_index, value="CHF"),
        RowSetCellEdit(binding="modelo-720-asset-row-identifier", row_index=row_index, value="CH-iban-001"),
        RowSetCellEdit(binding="modelo-720-asset-row-acquisition-date", row_index=row_index, value="2020-01-15"),
        RowSetCellEdit(binding="modelo-720-asset-row-valuation", row_index=row_index, value=Decimal("120000")),
    ]
    if country is not None:
        cells.insert(1, RowSetCellEdit(binding="modelo-720-asset-row-country", row_index=row_index, value=country))
    return tuple(cells)


def test_assemble_row_sets_delegates_a_declared_row_to_snapshot_command() -> None:
    snapshot = _snapshot("720", filing_year=2025, period="0A")

    assembled = assemble_row_sets_for_snapshot(
        (RowSetEdit(grouping="per_foreign_asset", cells=_foreign_asset_cells()),),
        snapshot,
    )

    source_kind, observations = assembled[0]
    assert source_kind == "foreign_asset"
    assert observations[0].source_id == "detalle:per_foreign_asset:row-1"
    assert isinstance(observations[0], Modelo720RowObservation)
    assert observations[0].country_code == "CH"


def test_assemble_row_sets_refuses_an_unknown_field_in_a_declared_grouping() -> None:
    snapshot = _snapshot("720", filing_year=2025, period="0A")
    cells = (*_foreign_asset_cells(), RowSetCellEdit(binding="unknown-row-field", row_index=1, value="x"))

    with pytest.raises(RegistryValidationError) as exc_info:
        assemble_row_sets_for_snapshot((RowSetEdit(grouping="per_foreign_asset", cells=cells),), snapshot)

    assert str(exc_info.value) == "application.calculations.row_set.errors.row_assembly_failed"
    assert exc_info.value.context == {
        "row_index": 1,
        "validation_error_type": "row_set_ingress",
        "validation_error_detail": "unknown_field",
        "grouping": "per_foreign_asset",
        "binding_id": "unknown-row-field",
    }


def test_assemble_row_sets_refuses_an_undeclared_grouping_before_s87() -> None:
    snapshot = _snapshot("720", filing_year=2025, period="0A")

    with pytest.raises(RegistryValidationError) as exc_info:
        assemble_row_sets_for_snapshot(
            (RowSetEdit(grouping="not-a-registry-grouping", cells=_foreign_asset_cells()),),
            snapshot,
        )

    assert str(exc_info.value) == "application.calculations.row_set.errors.row_assembly_failed"
    assert exc_info.value.context == {
        "row_index": 1,
        "validation_error_type": "row_set_ingress",
        "validation_error_detail": "undeclared_grouping",
        "grouping": "not-a-registry-grouping",
    }


def test_assemble_row_sets_refuses_duplicate_cell_coordinate_before_s87() -> None:
    snapshot = _snapshot("720", filing_year=2025, period="0A")
    duplicate = RowSetCellEdit(binding="modelo-720-asset-row-class", row_index=1, value="C")

    with pytest.raises(RegistryValidationError) as exc_info:
        assemble_row_sets_for_snapshot(
            (RowSetEdit(grouping="per_foreign_asset", cells=(duplicate, duplicate)),),
            snapshot,
        )

    assert str(exc_info.value) == "application.calculations.row_set.errors.row_assembly_failed"
    assert exc_info.value.context == {
        "row_index": 1,
        "validation_error_type": "row_set_ingress",
        "validation_error_detail": "duplicate_cell_coordinate",
        "grouping": "per_foreign_asset",
        "binding_id": "modelo-720-asset-row-class",
    }


def test_assemble_row_sets_refuses_a_binding_substituted_from_another_grouping() -> None:
    snapshot = _snapshot("349", filing_year=2025, period="1T")
    first_grouping, second_grouping = collect_row_sets(snapshot.revision)
    substituted_binding = str(second_grouping.columns[0].binding)

    with pytest.raises(RegistryValidationError) as exc_info:
        assemble_row_sets_for_snapshot(
            (
                RowSetEdit(
                    grouping=first_grouping.grouping,
                    cells=(RowSetCellEdit(binding=substituted_binding, row_index=1, value="DE"),),
                ),
            ),
            snapshot,
        )

    assert str(exc_info.value) == "application.calculations.row_set.errors.row_assembly_failed"
    assert (exc_info.value.context or {})["validation_error_detail"] == "caller_binding_substitution"
    assert (exc_info.value.context or {})["declared_grouping"] == second_grouping.grouping


def test_assemble_row_sets_refuses_two_blocks_claiming_the_same_row() -> None:
    snapshot = _snapshot("720", filing_year=2025, period="0A")
    first = RowSetEdit(
        grouping="per_foreign_asset",
        cells=(RowSetCellEdit(binding="modelo-720-asset-row-class", row_index=1, value="C"),),
    )
    second = RowSetEdit(
        grouping="per_foreign_asset",
        cells=(RowSetCellEdit(binding="modelo-720-asset-row-country", row_index=1, value="CH"),),
    )

    with pytest.raises(RegistryValidationError) as exc_info:
        assemble_row_sets_for_snapshot((first, second), snapshot)

    assert str(exc_info.value) == "application.calculations.row_set.errors.row_assembly_failed"
    assert (exc_info.value.context or {})["validation_error_detail"] == "row_ownership_collision"
    assert (exc_info.value.context or {})["first_row_set_index"] == 0
    assert (exc_info.value.context or {})["second_row_set_index"] == 1


def test_assemble_row_sets_preserves_s87_sparse_row_refusal() -> None:
    snapshot = _snapshot("720", filing_year=2025, period="0A")

    with pytest.raises(RegistryValidationError) as exc_info:
        assemble_row_sets_for_snapshot(
            (RowSetEdit(grouping="per_foreign_asset", cells=_foreign_asset_cells(country=None)),),
            snapshot,
        )

    assert str(exc_info.value) == "application.calculations.row_set.errors.row_assembly_failed"
    assert "country_code" in str((exc_info.value.context or {})["validation_error_detail"])
