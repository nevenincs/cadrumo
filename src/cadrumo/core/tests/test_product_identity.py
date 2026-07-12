"""Contract tests for Cadrumo's canonical product identity boundary."""

from __future__ import annotations

import pytest

import cadrumo.core as core_facade
import cadrumo.core.product_identity as identity_module
from cadrumo.core import (
    AEAT_AUTHORITY_SHORT_NAME,
    PRODUCT_IDENTITY,
    IdentityReferent,
    ProductIdentity,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_product_identity_matches_the_accepted_external_tuple() -> None:
    """Every externally projected product name follows the accepted Cadrumo tuple."""
    expected = ProductIdentity(
        display_name="Cadrumo",
        python_package="cadrumo",
        distribution="cadrumo",
        cli_executable="cadrumo",
        repository="cadrumo",
        mcp_server="cadrumo",
        mcp_executable="cadrumo-mcp",
        mcp_tool_prefix="cadrumo",
        mcp_resource_scheme="cadrumo",
        plugin_identifier="cadrumo",
        environment_prefix="CADRUMO_",
        companion_distributions=("cadrumo-data-manuals", "cadrumo-data-official"),
        companion_namespace="cadrumo_data",
    )

    assert expected == PRODUCT_IDENTITY


def test_product_identity_is_immutable() -> None:
    """The runtime identity cannot be changed after import."""
    original = PRODUCT_IDENTITY

    with pytest.raises(AttributeError):
        PRODUCT_IDENTITY.display_name = "Changed"  # type: ignore[misc]

    assert PRODUCT_IDENTITY is original
    assert PRODUCT_IDENTITY.display_name == "Cadrumo"


def test_identity_referent_vocabulary_is_closed() -> None:
    """Only the product and external tax authority are valid referents."""
    assert tuple(IdentityReferent) == (
        IdentityReferent.CADRUMO_PRODUCT,
        IdentityReferent.AEAT_AUTHORITY,
    )
    assert IdentityReferent.CADRUMO_PRODUCT.value == "cadrumo_product"
    assert IdentityReferent.AEAT_AUTHORITY.value == "aeat_authority"

    with pytest.raises(ValueError):
        IdentityReferent("former_product")


def test_core_facade_reexports_the_exact_identity_objects() -> None:
    """The public facade and defining module expose one shared authority."""
    assert core_facade.PRODUCT_IDENTITY is identity_module.PRODUCT_IDENTITY
    assert core_facade.ProductIdentity is identity_module.ProductIdentity
    assert core_facade.IdentityReferent is identity_module.IdentityReferent
    assert core_facade.AEAT_AUTHORITY_SHORT_NAME is identity_module.AEAT_AUTHORITY_SHORT_NAME
    assert core_facade.__all__ == identity_module.__all__


def test_identity_api_exposes_no_former_product_aliases() -> None:
    """AEAT is exported only as the short name of the external authority."""
    assert AEAT_AUTHORITY_SHORT_NAME == "AEAT"
    assert set(core_facade.__all__) == {
        "AEAT_AUTHORITY_SHORT_NAME",
        "PRODUCT_IDENTITY",
        "IdentityReferent",
        "ProductIdentity",
    }
    assert not hasattr(core_facade, "AEAT_PRODUCT_IDENTITY")
    assert not hasattr(core_facade, "AEAT_PRODUCT")
    assert not hasattr(core_facade, "AEAT_CLI_EXECUTABLE")
