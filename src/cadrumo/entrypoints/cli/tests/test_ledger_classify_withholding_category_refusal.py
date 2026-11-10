"""``ledger classify`` of a net-of-withholding invoice says what is missing, in the operator's language.

The refusal is the one the window serves for the same movement: the shared
classify operation returns a typed refusal, and the command words it from the
catalogue and attaches the recovery action resolved from the live command tree.
Every case drives the real ``aeat app ledger`` CLI against an isolated profile
bucket through the real persistence stack.
"""

from __future__ import annotations

import json
import re

import pytest

from ....application.ledger.staged_check_words import BLOCKER_FIX_LOCALE_KEYS
from ....core.i18n.render import tr
from ....domain.transactions.gross_validation import (
    GROSS_NEEDS_WITHHOLDING_CATEGORY_FIELD,
    GROSS_NEEDS_WITHHOLDING_CATEGORY_LOCALE_KEY,
)
from .cli_fixture_worlds import invoke_joined_cli as invoke_cached_cli
from .profile_world_fixtures import recorded_fx_isolated_backend

__all__ = ["recorded_fx_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# A received invoice of 2000.00 plus 420.00 IVA, settled net of a 300.00 withholding.
_CASH = "2120.00"
_ACTIVITY_CATEGORY = "actividad_economica"


def _add_received_row() -> str:
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-05-02",
            "--amount",
            _CASH,
            "--direction",
            "INCOMING",
            "--description",
            "FACTURA 2026-04",
            "--counterparty",
            "Cliente SL",
            "--idempotency-key",
            "withholding-row",
        ],
    )
    assert result.exit_code == 0, result.output
    transaction_id = json.loads(result.output)["result"]["transaction_id"]
    assert isinstance(transaction_id, str)
    return transaction_id


def _classify(transaction_id: str, *extra: str, language: str = "en", as_json: bool = False):
    arguments = ["--language", language]
    if as_json:
        arguments += ["--format", "json"]
    return invoke_cached_cli(
        [
            *arguments,
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "2000",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "420",
            *extra,
        ],
    )


def _words(text: str) -> str:
    return re.sub(r"\s+", " ", text)


@pytest.mark.parametrize("language", ["en", "es", "ca", "hu"])
def test_a_net_of_withholding_invoice_is_refused_in_the_catalogue_words_of_the_language(language: str) -> None:
    transaction_id = _add_received_row()

    refused = _classify(transaction_id, language=language)

    assert refused.exit_code != 0
    output = _words(refused.output)
    assert _words(tr(GROSS_NEEDS_WITHHOLDING_CATEGORY_LOCALE_KEY, locale=language)) in output
    assert _words(tr(BLOCKER_FIX_LOCALE_KEYS["needs_withholding_category"], locale=language)) in output
    for internal in ("taxable_base", "iva_amount", "recargo_amount", "!="):
        assert internal not in output


def test_the_refusal_carries_the_irpf_category_remedy_from_the_command_tree() -> None:
    transaction_id = _add_received_row()

    refused = _classify(transaction_id, as_json=True)

    assert refused.exit_code != 0
    action = json.loads(refused.output)["error"]["action"]
    assert action is not None, refused.output
    assert action["action"]["target_command_key"] == "ledger.classify"
    assert action["action"]["cli_path"] == ["aeat", "app", "ledger", "classify"]
    assert action["action"]["action_id"] == "operator.ledger.classify.irpf_category"
    assert action["missing_argument_names"] == [GROSS_NEEDS_WITHHOLDING_CATEGORY_FIELD]
    bound = {item["argument_name"]: item["value"] for item in action["argument_bindings"]}
    assert bound["transaction_id"] == transaction_id


def test_a_gap_no_category_explains_stays_refused_without_the_remedy() -> None:
    transaction_id = _add_received_row()

    refused = invoke_cached_cli(
        [
            "--language",
            "en",
            "--format",
            "json",
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "1000",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "210",
        ],
    )

    assert refused.exit_code != 0
    error = json.loads(refused.output)["error"]
    assert error["action"] is None or error["action"]["action"] is None
    assert _words(tr(GROSS_NEEDS_WITHHOLDING_CATEGORY_LOCALE_KEY, locale="en")) not in _words(refused.output)


def test_naming_the_category_classifies_the_same_invoice() -> None:
    transaction_id = _add_received_row()

    classified = _classify(transaction_id, "--irpf-category", _ACTIVITY_CATEGORY, as_json=True)

    assert classified.exit_code == 0, classified.output
    transaction = json.loads(classified.output)["result"]["transaction"]
    assert transaction["irpf_category"] == _ACTIVITY_CATEGORY
    assert transaction["taxable_base"] == "2000"
