"""Required content of a finished XML declaration, read from its schema's content model.

A small schema states each model-group shape the bundled XSDs use, so every expected
answer here is worked from the schema text and not from the check under test.
"""

from __future__ import annotations

from xml.etree.ElementTree import Element

import pytest
from defusedxml import ElementTree as DefusedElementTree

from ..errors import ModeloApplicationError
from ..export_xml_dictionary_modelo100 import refuse_family_minimum_without_its_rows
from ..export_xml_value_limits import (
    prune_childless_negative_blocks,
    refuse_xml_missing_required_content,
    xml_value_schema,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SCHEMA = """<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:complexType name="withRow">
    <xs:sequence><xs:element name="Row" type="xs:string" minOccurs="1" maxOccurs="3"/></xs:sequence>
    <xs:attribute name="flag" type="xs:string"/>
  </xs:complexType>
  <xs:element name="Declaracion">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="Head" type="xs:string"/>
        <xs:element name="Rows" type="withRow" minOccurs="0"/>
        <xs:element name="Free" type="xs:string" minOccurs="0"/>
        <xs:sequence minOccurs="0">
          <xs:element name="PairA" type="xs:string"/>
          <xs:element name="PairB" type="xs:string"/>
        </xs:sequence>
        <xs:choice>
          <xs:element name="OptionA" type="xs:string"/>
          <xs:sequence>
            <xs:element name="OptionB" type="xs:string"/>
            <xs:element name="OptionC" type="xs:string"/>
          </xs:sequence>
        </xs:choice>
      </xs:sequence>
      <xs:attribute name="needed" type="xs:string" use="required"/>
      <xs:attribute name="spare" type="xs:string"/>
    </xs:complexType>
  </xs:element>
</xs:schema>"""


def _schema() -> Element[str]:
    return DefusedElementTree.fromstring(_SCHEMA)


_SCHEMA_WITH_EMPTIABLE_CHOICE = """<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="Declaracion">
    <xs:complexType>
      <xs:choice>
        <xs:element name="Stated" type="xs:string"/>
        <xs:sequence>
          <xs:element name="Spare" type="xs:string" minOccurs="0"/>
        </xs:sequence>
      </xs:choice>
    </xs:complexType>
  </xs:element>
</xs:schema>"""


def _missing(document: str, *, schema: str = _SCHEMA) -> set[str]:
    """Return the paths refused; the boxes fall back to paths because no dictionary row names them."""
    try:
        refuse_xml_missing_required_content(
            DefusedElementTree.fromstring(document),
            schema=DefusedElementTree.fromstring(schema),
            source_id="synthetic",
            entries=(),
        )
    except ModeloApplicationError as refused:
        assert str(refused.translated_message).endswith("xml_value_required_missing")
        context = refused.context or {}
        return set(str(context.get("refused_boxes", context["box"])).split(", "))
    return set()


def test_a_document_holding_all_it_requires_passes() -> None:
    assert _missing('<Declaracion needed="1"><Head>h</Head><OptionA>a</OptionA></Declaracion>') == set()


def test_a_missing_required_child_and_attribute_are_each_named() -> None:
    assert _missing("<Declaracion><OptionA>a</OptionA></Declaracion>") == {"/@needed", "/Head"}


def test_a_required_child_of_a_present_optional_block_is_named() -> None:
    document = '<Declaracion needed="1"><Head>h</Head><Rows flag="SI"/><OptionA>a</OptionA></Declaracion>'
    assert _missing(document) == {"/Rows/Row"}


def test_an_optional_group_requires_nothing_until_it_is_begun() -> None:
    begun = '<Declaracion needed="1"><Head>h</Head><PairA>a</PairA><OptionA>a</OptionA></Declaracion>'
    assert _missing(begun) == {"/PairB"}


def test_a_choice_requires_only_its_begun_branch() -> None:
    assert _missing('<Declaracion needed="1"><Head>h</Head><OptionB>b</OptionB></Declaracion>') == {"/OptionC"}


def test_an_unbegun_required_choice_is_named_by_its_first_branch() -> None:
    assert _missing('<Declaracion needed="1"><Head>h</Head></Declaracion>') == {"/OptionA"}


def test_an_unbegun_choice_with_a_branch_that_requires_nothing_requires_nothing() -> None:
    assert _missing("<Declaracion/>", schema=_SCHEMA_WITH_EMPTIABLE_CHOICE) == set()


def _pruned(document: str) -> Element[str]:
    root = DefusedElementTree.fromstring(document)
    prune_childless_negative_blocks(
        root, schema=xml_value_schema(_schema(), source_id="synthetic", root_tag="Declaracion")
    )
    return root


def test_a_block_only_answering_no_is_left_out_when_it_cannot_hold_its_required_content() -> None:
    assert _pruned('<Declaracion><Rows flag="NO"/></Declaracion>').find("Rows") is None


@pytest.mark.parametrize(
    "block",
    ['<Rows flag="SI"/>', '<Rows flag="NO"><Row>r</Row></Rows>', "<Rows/>"],
    ids=["stated-yes", "has-its-rows", "states-nothing"],
)
def test_any_other_block_stays(block: str) -> None:
    assert _pruned(f"<Declaracion>{block}</Declaracion>").find("Rows") is not None


_MINIMUM = "<Declaracion>{rows}<DatosEconomicos><Resultados><MinimoPerFamRes>{amount}</MinimoPerFamRes></Resultados></DatosEconomicos></Declaracion>"
_HIJO = "<DatosIdentificativos><Hijos><Hijo/></Hijos></DatosIdentificativos>"
_ASCENDIENTE = "<DatosIdentificativos><Ascendientes><Ascendiente/></Ascendientes></DatosIdentificativos>"


@pytest.mark.parametrize(
    ("tag", "row"),
    [("MDES", "Hijo"), ("MASC", "Ascendiente")],
)
def test_a_claimed_family_minimum_with_no_identifying_row_refuses_naming_the_row(tag: str, row: str) -> None:
    document = DefusedElementTree.fromstring(_MINIMUM.format(rows="", amount=f"<{tag}>2400.00</{tag}>"))

    with pytest.raises(ModeloApplicationError) as refused:
        refuse_family_minimum_without_its_rows(document)

    assert str((refused.value.context or {})["box"]).endswith(f"/{row}")


@pytest.mark.parametrize(
    ("rows", "amount"),
    [
        (_HIJO, "<MDES>2400.00</MDES>"),
        (_ASCENDIENTE, "<MASC>1150.00</MASC>"),
        ("", "<MDES>0.00</MDES>"),
        ("", ""),
    ],
    ids=["descendant-listed", "ascendant-listed", "zero", "absent"],
)
def test_a_listed_or_unclaimed_minimum_passes(rows: str, amount: str) -> None:
    refuse_family_minimum_without_its_rows(DefusedElementTree.fromstring(_MINIMUM.format(rows=rows, amount=amount)))
