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

    # M720 declares no inline CASILLA-bearing field: every box it addresses is
    # represented through a binding, which is what `clasificar_casillas_oficiales`
    # is being asked to distinguish below.
    #
    # The records do each carry ONE inline field, and asserting `not record.fields`
    # therefore fails. Those two fields are trailing FILLERS -- type-1 at 181..500
    # and type-2 at 481..500 -- added so the emitted line reaches the 500 positions
    # the diseño declares, instead of the 180 and 480 a purely binding-derived
    # layout produced. Both cover exactly one design field, and the design itself
    # classifies both as reserved/blank, so they pad reserved space and blank no
    # data. They carry neither a casilla_id nor a literal, which is what the
    # narrowed assertion pins: an inline field that DID name a casilla would still
    # fail here, so this admits the filler without admitting inline representation.
    inline = [record.fields for layout in revision.export_layouts for record in layout.records]
    assert all(field.casilla_id is None and field.literal is None for fields in inline for field in fields), (
        "M720 must represent every casilla through a binding, never an inline export field"
    )

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


def _layoutless_revisions() -> list[tuple[str, str]]:
    """Every committed revision that declares no export layout at all."""
    return sorted(
        (str(modelo.id), revision_id)
        for modelo in bundled_authority().modelos
        for revision_id, revision in modelo.revisions.items()
        if not revision.export_layouts
    )


@pytest.mark.parametrize(("modelo_id", "revision_id"), _layoutless_revisions())
def test_layoutless_revision_is_explicitly_undefined(modelo_id: str, revision_id: str) -> None:
    """A revision with no export layout classifies every casilla as UNDEFINED.

    This pinned modelo 130 as its layoutless subject. The subject later gained
    an export layout, so it stopped being layoutless and the case failed on its
    own premise rather than on the classifier -- a decayed premise, not a
    regression. The subject is now derived from the property it needs, so a
    revision leaves this gate exactly when it gains a layout.
    """
    revision = bundled_authority().validate_modelo(modelo_id).revisions[revision_id]

    statuses = clasificar_casillas_oficiales(revision)

    assert statuses
    assert set(statuses.values()) == {EstadoCasillaOficial.UNDEFINED}


def test_revision_with_a_layout_addresses_at_least_one_casilla() -> None:
    """The contrapositive, which cannot go vacuous as the registry gains layouts.

    The layoutless population shrinks by design as authoring proceeds and
    would eventually empty, silently retiring the check above. This asserts the
    other direction on a revision that HAS a layout, so classification stays
    covered no matter how far the authoring gets.
    """
    authority = bundled_authority()
    revision = authority.snapshot("130", filing_year=2026, period="1T").revision

    statuses = clasificar_casillas_oficiales(revision)

    assert statuses
    assert EstadoCasillaOficial.ADDRESSED in set(statuses.values())
