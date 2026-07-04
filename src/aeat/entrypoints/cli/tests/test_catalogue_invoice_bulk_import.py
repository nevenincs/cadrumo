"""CLI regression for bulk catalogue-invoice import (``ledger invoice catalogue import``).

Covers the #254 sub-slice 4c (CSV/XLSX bulk import): a spreadsheet of invoice
rows creates one catalogue :class:`~aeat.domain.invoices.Invoice` per row,
delegating every write to :func:`aeat.application.invoices.create_catalogue_invoice`
(the sole sanctioned writer), a re-import of the identical file is a guarded
idempotent no-op (every row reports ``skipped_duplicate``), and a malformed row
is refused with its row number and failing field while the remaining valid
rows still import.

Real behaviour only: a real encrypted bucket session, the live Typer tree, and
real CSV/XLSX bytes. No mocks, stubs, or monkeypatch.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....application.invoices import BULK_INVOICE_IMPORT_REQUIRED_COLUMNS
from ....application.user_profile import profile_create_storage_span, register_minimal_profile
from ....application.workflow import workflow_state_repository
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# Two valid Spanish NIF/CIF counterparties (control digit verified).
_RECEIVED_COUNTERPARTY_CIF = "A58818501"
_ISSUED_COUNTERPARTY_NIF = "B12345674"

_CSV_HEADER = "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\n"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("11111111-1111-4111-8111-111111111111"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="11111111-1111-4111-8111-111111111111"),
        )
        yield


def _line_value(output: str, key: str) -> str:
    for line in output.splitlines():
        head, sep, tail = line.partition("\t")
        if sep and head.strip() == key:
            return tail.strip()
    raise AssertionError(f"no {key!r} line in CLI output:\n{output}")


def _json_result(output: str) -> dict[str, object]:
    envelope = json.loads(output)
    return envelope["result"]


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
            "app", "ledger", "invoice", "catalogue", "import",
            "--file", str(csv_path), "--kind", "received",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = _json_result(result.output)
    assert payload["rows"] == 3
    assert payload["created"] == 3
    assert payload["skipped_duplicate"] == 0
    assert payload["refused"] == []
    created_ids = payload["created_invoice_ids"]
    assert len(created_ids) == 3
    assert all(len(invoice_id) == 64 for invoice_id in created_ids)

    listed = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "invoice", "catalogue", "list", "--kind", "received"],
    )
    assert listed.exit_code == 0, listed.output
    rows = _json_result(listed.output)["rows"]
    numbers = {row["invoice_number"] for row in rows}
    assert {"2026-BULK-001", "2026-BULK-002", "2026-BULK-003"}.issubset(numbers)
    exempt_row = next(row for row in rows if row["invoice_number"] == "2026-BULK-003")
    assert exempt_row["iva_total"] == "0"


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
            "app", "ledger", "invoice", "catalogue", "import",
            "--file", str(csv_path), "--kind", "received",
        ],
    )  # fmt: skip
    assert first.exit_code == 0, first.output
    first_payload = _json_result(first.output)
    assert first_payload["created"] == 1
    assert first_payload["skipped_duplicate"] == 0

    second = invoke_cached_cli(
        [
            "--format", "json",
            "app", "ledger", "invoice", "catalogue", "import",
            "--file", str(csv_path), "--kind", "received",
        ],
    )  # fmt: skip
    assert second.exit_code == 0, second.output
    second_payload = _json_result(second.output)
    assert second_payload["rows"] == 1
    assert second_payload["created"] == 0
    assert second_payload["skipped_duplicate"] == 1
    assert second_payload["refused"] == []

    listed = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "invoice", "catalogue", "list", "--kind", "received"],
    )
    rows = _json_result(listed.output)["rows"]
    matching = [row for row in rows if row["invoice_number"] == "2026-DUP-001"]
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
            "app", "ledger", "invoice", "catalogue", "import",
            "--file", str(csv_path), "--kind", "received",
        ],
    )  # fmt: skip
    # Notices with WARNING severity surface a non-zero exit only when every row
    # fails; here one row succeeds, so the call still exits 0 but with visible
    # per-row refusals.
    assert result.exit_code == 0, result.output
    payload = _json_result(result.output)
    assert payload["rows"] == 3
    assert payload["created"] == 1
    refused = payload["refused"]
    assert len(refused) == 2
    bad_date_failure = next(f for f in refused if f["row_number"] == 3)
    assert bad_date_failure["field"] == "invoice_date"
    missing_nif_failure = next(f for f in refused if f["row_number"] == 4)
    assert missing_nif_failure["field"] == "counterparty_nif"


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
            "app", "ledger", "invoice", "catalogue", "import",
            "--file", str(csv_path), "--kind", "received",
        ],
    )  # fmt: skip
    assert result.exit_code == 1, result.output
    envelope = json.loads(result.output)
    assert envelope["notices"], "all-refused import must carry a notice"
    assert envelope["notices"][0]["severity"] == "warning"


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
            "app", "ledger", "invoice", "catalogue", "import",
            "--file", str(csv_path), "--kind", "issued",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = _json_result(result.output)
    assert payload["created"] == 1

    issued_listed = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "invoice", "catalogue", "list", "--kind", "issued"],
    )
    issued_rows = _json_result(issued_listed.output)["rows"]
    assert any(row["invoice_number"] == "2026-ISSUED-001" for row in issued_rows)

    received_listed = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "invoice", "catalogue", "list", "--kind", "received"],
    )
    received_rows = _json_result(received_listed.output)["rows"]
    assert not any(row["invoice_number"] == "2026-ISSUED-001" for row in received_rows)


def test_bulk_import_file_not_found_refuses_cleanly(tmp_path: Path) -> None:
    """A missing --file path refuses with an instructive error, not a traceback."""
    missing = tmp_path / "does-not-exist.csv"
    result = invoke_cached_cli(
        [
            "app", "ledger", "invoice", "catalogue", "import",
            "--file", str(missing), "--kind", "received",
        ],
    )  # fmt: skip
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "no encontrado" in result.output.lower()


def test_bulk_import_unknown_column_is_refused(tmp_path: Path) -> None:
    """An unrecognised column name refuses the whole file before any writes."""
    csv_path = tmp_path / "invoices.csv"
    csv_path.write_text(
        "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,bogus_column\n"
        + f"{_RECEIVED_COUNTERPARTY_CIF},Papeleria Sol SL,2026-BOGUS-001,2026-03-10,100.00,xyz\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        ["app", "ledger", "invoice", "catalogue", "import", "--file", str(csv_path), "--kind", "received"],
    )
    assert result.exit_code != 0

    listed = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "invoice", "catalogue", "list", "--kind", "received"],
    )
    rows = _json_result(listed.output)["rows"]
    assert not any(row["invoice_number"] == "2026-BOGUS-001" for row in rows)
