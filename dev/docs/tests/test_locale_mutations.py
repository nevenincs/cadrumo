"""Regression checks for the owning documentation catalogue serializer."""

from __future__ import annotations

import io

import pytest
from babel.messages.catalog import Catalog, Message
from babel.messages.pofile import read_po

from ..locale_catalogue_io import _render_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


@pytest.mark.parametrize("translation", ["Presentació", "Presentació\n"])
@pytest.mark.parametrize("with_obsolete", [False, True])
def test_catalogue_has_one_final_newline_without_changing_translation(translation: str, *, with_obsolete: bool) -> None:
    """Babel's separator must not become a blank EOF or trim message data."""
    catalogue = Catalog(locale="ca")
    catalogue.add("Filing", translation)
    if with_obsolete:
        catalogue.obsolete["Previous filing"] = Message("Previous filing", "Presentació anterior\n")

    rendered = _render_catalogue(catalogue)
    restored = read_po(io.BytesIO(rendered.encode("utf-8")))

    assert rendered.endswith("\n")
    assert not rendered.endswith("\n\n")
    assert restored["Filing"].string == translation
    if with_obsolete:
        assert restored.obsolete["Previous filing"].string == "Presentació anterior\n"
