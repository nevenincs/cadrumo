"""Native profile-worker journey for registered Modelo 036 commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.core.config import override_settings
from cadrumo.tests.cli_envelope import require_error_document, unwrap_cli_result

from ...native_commands.runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from .cli_runner import invoke_cached_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Modelo 036",
    "activities.description": "design",
    "censo.activity_start_date": "2025-01-01",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


def _invoke(profile: NativeCliProfileFixture, *command: str) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_cached_cli(
            (
                "--language",
                "en",
                "--format",
                "json",
                "--profile",
                profile.label,
                "--profile-secrets-stdin",
                *command,
            ),
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
    assert profile.passphrase not in result.output
    return result


def _record_event(
    profile: NativeCliProfileFixture, kind: str, *, declared_on: str, receipt: str, note: str
) -> dict[str, Any]:
    """Record one censal declaration event; the result echoes its dates and receipt but never its note."""
    recorded = _invoke(
        profile,
        "app",
        "modelo",
        "m036",
        kind,
        "--declared-on",
        declared_on,
        "--sede-justificante",
        receipt,
        "--note",
        note,
    )
    assert recorded.exit_code == 0, recorded.output
    result = unwrap_cli_result(recorded)
    assert result["event_kind"] == kind
    assert result["declared_on"] == declared_on
    assert result["sede_justificante"] == receipt
    assert result["note"] is None
    declaration_id = result["declaration_id"]
    assert isinstance(declaration_id, str) and len(declaration_id) == 64
    return result


def _list_returns_each_recorded_event(
    profile: NativeCliProfileFixture, recorded: dict[str, tuple[dict[str, Any], str]]
) -> list[dict[str, Any]]:
    """The listing holds exactly the recorded events, sorted by id, with their stored notes."""
    listed = _invoke(profile, "app", "modelo", "m036", "list")
    assert listed.exit_code == 0, listed.output
    list_result = unwrap_cli_result(listed)
    assert list_result["declaration_count"] == 3
    rows = list_result["declarations"]
    assert [row["declaration_id"] for row in rows] == sorted(entry[0]["declaration_id"] for entry in recorded.values())
    for row in rows:
        record, note = recorded[row["event_kind"]]
        assert row["declaration_id"] == record["declaration_id"]
        assert row["bucket_id"] == record["bucket_id"]
        assert row["profile_id"] == record["profile_id"]
        assert row["declared_on"] == record["declared_on"]
        assert row["recorded_at"] == record["recorded_at"]
        assert row["sede_justificante"] == record["sede_justificante"]
        assert row["note"] == note
    return rows


def _view_matches_the_listed_row(profile: NativeCliProfileFixture, alta_id: str, rows: list[dict[str, Any]]) -> None:
    viewed = _invoke(profile, "app", "modelo", "m036", "view", alta_id)
    assert viewed.exit_code == 0, viewed.output
    view_result = unwrap_cli_result(viewed)
    assert view_result["declaration_id"] == alta_id
    assert view_result["event_kind"] == "alta"
    alta_row = next(row for row in rows if row["declaration_id"] == alta_id)
    assert view_result["bucket_id"] == alta_row["bucket_id"]
    assert view_result["profile_id"] == alta_row["profile_id"]
    assert view_result["declared_on"] == alta_row["declared_on"]
    assert view_result["recorded_at"] == alta_row["recorded_at"]
    assert view_result["sede_justificante"] == alta_row["sede_justificante"]
    assert view_result["note"] == "Alta note"


def _viewing_an_unknown_declaration_is_refused(profile: NativeCliProfileFixture) -> None:
    missing = _invoke(profile, "app", "modelo", "m036", "view", "0" * 64)
    assert missing.exit_code != 0, missing.output
    error = require_error_document(missing.output)["error"]
    context = error["context"]
    assert error["category"] == "REFUSED"
    assert context["reason"] == "REFUSED_M036_DECLARATION_NOT_FOUND"
    assert context["refusal_code"] == "REFUSED_M036_DECLARATION_NOT_FOUND"
    assert context["terminal_condition"] == "refused"
    assert context["effect"] == "none"
    assert context["operation_id"]
    assert context["value"] == "0" * 64


def test_native_m036_five_commands_round_trip_real_worker_records(tmp_path: Path) -> None:
    """All five public commands use the installed worker and retain canonical fields."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-m036-operation", facts=_PROFILE_FACTS)

        alta = _record_event(profile, "alta", declared_on="2025-01-01", receipt="receipt-alta", note="Alta note")
        modificacion = _record_event(
            profile,
            "modificacion",
            declared_on="2025-03-01",
            receipt="receipt-modificacion",
            note="Modification note",
        )
        baja = _record_event(profile, "baja", declared_on="2026-01-01", receipt="receipt-baja", note="Baja note")
        rows = _list_returns_each_recorded_event(
            profile,
            {
                "alta": (alta, "Alta note"),
                "modificacion": (modificacion, "Modification note"),
                "baja": (baja, "Baja note"),
            },
        )
        _view_matches_the_listed_row(profile, alta["declaration_id"], rows)
        _viewing_an_unknown_declaration_is_refused(profile)
