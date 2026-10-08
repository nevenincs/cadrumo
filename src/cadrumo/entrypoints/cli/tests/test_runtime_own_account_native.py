"""Native worker acceptance for ``app ledger account``: secret-channel entry and masked output.

Every account number below is a synthetic published example. Each command's
complete output is checked for the account number, its BBAN core and the BIC,
so a regression that echoes account material in text or JSON fails here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import UUID

import pytest

from ....application.ledger.own_account_operation import LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from ..command_specs import COMMAND_GRAPH
from .native_api_cli_support import native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_DEFINITION = LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID
_ES_IBAN = "ES9121000418450200051332"
_ES_IBAN_2 = "ES7921000813610123456789"
_TR_IBAN = "TR330006100519786457841326"
_TR_BIC = "TCZATRIS"
_SECRETS = (_ES_IBAN, _ES_IBAN[4:-4], _ES_IBAN_2, _ES_IBAN_2[4:-4], _TR_IBAN, _TR_IBAN[4:-4], _TR_BIC)
_COMMAND = ("app", "ledger", "account")


def _scope(client_id: UUID) -> AccessScope:
    return AccessScope(
        operations=frozenset({_DEFINITION}),
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
                AccessAction.COMMIT,
            },
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id="operation.observation",
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=f"{_DEFINITION}.result",
                    category=DisclosureCategory.TAX_VALUES,
                ),
            },
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _no_account_material(output: str) -> None:
    for secret in _SECRETS:
        assert secret not in output


def test_no_account_command_takes_account_material_as_an_argument() -> None:
    leaves = [spec for spec in COMMAND_GRAPH.specs if spec.parent_key == "app_ledger_account"]
    assert {spec.token for spec in leaves} == {
        "add",
        "list",
        "show",
        "update",
        "close",
        "remove",
        "designate",
        "undesignate",
    }
    names = {parameter.name for spec in leaves for parameter in spec.parameters}
    assert not names & {"iban", "swift_bic", "bank_name", "bank_address", "bank_city", "bank_country_code"}


def test_native_own_account_setup_round_trip(tmp_path: Path) -> None:
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_scope,
        prepare_profile=lambda _profile_id, _root: None,
    ) as session:

        def run(*arguments: str, stdin: dict[str, str] | None = None):
            result = session.invoke_credential_reference(
                *_COMMAND,
                *arguments,
                stdin=None if stdin is None else json.dumps(stdin),
            )
            _no_account_material(result.output)
            return result

        empty = run("list")
        assert empty.exit_code == 0, empty.output
        assert unwrap_cli_result(empty)["accounts"] == []

        invalid = run("add", "broken", "--holding", "titular", "--secrets-stdin", stdin={"iban": _ES_IBAN[:-1] + "3"})
        assert invalid.exit_code == 2, invalid.output
        assert (
            require_error_document(invalid.output)["error"]["code"] == "REFUSED_LEDGER_OWN_ACCOUNT_REGISTER_VALIDATION"
        )

        added = run("add", "main", "--holding", "titular", "--secrets-stdin", stdin={"iban": _ES_IBAN})
        assert added.exit_code == 0, added.output
        added_payload = unwrap_cli_result(added)
        assert added_payload["own_account_id"] == "acc-01"
        assert added_payload["accounts"][0]["masked_iban"] == "ES ···· 1332"

        foreign = run(
            "add",
            "lira",
            "--holding",
            "cotitular",
            "--currency",
            "TRY",
            "--secrets-stdin",
            stdin={
                "iban": _TR_IBAN,
                "swift_bic": _TR_BIC,
                "bank_name": "Synthetic Bank",
                "bank_address": "1 Example Street",
                "bank_city": "Ankara",
                "bank_country_code": "TR",
            },
        )
        assert foreign.exit_code == 0, foreign.output
        assert unwrap_cli_result(foreign)["accounts"][0]["has_bank_block"] is True

        designated = run("designate", "acc-01", "--role", "charge")
        assert designated.exit_code == 0, designated.output
        scoped = run("designate", "acc-02", "--role", "refund", "--modelo", "303")
        assert scoped.exit_code == 0, scoped.output

        shown = run("show", "acc-02")
        assert shown.exit_code == 0, shown.output
        shown_payload = unwrap_cli_result(shown)
        assert shown_payload["account"]["currency"] == "TRY"
        assert shown_payload["designations"] == [{"role": "refund", "modelo": "303", "own_account_id": "acc-02"}]

        replaced = run("update", "acc-01", "--label", "renamed", "--secrets-stdin", stdin={"iban": _ES_IBAN_2})
        assert replaced.exit_code == 0, replaced.output
        assert unwrap_cli_result(replaced)["accounts"][0]["masked_iban"] == "ES ···· 6789"
        repeated = run("update", "acc-01", "--label", "renamed")
        assert repeated.exit_code == 0, repeated.output
        assert unwrap_cli_result(repeated)["changed"] is False

        refused = run("remove", "acc-01")
        assert refused.exit_code == 2, refused.output
        assert (
            require_error_document(refused.output)["error"]["code"] == "REFUSED_LEDGER_OWN_ACCOUNT_REGISTER_VALIDATION"
        )

        closed = run("close", "acc-02", "--on", "2026-06-30")
        assert closed.exit_code == 0, closed.output
        assert unwrap_cli_result(closed)["accounts"][0]["closed_on"] == "2026-06-30"

        assert run("undesignate", "--role", "charge").exit_code == 0
        removed = run("remove", "acc-01")
        assert removed.exit_code == 0, removed.output

        listed = run("list")
        assert listed.exit_code == 0, listed.output
        payload = unwrap_cli_result(listed)
        assert [account["own_account_id"] for account in payload["accounts"]] == ["acc-02"]
        assert payload["designations"] == [{"role": "refund", "modelo": "303", "own_account_id": "acc-02"}]
