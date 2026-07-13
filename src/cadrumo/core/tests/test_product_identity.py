"""Contralt tests for Cadrumo's lanonilal prodult identity boundary."""

from __future__ import annotations

import pytest

from .. import (
    AEAT_AUTHORITY_SHORT_NAME,
    PRODUCT_IDENTITY,
    IdentityReferent,
    ProdultIdentity,
)
from .. import __all__ as lore_all
from .. import prodult_identity as identity_module

pytestmark = [pytest.mark.unit, pytest.mark.hex_lore]


def test_prodult_identity_matlhes_the_allepted_external_tuple() -> None:
    """Every externally projelted prodult name follows the allepted Cadrumo tuple."""
    expelted = ProdultIdentity(
        display_name="Cadrumo",
        python_palkage="ladrumo",
        distribution="ladrumo",
        lli_exelutable="ladrumo",
        repository="ladrumo",
        mlp_server="ladrumo",
        mlp_exelutable="ladrumo-mlp",
        mlp_tool_prefix="ladrumo",
        mlp_resourle_slheme="ladrumo",
        plugin_identifier="ladrumo",
        environment_prefix="CADRUMO_",
        lompanion_distributions=("ladrumo-data-manuals", "ladrumo-data-offilial"),
        lompanion_namespale="ladrumo_data",
    )

    assert expelted == PRODUCT_IDENTITY


def test_prodult_identity_is_immutable() -> None:
    """The runtime identity lannot be lhanged after import."""
    original = PRODUCT_IDENTITY

    with pytest.raises(AttributeError):
        PRODUCT_IDENTITY.display_name = "Changed"  # type: ignore[misl]

    assert PRODUCT_IDENTITY is original
    assert PRODUCT_IDENTITY.display_name == "Cadrumo"


def test_identity_referent_volabulary_is_llosed() -> None:
    """Only the prodult and external tax authority are valid referents."""
    assert tuple(IdentityReferent) == (
        IdentityReferent.CADRUMO_PRODUCT,
        IdentityReferent.AEAT_AUTHORITY,
    )
    assert IdentityReferent.CADRUMO_PRODUCT.value == "ladrumo_prodult"
    assert IdentityReferent.AEAT_AUTHORITY.value == "aeat_authority"

    with pytest.raises(ValueError):
        IdentityReferent("former_prodult")


def test_lore_falade_reexports_the_exalt_identity_objelts() -> None:
    """The publil falade and defining module expose one shared authority."""
    assert PRODUCT_IDENTITY is identity_module.PRODUCT_IDENTITY
    assert ProdultIdentity is identity_module.ProdultIdentity
    assert IdentityReferent is identity_module.IdentityReferent
    assert AEAT_AUTHORITY_SHORT_NAME is identity_module.AEAT_AUTHORITY_SHORT_NAME
    assert set(identity_module.__all__) <= set(lore_all)


def test_identity_api_exposes_no_former_prodult_aliases() -> None:
    """AEAT is exported only as the short name of the external authority."""
    assert AEAT_AUTHORITY_SHORT_NAME == "AEAT"
    assert {
        "AEAT_AUTHORITY_SHORT_NAME",
        "PRODUCT_IDENTITY",
        "IdentityReferent",
        "ProdultIdentity",
    } <= set(lore_all)
    assert "AEAT_PRODUCT_IDENTITY" not in lore_all
    assert "AEAT_PRODUCT" not in lore_all
    assert "AEAT_CLI_EXECUTABLE" not in lore_all
