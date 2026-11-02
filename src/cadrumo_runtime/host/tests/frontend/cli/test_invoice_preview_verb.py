"""The invoice preview verb answers a draft through one authenticated profile worker."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.core.i18n.render import tr
from cadrumo.tests.cli_envelope import unwrap_cli_result
from cadrumo_runtime.host.tests.native_commands.runtime_profile_cli_fixture import (
    NativeCliProfileFixture,
    native_cli_profile_scope,
)

from ...native_profile_facts import native_general_iva_facts
from .cli_runner import invoke_cached_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_PROFILE_FACTS = native_general_iva_facts(surnames="Preview", description="synthetic invoice preview profile")

_COMPLETE_DRAFT = (
    "--kind",
    "received",
    "--counterparty-name",
    "Synthetic supplier",
    "--counterparty-nif",
    "A58818501",
    "--country-code",
    "ES",
    "--invoice-number",
    "PREVIEW-2026-001",
    "--invoice-date",
    "2026-04-15",
    "--currency",
    "EUR",
)


def _line(**figures: str) -> str:
    return json.dumps({"description": "Synthetic service", "quantity": "1", "unit_price": "100.00", **figures})


def _invoke(profile: NativeCliProfileFixture, *command: str, language: str = "en", output: str = "json") -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    profile_secret = json.dumps({"profile_passphrase": profile.passphrase})
    result = invoke_cached_cli(
        ["--language", language, "--format", output, "--profile", profile.label, "--profile-secrets-stdin", *command],
        input=profile_secret,
    )
    assert profile.passphrase not in result.output
    return result


def test_a_hundred_at_twenty_one_percent_previews_twenty_one_of_iva_and_stores_nothing(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-invoice-preview", facts=_PROFILE_FACTS)

        previewed = _invoke(
            profile,
            "app",
            "ledger",
            "invoice",
            "preview",
            *_COMPLETE_DRAFT,
            "--line",
            _line(iva_rate="RATE_21"),
        )

        assert previewed.exit_code == 0, previewed.output
        answer = unwrap_cli_result(previewed)
        # 100.00 * 0.21 = 21.00 of IVA, and 100.00 + 21.00 = 121.00 in all.
        assert answer["verdict"] == "would_accept"
        assert answer["refusal_code"] is None
        assert answer["invoice_id"]
        assert answer["missing_fields"] == []
        assert answer["findings"] == []
        assert (answer["totals"]["base"], answer["totals"]["iva"], answer["totals"]["total"]) == (
            "100.00",
            "21.00",
            "121.00",
        )
        assert answer["lines"][0]["subtotal"]["computed"] == "100.00"
        assert answer["lines"][0]["iva_amount"]["computed"] == "21.00"
        assert answer["on_date"] == "2026-04-15"
        assert answer["on_date_source"] == "issued_at"
        slots = {slot["slot"]: slot for slot in answer["rate_slots"]}
        assert slots["RATE_21"]["fraction"] == "0.21"
        assert all(tr(slot["label_key"]) != slot["label_key"] for slot in slots.values())

        listed = _invoke(profile, "app", "ledger", "invoice", "list")
        assert listed.exit_code == 0, listed.output
        assert unwrap_cli_result(listed)["rows"] == []


def test_a_stated_cuota_that_disagrees_is_refused_with_the_backends_figure(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-invoice-preview-refusal", facts=_PROFILE_FACTS)

        previewed = _invoke(
            profile,
            "app",
            "ledger",
            "invoice",
            "preview",
            *_COMPLETE_DRAFT,
            "--line",
            _line(iva_rate="RATE_21", iva_amount="20.00"),
        )

        assert previewed.exit_code == 0, previewed.output
        answer = unwrap_cli_result(previewed)
        assert answer["verdict"] == "would_refuse"
        assert answer["refusal_code"] == "line_iva_mismatch"
        assert answer["invoice_id"] is None
        figure = answer["lines"][0]["iva_amount"]
        assert (figure["computed"], figure["stated"]) == ("21.00", "20.00")
        assert [(item["code"], item["severity"]) for item in answer["findings"]] == [("line_iva_mismatch", "refusal")]

        worded = _invoke(
            profile,
            "app",
            "ledger",
            "invoice",
            "preview",
            *_COMPLETE_DRAFT,
            "--line",
            _line(iva_rate="RATE_21", iva_amount="20.00"),
            output="text",
        )
        assert worded.exit_code == 0, worded.output
        assert "verdict\twould_refuse" in worded.output
        assert (
            "The stated IVA amount, 20.00, differs by more than a cent from the subtotal times the rate, 21.0000."
            in worded.output
        ), worded.output


def test_a_bare_draft_is_incomplete_and_invents_no_figure(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-invoice-preview-empty", facts=_PROFILE_FACTS)

        previewed = _invoke(profile, "app", "ledger", "invoice", "preview")

        assert previewed.exit_code == 0, previewed.output
        answer = unwrap_cli_result(previewed)
        assert answer["verdict"] == "incomplete"
        assert "lines" in answer["missing_fields"]
        assert answer["totals"] == {"base": None, "iva": None, "recargo": None, "total": None, "net_of_retention": None}
        assert answer["invoice_id"] is None


def test_a_rule_refusal_names_itself_and_a_correction_serves_what_is_left_to_pay(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-invoice-preview-rules", facts=_PROFILE_FACTS)

        rectificativa = _invoke(
            profile,
            "app",
            "ledger",
            "invoice",
            "preview",
            *_COMPLETE_DRAFT,
            "--invoice-class",
            "RECTIFICATIVA",
            "--line",
            _line(iva_rate="RATE_21"),
        )
        assert rectificativa.exit_code == 0, rectificativa.output
        refused = unwrap_cli_result(rectificativa)
        assert (refused["verdict"], refused["refusal_code"]) == ("would_refuse", "invalid_invoice")
        assert [item["code"] for item in refused["rule_findings"]] == [
            "series_required_for_rectificativa",
            "rectified_invoice_required",
        ]
        assert all(tr(item["label_key"]) != item["label_key"] for item in refused["rule_findings"])

        # 1000.00 x 0.07 = 70.00 of retención, so 1210.00 stored - 70.00 = 1140.00 is left to pay.
        corrected = _invoke(
            profile,
            "app",
            "ledger",
            "invoice",
            "preview",
            "--kind",
            "issued",
            "--invoice-class",
            "ORDINARIA",
            "--counterparty-nif",
            "A58818501",
            "--country-code",
            "ES",
            "--invoice-date",
            "2026-04-15",
            "--taxable-base",
            "1000.00",
            "--retention-rate",
            "0.07",
            "--retention-amount",
            "70.00",
            "--stored-invoice-id",
            "f" * 64,
            "--stored-grand-total",
            "1210.00",
        )
        assert corrected.exit_code == 0, corrected.output
        answer = unwrap_cli_result(corrected)
        assert (answer["verdict"], answer["verdict_scope"]) == ("would_accept", "correction_facts")
        assert answer["invoice_id"] == "f" * 64
        assert answer["totals"]["net_of_retention"] == "1140.00"
