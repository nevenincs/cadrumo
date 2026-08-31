"""CLI regression for bulk catalogue-invoice import (``ledger invoice import``).

Covers the #254 sub-slice 4c (CSV/XLSX bulk import): a spreadsheet of invoice
rows creates one catalogue :class:`~domain.invoices.Invoice` per row,
delegating every write to :func:`~application.invoices.create_catalogue_invoice`
(the sole sanctioned writer), a re-import of the identical file is a guarded
idempotent no-op (every row reports ``skipped_duplicate``), and a malformed row
is refused with its row number and failing field while the remaining valid
rows still import.

Real behaviour only: a real encrypted bucket session, the live Typer tree, and
real CSV/XLSX bytes. No mocks, stubs, or monkeypatch.

See Also:
    :func:`~entrypoints.cli._ledger_business_invoice_cli.catalogue_import`
        Typer command exercised by this regression file.
    :func:`~application.invoices.import_invoices_from_rows`
        Application service receiving the rows parsed by the CLI.
    :func:`~application.invoices.read_bulk_invoice_import_rows`
        CSV/XLSX reader covering required-column and unknown-column refusal.
    :data:`~application.invoices.BULK_INVOICE_IMPORT_REQUIRED_COLUMNS`
        Public row-shape contract asserted by the CLI regression.

Catalogue identity and validation are the same contract bulk imports must
preserve as any other invoice-creation path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....application.invoices import BULK_INVOICE_IMPORT_REQUIRED_COLUMNS
from ....tests.cli_envelope import parse_json_object
from ....tests.cli_envelope import require_schema_envelope as _json_result
from ....tests.cli_runner import invoke_cached_cli
from ._isolated_profile_storage_fixtures import active_profile_isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["active_profile_isolated_backend"]

# Two valid Spanish NIF/CIF counterparties (control digit verified).
_RECEIVED_COUNTERPARTY_CIF = "A58818501"
_ISSUED_COUNTERPARTY_NIF = "B12345674"

_CSV_HEADER = "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\n"


def _get_list_value(payload: dict[str, object], key: str) -> list[object]:
    """Safely extract a list value from a JSON payload dict."""
    value = payload[key]
    assert isinstance(value, list), f"Expected list for {key}, got {type(value)}"
    return list[object](value)


def _get_dict_value(payload: dict[str, object], key: str) -> dict[str, object]:
    """Safely extract a dict value from a JSON payload dict."""
    value = payload[key]
    assert isinstance(value, dict), f"Expected dict for {key}, got {type(value)}"
    # A decoded JSON object always has str keys; see _json_result for why the
    # re-keyed comprehension (not a bare return) proves the shape to the checker.
    return {str(item_key): item_value for item_key, item_value in value.items()}


def _get_int_value(payload: dict[str, object], key: str) -> int:
    """Safely extract an int value from a JSON payload dict."""
    value = payload[key]
    assert isinstance(value, int), f"Expected int for {key}, got {type(value)}"
    return value


def test_required_columns_cover_the_documented_row_shape() -> None:
    """The declared required-column set matches the documented row shape."""
    assert (
        frozenset(
            {"counterparty_nif", "counterparty_name", "invoice_number", "invoice_date", "taxable_base"},
        )
        == BULK_INVOICE_IMPORT_REQUIRED_COLUMNS
    )


def test_bulk_import_creates_one_invoice_per_valid_row(tmp_path: Path) -> None:
    """N valid CSV rows create N catalogue invoices, each linked correctly."""
    csv_path = tmp_path / "invoices.csv"
    csv_path.write_text(
        _CSV_HEADER
        + f"{_RECEIVED_COUNTERPARTY_CIF},Papeleria Sol SL,2026-BULK-001,2026-03-10,100.00,21\n"
        + f"{_RECEIVED_COUNTERPARTY_CIF},Papeleria Sol SL,2026-BULK-002,2026-03-11,200.00,10\n"
        + f"{_RECEIVED_COUNTERPARTY_CIF},Papeleria Sol SL,2026-BULK-003,2026-03-12,50.00,\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "ledger", "invoice", "import",
            "--file", str(csv_path), "--kind", "received", "--country", "ES",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = _json_result(result.output)
    assert _get_int_value(payload, "rows") == 3
    assert _get_int_value(payload, "created") == 3
    assert _get_int_value(payload, "skipped_duplicate") == 0
    assert _get_list_value(payload, "refused") == []
    created_ids = _get_list_value(payload, "created_invoice_ids")
    assert len(created_ids) == 3
    assert all(isinstance(id_val, str) and len(id_val) == 64 for id_val in created_ids)

    listed = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "invoice", "list", "--kind", "received"],
    )
    assert listed.exit_code == 0, listed.output
    listed_payload = _json_result(listed.output)
    rows = _get_list_value(listed_payload, "rows")
    numbers = {row.get("invoice_number") for row in rows if isinstance(row, dict) and "invoice_number" in row}
    assert {"2026-BULK-001", "2026-BULK-002", "2026-BULK-003"}.issubset(numbers)
    exempt_row = next(
        (row for row in rows if isinstance(row, dict) and row.get("invoice_number") == "2026-BULK-003"),
        None,
    )
    assert exempt_row is not None, "Expected to find row with invoice_number 2026-BULK-003"
    assert exempt_row.get("iva_total") == "0"


def test_bulk_import_reimport_of_identical_file_is_idempotent_no_op(tmp_path: Path) -> None:
    """A re-import of an unchanged file skips every row as a duplicate, not an error."""
    csv_path = tmp_path / "invoices.csv"
    csv_path.write_text(
        _CSV_HEADER + f"{_RECEIVED_COUNTERPARTY_CIF},Papeleria Sol SL,2026-DUP-001,2026-03-10,100.00,21\n",
        encoding="utf-8",
    )

    first = invoke_cached_cli(
        [
            "--format", "json",
            "app", "ledger", "invoice", "import",
            "--file", str(csv_path), "--kind", "received", "--country", "ES",
        ],
    )  # fmt: skip
    assert first.exit_code == 0, first.output
    first_payload = _json_result(first.output)
    assert _get_int_value(first_payload, "created") == 1
    assert _get_int_value(first_payload, "skipped_duplicate") == 0

    second = invoke_cached_cli(
        [
            "--format", "json",
            "app", "ledger", "invoice", "import",
            "--file", str(csv_path), "--kind", "received", "--country", "ES",
        ],
    )  # fmt: skip
    assert second.exit_code == 0, second.output
    second_payload = _json_result(second.output)
    assert _get_int_value(second_payload, "rows") == 1
    assert _get_int_value(second_payload, "created") == 0
    assert _get_int_value(second_payload, "skipped_duplicate") == 1
    assert _get_list_value(second_payload, "refused") == []

    listed = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "invoice", "list", "--kind", "received"],
    )
    listed_payload = _json_result(listed.output)
    rows = _get_list_value(listed_payload, "rows")
    matching = [row for row in rows if isinstance(row, dict) and row.get("invoice_number") == "2026-DUP-001"]
    assert len(matching) == 1, "re-import must not duplicate the invoice record"


def test_bulk_import_refuses_malformed_row_with_row_number_and_field(tmp_path: Path) -> None:
    """A malformed row is refused with its row number and failing field; valid rows still import."""
    csv_path = tmp_path / "invoices.csv"
    csv_path.write_text(
        _CSV_HEADER
        + f"{_RECEIVED_COUNTERPARTY_CIF},Papeleria Sol SL,2026-OK-001,2026-03-10,100.00,21\n"
        + f"{_RECEIVED_COUNTERPARTY_CIF},Papeleria Sol SL,2026-BAD-001,not-a-date,50.00,21\n"
        + ",Papeleria Sol SL,2026-BAD-002,2026-03-12,50.00,21\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "ledger", "invoice", "import",
            "--file", str(csv_path), "--kind", "received", "--country", "ES",
        ],
    )  # fmt: skip
    # Notices with WARNING severity surface a non-zero exit only when every row
    # fails; here one row succeeds, so the call still exits 0 but with visible
    # per-row refusals.
    assert result.exit_code == 0, result.output
    payload = _json_result(result.output)
    assert _get_int_value(payload, "rows") == 3
    assert _get_int_value(payload, "created") == 1
    refused = _get_list_value(payload, "refused")
    assert len(refused) == 2
    bad_date_failure = next(
        (f for f in refused if isinstance(f, dict) and f.get("row_number") == 3),
        None,
    )
    assert bad_date_failure is not None, "Expected refusal with row_number 3"
    assert bad_date_failure.get("field") == "invoice_date"
    missing_nif_failure = next(
        (f for f in refused if isinstance(f, dict) and f.get("row_number") == 4),
        None,
    )
    assert missing_nif_failure is not None, "Expected refusal with row_number 4"
    assert missing_nif_failure.get("field") == "counterparty_nif"


def test_bulk_import_all_rows_refused_exits_nonzero_with_notice(tmp_path: Path) -> None:
    """When every row fails, the command exits non-zero with a WARNING notice."""
    csv_path = tmp_path / "invoices.csv"
    csv_path.write_text(
        _CSV_HEADER + ",Papeleria Sol SL,2026-BAD-003,2026-03-12,50.00,21\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "ledger", "invoice", "import",
            "--file", str(csv_path), "--kind", "received", "--country", "ES",
        ],
    )  # fmt: skip
    assert result.exit_code == 1, result.output
    envelope = parse_json_object(result.output)
    notices = _get_list_value(envelope, "notices")
    assert notices, "all-refused import must carry a notice"
    first_notice = next((n for n in notices if isinstance(n, dict)), None)
    assert first_notice is not None, "Expected at least one notice"
    assert first_notice.get("severity") == "warning"


def test_bulk_import_kind_issued_routes_to_collectible_invoices(tmp_path: Path) -> None:
    """``--kind issued`` creates a collectible (issued) invoice, not received."""
    csv_path = tmp_path / "invoices.csv"
    csv_path.write_text(
        _CSV_HEADER + f"{_ISSUED_COUNTERPARTY_NIF},Cliente SL,2026-ISSUED-001,2026-03-10,300.00,21\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "ledger", "invoice", "import",
            "--file", str(csv_path), "--kind", "issued", "--country", "ES",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = _json_result(result.output)
    assert _get_int_value(payload, "created") == 1

    issued_listed = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "invoice", "list", "--kind", "issued"],
    )
    issued_payload = _json_result(issued_listed.output)
    issued_rows = _get_list_value(issued_payload, "rows")
    assert any(isinstance(row, dict) and row.get("invoice_number") == "2026-ISSUED-001" for row in issued_rows)

    received_listed = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "invoice", "list", "--kind", "received"],
    )
    received_payload = _json_result(received_listed.output)
    received_rows = _get_list_value(received_payload, "rows")
    assert not any(isinstance(row, dict) and row.get("invoice_number") == "2026-ISSUED-001" for row in received_rows)


def test_bulk_import_file_not_found_refuses_cleanly(tmp_path: Path) -> None:
    """A missing --file path refuses with an instructive error, not a traceback."""
    missing = tmp_path / "does-not-exist.csv"
    result = invoke_cached_cli(
        [
            "app", "ledger", "invoice", "import",
            "--file", str(missing), "--kind", "received",
        ],
    )  # fmt: skip
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "no encontrado" in result.output.lower()


def test_bulk_import_unknown_column_is_reported_and_the_row_still_imports(tmp_path: Path) -> None:
    """An unrecognised column is reported through the notice channel, not refused.

    This assertion was inverted. The importer used to refuse the whole file for
    a single column it did not recognise, so a book carrying every required
    field plus one extra imported nothing at all. The extra column must be named
    to the operator and the row must land.
    """
    csv_path = tmp_path / "invoices.csv"
    csv_path.write_text(
        "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,bogus_column\n"
        + f"{_RECEIVED_COUNTERPARTY_CIF},Papeleria Sol SL,2026-BOGUS-001,2026-03-10,100.00,xyz\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "invoice",
            "import",
            "--file",
            str(csv_path),
            "--kind",
            "received",
            "--country",
            "ES",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "bogus_column" in result.output

    listed = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "invoice", "list", "--kind", "received"],
    )
    listed_payload = _json_result(listed.output)
    rows = _get_list_value(listed_payload, "rows")
    assert any(isinstance(row, dict) and row.get("invoice_number") == "2026-BOGUS-001" for row in rows)


def test_bulk_import_still_refuses_a_file_with_no_required_column(tmp_path: Path) -> None:
    """Positive control: dropping the refuse-whole must not remove every refusal.

    Without this, the test above would pass equally against an importer that
    accepted anything at all.
    """
    csv_path = tmp_path / "no_base.csv"
    csv_path.write_text(
        "counterparty_nif,counterparty_name,invoice_number,invoice_date\n"
        + f"{_RECEIVED_COUNTERPARTY_CIF},Papeleria Sol SL,2026-NOBASE-001,2026-03-10\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        ["app", "ledger", "invoice", "import", "--file", str(csv_path), "--kind", "received", "--country", "ES"],
    )
    assert result.exit_code != 0
