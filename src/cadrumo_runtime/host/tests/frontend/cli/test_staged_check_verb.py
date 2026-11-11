"""The staged check verb answers staged cells through one authenticated profile worker and stores nothing."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.tests.cli_envelope import unwrap_cli_result
from cadrumo_runtime.host.tests.native_commands.runtime_profile_cli_fixture import (
    NativeCliProfileFixture,
    native_cli_profile_scope,
)

from ...native_profile_facts import native_general_iva_facts
from .cli_runner import invoke_cached_cli
from .machine_secret_pipe import machine_secret_descriptor_option

_YEAR = filing_year_envelope().horizon

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_PROFILE_FACTS = native_general_iva_facts()


def _invoke(profile: NativeCliProfileFixture, *command: str, secrets: dict[str, str] | None = None) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    profile_secret = json.dumps({"profile_passphrase": profile.passphrase})
    channel = () if secrets is None else machine_secret_descriptor_option(secrets)
    result = invoke_cached_cli(
        [
            *("--language", "en", "--format", "json", "--profile", profile.label, "--profile-secrets-stdin"),
            *command,
            *channel,
        ],
        input=profile_secret,
    )
    assert profile.passphrase not in result.output
    return result


def _add_outgoing(profile: NativeCliProfileFixture) -> str:
    added = _invoke(
        profile,
        *("app", "ledger", "add", "--date", date(_YEAR, 2, 10).isoformat(), "--amount", "60.50"),
        *("--direction", "OUTGOING", "--description", "phone bill"),
    )
    assert added.exit_code == 0, added.output
    transaction_id = unwrap_cli_result(added)["transaction_id"]
    assert isinstance(transaction_id, str)
    return transaction_id


def _row(transaction_id: str, **cells: str | None) -> str:
    return json.dumps({"transaction_id": transaction_id, "cells": [{"field": k, "value": v} for k, v in cells.items()]})


def test_staged_cells_are_answered_and_nothing_is_written(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-staged-check", facts=_PROFILE_FACTS)
        transaction_id = _add_outgoing(profile)

        checked = _invoke(
            profile,
            *("app", "ledger", "staged-check"),
            secrets={
                "rows": json.dumps(
                    [
                        json.loads(_row(transaction_id, business_classification="MIXED", notes=None, amount="61.00")),
                        json.loads(_row("0" * 64, notes="unknown row")),
                    ]
                ),
                "drafts": json.dumps([{"key": "new", "fields": [{"field": "amount", "value": "1.00"}]}]),
            },
        )

        assert checked.exit_code == 0, checked.output
        answer = unwrap_cli_result(checked)
        row, unknown = answer["rows"]
        assert unknown["found"] is False
        assert row["found"] is True
        # Staged Mixed makes the row classified, so the bulk takes the classification; no write can blank notes;
        # an amount only an update takes; Mixed without a share is held back; a new amount is a new identity.
        assert {item["field"]: (item["route"], item["refused"]) for item in row["routes"]} == {
            "business_classification": ("bulk", None),
            "notes": (None, "cannot_clear"),
            "amount": ("update", None),
        }
        assert {item["kind"] for item in row["blockers"]} == {"cannot_clear", "mixed_needs_share"}
        assert row["identity_fields"] == ["amount"]
        assert row["takes_expense_category"] is True
        # The row is unclassified as stored, but the Mixed staged travels in the same write, so a category can be set.
        assert row["category_settable"] is True
        assert answer["drafts"][0]["blockers"][0]["fields"] == ["booked_date", "currency", "direction", "description"]

        listed = _invoke(profile, "app", "ledger", "list")
        assert listed.exit_code == 0, listed.output
        rows = unwrap_cli_result(listed)["rows"]
        assert [item["transaction_id"] for item in rows] == [transaction_id]


def test_a_staged_row_on_the_command_line_is_refused_as_an_unknown_option(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-staged-check-argv", facts=_PROFILE_FACTS)

        refused = _invoke(profile, "app", "ledger", "staged-check", "--row", _row("0" * 64, notes="private"))

        assert refused.exit_code != 0
        assert "Unknown option '--row'" in refused.output
