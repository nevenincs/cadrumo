"""The counterparty country must be stated, never assumed to be Spain.

Domesticity is decided on ``counterparty_country``: the Modelo 303 invoice
screen reads it and nothing else, and the country also routes both informativas.
An unstated country resolving to ``ES`` therefore does not merely leave a field
blank -- it silently enlarges the domestic population, which is an undeclared
fact defaulting to the reading that declares more.

The CLI option that feeds this entry point is already required and says so in
its own help text. The application function carried a default anyway. Nothing
reached it: the one production caller passes the value explicitly and no test
called the function at all, so the default was unreachable rather than
load-bearing. That is exactly the state in which a default is worth removing --
free to close now, and a live fail-open the moment some future caller omits the
argument and gets Spain without asking for it.

Asserted on the SIGNATURE rather than through a call, because the property is
"no default exists" and a call cannot show the absence of one. A behavioural
test would pass equally well against a function that defaults to ``ES``, since
every real caller passes the value.
"""

from __future__ import annotations

import inspect

import pytest

from ..creation_wizard import create_invoice_via_wizard

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_the_wizard_requires_a_stated_counterparty_country() -> None:
    """No default, so omitting the country is a caller error rather than Spain."""
    parameter = inspect.signature(create_invoice_via_wizard).parameters["country_code"]

    assert parameter.default is inspect.Parameter.empty, (
        f"country_code has regained a default ({parameter.default!r}). An unstated counterparty "
        "country must stay unstated: it decides domesticity for the Modelo 303 invoice screen, so "
        "defaulting it to Spain declares operations domestic that nobody said were domestic"
    )
