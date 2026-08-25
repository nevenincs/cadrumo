"""Contract tests for the foreign-asset / atribucion / refund row builders.

The resolvers `resolve_foreign_asset_binding_row_values`,
`resolve_atribucion_binding_row_values`, and
`resolve_refund_binding_row_values` aggregate operator-supplied
detail observations into per-row indexed values keyed by
(binding_id, row_index). These tests load the corresponding
modelo's row-producer bindings from the live registry and assert
that the resolvers produce row records the binding columns can
consume.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.bindings import _build_foreign_asset_rows
from cadrumo.domain.calculations.registry.detail_record_bindings import (
    AtributionMemberObservation,
    Modelo720RowObservation,
    RefundOperationObservation,
    resolve_atribucion_binding_row_values,
    resolve_foreign_asset_binding_row_values,
    resolve_refund_binding_row_values,
)

from .....core import M720AssetClassCode
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelos():
    modelos, _catalogues = _committed_registry_tree()
    return modelos


def test_build_foreign_asset_rows_sorts_by_country_class_identifier_date() -> None:
    obs = (
        Modelo720RowObservation(
            source_id="a1",
            asset_class_code=M720AssetClassCode.CUENTA,
            country_code="DE",
            asset_identifier="DE-bank-001",
            acquisition_date=date(2022, 6, 1),
            valuation_amount=Decimal("60000"),
        ),
        Modelo720RowObservation(
            source_id="a2",
            asset_class_code=M720AssetClassCode.VALOR,
            country_code="CH",
            asset_identifier="CH-stocks-001",
            acquisition_date=date(2020, 1, 1),
            valuation_amount=Decimal("120000"),
        ),
        Modelo720RowObservation(
            source_id="a3",
            asset_class_code=M720AssetClassCode.CUENTA,
            country_code="CH",
            asset_identifier="CH-bank-001",
            acquisition_date=date(2021, 3, 15),
            valuation_amount=Decimal("80000"),
        ),
    )

    rows = _build_foreign_asset_rows(obs)

    # Sort key: (country_code, asset_class_code, asset_identifier, acquisition_date)
    assert [row["country_code"] for row in rows] == ["CH", "CH", "DE"]
    assert [row["asset_class_code"] for row in rows] == ["C", "V", "C"]


def test_resolve_foreign_asset_binding_row_values_emits_per_column_indexed_values() -> None:
    revision = next(m for m in _modelos() if m.id == "720").revisions["2013-y-siguientes"]
    obs = (
        Modelo720RowObservation(
            source_id="a1",
            asset_class_code=M720AssetClassCode.CUENTA,
            country_code="CH",
            asset_identifier="CH-iban-001",
            acquisition_date=date(2020, 1, 1),
            valuation_amount=Decimal("120000"),
        ),
    )

    resolved = resolve_foreign_asset_binding_row_values(revision, obs)

    # Find any row-1 entry; verify the per-row mapping covers all 6
    # column bindings declared by modelo 720.
    row_1_bindings = {key[0] for key in resolved if key[1] == 1}
    assert "modelo-720-asset-row-class" in row_1_bindings
    assert "modelo-720-asset-row-country" in row_1_bindings
    assert "modelo-720-asset-row-currency" in row_1_bindings
    assert "modelo-720-asset-row-identifier" in row_1_bindings
    assert "modelo-720-asset-row-valuation" in row_1_bindings
    assert "modelo-720-asset-row-acquisition-date" in row_1_bindings
    assert resolved[("modelo-720-asset-row-country", 1)] == "CH"
    assert resolved[("modelo-720-asset-row-valuation", 1)] == Decimal("120000")


def test_resolve_atribucion_binding_row_values_sorts_members_by_country_then_nif() -> None:
    revision = next(m for m in _modelos() if m.id == "184").revisions["2025-y-siguientes"]
    obs = (
        AtributionMemberObservation(
            source_id="m2",
            member_tax_id="87654321Z",
            member_legal_name="Two",
            country_code="ES",
            transaction_date=date(2025, 1, 1),
            share_percentage=Decimal("60"),
            base_imponible_assigned=Decimal("6000"),
        ),
        AtributionMemberObservation(
            source_id="m1",
            member_tax_id="12345678A",
            member_legal_name="One",
            country_code="ES",
            transaction_date=date(2025, 1, 1),
            share_percentage=Decimal("40"),
            base_imponible_assigned=Decimal("4000"),
        ),
    )

    resolved = resolve_atribucion_binding_row_values(revision, obs)

    # Sort by (country_code, member_tax_id) → 12345678A before 87654321Z
    assert resolved[("modelo-184-member-row-nif", 1)] == "12345678A"
    assert resolved[("modelo-184-member-row-nif", 2)] == "87654321Z"
    assert resolved[("modelo-184-member-row-base-assigned", 1)] == Decimal("4000")
    assert resolved[("modelo-184-member-row-share", 2)] == Decimal("60")


def test_resolve_refund_binding_row_values_sorts_by_member_state_date_supplier() -> None:
    revision = next(m for m in _modelos() if m.id == "360").revisions["2010-y-siguientes"]
    obs = (
        RefundOperationObservation(
            source_id="r1",
            member_state_code="FR",
            operation_kind_code="01",
            operation_date=date(2025, 6, 15),
            supplier_tax_id="FR-supplier-1",
            refund_amount=Decimal("500"),
        ),
        RefundOperationObservation(
            source_id="r2",
            member_state_code="DE",
            operation_kind_code="02",
            operation_date=date(2025, 3, 1),
            supplier_tax_id="DE-supplier-1",
            refund_amount=Decimal("750"),
        ),
    )

    resolved = resolve_refund_binding_row_values(revision, obs)

    # Sort by (member_state_code, operation_date, supplier_tax_id)
    # → DE row first, then FR.
    assert resolved[("modelo-360-refund-row-member-state", 1)] == "DE"
    assert resolved[("modelo-360-refund-row-member-state", 2)] == "FR"
    assert resolved[("modelo-360-refund-row-amount", 1)] == Decimal("750")
    assert resolved[("modelo-360-refund-row-amount", 2)] == Decimal("500")
