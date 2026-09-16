"""A foreign-currency statement imports against the live ECB reference rates.

Lane suites convert against recorded ECB answers. This is the one CLI import
that binds the live provider, the way the ``aeat`` console script does, so the
real transport and the published series stay exercised end to end.
"""

from __future__ import annotations

import json

import pytest

from ....adapters.outbound.fx.ecb_provider import default_ecb_rate_provider
from ....application.exchange_rate_provider import bind_exchange_rate_provider_factory
from ....tests.live_gate import requires_live_enabled
from ._isolated_profile_storage_fixtures import recorded_fx_isolated_backend
from ._ledger_corpus_support import _CORPUS, _invoke
from .ledger_cli import list_ledger_rows_via_cli as _list_rows

__all__ = ["recorded_fx_isolated_backend"]

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_entrypoint]

_MULTI_CURRENCY_STATEMENT = "revolut-multi.csv"


def test_a_multi_currency_statement_converts_against_the_live_series() -> None:
    requires_live_enabled()

    with bind_exchange_rate_provider_factory(default_ecb_rate_provider):
        result = _invoke(
            [
                "--format",
                "json",
                "app",
                "ledger",
                "import",
                "--file",
                str(_CORPUS / _MULTI_CURRENCY_STATEMENT),
                "--provider",
                "csv",
            ],
        )
        rows = _list_rows()

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["result"]["imported"] > 0
    foreign = [row for row in rows if row.get("currency") not in (None, "EUR")]
    assert foreign, "the statement must carry foreign-currency rows for this test to reach the ECB"
    assert all(row.get("value_in_eur") not in (None, "") for row in foreign), foreign[:2]
