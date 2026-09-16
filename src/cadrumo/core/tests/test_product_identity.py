"""Contract tests for Cadrumo's canonical product identity boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from .. import product_identity as identity_module
from ..product_identity import (
    PRODUCT_IDENTITY,
    ProductIdentity,
    normalise_product_identity_references,
)
from ..toml import parse_toml

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_product_identity_matches_the_accepted_external_tuple() -> None:
    """Every externally projected product name follows the accepted CADRUMO tuple."""
    expected = ProductIdentity(
        display_name="CADRUMO",
        prose_name="Cadrumo",
        python_package="cadrumo",
        distribution="cadrumo",
        cli_executable="aeat",
        repository="nevenincs/cadrumo",
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
    pyproject = parse_toml((repository_root / relative_pyproject).read_text(encoding="utf-8"))
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


def test_product_identity_normalizes_only_unambiguous_stale_command_prefixes() -> None:
    """The shared normalizer preserves prose, machine identifiers, and authority names."""
    assert (
        normalise_product_identity_references(
            "Cadrumo serves AEAT; run cadrumo app status, keep cadrumo-helper and CADRUMO_TOKEN."
        )
        == "Cadrumo serves AEAT; run aeat app status, keep cadrumo-helper and CADRUMO_TOKEN."
    )


def test_product_identity_is_immutable() -> None:
    """The runtime identity cannot be changed after import."""
    original = PRODUCT_IDENTITY
    field_name = "display_name"

    with pytest.raises(AttributeError):
        setattr(PRODUCT_IDENTITY, field_name, "Changed")

    assert PRODUCT_IDENTITY is original
    assert PRODUCT_IDENTITY.display_name == "CADRUMO"


def test_identity_api_exposes_no_former_product_aliases() -> None:
    """AEAT-prefixed exports name genuine AEAT-format contracts."""
    # AEAT_CSV_* names the shape contract for AEAT's own Codigo Seguro de
    # Verificacion (the identifier AEAT prints on a justificante) -- a
    # legitimate AEAT-referent export per aeat-naming,
    # not a former-product alias.
    allowed_aeat_names = {
        "AEAT_CSV_MIN_LENGTH",
        "AEAT_CSV_MAX_LENGTH",
        "AEAT_CSV_PATTERN",
        "AeatProductSoftwareEvidence",
        "AeatProductSoftwareIdentity",
    }
    identity_aeat_names = {"AEAT_AUTHORITY_SHORT_NAME"}
    assert {name for name in identity_module.__all__ if name.casefold().startswith("aeat")} == identity_aeat_names
    assert allowed_aeat_names  # the wider cross-module set stays documented above
