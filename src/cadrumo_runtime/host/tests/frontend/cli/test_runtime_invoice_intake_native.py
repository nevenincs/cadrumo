"""Native worker acceptance for invoice import and guided manual intake."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import cast

import pytest
from click.testing import Result

from cadrumo.tests.cli_envelope import require_error_document, unwrap_cli_result, unwrap_envelope_notices

from ...native_commands.runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from ...native_profile_facts import native_general_iva_facts
from .profile_cli_support import invoke_native_profile

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_PROFILE_FACTS = {
    **native_general_iva_facts(),
    "identity.name": "Native",
    "identity.surnames": "Invoice Intake",
    "activities.description": "design",
    "censo.activity_start_date": "2025-01-01",
    "contact.postcode": "28013",
}
_SUPPLIER_CIF = "B00010157"


def _tax_id_token(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:8]}"


def _import_book(profile: NativeCliProfileFixture, book: Path) -> Result:
    return invoke_native_profile(
        profile, "app", "ledger", "invoice", "import", "--file", str(book), "--kind", "received"
    )


def _list_received(profile: NativeCliProfileFixture) -> Result:
    return invoke_native_profile(profile, "app", "ledger", "invoice", "list", "--kind", "received")


def _assert_partial_import(profile: NativeCliProfileFixture, partial_book: Path, tmp_path: Path) -> object:
    """A book with one refused row creates the valid row and reports the refusal; a repeat skips it."""
    partial = _import_book(profile, partial_book)
    assert partial.exit_code == 0, partial.output
    assert str(tmp_path) not in partial.output
    partial_payload = unwrap_cli_result(partial)
    profile_id = partial_payload["bucket_id"]
    assert partial_payload["rows"] == 2
    assert partial_payload["created"] == 1
    assert partial_payload["skipped_duplicate"] == 0
    assert partial_payload["refused"] == [
        {
            "row_number": 3,
            "field": "invoice_number",
            "reason": "required field is missing or blank",
        }
    ]
    assert len(cast(list[object], partial_payload["created_invoice_ids"])) == 1

    repeated_partial = _import_book(profile, partial_book)
    assert repeated_partial.exit_code == 0, repeated_partial.output
    repeated_partial_payload = unwrap_cli_result(repeated_partial)
    assert repeated_partial_payload["created"] == 0
    assert repeated_partial_payload["skipped_duplicate"] == 1
    assert len(cast(list[object], repeated_partial_payload["refused"])) == 1
    assert not any(
        notice.get("code") == "ledger.invoice.catalogue.import.all_refused"
        for notice in unwrap_envelope_notices(repeated_partial.output)
    )
    return profile_id


def _assert_clean_import_is_idempotent(profile: NativeCliProfileFixture, clean_book: Path, profile_id: object) -> None:
    first_import = _import_book(profile, clean_book)
    assert first_import.exit_code == 0, first_import.output
    first_import_payload = unwrap_cli_result(first_import)
    assert first_import_payload["bucket_id"] == profile_id
    assert first_import_payload["created"] == 1
    assert first_import_payload["created_invoice_ids"]

    repeated_import = _import_book(profile, clean_book)
    assert repeated_import.exit_code == 0, repeated_import.output
    repeated_import_payload = unwrap_cli_result(repeated_import)
    assert repeated_import_payload["bucket_id"] == profile_id
    assert repeated_import_payload["created"] == 0
    assert repeated_import_payload["skipped_duplicate"] == 1
    assert repeated_import_payload["created_invoice_ids"] == []


def _assert_wizard_creates_once(profile: NativeCliProfileFixture, profile_id: object) -> None:
    """The wizard stores a tokenised counterparty and a replay returns the same invoice."""
    wizard_args = (
        "app",
        "ledger",
        "invoice",
        "wizard",
        "--kind",
        "received",
        "--counterparty-nif",
        _SUPPLIER_CIF,
        "--counterparty-name",
        "Manual Supplier SL",
        "--invoice-number",
        "WIZARD-001",
        "--invoice-date",
        "2026-03-13",
        "--operation-date",
        "2026-03-01",
        "--country-code",
        "ES",
        "--taxable-base",
        "125.00",
        "--iva-rate",
        "21",
        "--retention-amount",
        "15.00",
        "--notes",
        "manual intake",
    )
    created = invoke_native_profile(profile, *wizard_args)
    assert created.exit_code == 0, created.output
    created_payload = unwrap_cli_result(created)
    assert created_payload["bucket_id"] == profile_id
    assert created_payload["already_existed"] is False
    assert created_payload["counterparty_tax_id"] == _tax_id_token(_SUPPLIER_CIF)
    assert created_payload["counterparty_tax_id"] != _SUPPLIER_CIF
    assert created_payload["operation_date"] == "2026-03-01"
    assert created_payload["retention_amount"] == "15.00"
    assert created_payload["notes"] == "manual intake"

    repeated_wizard = invoke_native_profile(profile, *wizard_args)
    assert repeated_wizard.exit_code == 0, repeated_wizard.output
    repeated_wizard_payload = unwrap_cli_result(repeated_wizard)
    assert repeated_wizard_payload["bucket_id"] == profile_id
    assert repeated_wizard_payload["already_existed"] is True
    assert repeated_wizard_payload["invoice_id"] == created_payload["invoice_id"]


def _assert_refused_wizard_is_a_noop(profile: NativeCliProfileFixture) -> None:
    before_refusal = _list_received(profile)
    assert before_refusal.exit_code == 0, before_refusal.output
    before_refusal_rows = unwrap_cli_result(before_refusal)["rows"]

    refused_wizard = invoke_native_profile(
        profile,
        "app",
        "ledger",
        "invoice",
        "wizard",
        "--kind",
        "received",
        "--counterparty-nif",
        _SUPPLIER_CIF,
        "--counterparty-name",
        "",
        "--invoice-number",
        "WIZARD-INVALID-001",
        "--invoice-date",
        "2026-03-14",
        "--country-code",
        "ES",
        "--taxable-base",
        "invalid",
        "--iva-rate",
        "21",
        "--invoice-class",
        "UNDECLARED",
        "--series",
        " ",
    )
    assert refused_wizard.exit_code == 1, refused_wizard.output
    refusal = require_error_document(refused_wizard.output)["error"]
    assert refusal["code"] == "ERROR_INVOICE_VALIDATION"
    assert refusal["category"] == "ERROR"
    refusal_context = cast(dict[str, object], refusal["context"])
    assert refusal_context["fields"] == "counterparty_name, taxable_base, invoice_class, series"
    assert refusal_context["field_count"] == "4"
    operation_id = cast(str, refusal_context["operation_id"])
    assert len(operation_id) == 64
    assert refusal_context["terminal_condition"] == "refused"
    assert refusal_context["effect"] == "none"
    assert refusal_context["refusal_code"] == "REFUSED_INVOICE_WIZARD_VALIDATION"

    after_refusal = _list_received(profile)
    assert after_refusal.exit_code == 0, after_refusal.output
    assert unwrap_cli_result(after_refusal)["rows"] == before_refusal_rows


def _assert_listed_invoices(profile: NativeCliProfileFixture, partial_book: Path, profile_id: object) -> None:
    listed = _list_received(profile)
    assert listed.exit_code == 0, listed.output
    list_payload = unwrap_cli_result(listed)
    assert list_payload["bucket_id"] == profile_id
    rows = cast(list[dict[str, object]], list_payload["rows"])
    imported = next(row for row in rows if row["invoice_number"] == "IMPORT-VALID-001")
    assert imported["source_filename"] == partial_book.name
    assert imported["source_sha256"] == hashlib.sha256(partial_book.read_bytes()).hexdigest()
    assert imported["source_row_index"] == 2
    assert any(row["invoice_number"] == "IMPORT-DUP-001" for row in rows)
    assert any(row["invoice_number"] == "WIZARD-001" for row in rows)


def test_native_import_and_wizard_preserve_worker_results_and_noop_effects(tmp_path: Path) -> None:
    """Imports and wizard writes use one registered exact-profile worker end to end."""
    partial_book = tmp_path / "partial.csv"
    partial_book.write_bytes(
        (
            "﻿counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate,"
            "country_code,notes\n"
            f"{_SUPPLIER_CIF},Import Supplier SL,IMPORT-VALID-001,2026-03-10,100.00,21,ES,valid row\n"
            f"{_SUPPLIER_CIF},Import Supplier SL,,2026-03-11,50.00,10,ES,missing number\n"
        ).encode()
    )
    clean_book = tmp_path / "clean.csv"
    clean_book.write_text(
        "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate,country_code\n"
        f"{_SUPPLIER_CIF},Import Supplier SL,IMPORT-DUP-001,2026-03-12,75.00,10,ES\n",
        encoding="utf-8",
    )

    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-invoice-intake", facts=_PROFILE_FACTS)

        profile_id = _assert_partial_import(profile, partial_book, tmp_path)
        _assert_clean_import_is_idempotent(profile, clean_book, profile_id)
        _assert_wizard_creates_once(profile, profile_id)
        _assert_refused_wizard_is_a_noop(profile)
        _assert_listed_invoices(profile, partial_book, profile_id)
