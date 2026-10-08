"""Native worker acceptance for private counterparty facts and grants."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import UUID

import pytest

from ....application.ledger.counterparty_operation import LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....core.period import Period
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from .native_api_cli_support import native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_IDENTIFIER = "B12345674"
_DEFINITION = LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID


def _scope(client_id: UUID, *, commit: bool, finite_period: bool = False) -> AccessScope:
    actions = {
        AccessAction.SUBMIT,
        AccessAction.START,
        AccessAction.RESUME,
        AccessAction.OBSERVE,
        AccessAction.RESULT,
        AccessAction.CANCEL,
        AccessAction.DETACH,
    }
    if commit:
        actions.add(AccessAction.COMMIT)
    return AccessScope(
        operations=frozenset({_DEFINITION}),
        actions=frozenset(actions),
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
            }
        ),
        periods=frozenset({Period.from_year_and_code(2025, "1T")}) if finite_period else None,
        allow_period_independent=not finite_period,
        allow_delegation=False,
    )


def test_native_counterparty_confirm_view_withdraw_and_retry(tmp_path: Path) -> None:
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=lambda client_id: _scope(client_id, commit=True),
        prepare_profile=lambda _profile_id, _root: None,
    ) as session:
        command = ("app", "ledger", "counterparty")
        unanswered = session.invoke_credential_reference(*command, "view", _IDENTIFIER)
        assert unanswered.exit_code == 0, unanswered.output
        assert unwrap_cli_result(unanswered)["confirmed"] is False
        assert unwrap_cli_result(unanswered)["territorial_scope"] is None

        empty_assertion = session.invoke_credential_reference(*command, "confirm", _IDENTIFIER)
        assert empty_assertion.exit_code == 2
        invalid_enum = session.invoke_credential_reference(*command, "confirm", _IDENTIFIER, "--scope", "canarias")
        assert invalid_enum.exit_code == 2

        confirmed = session.invoke_credential_reference(*command, "confirm", _IDENTIFIER, "--scope", "es_canarias")
        assert confirmed.exit_code == 0, confirmed.output
        assert unwrap_cli_result(confirmed)["recorded"] is True

        repeated = session.invoke_credential_reference(*command, "confirm", _IDENTIFIER, "--scope", "es_canarias")
        assert repeated.exit_code == 0, repeated.output
        assert unwrap_cli_result(repeated)["recorded"] is False

        amended_note = session.invoke_credential_reference(
            *command, "confirm", _IDENTIFIER, "--scope", "es_canarias", "--note", "Reviewed evidence"
        )
        assert amended_note.exit_code == 0, amended_note.output
        assert unwrap_cli_result(amended_note)["recorded"] is False

        conflict = session.invoke_credential_reference(*command, "confirm", _IDENTIFIER, "--scope", "es_mainland")
        assert conflict.exit_code == 2, conflict.output
        assert (
            require_error_document(conflict.output)["error"]["code"]
            == "REFUSED_LEDGER_COUNTERPARTY_ESTABLISHMENT_CONFLICT"
        )

        viewed = session.invoke_credential_reference(*command, "view", _IDENTIFIER, "--evidenced-scope", "es_mainland")
        assert viewed.exit_code == 0, viewed.output
        payload = unwrap_cli_result(viewed)
        assert payload["contradicted"] is True
        assert payload["territorial_scope"] is None
        assert payload["confirmed_scope"] == "es_canarias"
        assert any(
            notice["code"] == "ledger.counterparty.evidence_contradicts_confirmation"
            and notice["severity"] == "warning"
            for notice in json.loads(viewed.output)["notices"]
        )

        agreed = session.invoke_credential_reference(*command, "view", _IDENTIFIER, "--evidenced-scope", "es_canarias")
        assert agreed.exit_code == 0, agreed.output
        assert unwrap_cli_result(agreed)["territorial_scope"] == "es_canarias"
        assert unwrap_cli_result(agreed)["contradicted"] is False

        withdrawn = session.invoke_credential_reference(*command, "withdraw", _IDENTIFIER)
        assert withdrawn.exit_code == 0, withdrawn.output
        assert unwrap_cli_result(withdrawn)["withdrawn"] is True
        repeated_withdrawal = session.invoke_credential_reference(*command, "withdraw", _IDENTIFIER)
        assert repeated_withdrawal.exit_code == 0, repeated_withdrawal.output
        assert unwrap_cli_result(repeated_withdrawal)["withdrawn"] is False

        identified = session.invoke_credential_reference(
            *command, "confirm", _IDENTIFIER, "--identification-state", "de"
        )
        assert identified.exit_code == 0, identified.output
        assert unwrap_cli_result(identified)["recorded"] is True
        repeated_identification = session.invoke_credential_reference(
            *command, "confirm", _IDENTIFIER, "--identification-state", "de"
        )
        assert repeated_identification.exit_code == 0, repeated_identification.output
        assert unwrap_cli_result(repeated_identification)["recorded"] is False
        identified_view = session.invoke_credential_reference(*command, "view", _IDENTIFIER)
        assert identified_view.exit_code == 0, identified_view.output
        assert unwrap_cli_result(identified_view)["identification_state"] == "de"
        assert unwrap_cli_result(identified_view)["territorial_scope"] is None


@pytest.mark.parametrize(
    ("finite_period", "commit"),
    [(True, True), (False, False)],
    ids=["finite-period", "missing-commit"],
)
def test_native_counterparty_denies_finite_period_and_missing_commit(
    tmp_path: Path, *, finite_period: bool, commit: bool
) -> None:
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=lambda client_id: _scope(client_id, commit=commit, finite_period=finite_period),
        prepare_profile=lambda _profile_id, _root: None,
    ) as session:
        result = session.invoke_credential_reference(
            "app", "ledger", "counterparty", "confirm", _IDENTIFIER, "--scope", "es_canarias"
        )
        assert result.exit_code == 2, result.output
        error = require_error_document(result.output)["error"]
        if finite_period:
            assert error["code"] in {"REFUSED_CLI_BOUNDARY", "REFUSED_RUNTIME_FRONTEND"}
            assert error["context"]["reason"] == "period_denied"
        else:
            assert error["code"] == "REFUSED_PROFILE_ACCESS"
            assert error["context"]["reason"] in {"operation_denied", "REFUSED_PROFILE_ACCESS"}
            untouched = session.invoke_credential_reference("app", "ledger", "counterparty", "view", _IDENTIFIER)
            assert untouched.exit_code == 0, untouched.output
            assert unwrap_cli_result(untouched)["confirmed"] is False
