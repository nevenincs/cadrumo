"""Portable parser and presentation contracts for ``ledger invoice import``."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from ....application.invoices.bulk_import import BULK_INVOICE_IMPORT_REQUIRED_COLUMNS
from ....application.invoices.catalogue_intake_operation import (
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
from ....tests.cli_envelope import require_error_document
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

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


def test_required_columns_cover_the_documented_row_shape() -> None:
    assert (
        frozenset({"counterparty_nif", "counterparty_name", "invoice_number", "invoice_date", "taxable_base"})
        == BULK_INVOICE_IMPORT_REQUIRED_COLUMNS
    )


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


def test_import_help_keeps_file_kind_and_country_options() -> None:
    result = invoke_cached_cli(["app", "ledger", "invoice", "import", "--help"])
    assert result.exit_code == 0, result.output
    assert "--file" in result.output
    assert "--kind" in result.output
    assert "--country" in result.output


def test_missing_import_file_keeps_the_typed_clean_refusal(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.csv"
    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "invoice", "import", "--file", str(missing), "--kind", "received"]
    )
    assert result.exit_code == 2, result.output
    error = require_error_document(result.output)["error"]
    assert missing.name in result.output
    assert str(tmp_path) not in result.output
    assert error["code"] == "ERROR_INVOICE_VALIDATION"
