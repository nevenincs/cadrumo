"""Contract tests for Cadrumo's canonical product identity boundary."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from .. import (
    AEAT_AUTHORITY_SHORT_NAME,
    PRODUCT_IDENTITY,
    AeatProductSoftwareEvidence,
    AeatProductSoftwareIdentity,
    AeatProgramIdentifier,
    IdentityReferent,
    ProductIdentity,
    normalise_product_identity_references,
)
from .. import __all__ as core_all
from .. import product_identity as identity_module

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_IDENTITY_EXPORTS = frozenset(
    {
        "AEAT_AUTHORITY_SHORT_NAME",
        "AeatProductSoftwareEvidence",
        "AeatProductSoftwareIdentity",
        "AeatProgramIdentifier",
        "PRODUCT_IDENTITY",
        "IdentityReferent",
        "ProductIdentity",
        "normalise_product_identity_references",
    }
)

_CORE_IDENTITY_OBJECTS = {
    "AEAT_AUTHORITY_SHORT_NAME": AEAT_AUTHORITY_SHORT_NAME,
    "AeatProductSoftwareEvidence": AeatProductSoftwareEvidence,
    "AeatProductSoftwareIdentity": AeatProductSoftwareIdentity,
    "AeatProgramIdentifier": AeatProgramIdentifier,
    "PRODUCT_IDENTITY": PRODUCT_IDENTITY,
    "IdentityReferent": IdentityReferent,
    "ProductIdentity": ProductIdentity,
    "normalise_product_identity_references": normalise_product_identity_references,
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


def test_aeat_product_software_identity_requires_exact_values_and_evidence() -> None:
    """An export header cannot reuse a filing participant or an implicit product default."""
    identity = AeatProductSoftwareIdentity(
        program_identifier="C303",
        developer_tax_id="Y0000001S",
        evidence=(
            AeatProductSoftwareEvidence(
                reference="aeat-software-registration:c303",
                digest="a" * 64,
            ),
        ),
    )

    assert identity.program_identifier == "C303"
    assert identity.developer_tax_id == "Y0000001S"
    assert identity.evidence[0].reference == "aeat-software-registration:c303"
    assert not {
        name
        for name in vars(identity_module)
        if name.startswith("M303ProductSoftware") or name == "M303ProgramIdentifier"
    }

    with pytest.raises(ValueError, match="program_identifier"):
        AeatProductSoftwareIdentity(
            program_identifier="303",
            developer_tax_id="Y0000001S",
            evidence=identity.evidence,
        )
    with pytest.raises(ValueError, match="at least 1 item"):
        AeatProductSoftwareIdentity(
            program_identifier="C303",
            developer_tax_id="Y0000001S",
            evidence=(),
        )


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
    """AEAT is public only as the explicit external-authority short name or a genuine AEAT-format contract."""
    assert AEAT_AUTHORITY_SHORT_NAME == "AEAT"
    # AEAT_CSV_* names the shape contract for AEAT's own Codigo Seguro de
    # Verificacion (the identifier AEAT prints on a justificante) -- a
    # legitimate AEAT-referent export per aeat-naming,
    # not a former-product alias.
    # AEAT_RECORD_BATCH_SHAPES names the document shapes of AEAT's OWN record-
    # supply submissions (SII and VERI*FACTU). The referent is the tax
    # authority's published schema, not this product, so per aeat-naming it
    # keeps the AEAT name -- renaming it would misname whose records they are.
    allowed_aeat_names = {
        "AEAT_AUTHORITY_SHORT_NAME",
        "AEAT_CSV_MIN_LENGTH",
        "AEAT_CSV_MAX_LENGTH",
        "AEAT_CSV_PATTERN",
        "AEAT_RECORD_BATCH_SHAPES",
        "AeatProductSoftwareEvidence",
        "AeatProductSoftwareIdentity",
        "AeatProgramIdentifier",
    }
    assert {name for name in core_all if name.casefold().startswith("aeat")} == allowed_aeat_names
    assert "__getattr__" not in vars(identity_module)
