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
from pathlib import Path

import pytest

from cadrumo.core.foreign_asset_obligation import M720AssetClassCode
from cadrumo.domain.calculations.registry.binding_targets import BindingConsumerKind, binding_consumers
from cadrumo.domain.calculations.registry.detail_record_bindings import (
    AtributionMemberObservation,
    Modelo720RowObservation,
    Modelo720ValuedRow,
    resolve_atribucion_binding_row_values,
    resolve_foreign_asset_binding_row_values,
)
from cadrumo.domain.currency.service import CurrencyNormalizationService
from cadrumo.domain.foreign_assets.record_join import Modelo720Record
from cadrumo.domain.foreign_assets.register import (
    ForeignAssetDeclarationEntry,
    ForeignAssetRegisterEntry,
    M720AssetIdentifier,
    M720DeclarantCondition,
    M720IdentifierScheme,
)
from cadrumo.domain.foreign_assets.valuation import M720ValuationEvent

from ..compiler.loader import load_modelo_directory
from ..conformance.registry_schema_support import committed_registry_tree as _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelos():
    modelos, _catalogues = _committed_registry_tree()
    return modelos


def _modelo720_revision():
    root = Path(__file__).resolve().parents[3]
    return load_modelo_directory(root / "src/cadrumo/_data/registry/aeat/modelos/720").revisions["2013-y-siguientes"]


def _valued(
    source_id: str,
    asset_class: M720AssetClassCode,
    country: str,
    identifier: str,
    acquired: date,
    valuation: str,
) -> Modelo720Record:
    observation = Modelo720RowObservation(
        source_id=source_id,
        asset_ref="m720a_" + source_id.encode().hex().ljust(32, "0"),
        asset_class_code=asset_class,
        country_code=country,
        currency_code="EUR",
        asset_identifier=identifier,
        acquisition_date=acquired,
        valuation_amount=Decimal(valuation),
        valuation_event=M720ValuationEvent.YEAR_END,
    )
    valuation_eur = CurrencyNormalizationService().normalize(observation.native_amount, date(2025, 12, 31))
    return Modelo720Record(
        row=Modelo720ValuedRow(observation=observation, valuation=valuation_eur),
        asset=ForeignAssetRegisterEntry(
            asset_ref=observation.asset_ref,
            asset_class=asset_class,
            subclave=1,
            country_code=country,
            identifier=M720AssetIdentifier(
                scheme=(
                    M720IdentifierScheme.ACCOUNT_CODE
                    if asset_class is M720AssetClassCode.CUENTA
                    else M720IdentifierScheme.NO_ISIN_ISSUER_COUNTRY
                ),
                value=identifier,
            ),
            description="synthetic asset",
            held_since=date(2015, 1, 1),
        ),
        declaration=ForeignAssetDeclarationEntry(
            asset_ref=observation.asset_ref,
            condition=M720DeclarantCondition.TITULAR,
            participation_pct=Decimal("100.00"),
        ),
    )


def test_build_foreign_asset_rows_sorts_by_country_class_identifier_date() -> None:
    revision = _modelo720_revision()
    rows = (
        _valued("a1", M720AssetClassCode.CUENTA, "DE", "DE-bank-001", date(2022, 6, 1), "60000"),
        _valued("a2", M720AssetClassCode.VALOR, "CH", "ZCH", date(2020, 1, 1), "120000"),
        _valued("a3", M720AssetClassCode.CUENTA, "CH", "CH-bank-001", date(2021, 3, 15), "80000"),
    )

    resolved = resolve_foreign_asset_binding_row_values(revision, rows)

    # Sort key: (country_code, asset_class_code, asset_identifier, acquisition_date, asset_ref)
    assert [resolved[("modelo-720-asset-row-country", index)] for index in (1, 2, 3)] == ["CH", "CH", "DE"]
    assert [resolved[("modelo-720-asset-row-class", index)] for index in (1, 2, 3)] == ["C", "V", "C"]


def test_resolve_foreign_asset_binding_row_values_emits_per_column_indexed_values() -> None:
    revision = _modelo720_revision()
    rows = (_valued("a1", M720AssetClassCode.CUENTA, "CH", "CH-iban-001", date(2020, 1, 1), "120000"),)

    resolved = resolve_foreign_asset_binding_row_values(revision, rows)

    # The per-row mapping covers every foreign-asset column modelo 720 declares.
    declared = {binding.id for binding in revision.bindings if binding.source == "foreign_asset"}
    assert {key[0] for key in resolved if key[1] == 1} == declared
    consumers = binding_consumers(revision)
    assert all(
        any(ref.kind is BindingConsumerKind.APPLICATION_ROW_VALUE for ref in consumers[binding_id])
        for binding_id in declared
    )
    assert all(
        not any(ref.kind is BindingConsumerKind.APPLICATION_ROW_VALUE for ref in consumers[binding.id])
        for binding in revision.bindings
        if binding.source != "foreign_asset"
    )
    assert resolved[("modelo-720-asset-row-country", 1)] == "CH"
    assert resolved[("modelo-720-asset-row-valuation", 1)] == Decimal("120000")
    assert resolved[("modelo-720-asset-row-currency", 1)] == "EUR"
    assert resolved[("modelo-720-asset-row-valuation-event", 1)] == "year_end"


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
            clave="D",
        ),
        AtributionMemberObservation(
            source_id="m1",
            member_tax_id="12345678A",
            member_legal_name="One",
            country_code="ES",
            transaction_date=date(2025, 1, 1),
            share_percentage=Decimal("40"),
            base_imponible_assigned=Decimal("4000"),
            clave="D",
        ),
    )

    resolved = resolve_atribucion_binding_row_values(revision, obs)

    # Sort by (country_code, member_tax_id) → 12345678A before 87654321Z
    assert resolved[("modelo-184-member-row-nif", 1)] == "12345678A"
    assert resolved[("modelo-184-member-row-nif", 2)] == "87654321Z"
    assert resolved[("modelo-184-member-row-base-assigned", 1)] == Decimal("4000")
    assert resolved[("modelo-184-member-row-share", 2)] == Decimal("60")
