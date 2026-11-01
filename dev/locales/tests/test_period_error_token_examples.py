"""The period refusal names real filing-token examples in every language."""

import pytest

from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.core.period import Period, PeriodError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_period_refusal_shows_real_individual_tokens(language: OutputLanguage) -> None:
    """Examples describe token syntax without claiming a modelo supports that period."""
    with override_settings(cadrumo_output_language=language.value):
        message = tr("cli.app.modelo.work.period_token_unrecognised", **{"token": "bad", "year": "2026"})
    assert "bad" in message and "2026" in message
    for code in ("0A", "1T", "2T", "3T", "4T", "01", "12"):
        assert code in message
        assert Period.from_year_and_code(2026, code).code == code
    for invalid in ("Qn", "MM"):
        assert invalid not in message
        with pytest.raises(PeriodError):
            Period.from_year_and_code(2026, invalid)
