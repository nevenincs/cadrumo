"""The declaration's mandatory ``Aux`` block is declared, or the export refuses.

Every AEAT Modelo 100 XSD opens ``Declaracion`` with ``Aux``, ``minOccurs="1"``,
whose ``Idioma`` and ``VERSION`` children are mandatory too. No bundled dictionary
declares a single ``Aux`` row in any of the six revisions, so the dictionary-driven
writer cannot reach the block and its values are declared on the export layout.

``aux_version`` is deliberately undeclared today: AEAT publishes no authoritative
value for it anywhere in the bundled corpus, and ``tipo_String4L`` is permissive
enough that an invented token would validate while asserting something nothing
verified. So the export refuses instead.

The refusal is scaffolding, not a specification, and this module proves that:
:func:`test_the_refusal_retires_when_the_layout_declares_the_value` shows it stops
firing the moment a layout carries a value. Without that, a later reader finds a
green test asserting the export refuses and reads it as the intended behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from defusedxml import ElementTree as DefusedElementTree

from ....core import DeclaracionIdioma, ExportLayoutFormat
from ....domain.filing import FilingExportError
from .._export_parity import assert_xml_declaration_aux_declared
from .._export_xml_dictionary import render_xml_dictionary_layout
from ..runtime import build_runtime_schema_provider
from .test_export import _approved_modelo_100_xml_dictionary_draft, _schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_HEADERS = {"surnames": "SURNAME BLANK", "name": "STATE"}


def _modelo_100_layout(filing_year: int = 2024):
    provider = _schema_provider(filing_year=filing_year, period="0A", modelos=("100",))
    return provider.get_subview("100").export_layouts[0]


def test_every_modelo_100_layout_declares_its_idioma() -> None:
    """``Idioma`` is derivable, so it is declared rather than refused on.

    A Spanish-language filing declares ``E``; the schema pattern ``(E|G|C|V){1}``
    is what makes the set closed, so this is AEAT's constraint rather than ours.
    """
    for filing_year in range(2020, 2026):
        layout = _modelo_100_layout(filing_year)

        assert layout.format is ExportLayoutFormat.XML_DICTIONARY
        assert layout.aux_idioma is DeclaracionIdioma.CASTELLANO, filing_year


def test_no_modelo_100_layout_invents_a_version() -> None:
    """``VERSION`` stays undeclared while no AEAT source carries a real value.

    Guards the specific regression this feature exists to prevent: someone filling
    the field with a plausible four-character token so the export starts working.
    A real AEAT-submitted fixture in this tree carries ``2.02``, which is a
    redaction placeholder rather than an authority.
    """
    for filing_year in range(2020, 2026):
        assert _modelo_100_layout(filing_year).aux_version is None, filing_year


def test_the_export_refuses_and_names_the_undeclared_field() -> None:
    """The operator learns which field is missing, not merely that something is."""
    layout = _modelo_100_layout()

    with pytest.raises(FilingExportError) as refusal:
        assert_xml_declaration_aux_declared(layout)

    message = str(refusal.value)
    assert "aux_version" in message
    assert "aux_idioma" not in message, "idioma is declared; naming it would misdirect the operator"
    assert "Aux" in message


def test_the_export_writes_no_file_when_it_refuses(tmp_path: Path) -> None:
    """The refusal reaches the operator through the real export entrypoint.

    Asserting the guard in isolation would not prove ``export_draft`` calls it, nor
    that it runs before the bytes are written.
    """
    from .._export import export_draft

    draft = _approved_modelo_100_xml_dictionary_draft()
    provider = _schema_provider(filing_year=2024, period="0A", modelos=("100",))
    output = tmp_path / "modelo-100-2024.xml"

    with pytest.raises(FilingExportError, match="aux_version"):
        export_draft(draft, output_path=output, headers=dict(_HEADERS), schema_provider=provider)

    assert not output.exists(), "a refused export must leave no artefact behind"


def test_the_refusal_retires_when_the_layout_declares_the_value(tmp_path: Path) -> None:
    """Filling the declared parameter is all it takes; no code change follows.

    The layout is rebuilt through the registry's own model — the same construction
    the loader performs when it hydrates the TOML — rather than by patching the
    guard or the layout object in place, so what this proves is retirement under
    the mechanism a real declaration will use.
    """
    layout = _modelo_100_layout()
    declared = layout.model_copy(update={"aux_version": "1.00"})

    assert_xml_declaration_aux_declared(declared)

    provider = _schema_provider(filing_year=2024, period="0A", modelos=("100",))
    payload = render_xml_dictionary_layout(
        declared,
        draft=_approved_modelo_100_xml_dictionary_draft(),
        headers=dict(_HEADERS),
        schema_provider=provider,
    )
    root = DefusedElementTree.fromstring(payload)
    aux = root.find("./Aux")

    assert aux is not None, "a declared layout must write the Aux block"
    assert [child.tag for child in aux] == ["Idioma", "VERSION"]
    assert aux.findtext("Idioma") == "E"
    assert aux.findtext("VERSION") == "1.00"
    assert next(child.tag for child in root) == "Aux", "Aux is first in the declared XSD sequence"


def test_a_layout_may_not_declare_half_the_block(tmp_path: Path) -> None:
    """A partial ``Aux`` is invalid, so declaring only one half still refuses."""
    layout = _modelo_100_layout()
    version_only = layout.model_copy(update={"aux_idioma": None, "aux_version": "1.00"})

    with pytest.raises(FilingExportError, match="aux_idioma"):
        assert_xml_declaration_aux_declared(version_only)


def test_the_guard_leaves_fixed_width_exports_alone() -> None:
    """The refusal is scoped to the format that has an ``Aux`` block.

    A fichero-BOE layout has none, so the guard must be a no-op there; otherwise
    it would refuse every other modelo's export.
    """
    provider = build_runtime_schema_provider(modelos=("303",))
    layout = provider.get_subview("303").export_layouts[0]

    assert layout.format is ExportLayoutFormat.FIXED_WIDTH
    assert_xml_declaration_aux_declared(layout)
