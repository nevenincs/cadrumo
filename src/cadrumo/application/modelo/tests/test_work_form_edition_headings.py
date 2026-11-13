"""Every supported year's form names its pages and sections from the catalogue, in each language.

A heading counts as named when the work form discloses it as ``LOCALIZED``:
the text came from a catalogue key in the requested language, either the
edition's own key or the modelo-wide key every edition shares. The design's
untranslated Spanish words (``OFFICIAL_SPANISH``), a Spanish catalogue text
served in another language (``SPANISH_FALLBACK``) and the part's id
(``TECHNICAL``) do not count. The years are the registry's support envelope,
so a year projected from the nearest edition is checked as well.
"""

from __future__ import annotations

import pytest

from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..work_form_field_vocabulary import ModeloFormTextDisclosure
from ..work_form_models import ModeloWorkForm
from .work_form_fixture import built_form

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_ANNUAL = "0A"


def _unnamed_parts(form: ModeloWorkForm) -> list[str]:
    unnamed = [
        f"page {page.id}: {page.heading.disclosure.value} {page.heading.text!r}"
        for page in form.pages
        if page.heading.disclosure is not ModeloFormTextDisclosure.LOCALIZED
    ]
    unnamed += [
        f"section {section.id}: {section.heading.disclosure.value} {section.heading.text!r}"
        for page in form.pages
        for section in page.sections
        if section.heading.disclosure is not ModeloFormTextDisclosure.LOCALIZED
    ]
    return unnamed


@pytest.mark.parametrize("modelo", ["100", "296"])
@pytest.mark.parametrize("language", list(OutputLanguage))
def test_every_supported_year_names_each_page_and_section_in_the_language(
    operation: PinnedAuthorityOperation, modelo: str, language: OutputLanguage
) -> None:
    years = filing_year_envelope().years
    unnamed = {
        year: parts
        for year in years
        if (parts := _unnamed_parts(built_form(operation, modelo, year, _ANNUAL, language=language)))
    }

    assert years
    assert unnamed == {}
