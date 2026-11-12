"""Every form-wide family of carry statements the registry can declare has its words in every output language.

A binding names its family in the registry, and the form words the action,
the statement, the per-carry effect and the field's origin from it. A family
without words would leave the whole declaration's form unloadable, so each one
must resolve to authored text in every catalogue, distinct across languages. A
family stated row by row is answered per row through its edit address and has
no form-wide words.
"""

from __future__ import annotations

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("family", tuple(family for family in AbsenceAttestationFamily if not family.row_grain))
def test_every_statement_family_is_worded_in_every_language(family: AbsenceAttestationFamily) -> None:
    for part in ("action", "statement", "effect", "origin"):
        key = f"application.modelo.work_form.carry_attestation.{family.value}.{part}"
        worded = {language: lookup_translation(key, locale=language.value) for language in OutputLanguage}
        assert all(words is not None for words in worded.values()), (key, worded)
        assert len(set(worded.values())) == len(worded), (key, worded)
