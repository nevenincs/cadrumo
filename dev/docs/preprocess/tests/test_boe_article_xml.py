"""BOE response metadata and other versions must not become legal prose."""

from pathlib import Path

import pytest

from ..boe_article_xml import article_response_units, article_version_units
from ..normatives_html import build_outputs, build_xml_outputs, legal_markup_units
from ..schema import SourceDocumentKind
from ..sidecar import PreprocessSidecarError

pytestmark = [pytest.mark.unit, pytest.mark.docs, pytest.mark.hex_core]


def _response(versions: str) -> str:
    return (
        '<?xml version="1.0"?><response><status><code>200</code><text>ok</text></status>'
        '<data><bloque id="a1-2" titulo="Artículo 10">' + versions + "</bloque></data></response>"
    )


_OLD = '<version id_norma="BOE-A-2000-1" fecha_vigencia="20000101"><p>Old <b>rule</b>.</p></version>'
_NEW = '<version id_norma="BOE-A-2020-2" fecha_vigencia="20200101"><p>New rule.</p></version>'


def test_response_versions_are_separate_and_status_is_not_prose(tmp_path: Path) -> None:
    source = tmp_path / "article.html"
    source.write_text(_response(_OLD + _NEW), encoding="utf-8")
    (output,) = build_outputs(source, repo_root=tmp_path)
    assert output.source_kind is SourceDocumentKind.NORMATIVES_XML
    assert [unit.text for unit in output.units] == ["Old rule.", "New rule."]
    assert output.units[0].anchor == "#a1-2"
    assert output.units[0].section is not None
    assert output.units[1].section is not None
    assert "2000-01-01" in output.units[0].section
    assert "2020-01-01" in output.units[1].section


@pytest.mark.parametrize(
    "markup",
    [
        _response(_OLD + _OLD),
        _response(""),
        _response(_OLD).replace("<code>200</code>", "<code>400</code>"),
        _response(_OLD).replace("20000101", "20001301"),
        _response(_OLD).replace("BOE-A-2000-1", "BOE-A-invalid"),
        '<!DOCTYPE response [<!ENTITY injected "not evidence">]>' + _response(_OLD).split("?>", 1)[1],
        "<?xml version='1.0'?><other/>",
        "<?xml version='1.0'?><response>",
    ],
)
def test_invalid_or_ambiguous_response_is_refused(markup: str) -> None:
    with pytest.raises(PreprocessSidecarError):
        article_response_units(markup, segment=legal_markup_units)


def test_xml_without_declaration_uses_the_same_extractor(tmp_path: Path) -> None:
    source = tmp_path / "article.html"
    source.write_text(_response(_OLD).split("?>", 1)[1], encoding="utf-8")
    (output,) = build_outputs(source, repo_root=tmp_path)
    assert output.source_kind is SourceDocumentKind.NORMATIVES_XML
    assert output.units[0].text == "Old rule."


def test_ordinal_provisions_keep_their_existing_citation_boundaries() -> None:
    version = (
        '<version id_norma="BOE-A-2000-1" fecha_vigencia="20000101">'
        '<p class="parrafo_2">Primero. First provision.</p><p>First body.</p>'
        '<p class="parrafo_2">Segundo. Second provision.</p><p>Second body.</p>'
        "</version>"
    )
    units = article_response_units(_response(version), segment=legal_markup_units)
    assert [unit.title for unit in units] == ["Primero. First provision.", "Segundo. Second provision."]
    assert [unit.text for unit in units] == ["First body.", "Second body."]
    assert [unit.anchor for unit in units] == ["#primero", "#segundo"]


def test_sliced_version_preserves_legal_identity_and_dates(tmp_path: Path) -> None:
    source = tmp_path / "article.xml"
    source.write_text(
        '<version id_norma="BOE-A-2023-1" fecha_publicacion="20231228" fecha_vigencia="20240101">'
        '<p class="articulo">Artículo 1. Rule.</p><p>Exact body.</p></version>',
        encoding="utf-8",
    )

    (output,) = build_xml_outputs(source, repo_root=tmp_path)

    assert output.source_kind is SourceDocumentKind.NORMATIVES_XML
    assert output.preprocessor_id == "boe-legal-xml"
    assert output.units[0].text == "Artículo 1. Rule.Exact body."
    assert "BOE-A-2023-1" in (output.units[0].section or "")
    assert "fecha_publicacion=2023-12-28" in (output.units[0].section or "")
    assert "fecha_vigencia=2024-01-01" in (output.units[0].section or "")


def test_sliced_version_refuses_missing_identity_metadata() -> None:
    with pytest.raises(PreprocessSidecarError, match="lacks instrument"):
        article_version_units("<version><p>Text</p></version>", segment=legal_markup_units)
