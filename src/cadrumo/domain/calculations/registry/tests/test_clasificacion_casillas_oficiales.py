"""Real bundled-registry proofs for the canonical official-box classifier."""

from __future__ import annotations

import pytest

from .....core import EstadoCasillaOficial, validated_casilla_id
from .. import RegistryValidationError, bundled_authority, clasificar_casillas_oficiales
from .. import _export as owner

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_classifier_is_the_public_registry_identity() -> None:
    assert clasificar_casillas_oficiales is owner.clasificar_casillas_oficiales


def test_m720_binding_derived_design_distinguishes_declared_binding_representation() -> None:
    authority = bundled_authority()
    revision = authority.validate_modelo("720").revisions["2013-y-siguientes"]

    assert all(not record.fields for layout in revision.export_layouts for record in layout.records)

    statuses = clasificar_casillas_oficiales(revision)

    assert statuses[validated_casilla_id("decl.ejercicio", surface="M720 filing year")] is (
        EstadoCasillaOficial.REPRESENTED_VIA_BINDING
    )
    assert statuses[validated_casilla_id("decl.tipo-declaracion", surface="M720 declaration type")] is (
        EstadoCasillaOficial.REPRESENTED_VIA_BINDING
    )
    assert statuses[validated_casilla_id("cuentas.valoracion", surface="M720 account valuation")] is (
        EstadoCasillaOficial.UNDEFINED
    )


def test_m100_2024_uses_the_official_xml_dictionary_and_requires_its_authority() -> None:
    authority = bundled_authority()
    revision = authority.snapshot("100", filing_year=2024, period="0A").revision

    with pytest.raises(RegistryValidationError, match="requires source_root and sources"):
        clasificar_casillas_oficiales(revision)

    statuses = clasificar_casillas_oficiales(
        revision,
        source_root=authority.source_root,
        sources=authority.catalogues.sources,
    )

    assert statuses[validated_casilla_id("0001", surface="M100 official box 0001")] is EstadoCasillaOficial.ADDRESSED
    assert statuses[validated_casilla_id("ANOASDLG", surface="M100 dictionary-only family field")] is (
        EstadoCasillaOficial.UNDEFINED
    )


def test_m349_binding_derived_rows_address_casillas_without_export_refs() -> None:
    authority = bundled_authority()
    revision = authority.snapshot("349", filing_year=2026, period="1T").revision

    statuses = clasificar_casillas_oficiales(revision)

    assert statuses[validated_casilla_id("decl.numero-operadores", surface="M349 declared operator count")] is (
        EstadoCasillaOficial.ADDRESSED
    )
    assert statuses[validated_casilla_id("op.codigo-pais", surface="M349 operator country code")] is (
        EstadoCasillaOficial.ADDRESSED
    )
    country_code = next(casilla for casilla in revision.casillas if str(casilla.id) == "op.codigo-pais")
    assert not country_code.export_refs


def test_layoutless_revision_is_explicitly_undefined() -> None:
    authority = bundled_authority()
    revision = authority.snapshot("130", filing_year=2026, period="1T").revision

    statuses = clasificar_casillas_oficiales(revision)

    assert statuses
    assert set(statuses.values()) == {EstadoCasillaOficial.UNDEFINED}
