"""Tests for the Modelo 720 / 721 foreign-asset obligation-group semantic layer.

These assert the typed abstraction (obligation bloque per clave, grounded
thresholds) maps correctly and is grounded in the RD 1065/2007 articles the
legal registry already defines. They do not exercise the M720 aggregation or
its per-obligation-block declarability gate; those live in the application layer.
"""

from __future__ import annotations

import pytest

from ..aggregation import ForeignAssetClass
from ..foreign_asset_obligation import (
    FOREIGN_ASSET_CLASS_OBLIGATION_GROUP,
    MODELO_720_FOREIGN_ASSET_CLASS_CODES,
    ForeignAssetObligationGroup,
    foreign_asset_obligation_group,
)

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
