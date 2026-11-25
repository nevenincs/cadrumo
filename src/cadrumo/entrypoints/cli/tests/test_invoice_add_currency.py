"""The invoice add command folds a typed currency to its ISO 4217 code at the boundary, or refuses it.

The request takes only an upper-case three-letter code; the command line keeps
accepting ``eur`` by folding it before it builds the request, and refuses what no
folding makes a code, naming its option, in the served rule-finding words.
"""

from __future__ import annotations

import pytest
import typer

from ....core.i18n.render import tr
from ..ledger_business_invoice_commands import _invoice_currency

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(("typed", "code"), [("eur", "EUR"), (" usd ", "USD"), ("GBP", "GBP")])
def test_a_typed_currency_folds_to_its_code(typed: str, code: str) -> None:
    assert _invoice_currency(typed) == code


@pytest.mark.parametrize("typed", ["EURO", "€", "EU", "E1R"])
def test_a_currency_no_folding_makes_a_code_is_refused_naming_its_option(typed: str) -> None:
    with pytest.raises(typer.BadParameter) as refused:
        _invoice_currency(typed)

    message = str(refused.value)
    assert "--currency" in message
    assert tr("application.invoices.figures_preview.rule_finding.currency_invalid") in message
