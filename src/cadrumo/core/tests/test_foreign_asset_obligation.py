"""Structural tests for the opaque foreign-asset obligation-group token."""

from __future__ import annotations

import pytest

from ..foreign_asset_obligation import ForeignAssetObligationGroup

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_registry_projection_creates_an_opaque_group_token() -> None:
    token = ForeignAssetObligationGroup.from_registry("cuentas")

    assert isinstance(token, ForeignAssetObligationGroup)
    assert token.value == "cuentas"
    assert token.name == "cuentas"


def test_group_token_cannot_be_constructed_without_registry_projection() -> None:
    with pytest.raises(TypeError, match="projected from the facts registry"):
        ForeignAssetObligationGroup("cuentas")
