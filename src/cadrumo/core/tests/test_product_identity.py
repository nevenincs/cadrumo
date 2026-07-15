"""Contract tests for Cadrumo's canonical product identity boundary."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from .. import (
    AEAT_AUTHORITY_SHORT_NAME,
    PRODUCT_IDENTITY,
    IdentityReferent,
    ProductIdentity,
)
from .. import __all__ as core_all
from .. import product_identity as identity_module

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_IDENTITY_EXPORTS = frozenset(
    {
        "AEAT_AUTHORITY_SHORT_NAME",
        "PRODUCT_IDENTITY",
        "IdentityReferent",
        "ProductIdentity",
    }
)

_CORE_IDENTITY_OBJECTS = {
    "AEAT_AUTHORITY_SHORT_NAME": AEAT_AUTHORITY_SHORT_NAME,
    "PRODUCT_IDENTITY": PRODUCT_IDENTITY,
    "IdentityReferent": IdentityReferent,
    "ProductIdentity": ProductIdentity,
}


def test_product_identity_matches_the_accepted_external_tuple() -> None:
    """Every externally projected product name follows the accepted CADRUMO tuple."""
    expected = ProductIdentity(
        display_name="CADRUMO",
        prose_name="Cadrumo",
        python_package="cadrumo",
        distribution="cadrumo",
        cli_executable="aeat",
        repository="nevenincs/cadrumo",
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


@pytest.mark.parametrize(
    "relative_pyproject",
    (
        Path("pyproject.toml"),
        Path("packaging/cadrumo_data_manuals/pyproject.toml"),
        Path("packaging/cadrumo_data_official/pyproject.toml"),
    ),
)
def test_repository_metadata_consumes_the_owner_qualified_slug(
    relative_pyproject: Path,
) -> None:
    """Root and companion metadata project the canonical repository slug."""
    repository_root = Path(__file__).resolve().parents[4]
    pyproject = tomllib.loads((repository_root / relative_pyproject).read_text(encoding="utf-8"))
    repository_url = f"https://github.com/{PRODUCT_IDENTITY.repository}"

    assert pyproject["project"]["urls"] == {
        "Homepage": repository_url,
        "Issues": f"{repository_url}/issues",
        "Repository": repository_url,
    }


def test_product_identity_distinguishes_prose_from_identity_context() -> None:
    """Sentence copy and identity contexts expose their ratified casing."""
    assert PRODUCT_IDENTITY.prose_name == "Cadrumo"
    assert PRODUCT_IDENTITY.display_name == "CADRUMO"
    assert PRODUCT_IDENTITY.prose_name != PRODUCT_IDENTITY.display_name


def test_product_identity_is_immutable() -> None:
    """The runtime identity cannot be changed after import."""
    original = PRODUCT_IDENTITY
    field_name = "display_name"

    with pytest.raises(AttributeError):
        setattr(PRODUCT_IDENTITY, field_name, "Changed")

    assert PRODUCT_IDENTITY is original
    assert PRODUCT_IDENTITY.display_name == "CADRUMO"


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
    """The defining module and core facade expose one closed identity API."""
    assert set(identity_module.__all__) == _IDENTITY_EXPORTS
    identity_objects = tuple(getattr(identity_module, name) for name in _IDENTITY_EXPORTS)
    assert {
        name
        for name in core_all
        if any(_CORE_IDENTITY_OBJECTS.get(name) is identity_object for identity_object in identity_objects)
    } == _IDENTITY_EXPORTS

    for export_name in _IDENTITY_EXPORTS:
        assert _CORE_IDENTITY_OBJECTS[export_name] is getattr(identity_module, export_name)


def test_identity_api_exposes_no_former_product_aliases() -> None:
    """AEAT is public only as the explicit external-authority short name."""
    assert AEAT_AUTHORITY_SHORT_NAME == "AEAT"
    assert {name for name in core_all if name.casefold().startswith("aeat")} == {"AEAT_AUTHORITY_SHORT_NAME"}
    assert "__getattr__" not in vars(identity_module)
