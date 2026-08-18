"""End-to-end integration test for the detail-record round-trip.

Exercises the full chain in one path:
    operator-typed cells → assembler → typed observations →
    row-resolver → per-binding row-indexed values

Covers the loop without Sheets API mocking by passing real
``RowSetCellEdit`` records directly into the assembler. If
the assembler's ``row_field`` mapping or the resolver's row-builder
sort order ever drifts, the round-trip diverges and these tests
fail. The same shape an operator types in the Detalle tab survives
the trip back through the local-store ingest path.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.outbound.google import RowSetCellEdit
from ....core.resources import resources
from ....domain.calculations.registry import (
    resolve_atribucion_binding_row_values,
    resolve_foreign_asset_binding_row_values,
    resolve_refund_binding_row_values,
    resolve_related_party_binding_row_values,
    resolve_withholding_binding_row_values,
)
from .._row_set_assembly import (
    assemble_atribucion_observations,
    assemble_foreign_asset_observations,
    assemble_refund_observations,
    assemble_related_party_observations,
    assemble_withholding_observations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _modelo(modelo_id: str, revision_id: str):
    return resources().modelos.get(modelo_id).revisions[revision_id]


def test_modelo_190_perceptor_round_trip_preserves_typed_values() -> None:
    """Operator-typed perceptor rows survive assembler → resolver intact."""

    revision = _modelo("190", "2025-y-siguientes")

    # Two perceptors: one with cash + retención, one with everything.
    typed_cells = (
        RowSetCellEdit(binding="modelo-190-perceptor-row-nif", row_index=1, value="12345678A"),
        RowSetCellEdit(binding="modelo-190-perceptor-row-name", row_index=1, value="Perceptor One"),
        RowSetCellEdit(binding="modelo-190-perceptor-row-clave", row_index=1, value="A"),
        RowSetCellEdit(binding="modelo-190-perceptor-row-percibido-dinerario", row_index=1, value=Decimal("10000")),
        RowSetCellEdit(binding="modelo-190-perceptor-row-retencion-practicada", row_index=1, value=Decimal("1500")),
        RowSetCellEdit(binding="modelo-190-perceptor-row-nif", row_index=2, value="87654321Z"),
        RowSetCellEdit(binding="modelo-190-perceptor-row-name", row_index=2, value="Perceptor Two"),
        RowSetCellEdit(binding="modelo-190-perceptor-row-clave", row_index=2, value="G"),
        RowSetCellEdit(binding="modelo-190-perceptor-row-subclave", row_index=2, value="01"),
        RowSetCellEdit(binding="modelo-190-perceptor-row-percibido-dinerario", row_index=2, value=Decimal("30000")),
        RowSetCellEdit(binding="modelo-190-perceptor-row-percibido-especie", row_index=2, value=Decimal("5000")),
        RowSetCellEdit(binding="modelo-190-perceptor-row-retencion-practicada", row_index=2, value=Decimal("5500")),
        RowSetCellEdit(binding="modelo-190-perceptor-row-ingreso-a-cuenta", row_index=2, value=Decimal("750")),
    )

    observations = assemble_withholding_observations(typed_cells, revision, filing_year=2025)
    resolved = resolve_withholding_binding_row_values(revision, observations)

    # Perceptor 12345678A (clave A) sorts before 87654321Z (clave G); both
    # are domestic (country_code defaults to "ES") so the (country, NIF,
    # clave, subclave) sort puts 12345678A at row 1 and 87654321Z at row 2.
    assert resolved[("modelo-190-perceptor-row-nif", 1)] == "12345678A"
    assert resolved[("modelo-190-perceptor-row-clave", 1)] == "A"
    assert resolved[("modelo-190-perceptor-row-percibido-dinerario", 1)] == Decimal("10000")
    assert resolved[("modelo-190-perceptor-row-retencion-practicada", 1)] == Decimal("1500")

    assert resolved[("modelo-190-perceptor-row-nif", 2)] == "87654321Z"
    assert resolved[("modelo-190-perceptor-row-clave", 2)] == "G"
    assert resolved[("modelo-190-perceptor-row-subclave", 2)] == "01"
    assert resolved[("modelo-190-perceptor-row-percibido-dinerario", 2)] == Decimal("30000")
    assert resolved[("modelo-190-perceptor-row-percibido-especie", 2)] == Decimal("5000")
    assert resolved[("modelo-190-perceptor-row-retencion-practicada", 2)] == Decimal("5500")
    assert resolved[("modelo-190-perceptor-row-ingreso-a-cuenta", 2)] == Decimal("750")


def test_modelo_720_foreign_asset_round_trip_preserves_dates_and_currency() -> None:
    """Foreign asset detail rows preserve ISO dates + currency through the loop."""

    revision = _modelo("720", "2013-y-siguientes")
    typed_cells = (
        RowSetCellEdit(binding="modelo-720-asset-row-class", row_index=1, value="C"),
        RowSetCellEdit(binding="modelo-720-asset-row-country", row_index=1, value="CH"),
        RowSetCellEdit(binding="modelo-720-asset-row-currency", row_index=1, value="CHF"),
        RowSetCellEdit(binding="modelo-720-asset-row-identifier", row_index=1, value="CH-iban-001"),
        RowSetCellEdit(binding="modelo-720-asset-row-acquisition-date", row_index=1, value="2020-01-15"),
        RowSetCellEdit(binding="modelo-720-asset-row-valuation", row_index=1, value=Decimal("120000")),
    )

    observations = assemble_foreign_asset_observations(typed_cells, revision, filing_year=2025)
    resolved = resolve_foreign_asset_binding_row_values(revision, observations)

    assert resolved[("modelo-720-asset-row-class", 1)] == "C"
    assert resolved[("modelo-720-asset-row-country", 1)] == "CH"
    assert resolved[("modelo-720-asset-row-currency", 1)] == "CHF"
    assert resolved[("modelo-720-asset-row-identifier", 1)] == "CH-iban-001"
    assert resolved[("modelo-720-asset-row-acquisition-date", 1)] == "2020-01-15"
    assert resolved[("modelo-720-asset-row-valuation", 1)] == Decimal("120000")


def test_modelo_232_related_party_round_trip_preserves_operation_metadata() -> None:
    revision = _modelo("232", "2018-y-siguientes")
    typed_cells = (
        RowSetCellEdit(binding="modelo-232-related-party-row-nif", row_index=1, value="A12345678"),
        RowSetCellEdit(binding="modelo-232-related-party-row-name", row_index=1, value="Counter SL"),
        RowSetCellEdit(binding="modelo-232-related-party-row-country", row_index=1, value="ES"),
        RowSetCellEdit(binding="modelo-232-related-party-row-operation-kind", row_index=1, value="01"),
        RowSetCellEdit(binding="modelo-232-related-party-row-tpr-method", row_index=1, value="1A"),
        RowSetCellEdit(binding="modelo-232-related-party-row-amount", row_index=1, value=Decimal("50000")),
    )

    observations = assemble_related_party_observations(typed_cells, revision, filing_year=2025)
    resolved = resolve_related_party_binding_row_values(revision, observations)

    assert resolved[("modelo-232-related-party-row-nif", 1)] == "A12345678"
    assert resolved[("modelo-232-related-party-row-operation-kind", 1)] == "01"
    assert resolved[("modelo-232-related-party-row-tpr-method", 1)] == "1A"
    assert resolved[("modelo-232-related-party-row-amount", 1)] == Decimal("50000")


def test_modelo_184_atribucion_member_round_trip_preserves_share_and_base() -> None:
    revision = _modelo("184", "2015-y-siguientes")
    typed_cells = (
        RowSetCellEdit(binding="modelo-184-member-row-nif", row_index=1, value="11111111A"),
        RowSetCellEdit(binding="modelo-184-member-row-name", row_index=1, value="Member One"),
        RowSetCellEdit(binding="modelo-184-member-row-share", row_index=1, value=Decimal("60")),
        RowSetCellEdit(binding="modelo-184-member-row-base-assigned", row_index=1, value=Decimal("6000")),
        RowSetCellEdit(binding="modelo-184-member-row-nif", row_index=2, value="22222222B"),
        RowSetCellEdit(binding="modelo-184-member-row-name", row_index=2, value="Member Two"),
        RowSetCellEdit(binding="modelo-184-member-row-share", row_index=2, value=Decimal("40")),
        RowSetCellEdit(binding="modelo-184-member-row-base-assigned", row_index=2, value=Decimal("4000")),
    )

    observations = assemble_atribucion_observations(typed_cells, revision, filing_year=2025)
    resolved = resolve_atribucion_binding_row_values(revision, observations)

    # Members sort by (country_code, member_tax_id) — both domestic, so
    # 11111111A precedes 22222222B.
    assert resolved[("modelo-184-member-row-nif", 1)] == "11111111A"
    assert resolved[("modelo-184-member-row-share", 1)] == Decimal("60")
    assert resolved[("modelo-184-member-row-base-assigned", 1)] == Decimal("6000")
    assert resolved[("modelo-184-member-row-nif", 2)] == "22222222B"
    assert resolved[("modelo-184-member-row-share", 2)] == Decimal("40")


def test_modelo_360_refund_round_trip_preserves_member_state_and_dates() -> None:
    revision = _modelo("360", "2010-y-siguientes")
    typed_cells = (
        RowSetCellEdit(binding="modelo-360-refund-row-member-state", row_index=1, value="FR"),
        RowSetCellEdit(binding="modelo-360-refund-row-operation-kind", row_index=1, value="01"),
        RowSetCellEdit(binding="modelo-360-refund-row-operation-date", row_index=1, value="2025-06-15"),
        RowSetCellEdit(binding="modelo-360-refund-row-supplier-nif", row_index=1, value="FR-supplier-1"),
        RowSetCellEdit(binding="modelo-360-refund-row-amount", row_index=1, value=Decimal("500")),
        RowSetCellEdit(binding="modelo-360-refund-row-member-state", row_index=2, value="DE"),
        RowSetCellEdit(binding="modelo-360-refund-row-operation-kind", row_index=2, value="02"),
        RowSetCellEdit(binding="modelo-360-refund-row-operation-date", row_index=2, value="2025-03-01"),
        RowSetCellEdit(binding="modelo-360-refund-row-supplier-nif", row_index=2, value="DE-supplier-1"),
        RowSetCellEdit(binding="modelo-360-refund-row-amount", row_index=2, value=Decimal("750")),
    )

    observations = assemble_refund_observations(typed_cells, revision, filing_year=2025)
    resolved = resolve_refund_binding_row_values(revision, observations)

    # Refund operations sort by (member_state_code, operation_date,
    # supplier_tax_id) — DE precedes FR.
    assert resolved[("modelo-360-refund-row-member-state", 1)] == "DE"
    assert resolved[("modelo-360-refund-row-amount", 1)] == Decimal("750")
    assert resolved[("modelo-360-refund-row-member-state", 2)] == "FR"
    assert resolved[("modelo-360-refund-row-amount", 2)] == Decimal("500")
