"""Tests for the Modelo 720 / 721 foreign-asset obligation-group semantic layer.

These assert the typed abstraction (obligation bloque per clave, grounded
thresholds) maps correctly and is grounded in the RD 1065/2007 articles the
legal registry already defines. They do not exercise the M720 aggregation or
its per-obligation-block declarability gate; those live in the application layer.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from .._foreign_asset_obligation import (
    FOREIGN_ASSET_CLASS_OBLIGATION_GROUP,
    FOREIGN_ASSET_DECLARATION_THRESHOLDS,
    MODELO_720_FOREIGN_ASSET_CLASS_CODES,
    MODELO_720_REDECLARATION_INCREASE_THRESHOLD_EUR,
    ForeignAssetDeclarationThreshold,
    ForeignAssetObligationGroup,
    foreign_asset_class_declaration_threshold,
    foreign_asset_declaration_threshold,
    foreign_asset_obligation_group,
)
from ..aggregation import ForeignAssetClass
from ..external_constants import MODELO_720_REPORTING_THRESHOLD_EUR

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class TestObligationGroupMapping:
    def test_every_asset_class_maps_to_a_group(self) -> None:
        """The clave -> bloque map is total: no ForeignAssetClass is unmapped."""
        assert set(FOREIGN_ASSET_CLASS_OBLIGATION_GROUP) == set(ForeignAssetClass)

    def test_account_maps_to_cuentas(self) -> None:
        assert foreign_asset_obligation_group(ForeignAssetClass.ACCOUNT) is ForeignAssetObligationGroup.CUENTAS

    def test_real_estate_maps_to_inmuebles(self) -> None:
        assert foreign_asset_obligation_group(ForeignAssetClass.REAL_ESTATE) is ForeignAssetObligationGroup.INMUEBLES

    def test_iic_maps_to_valores_bloque(self) -> None:
        assert (
            foreign_asset_obligation_group(ForeignAssetClass.COLLECTIVE_INVESTMENT)
            is ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS
        )

    def test_virtual_currency_maps_to_monedas_virtuales(self) -> None:
        assert (
            foreign_asset_obligation_group(ForeignAssetClass.VIRTUAL_CURRENCY)
            is ForeignAssetObligationGroup.MONEDAS_VIRTUALES
        )

    def test_security_and_insurance_share_the_valores_bloque(self) -> None:
        """RD 1065/2007 art. 42 ter is one bloque covering valores AND seguros."""
        assert (
            foreign_asset_obligation_group(ForeignAssetClass.SECURITY)
            is ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS
        )
        assert (
            foreign_asset_obligation_group(ForeignAssetClass.COLLECTIVE_INVESTMENT)
            is ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS
        )
        assert (
            foreign_asset_obligation_group(ForeignAssetClass.INSURANCE)
            is ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS
        )

    def test_class_level_threshold_composes_group_threshold(self) -> None:
        for asset_class in ForeignAssetClass:
            group = foreign_asset_obligation_group(asset_class)
            assert foreign_asset_class_declaration_threshold(asset_class) == foreign_asset_declaration_threshold(group)

    def test_modelo_720_class_codes_match_official_record_design(self) -> None:
        assert dict(MODELO_720_FOREIGN_ASSET_CLASS_CODES) == {
            ForeignAssetClass.ACCOUNT: "C",
            ForeignAssetClass.SECURITY: "V",
            ForeignAssetClass.COLLECTIVE_INVESTMENT: "I",
            ForeignAssetClass.INSURANCE: "S",
            ForeignAssetClass.REAL_ESTATE: "B",
        }

    def test_modelo_720_class_codes_exclude_modelo_721_virtual_currency(self) -> None:
        assert ForeignAssetClass.VIRTUAL_CURRENCY not in MODELO_720_FOREIGN_ASSET_CLASS_CODES


class TestDeclarationThresholds:
    def test_every_group_has_a_threshold(self) -> None:
        assert set(FOREIGN_ASSET_DECLARATION_THRESHOLDS) == set(ForeignAssetObligationGroup)

    def test_initial_floor_is_the_canonical_50000(self) -> None:
        """The initial floor equals the single canonical 50.000 EUR authority."""
        assert Decimal("50000.00") == MODELO_720_REPORTING_THRESHOLD_EUR
        for threshold in FOREIGN_ASSET_DECLARATION_THRESHOLDS.values():
            assert threshold.initial_declaration_floor_eur == MODELO_720_REPORTING_THRESHOLD_EUR

    def test_redeclaration_delta_is_20000(self) -> None:
        assert Decimal("20000.00") == MODELO_720_REDECLARATION_INCREASE_THRESHOLD_EUR
        for threshold in FOREIGN_ASSET_DECLARATION_THRESHOLDS.values():
            assert threshold.redeclaration_increase_delta_eur == MODELO_720_REDECLARATION_INCREASE_THRESHOLD_EUR

    def test_every_group_binds_its_rgat_article(self) -> None:
        """Each bloque cites the RD 1065/2007 article that establishes it."""
        expected_binding_article = {
            ForeignAssetObligationGroup.CUENTAS: "rd-1065-2007:art-42-bis",
            ForeignAssetObligationGroup.VALORES_DERECHOS_SEGUROS: "rd-1065-2007:art-42-ter",
            ForeignAssetObligationGroup.INMUEBLES: "rd-1065-2007:art-54-bis",
            ForeignAssetObligationGroup.MONEDAS_VIRTUALES: "rd-1065-2007:art-42-quater",
        }
        for group, article in expected_binding_article.items():
            assert article in foreign_asset_declaration_threshold(group).legal_refs

    def test_legal_refs_resolve_against_the_legal_registry(self) -> None:
        """Every cited legal ref is defined in the bundled legal authoring tree."""
        legal_dir = Path(__file__).resolve().parents[2] / "_data" / "registry" / "aeat" / "legal"
        corpus = "\n".join(path.read_text(encoding="utf-8") for path in legal_dir.glob("*.toml"))
        for threshold in FOREIGN_ASSET_DECLARATION_THRESHOLDS.values():
            for ref in threshold.legal_refs:
                assert f'"{ref}"' in corpus, f"legal ref {ref} is not defined in the legal registry"

    def test_threshold_model_is_frozen(self) -> None:
        from pydantic import ValidationError

        threshold = foreign_asset_declaration_threshold(ForeignAssetObligationGroup.CUENTAS)
        with pytest.raises(ValidationError):
            threshold.initial_declaration_floor_eur = Decimal("1")  # type: ignore[misc]

    def test_threshold_rejects_non_positive_floor(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ForeignAssetDeclarationThreshold(
                group=ForeignAssetObligationGroup.CUENTAS,
                initial_declaration_floor_eur=Decimal("0"),
                redeclaration_increase_delta_eur=Decimal("20000.00"),
                legal_refs=("rd-1065-2007:art-42-bis",),
            )

    def test_threshold_rejects_empty_legal_refs(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ForeignAssetDeclarationThreshold(
                group=ForeignAssetObligationGroup.CUENTAS,
                initial_declaration_floor_eur=MODELO_720_REPORTING_THRESHOLD_EUR,
                redeclaration_increase_delta_eur=MODELO_720_REDECLARATION_INCREASE_THRESHOLD_EUR,
                legal_refs=(),
            )
