"""Owning contract probes extracted from native integration scenarios."""

from __future__ import annotations

import pytest
import typer

from cadrumo.core.config import override_settings
from cadrumo.core.i18n.render import clear_output_language_cache, tr

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("locale", ("ca", "en", "es", "hu"))
def test_llm_diagnostics_date_parser_uses_catalogue_leaf(locale: str) -> None:
    """The command's existing date parser retains the localized message leaf."""
    from cadrumo.entrypoints.cli.ledger_read_commands import _parse_iso_date

    with override_settings(cadrumo_output_language=locale):
        clear_output_language_cache()
        expected = tr(
            "cli.ledger.llm_diagnostics.bad_date",
            option="--since",
            value="not-a-date",
        )
        with pytest.raises(typer.BadParameter) as error:
            _parse_iso_date("not-a-date", "--since")
    clear_output_language_cache()

    assert error.value.message == expected
