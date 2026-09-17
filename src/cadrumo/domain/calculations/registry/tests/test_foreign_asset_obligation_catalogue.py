"""Tests for the registry-owned foreign-asset obligation taxonomy."""

from __future__ import annotations

import pytest

from .....core.aggregation import ForeignAssetClass
from .....core.foreign_asset_obligation import MODELO_720_FOREIGN_ASSET_CLASS_CODES
from ..foreign_asset_obligation_catalogue import resolve_foreign_asset_obligation_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


class TestObligationGroupMapping:
    def test_every_asset_class_maps_to_a_group(self) -> None:
        """The registry projection maps every asset class to a declared group."""
        catalogue = resolve_foreign_asset_obligation_catalogue()
        mapped = {catalogue.group_for_asset_class(asset_class) for asset_class in ForeignAssetClass}
        assert mapped == set(catalogue.group_choices)

    def test_account_maps_to_cuentas(self) -> None:
        assert (
            resolve_foreign_asset_obligation_catalogue().group_for_asset_class(ForeignAssetClass.ACCOUNT).value
            == "cuentas"
        )

    def test_real_estate_maps_to_inmuebles(self) -> None:
        assert (
            resolve_foreign_asset_obligation_catalogue().group_for_asset_class(ForeignAssetClass.REAL_ESTATE).value
            == "inmuebles"
        )

    def test_iic_maps_to_valores_bloque(self) -> None:
        assert (
            resolve_foreign_asset_obligation_catalogue()
            .group_for_asset_class(ForeignAssetClass.COLLECTIVE_INVESTMENT)
            .value
            == "valores_derechos_seguros"
        )

    def test_virtual_currency_maps_to_monedas_virtuales(self) -> None:
        assert (
            resolve_foreign_asset_obligation_catalogue().group_for_asset_class(ForeignAssetClass.VIRTUAL_CURRENCY).value
            == "monedas_virtuales"
        )

    def test_security_and_insurance_share_the_valores_bloque(self) -> None:
        """RD 1065/2007 art. 42 ter is one bloque covering valores AND seguros."""
        assert (
            resolve_foreign_asset_obligation_catalogue().group_for_asset_class(ForeignAssetClass.SECURITY).value
            == "valores_derechos_seguros"
        )
        assert (
            resolve_foreign_asset_obligation_catalogue()
            .group_for_asset_class(ForeignAssetClass.COLLECTIVE_INVESTMENT)
            .value
            == "valores_derechos_seguros"
        )
        assert (
            resolve_foreign_asset_obligation_catalogue().group_for_asset_class(ForeignAssetClass.INSURANCE).value
            == "valores_derechos_seguros"
        )

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
