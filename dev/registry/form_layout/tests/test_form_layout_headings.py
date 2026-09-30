"""Heading catalogue coverage for the shared column vocabulary and the most-filed modelos.

The shared vocabulary is translated once for every modelo, so every member
must hold a real value in each supported locale. The most-filed modelos'
layouts must find a translation for every heading the design names; a heading
the design leaves unnamed falls back to the technical id and is not required.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import cache

import pytest

from cadrumo.core.i18n.render import lookup_translation
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormGridBlock,
    FormLayoutDefinition,
    FormRepeatingGroupBlock,
)

from ...compiler.loader import load_registry_tree
from ..cli import REGISTRY_ROOT
from ..column_vocabulary import SHARED_COLUMN_HEADING_KEY_PREFIX, SHARED_COLUMN_KEYS

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LOCALES = ("es", "en", "ca", "hu")
_MOST_FILED = ("111", "115", "130", "303", "390")


@cache
def _layouts() -> tuple[FormLayoutDefinition, ...]:
    modelos, _catalogues = load_registry_tree(REGISTRY_ROOT)
    return tuple(
        revision.form_layouts[0]
        for modelo in modelos
        if str(modelo.id) in _MOST_FILED
        for revision in modelo.revisions.values()
    )


def _named_headings(layout: FormLayoutDefinition) -> Iterator[tuple[str, str]]:
    """Yield every heading key the layout declares together with the official words it names."""
    for page in layout.pages:
        if page.official_ref:
            yield page.heading_key, page.official_ref
        for section in page.sections:
            if section.official_heading:
                yield section.heading_key, section.official_heading
            for block in section.blocks:
                if isinstance(block, FormGridBlock):
                    yield from ((column.heading_key, column.official_heading or column.key) for column in block.columns)
                    yield from ((row.heading_key, row.official_heading or row.key) for row in block.rows)
                elif isinstance(block, FormRepeatingGroupBlock):
                    yield from ((column.heading_key, column.official_heading or column.key) for column in block.columns)


@pytest.mark.parametrize("locale", _LOCALES)
def test_every_shared_column_is_translated(locale: str) -> None:
    missing = sorted(
        key
        for key in SHARED_COLUMN_KEYS
        if not lookup_translation(f"{SHARED_COLUMN_HEADING_KEY_PREFIX}.{key}", locale=locale)
    )
    assert missing == []


@pytest.mark.parametrize("locale", _LOCALES)
def test_every_named_heading_of_the_most_filed_modelos_is_translated(locale: str) -> None:
    missing = sorted(
        {key for layout in _layouts() for key, _official in _named_headings(layout)}
        - {
            key
            for layout in _layouts()
            for key, _official in _named_headings(layout)
            if lookup_translation(key, locale=locale)
        }
    )
    assert missing == []


#: Proper names and the word "Total" read the same in English and Spanish.
_SAME_IN_ENGLISH = frozenset({"total", "territorio_araba_alava", "territorio_bizkaia", "territorio_gipuzkoa"})


def test_english_column_headings_are_translations_not_echoes() -> None:
    echoed = {
        member
        for member in SHARED_COLUMN_KEYS
        if lookup_translation(f"{SHARED_COLUMN_HEADING_KEY_PREFIX}.{member}", locale="en")
        == lookup_translation(f"{SHARED_COLUMN_HEADING_KEY_PREFIX}.{member}", locale="es")
    }
    assert echoed == _SAME_IN_ENGLISH
