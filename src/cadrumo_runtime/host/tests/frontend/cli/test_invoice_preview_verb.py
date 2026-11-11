"""The invoice preview verb answers a draft through one authenticated profile worker."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.core.i18n.render import tr
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

_COMPLETE_DRAFT = (
    "--kind",
    "received",
    "--counterparty-name",
    "Synthetic supplier",
    "--country-code",
    "ES",
    "--invoice-number",
    "PREVIEW-2026-001",
    "--invoice-date",
    date(_YEAR, 4, 15).isoformat(),
    "--currency",
    "EUR",
)


def _line(**figures: str) -> str:
    return json.dumps({"description": "Synthetic service", "quantity": "1", "unit_price": "100.00", **figures})


_NIF = "B00010157"


def _draft_secrets(*lines: str, nif: str | None = _NIF) -> dict[str, str]:
    """The preview's private draft material: the counterparty tax id and the draft lines as one JSON array."""
    return {"counterparty_nif": nif or "", "lines": json.dumps([json.loads(line) for line in lines])}


def _invoke(
    profile: NativeCliProfileFixture,
    *command: str,
    language: str = "en",
    output: str = "json",
    secrets: dict[str, str] | None = None,
) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    profile_secret = json.dumps({"profile_passphrase": profile.passphrase})
    channel = () if secrets is None else machine_secret_descriptor_option(secrets)
    result = invoke_cached_cli(
        [
            *("--language", language, "--format", output, "--profile", profile.label, "--profile-secrets-stdin"),
            *command,
            *channel,
        ],
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
            secrets=_draft_secrets(_line(iva_rate="RATE_21")),
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
        assert answer["on_date"] == date(_YEAR, 4, 15).isoformat()
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
            secrets=_draft_secrets(_line(iva_rate="RATE_21", iva_amount="20.00")),
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
            secrets=_draft_secrets(_line(iva_rate="RATE_21", iva_amount="20.00")),
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

        previewed = _invoke(profile, "app", "ledger", "invoice", "preview", secrets=_draft_secrets(nif=None))

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
            secrets=_draft_secrets(_line(iva_rate="RATE_21")),
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
            "--country-code",
            "ES",
            "--invoice-date",
            date(_YEAR, 4, 15).isoformat(),
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
            secrets=_draft_secrets(),
        )
        assert corrected.exit_code == 0, corrected.output
        answer = unwrap_cli_result(corrected)
        assert (answer["verdict"], answer["verdict_scope"]) == ("would_accept", "correction_facts")
        assert answer["invoice_id"] == "f" * 64
        assert answer["totals"]["net_of_retention"] == "1140.00"


def test_a_counterparty_tax_id_or_line_on_the_command_line_is_refused_as_an_unknown_option(tmp_path: Path) -> None:
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-invoice-preview-argv", facts=_PROFILE_FACTS)

        for option, value in (("--counterparty-nif", _NIF), ("--line", _line())):
            refused = _invoke(profile, "app", "ledger", "invoice", "preview", option, value)

            assert refused.exit_code != 0
            assert f"Unknown option '{option}'" in refused.output
