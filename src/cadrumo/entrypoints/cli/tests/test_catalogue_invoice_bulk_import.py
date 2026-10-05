"""Parser, presentation and worker-backed contracts for ``ledger invoice import``.

The presentation contracts run anywhere. The book-level behaviour -- how many
invoices a book creates, which kind they land under, how an unknown column and
a wholly refused book are reported -- can only be observed through a registered
profile worker, because ``ledger invoice import`` submits a runtime operation
and refuses at the boundary when no worker serves the invocation.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.invoices.bulk_import import BULK_INVOICE_IMPORT_REQUIRED_COLUMNS
from ....application.invoices.catalogue_intake_contracts import (
    InvoiceImportProjection,
    InvoiceImportRowFailure,
)
from ....entrypoints.cli._ledger_business_invoice_cli import (
    _invoice_import_all_refused_report,
    _invoice_import_mapping_reports,
    _invoice_import_payload,
    _invoice_import_refusal_lines,
    _invoice_import_summary_lines,
    _invoice_import_unmapped_report,
)
from ....tests.cli_envelope import require_error_document, unwrap_cli_result, unwrap_envelope_notices
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_INVOICE_ID = "a" * 64
_ROW_FAILURE = InvoiceImportRowFailure(
    row_number=3,
    field="invoice_number",
    reason="required field is missing or blank",
)


def _projection(
    *,
    rows: int,
    created: int,
    skipped_duplicate: int = 0,
    refused: tuple[InvoiceImportRowFailure, ...] = (),
    created_invoice_ids: tuple[str, ...] = (),
    unmapped_column_headers: tuple[str, ...] = (),
    mapping_reasons: tuple[str, ...] = (),
) -> InvoiceImportProjection:
    return InvoiceImportProjection(
        profile_id=_PROFILE_ID,
        rows=rows,
        created=created,
        skipped_duplicate=skipped_duplicate,
        refused=refused,
        created_invoice_ids=created_invoice_ids,
        unmapped_column_headers=unmapped_column_headers,
        mapping_reasons=mapping_reasons,
    )


@pytest.mark.unit
def test_required_columns_cover_the_documented_row_shape() -> None:
    assert (
        frozenset({"counterparty_nif", "counterparty_name", "invoice_number", "invoice_date", "taxable_base"})
        == BULK_INVOICE_IMPORT_REQUIRED_COLUMNS
    )


@pytest.mark.unit
def test_import_presenter_preserves_partial_row_facts_and_mapping_notes() -> None:
    projection = _projection(
        rows=2,
        created=1,
        refused=(_ROW_FAILURE,),
        created_invoice_ids=(_INVOICE_ID,),
        unmapped_column_headers=("legacy_tag",),
        mapping_reasons=("column 8 legacy_tag: role was not applied",),
    )

    assert _invoice_import_payload(projection) == {
        "bucket_id": str(_PROFILE_ID),
        "rows": 2,
        "created": 1,
        "skipped_duplicate": 0,
        "refused": [{"row_number": 3, "field": "invoice_number", "reason": "required field is missing or blank"}],
        "created_invoice_ids": [_INVOICE_ID],
    }
    assert _invoice_import_summary_lines(str(_PROFILE_ID), projection) == [
        f"bucket\t{_PROFILE_ID}",
        "rows\t2",
        "created\t1",
        "skipped_duplicate\t0",
        "refused\t1",
    ]
    assert _invoice_import_refusal_lines(projection) == [
        "  refused\trow=3\tfield=invoice_number\treason=required field is missing or blank"
    ]

    unmapped = _invoice_import_unmapped_report(projection.unmapped_column_headers)
    assert unmapped is not None
    assert unmapped[0] == "unmapped_columns\tlegacy_tag"
    assert unmapped[1].code == "ledger.invoice.catalogue.import.unmapped_columns"
    assert unmapped[1].context == {"columns": "legacy_tag", "count": "1"}

    mapping_lines, mapping_notices = _invoice_import_mapping_reports(projection.mapping_reasons)
    assert mapping_lines == ["mapping_note\tcolumn 8 legacy_tag: role was not applied"]
    assert len(mapping_notices) == 1
    assert mapping_notices[0].code == "ledger.invoice.catalogue.import.column_role_not_applied"


@pytest.mark.unit
def test_all_refused_import_uses_warning_notice_and_only_refused_rows() -> None:
    all_refused = _projection(rows=1, created=0, refused=(_ROW_FAILURE,))
    report = _invoice_import_all_refused_report(all_refused)
    assert report is not None
    message, notice = report
    assert message
    assert notice.code == "ledger.invoice.catalogue.import.all_refused"
    assert notice.context == {"rows": "1", "refused": "1"}

    duplicate_only = _projection(rows=1, created=0, skipped_duplicate=1)
    assert _invoice_import_all_refused_report(duplicate_only) is None

    repeated_mixed_book = _projection(rows=2, created=0, skipped_duplicate=1, refused=(_ROW_FAILURE,))
    assert _invoice_import_all_refused_report(repeated_mixed_book) is None


@pytest.mark.unit
def test_import_help_keeps_file_kind_and_country_options() -> None:
    result = invoke_cached_cli(["app", "ledger", "invoice", "import", "--help"])
    assert result.exit_code == 0, result.output
    assert "--file" in result.output
    assert "--kind" in result.output
    assert "--country" in result.output


@pytest.mark.unit
def test_missing_import_file_keeps_the_typed_clean_refusal(tmp_path: Path) -> None:
    """A missing ``--file`` is refused by the shared argv existence contract.

    The ``--file`` option declares ``ParameterConstraint(exists=True, ...)``
    in ``_app_ledger_invoice_intake_command_specs.py``, so click rejects a
    missing path before the command body (and its ``InvoiceValidationError``
    handling in ``submit_invoice_import``) ever runs. Every leaf with that
    same constraint is refused the same uniform way, re-keyed by
    ``_terminal_errors._build_parse_time_refusal`` into a
    ``CliRefusedBoundaryError`` (``REFUSED_CLI_BOUNDARY``) rather than a
    domain-specific code; see ``test_missing_csv_is_refused_at_the_file_parameter``
    in ``test_ledger_import_ux.py`` for the same contract on another import verb.
    """
    missing = tmp_path / "does-not-exist.csv"
    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "invoice", "import", "--file", str(missing), "--kind", "received"]
    )
    assert result.exit_code == 2, result.output
    error = require_error_document(result.output)["error"]
    assert missing.name in result.output
    assert str(tmp_path) not in result.output
    assert error["code"] == "REFUSED_CLI_BOUNDARY"


_SUPPLIER_CIF = "A58818501"
_CUSTOMER_NIF = "B12345674"
_CSV_HEADER = "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\n"
_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Invoice Book",
    "activities.description": "design",
    "censo.activity_start_date": "2025-01-01",
    "contact.postcode": "28013",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


def _invoke(profile: NativeCliProfileFixture, *command: str) -> Result:
    """Run one command through a fresh protected-stdin profile binding."""
    assert profile.label is not None
    close_active_bucket_session()
    result = invoke_cached_cli(
        ("--language", "en", "--format", "json", "--profile", profile.label, "--profile-secrets-stdin", *command),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


def _import(profile: NativeCliProfileFixture, book: Path, *, kind: str, country: str | None = "ES") -> Result:
    command = ["app", "ledger", "invoice", "import", "--file", str(book), "--kind", kind]
    if country is not None:
        command += ["--country", country]
    return _invoke(profile, *command)


def _listed_rows(profile: NativeCliProfileFixture, *, kind: str) -> tuple[Mapping[str, object], ...]:
    listed = _invoke(profile, "app", "ledger", "invoice", "list", "--kind", kind)
    assert listed.exit_code == 0, listed.output
    rows = cast(Sequence[Mapping[str, object]], unwrap_cli_result(listed)["rows"])
    return tuple(rows)


def _row(rows: tuple[Mapping[str, object], ...], invoice_number: str) -> Mapping[str, object]:
    match = [row for row in rows if row.get("invoice_number") == invoice_number]
    assert len(match) == 1, f"{invoice_number} matched {len(match)} rows"
    return match[0]


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
@pytest.mark.usefixtures("authority_operation")
def test_every_valid_row_becomes_one_invoice_carrying_its_own_source_provenance(tmp_path: Path) -> None:
    """N valid rows create N invoices, each stamped with the row it came from.

    The per-row provenance is what lets an operator trace a catalogue record
    back to the line of the book that produced it, and a blank rate must land
    as a proven exempt zero rather than being filled in from its neighbours.
    """
    book = tmp_path / "invoices.csv"
    book.write_text(
        _CSV_HEADER
        + f"{_SUPPLIER_CIF},Papeleria Sol SL,2026-BULK-001,2026-03-10,100.00,21\n"
        + f"{_SUPPLIER_CIF},Papeleria Sol SL,2026-BULK-002,2026-03-11,200.00,10\n"
        + f"{_SUPPLIER_CIF},Papeleria Sol SL,2026-BULK-003,2026-03-12,50.00,\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(book.read_bytes()).hexdigest()

    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-invoice-book", facts=_PROFILE_FACTS)

        imported = _import(profile, book, kind="received")
        assert imported.exit_code == 0, imported.output
        payload = unwrap_cli_result(imported)
        assert payload["rows"] == 3
        assert payload["created"] == 3
        assert payload["skipped_duplicate"] == 0
        assert payload["refused"] == []
        created_ids = cast(Sequence[str], payload["created_invoice_ids"])
        assert len(created_ids) == 3
        assert all(len(created_id) == 64 for created_id in created_ids)

        rows = _listed_rows(profile, kind="received")
        first = _row(rows, "2026-BULK-001")
        assert first["source_filename"] == book.name
        assert first["source_sha256"] == digest
        assert first["source_row_index"] == 2
        assert _row(rows, "2026-BULK-002")["source_row_index"] == 3
        assert _row(rows, "2026-BULK-003")["iva_total"] == "0"


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
@pytest.mark.usefixtures("authority_operation")
def test_the_declared_kind_decides_which_side_of_the_catalogue_a_book_lands_on(tmp_path: Path) -> None:
    """``--kind issued`` creates a collectible invoice and no received one."""
    book = tmp_path / "issued.csv"
    book.write_text(
        _CSV_HEADER + f"{_CUSTOMER_NIF},Cliente SL,2026-ISSUED-001,2026-03-10,300.00,21\n",
        encoding="utf-8",
    )

    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-invoice-book-issued", facts=_PROFILE_FACTS)

        imported = _import(profile, book, kind="issued")
        assert imported.exit_code == 0, imported.output
        assert unwrap_cli_result(imported)["created"] == 1

        issued = _listed_rows(profile, kind="issued")
        assert _row(issued, "2026-ISSUED-001")["base_total"] == "300.00"
        received = _listed_rows(profile, kind="received")
        assert not any(row.get("invoice_number") == "2026-ISSUED-001" for row in received)


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
@pytest.mark.usefixtures("authority_operation")
def test_an_unknown_column_is_named_rather_than_costing_the_operator_the_whole_book(tmp_path: Path) -> None:
    """One unrecognised column is reported; the row it sits on still imports.

    The positive control in the same session proves the importer has not simply
    stopped refusing: a book missing a required column is still rejected whole,
    because there is no row to salvage from it.
    """
    extra_column = tmp_path / "extra_column.csv"
    extra_column.write_text(
        "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,bogus_column\n"
        + f"{_SUPPLIER_CIF},Papeleria Sol SL,2026-BOGUS-001,2026-03-10,100.00,xyz\n",
        encoding="utf-8",
    )
    missing_required = tmp_path / "no_base.csv"
    missing_required.write_text(
        "counterparty_nif,counterparty_name,invoice_number,invoice_date\n"
        + f"{_SUPPLIER_CIF},Papeleria Sol SL,2026-NOBASE-001,2026-03-10\n",
        encoding="utf-8",
    )

    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-invoice-book-columns", facts=_PROFILE_FACTS)

        tolerated = _import(profile, extra_column, kind="received")
        assert tolerated.exit_code == 0, tolerated.output
        assert "bogus_column" in tolerated.output
        assert _row(_listed_rows(profile, kind="received"), "2026-BOGUS-001")["base_total"] == "100.00"

        refused = _import(profile, missing_required, kind="received")
        assert refused.exit_code != 0, refused.output
        remaining = _listed_rows(profile, kind="received")
        assert not any(row.get("invoice_number") == "2026-NOBASE-001" for row in remaining)


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
@pytest.mark.usefixtures("authority_operation")
def test_a_book_whose_every_row_fails_exits_nonzero_and_says_so(tmp_path: Path) -> None:
    """Nothing imported is a failure the operator must see, not a quiet zero.

    The partially refused book in the same session is the contrast: it keeps the
    created row, exits zero, and carries its per-row refusal with the row number
    and the field that failed.
    """
    all_bad = tmp_path / "all_bad.csv"
    all_bad.write_text(
        _CSV_HEADER + ",Papeleria Sol SL,2026-BAD-003,2026-03-12,50.00,21\n",
        encoding="utf-8",
    )
    mixed = tmp_path / "mixed.csv"
    mixed.write_text(
        _CSV_HEADER
        + f"{_SUPPLIER_CIF},Papeleria Sol SL,2026-OK-001,2026-03-10,100.00,21\n"
        + f"{_SUPPLIER_CIF},Papeleria Sol SL,2026-BAD-001,not-a-date,50.00,21\n",
        encoding="utf-8",
    )

    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-invoice-book-refusals", facts=_PROFILE_FACTS)

        refused = _import(profile, all_bad, kind="received")
        assert refused.exit_code == 1, refused.output
        notices = unwrap_envelope_notices(refused.output)
        assert any(
            notice.get("code") == "ledger.invoice.catalogue.import.all_refused" and notice.get("severity") == "warning"
            for notice in notices
        ), notices

        partial = _import(profile, mixed, kind="received")
        assert partial.exit_code == 0, partial.output
        payload = unwrap_cli_result(partial)
        assert payload["rows"] == 2
        assert payload["created"] == 1
        row_failures = cast(Sequence[Mapping[str, object]], payload["refused"])
        assert len(row_failures) == 1
        assert row_failures[0]["row_number"] == 3
        assert row_failures[0]["field"] == "invoice_date"
