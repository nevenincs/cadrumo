"""Domain tokens reach the declaration as the códigos AEAT enumerates.

Some rows carry a value whose stored form is a domain token rather than the code
the schema accepts: a comunidad is stored as ``andalucia`` where
``codigoCADeclaracion`` enumerates ``01``-``20``, and a marital status as the
profile's own value where ``ECIVIL`` accepts Estado Civil ``1``-``4``. Writing
the token through produces a file AEAT's own validator rejects.

The conversion is a table rather than a branch per field, and runs after
:func:`_format_xml_dictionary_value` rather than instead of it -- that function
decides how a value is written, the table decides which official code the
written value stands for.

The oracle is the bundled XSD's own enumeration, read here rather than restated,
so :func:`test_the_untranslated_token_is_not_a_valid_codigo` is what makes the
rest of the module non-vacuous: it fails if the stored token ever becomes an
accepted código, which would make converting it pointless.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from defusedxml import ElementTree as DefusedElementTree

from ....domain.filing import FilingExportValidationError
from .._export_xml_dictionary import (
    _MODELO_100_EXPORT_CODE_CONVERTERS,
    _xml_dictionary_xsd_source,
    render_xml_dictionary_layout,
)
from .test_export import _approved_modelo_100_xml_dictionary_draft, _schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_HEADERS = {"surnames": "SURNAME BLANK", "name": "STATE"}
_CCAA_PATH = "./DatosEconomicos"
_CCAA_ATTRIBUTE = "codigoCADeclaracion"


def _declared_ccaa_codigos() -> frozenset[str]:
    """The códigos ``tipo_CCAA`` enumerates, read from the bundled official XSD."""
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("100",))
    layout = provider.get_subview("100").export_layouts[0]
    source = _xml_dictionary_xsd_source(layout, provider.sources)
    assert provider.source_root is not None
    # AEAT publishes these declaring ISO-8859-1, and the código table lives in an
    # accented xs:documentation annotation inside the same simpleType.
    text = (Path(provider.source_root) / Path(source.corpus_path)).read_bytes().decode("iso-8859-1")
    declaration = re.search(r'<xs:simpleType name="tipo_CCAA">.*?</xs:simpleType>', text, re.S)
    assert declaration is not None, "the bundled XSD declares no tipo_CCAA"
    return frozenset(re.findall(r'<xs:enumeration value="([^"]+)"', declaration.group(0)))


def _render(**dictionary_values: object):
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("100",))
    layout = provider.get_subview("100").export_layouts[0]
    draft = _approved_modelo_100_xml_dictionary_draft()
    payload = render_xml_dictionary_layout(
        layout,
        draft=draft,
        headers=dict(_HEADERS),
        dictionary_values={"DPNIF_D": draft.profile_tax_id, **dictionary_values},
        schema_provider=provider,
    )
    root = DefusedElementTree.fromstring(payload)
    assert root is not None
    return root


def test_the_untranslated_token_is_not_a_valid_codigo() -> None:
    """The oracle: writing the stored token through would be rejected by AEAT.

    Without this the conversion assertions below prove only that the code does
    what the code does.
    """
    codigos = _declared_ccaa_codigos()

    assert codigos, "tipo_CCAA enumerates nothing; the oracle is broken"
    assert "andalucia" not in codigos
    assert "01" in codigos


def test_the_comunidad_reaches_the_declaration_as_its_codigo() -> None:
    """The defect this closes: ``andalucia`` was filed verbatim."""
    root = _render(ZCCAD="andalucia")

    economicos = root.find(_CCAA_PATH)

    assert economicos is not None
    assert economicos.get(_CCAA_ATTRIBUTE) == "01"


@pytest.mark.parametrize(("comunidad", "codigo"), [("madrid", "12"), ("murcia", "13")])
def test_each_comunidad_maps_to_its_own_codigo(comunidad: str, codigo: str) -> None:
    """Distinct comunidades produce distinct códigos.

    A single case would pass against a converter that returned one constant, and
    Madrid/Murcia are the pair that other CCAA numberings disagree on, so getting
    both right is evidence the Modelo 100 table is the one being used.
    """
    economicos = _render(ZCCAD=comunidad).find(_CCAA_PATH)

    assert economicos is not None
    assert economicos.get(_CCAA_ATTRIBUTE) == codigo


def test_a_comunidad_with_no_codigo_refuses_rather_than_filing_the_token() -> None:
    """An unmappable comunidad fails the export instead of writing something.

    Falling back to the raw token would produce a file that fails at AEAT after
    the taxpayer believed it was written, so the refusal is the safe direction.
    """
    with pytest.raises(FilingExportValidationError, match="ceuta"):
        _render(ZCCAD="ceuta")


def test_both_converted_rows_are_declared_in_one_table() -> None:
    """The dispatch is the single home, so the next conversion is data.

    Guards the shape rather than the values: a new conversion added as another
    branch inside the renderer would leave this table short and pass every other
    assertion here.
    """
    assert set(_MODELO_100_EXPORT_CODE_CONVERTERS) == {"ECIVIL", "ZCCAD"}


def test_the_marital_status_still_converts_after_moving_into_the_table() -> None:
    """The ECIVIL conversion survived being moved out of its own branch."""
    ecivil = _render(ECIVIL="4").find("./DatosIdentificativos/Declarante/ECIVIL")

    assert ecivil is not None
    assert ecivil.text == "4"

    with pytest.raises(FilingExportValidationError, match="pareja de hecho"):
        _render(ECIVIL="5")
