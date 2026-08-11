"""``TomaDatosAmpliada`` carries both identity attributes AEAT requires.

``titular`` and ``nif`` are both ``use="required"`` on
``tipo_TomaDatosAmpliada``, and a declaration went out carrying neither. They
are missing for two DIFFERENT reasons, and the fix for one is the wrong fix for
the other:

``titular`` IS dictionary-declared. Thirty-five field ids -- ``TITA`` on casilla
0001, ``TITBIH`` on 0026, and so on -- all map to
``/DatosEconomicos/TomaDatosAmpliada/@titular``, so the ordinary walk writes it
from whichever titular casilla the return populates. It was blank only because
no such casilla carried a value.

``nif`` is declared by no dictionary row at all, so no value could reach it and
it is stamped from the approved draft after the walk.

The distinction is load-bearing, not bookkeeping: stamping a constant
``titular`` would satisfy the schema while silently re-attributing a spouse's
income section from código 3 to the declarante's 2 on a filed return.
:func:`test_titular_tracks_its_casilla_rather_than_a_constant` is the guard
against exactly that, and it fails against a constant stamp.

Both reasons are read from the bundled official XSD and dictionary rather than
asserted, so this module cannot quietly agree with the writer it covers.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest
from defusedxml import ElementTree as DefusedElementTree

from ....domain.calculations.registry import xml_dictionary_entries
from ....domain.filing import ModeloValue, ModeloValueKind
from .._export_xml_dictionary import _xml_dictionary_xsd_source, render_xml_dictionary_layout
from .test_export import _approved_modelo_100_xml_dictionary_draft, _schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_HEADERS = {"surnames": "SURNAME BLANK", "name": "STATE"}
_TOMA_DATOS_PATH = "/DatosEconomicos/TomaDatosAmpliada"

# Every exercise AEAT publishes a Modelo 100 XSD for in this tree. Asserted
# across all of them because a fix pinned to one year silently stops applying
# the moment a new revision is bundled.
_FILING_YEARS = tuple(range(2020, 2026))

# One of the thirty-five titular field ids, and the casilla behind it.
_TITULAR_CASILLA = "0001"


def _xsd_text(filing_year: int) -> str:
    provider = _schema_provider(filing_year=filing_year, period="0A", modelos=("100",))
    layout = provider.get_subview("100").export_layouts[0]
    source = _xml_dictionary_xsd_source(layout, provider.sources)
    assert provider.source_root is not None
    # AEAT publishes these declaring ISO-8859-1, and the accented prose in the
    # xs:documentation annotations is genuinely in that encoding.
    return (Path(provider.source_root) / Path(source.corpus_path)).read_bytes().decode("iso-8859-1")


def _render(*, titular_code: str | None = None, tax_id: str | None = None):
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("100",))
    layout = provider.get_subview("100").export_layouts[0]
    draft = _approved_modelo_100_xml_dictionary_draft()
    if tax_id is not None:
        draft = draft.model_copy(update={"profile_tax_id": tax_id, "subject_tax_id": tax_id})
    if titular_code is not None:
        draft = draft.model_copy(
            update={
                "values": (
                    *draft.values,
                    ModeloValue(
                        casilla_id=_TITULAR_CASILLA,
                        value=Decimal(titular_code),
                        kind=ModeloValueKind.LITERAL,
                        source="titular under test",
                    ),
                ),
            },
        )
    payload = render_xml_dictionary_layout(
        layout,
        draft=draft,
        headers=dict(_HEADERS),
        # The identity row travels the channel the export service composes it
        # on, so the document carries the same NIF twice by two different
        # routes -- which is the disagreement the stamp exists to prevent.
        dictionary_values={"DPNIF_D": draft.profile_tax_id},
        schema_provider=provider,
    )
    root = DefusedElementTree.fromstring(payload)
    assert root is not None
    blocks = list(root.iter("TomaDatosAmpliada"))
    assert blocks, "the declaration rendered no TomaDatosAmpliada block"
    return root, blocks, draft


@pytest.mark.parametrize("attribute", ["titular", "nif"])
@pytest.mark.parametrize("filing_year", _FILING_YEARS)
def test_the_schema_requires_the_attribute(filing_year: int, attribute: str) -> None:
    """The oracle: AEAT declares both mandatory, in every bundled exercise."""
    declaration = re.search(
        r'<xs:complexType name="tipo_TomaDatosAmpliada">.*?</xs:complexType>',
        _xsd_text(filing_year),
        re.S,
    )
    assert declaration is not None, f"{filing_year} declares no tipo_TomaDatosAmpliada"
    assert re.search(
        rf'<xs:attribute name="{attribute}"[^/]*use="required"',
        declaration.group(0),
    ), f"{filing_year} no longer requires @{attribute}"


def test_the_dictionary_routes_titular_but_not_nif() -> None:
    """Why the two attributes are filled by different mechanisms.

    A ``dictionary_path_overrides`` entry re-points a row AEAT already
    publishes; it cannot invent one. So a row existing for ``titular`` and none
    existing for ``nif`` is the whole reason one is walked and one is stamped.
    If a ``nif`` row ever appears, it becomes the right home and the stamp turns
    into a competing second authority.
    """
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("100",))
    layout = provider.get_subview("100").export_layouts[0]
    entries = xml_dictionary_entries(layout, source_root=provider.source_root, sources=provider.sources)

    titular_rows = [entry.field_id for entry in entries if entry.path == f"{_TOMA_DATOS_PATH}/@titular"]
    nif_rows = [entry.field_id for entry in entries if entry.path == f"{_TOMA_DATOS_PATH}/@nif"]

    assert titular_rows, "no dictionary row reaches @titular; the walk can no longer fill it"
    assert nif_rows == [], f"the dictionary now reaches @nif via {nif_rows}; the stamp is a second authority"


def test_titular_is_absent_when_no_titular_casilla_is_declared() -> None:
    """A blank ``titular`` is an unfilled casilla, not a writer that cannot write.

    Pins the reason the attribute was missing, so a later reader does not
    conclude the walk is incapable of writing it and add a stamp.
    """
    _, blocks, _ = _render()

    assert [block.get("titular") for block in blocks] == [None] * len(blocks)


@pytest.mark.parametrize("code", ["2", "3"])
def test_titular_tracks_its_casilla_rather_than_a_constant(code: str) -> None:
    """The walk writes whichever titular the return declares.

    Código 2 is the declarante and 3 the cónyuge. A constant stamp would pass
    the ``2`` case and file the ``3`` case under the wrong taxpayer, so this
    asserts both: it is the regression guard for re-attributed income.
    """
    _, blocks, _ = _render(titular_code=code)

    assert [block.get("titular") for block in blocks] == [code] * len(blocks)


def test_the_block_nif_is_the_approved_drafts() -> None:
    """The stamped attribute carries the identity the figures were approved against."""
    _, blocks, draft = _render()

    assert [block.get("nif") for block in blocks] == [draft.profile_tax_id] * len(blocks)


def test_the_block_nif_cannot_disagree_with_the_identity_row() -> None:
    """The same NIF reaches the file twice; the two must be the same bytes.

    ``DPNIF_D`` and this attribute are two statements of one taxpayer's identity
    in one artefact. Reading either from a live profile would let a profile
    edited between approval and export make them disagree, so both are taken
    from the approved draft and this pins that they still are.
    """
    root, blocks, _ = _render()

    row = root.find("./DatosIdentificativos/Declarante/DPNIF_D")

    assert row is not None and row.text, "the identity row is absent; this proves nothing"
    for block in blocks:
        assert block.get("nif") == row.text


def test_the_nif_stamp_tracks_the_draft_rather_than_a_constant() -> None:
    """A different approved identity produces a different attribute.

    Guards the failure mode a literal NIF frozen into the writer would pass
    every other assertion here with, since they all share one fixture.
    """
    _, blocks, _ = _render(tax_id="87654321X")

    assert [block.get("nif") for block in blocks] == ["87654321X"] * len(blocks)
