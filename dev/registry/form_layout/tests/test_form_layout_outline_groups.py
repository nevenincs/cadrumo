"""The reviewed outline declarations reach their layouts whole, and their headings and part names are translated.

The Modelo 100 layout carries the outline ``outline_groups.toml`` declares
for it, and every heading a navigator draws from that edition, its pages,
sections and outline groups, reads as words in each supported locale. A part
heading is scoped to its edition, because a positional section id holds
different boxes in another year's design.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import pytest

from cadrumo.core.i18n.render import lookup_translation
from cadrumo.domain.calculations.registry.modelo_localization import form_heading_edition_locale_key
from cadrumo.domain.calculations.registry.schema_form_layouts import FormLayoutDefinition
from dev.locales.form_layout_heading_scan import scan_form_layout_heading_keys

from ...compiler.loader import load_registry_tree
from ..cli import REGISTRY_ROOT
from ..outline_groups import OutlineGroupRefusedError, read_outline_groups

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LOCALES = ("es", "en", "ca", "hu")


def _outlined_revision() -> str:
    """The one Modelo 100 revision that ``outline_groups.toml`` declares an outline for."""
    (revision,) = (revision for modelo, revision in read_outline_groups().outlines if modelo == "100")
    return revision


@cache
def _renta_layouts() -> dict[str, FormLayoutDefinition]:
    modelos, _catalogues = load_registry_tree(REGISTRY_ROOT)
    renta = next(modelo for modelo in modelos if str(modelo.id) == "100")
    return {str(revision_id): revision.form_layouts[0] for revision_id, revision in renta.revisions.items()}


def _edition_keys(layout: FormLayoutDefinition) -> list[str]:
    keys = [page.heading_key for page in layout.pages]
    keys += [section.heading_key for page in layout.pages for section in page.sections]
    edition = (form_heading_edition_locale_key("100", layout.revision_id, key) for key in keys)
    return [key for key in edition if key is not None]


def test_the_outlined_renta_layout_carries_the_declared_outline() -> None:
    revision = _outlined_revision()
    layout = _renta_layouts()[revision]

    assert layout.outline == read_outline_groups().for_revision("100", revision)
    assert all(group.heading_key == f"modelo.schema.100.form.outline.{group.id}.heading" for group in layout.outline)


def test_an_outline_belongs_to_the_one_revision_it_names() -> None:
    layouts = _renta_layouts()

    assert [revision for revision, layout in layouts.items() if layout.outline] == [_outlined_revision()]


@pytest.mark.parametrize("locale", _LOCALES)
def test_every_outlined_renta_heading_reads_as_words(locale: str) -> None:
    layout = _renta_layouts()[_outlined_revision()]
    keys = [page.heading_key for page in layout.pages]
    keys += [section.heading_key for page in layout.pages for section in page.sections]

    def worded(key: str | None) -> bool:
        return key is not None and bool(lookup_translation(key, locale=locale))

    unworded = [
        key
        for key in keys
        if not worded(form_heading_edition_locale_key("100", layout.revision_id, key)) and not worded(key)
    ]
    assert unworded == []
    assert [group.id for group in layout.outline if not worded(group.heading_key)] == []


def test_the_locale_scanner_admits_the_edition_and_outline_headings() -> None:
    layout = _renta_layouts()[_outlined_revision()]
    admitted = scan_form_layout_heading_keys()

    assert set(_edition_keys(layout)) <= admitted
    assert {group.heading_key for group in layout.outline} <= admitted
    assert f"modelo.schema.100.revision.{layout.revision_id}.form.section.nowhere.heading" not in admitted


@pytest.mark.parametrize(
    "document",
    [
        '[[outlines]]\nmodelo = "100"\nrevision = "synthetic"\ngroups = [{ id = "a", sections = ["no-slash"] }]\n',
        '[[outlines]]\nmodelo = "100"\nrevision = "synthetic"\ngroups = [{ sections = ["p/s"] }]\n',
        '[[outlines]]\nmodelo = "100"\nrevision = "synthetic"\ngroups = []\n'
        '[[outlines]]\nmodelo = "100"\nrevision = "synthetic"\ngroups = []\n',
        'outlines = "none"\n',
    ],
)
def test_an_outline_declaration_that_is_not_one_outline_per_revision_is_refused(tmp_path: Path, document: str) -> None:
    path = tmp_path / "outline_groups.toml"
    path.write_text(document, encoding="utf-8")

    with pytest.raises(OutlineGroupRefusedError):
        read_outline_groups(path)


def test_a_missing_declaration_declares_no_outline(tmp_path: Path) -> None:
    assert read_outline_groups(tmp_path / "absent.toml").for_revision("100", "synthetic") == ()
