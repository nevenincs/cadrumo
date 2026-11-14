"""Every family of carry statements the registry can declare has its words in every output language.

A binding names its family in the registry, and the form words the action,
the statement and the per-carry effect from it. A family without words would
leave the whole declaration's form unloadable, so each one must resolve to
authored text in every catalogue, distinct across languages. A form-wide
family also words the field's origin; a family stated row by row is offered
once per row instead and words the row it names by its number.
"""

from __future__ import annotations

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation, tr
from ....domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PREFIX = "application.modelo.work_form.carry_attestation"


def _assert_worded(key: str) -> None:
    worded = {language: lookup_translation(key, locale=language.value) for language in OutputLanguage}
    assert all(words is not None for words in worded.values()), (key, worded)
    assert len(set(worded.values())) == len(worded), (key, worded)


@pytest.mark.parametrize("family", tuple(family for family in AbsenceAttestationFamily if not family.row_grain))
def test_every_form_wide_statement_family_is_worded_in_every_language(family: AbsenceAttestationFamily) -> None:
    for part in ("action", "statement", "effect", "origin"):
        _assert_worded(f"{_PREFIX}.{family.value}.{part}")


@pytest.mark.parametrize("family", tuple(family for family in AbsenceAttestationFamily if family.row_grain))
def test_every_row_statement_family_is_worded_in_every_language_and_names_its_row(
    family: AbsenceAttestationFamily,
) -> None:
    for part in ("action", "statement", "effect", "row"):
        _assert_worded(f"{_PREFIX}.{family.value}.{part}")
    rows = {
        language: tr(f"{_PREFIX}.{family.value}.row", number=2, locale=language.value) for language in OutputLanguage
    }
    assert all("2" in words and "{" not in words for words in rows.values()), rows
    assert tr(f"{_PREFIX}.{family.value}.row", number=1, locale="en") != rows[OutputLanguage.EN]
