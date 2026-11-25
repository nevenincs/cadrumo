"""The form heads its withholding credits by who withheld them, as its register bindings say.

A credit fed by the retención soportada register is withholding taken from the
filer's own income (Modelo 100). A credit fed by the retenciones a cuenta or
withholding register is withholding the filer took from others and pays in
(Modelos 111 and 115). A form with no register credit serves no heading.
"""

from __future__ import annotations

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from .work_form_fixture import built_form

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_SUFFERED = "application.modelo.work_form.credits_heading.suffered"
_PRACTISED = "application.modelo.work_form.credits_heading.practised"


@pytest.mark.parametrize(
    ("modelo", "period", "key"),
    [("100", "0A", _SUFFERED), ("111", "1T", _PRACTISED), ("115", "1T", _PRACTISED), ("130", "1T", None)],
)
@pytest.mark.parametrize("language", list(OutputLanguage))
def test_the_credits_heading_says_who_withheld(
    operation: PinnedAuthorityOperation, modelo: str, period: str, key: str | None, language: OutputLanguage
) -> None:
    year = operation.supported_filing_years().horizon
    form = built_form(operation, modelo, year, period, language=language)

    assert bool(form.withholding_credits) is (key is not None), modelo
    assert form.withholding_credits_heading == (None if key is None else tr(key, locale=language.value))
