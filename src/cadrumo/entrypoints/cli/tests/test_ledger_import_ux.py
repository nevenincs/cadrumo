"""Ledger import UX regression tests."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ._ledger_ux_support import (
    _FOUR_ROW_CSV,
    _FOUR_ROW_OFX,
    _N26_HEADER,
    _invoke,
    _open_ledger_ux_session,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _open_bucket_session(tmp_path: Path) -> Iterator[None]:
    with _open_ledger_ux_session(tmp_path):
        yield


def test_import_help_lists_recognised_providers() -> None:
    """`import --help` enumerates the accepted --provider values."""
    result = _invoke(["app", "ledger", "import", "--help"])
    assert result.exit_code == 0, result.output
    haystack = " ".join(result.output.split())
    for provider in ("csv", "ofx", "xlsx", "n26"):
        assert provider in haystack


def test_unknown_provider_error_enumerates_known_providers(tmp_path: Path) -> None:
    """An unknown --provider is refused with the recognised set inline."""
    statement = tmp_path / "statement.csv"
    statement.write_text(
        _N26_HEADER + "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    result = _invoke(["app", "ledger", "import", "--file", str(statement), "--provider", "quickbooks"])
    assert result.exit_code != 0
    assert "quickbooks" in result.output
    for provider in ("csv", "ofx", "xlsx", "n26"):
        assert provider in result.output


def test_generic_csv_missing_currency_warning_is_provider_neutral_in_cli(tmp_path: Path) -> None:
    """`--provider csv` warnings must not invent a bank brand for generic CSV."""
    statement = tmp_path / "generic.csv"
    statement.write_text("Date,Description,Amount\n2026-04-15,Invoice 1,121.00\n", encoding="utf-8")

    result = _invoke(
        ["app", "ledger", "import", "--file", str(statement), "--provider", "csv", "--dry-run", "--verbose"],
    )

    assert result.exit_code == 0, result.output
    assert "CSV has no currency column; falling back to EUR" in result.output
    assert "N26 CSV has no currency column" not in result.output


@pytest.mark.parametrize(
    ("filename", "contents"),
    [
        (
            "missing-currency.csv",
            "Date,Description,Amount\n2026-04-15,Invoice 1,121.00\n",
        ),
        (
            "blank-currency.csv",
            _N26_HEADER + "2026-04-15,Client SL,Invoice 1,121.00,,n26-001\n",
        ),
    ],
)
def test_missing_or_blank_csv_currency_imports_as_default_and_list_view_succeed(
    tmp_path: Path,
    filename: str,
    contents: str,
) -> None:
    """Missing or blank CSV currency defaults at import and never breaks list/view payload validation."""
    statement = tmp_path / filename
    statement.write_text(contents, encoding="utf-8")

    imported = _invoke(["app", "ledger", "import", "--file", str(statement), "--provider", "csv"])
    assert imported.exit_code == 0, imported.output

    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = json.loads(listed.output)["result"]["rows"]
    assert len(rows) == 1
    assert rows[0]["currency"] == "EUR"

    viewed = _invoke(["--format", "json", "app", "ledger", "view", rows[0]["transaction_id"]])
    assert viewed.exit_code == 0, viewed.output
    assert json.loads(viewed.output)["result"]["transaction"]["currency"] == "EUR"


def test_short_csv_currency_refuses_at_import_with_currency_column_message(tmp_path: Path) -> None:
    """A malformed nonblank CSV currency cell is not misreported as config repair."""
    statement = tmp_path / "short-currency.csv"
    statement.write_text(
        _N26_HEADER + "2026-04-15,Client SL,Invoice 1,121.00,EU,n26-001\n",
        encoding="utf-8",
    )

    result = _invoke(["app", "ledger", "import", "--file", str(statement), "--provider", "csv"])

    assert result.exit_code != 0
    assert "CSV row 2" in result.output
    assert "currency column" in result.output
    assert "EU" in result.output
    assert "command input failed validation" not in result.output.lower()
    assert "config repair" not in result.output.lower()


@pytest.mark.parametrize(
    ("locale", "inner_fragment"),
    [
        ("es", "Formato de fecha no válido"),
        ("ca", "Format de data no vàlid"),
        ("hu", "Érvénytelen dátumformátum"),
    ],
)
def test_malformed_csv_date_import_localises_inner_reason(
    tmp_path: Path,
    locale: str,
    inner_fragment: str,
) -> None:
    """A malformed CSV date keeps row and column context without leaking raw English."""
    statement = tmp_path / f"bad-date-{locale}.csv"
    statement.write_text(
        _N26_HEADER + "not-a-date,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )

    result = _invoke(["--language", locale, "app", "ledger", "import", "--file", str(statement), "--provider", "csv"])

    assert result.exit_code != 0
    flattened = " ".join(result.output.split())
    assert "CSV row 2" in flattened
    assert "Date" in flattened
    assert "not-a-date" in flattened
    assert "YYYY-MM-DD" in flattened
    assert inner_fragment in flattened
    assert "unsupported date format" not in flattened


def test_import_of_a_headers_only_csv_explains_zero_rows(tmp_path: Path) -> None:
    """A parsed-but-empty CSV explains the zero result, never silently.

    A header-only N26 CSV fails provider validation outright with a
    specific "no data rows" reason. The operator must see that reason
    rather than a bare "imported 0" success line — the silent-success
    path is the defect.
    """
    statement = tmp_path / "empty.csv"
    statement.write_text(_N26_HEADER, encoding="utf-8")
    result = _invoke(["app", "ledger", "import", "--file", str(statement), "--provider", "csv"])
    assert result.exit_code != 0
    assert "no data rows" in result.output.lower()


def test_import_of_a_blank_data_row_csv_emits_a_notice(tmp_path: Path) -> None:
    """A CSV that validates but yields no rows carries an explicit notice.

    A recognised header followed only by an all-whitespace data row
    passes provider validation, parses to zero rows, and previously
    reported a bare "imported 0" with exit 0 — indistinguishable from
    success. The notice line is the fix.
    """
    statement = tmp_path / "blank.csv"
    statement.write_text(_N26_HEADER + " , , , , , \n", encoding="utf-8")
    result = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "csv"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["imported"] == 0
    assert "empty_import_notice" in payload
    assert "no data rows" in payload["empty_import_notice"].lower()


def test_reimport_of_existing_rows_explains_the_zero_import(tmp_path: Path) -> None:
    """Re-importing only-duplicate rows reports why nothing was added."""
    statement = tmp_path / "statement.csv"
    statement.write_text(
        _N26_HEADER + "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    first = _invoke(["app", "ledger", "import", "--file", str(statement), "--provider", "csv"])
    assert first.exit_code == 0, first.output
    second = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "csv"],
    )
    assert second.exit_code == 0, second.output
    payload = json.loads(second.output)["result"]
    assert payload["imported"] == 0
    assert payload["skipped"] == 1
    assert "empty_import_notice" in payload
    assert "duplicate" in payload["empty_import_notice"].lower()


def test_import_dry_run_reports_the_real_would_import_count(tmp_path: Path) -> None:
    """`import --dry-run` previews the true count, never a flat zero.

    The defect: a dry run reported `imported 0` even when a real import
    of the same file added four rows. The preview must report what a
    real import would add.
    """
    statement = tmp_path / "statement.csv"
    statement.write_text(_FOUR_ROW_CSV, encoding="utf-8")

    dry_run = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "csv", "--dry-run"],
    )
    assert dry_run.exit_code == 0, dry_run.output
    payload = json.loads(dry_run.output)["result"]
    assert payload["dry_run"] is True
    assert payload["imported"] == 4
    assert payload["skipped"] == 0
    assert "dry_run_notice" in payload

    real = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "csv"],
    )
    assert real.exit_code == 0, real.output
    assert json.loads(real.output)["result"]["imported"] == 4


def test_import_dry_run_counts_existing_rows_as_would_skip(tmp_path: Path) -> None:
    """After a real import the dry run previews every row as a would-skip."""
    statement = tmp_path / "statement.csv"
    statement.write_text(_FOUR_ROW_CSV, encoding="utf-8")

    first = _invoke(["app", "ledger", "import", "--file", str(statement), "--provider", "csv"])
    assert first.exit_code == 0, first.output

    dry_run = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "csv", "--dry-run"],
    )
    assert dry_run.exit_code == 0, dry_run.output
    payload = json.loads(dry_run.output)["result"]
    assert payload["imported"] == 0
    assert payload["skipped"] == 4


def test_reimport_after_editing_a_transaction_still_deduplicates(
    tmp_path: Path,
) -> None:
    """An edited transaction is not re-imported as a fresh duplicate.

    The defect: editing a row changed its content-derived id, so a
    re-import of the source statement re-added the edited row. The
    stamped import fingerprint is stable across the edit.
    """
    statement = tmp_path / "statement.csv"
    statement.write_text(_FOUR_ROW_CSV, encoding="utf-8")

    first = _invoke(["app", "ledger", "import", "--file", str(statement), "--provider", "csv"])
    assert first.exit_code == 0, first.output

    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    rows = json.loads(listed.output)["result"]["rows"]
    assert len(rows) == 4
    target = rows[0]["transaction_id"]

    edited = _invoke(
        ["app", "ledger", "update", target, "--description", "Invoice 1 - corrected narrative"],
    )
    assert edited.exit_code == 0, edited.output

    reimport = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "csv"],
    )
    assert reimport.exit_code == 0, reimport.output
    payload = json.loads(reimport.output)["result"]
    assert payload["imported"] == 0, payload
    assert payload["skipped"] == 4
    after = _invoke(["--format", "json", "app", "ledger", "list"])
    assert len(json.loads(after.output)["result"]["rows"]) == 4


def test_cross_format_import_of_the_same_movements_deduplicates(
    tmp_path: Path,
) -> None:
    """Importing the same movements as OFX after CSV adds nothing.

    The defect: an OFX re-export of bank movements already imported
    from a CSV duplicated every row, because the dedup key folded in
    the provider id and file format.
    """
    csv_statement = tmp_path / "statement.csv"
    csv_statement.write_text(_FOUR_ROW_CSV, encoding="utf-8")
    ofx_statement = tmp_path / "statement.ofx"
    ofx_statement.write_text(_FOUR_ROW_OFX, encoding="ascii")

    csv_import = _invoke(["app", "ledger", "import", "--file", str(csv_statement), "--provider", "csv"])
    assert csv_import.exit_code == 0, csv_import.output

    ofx_import = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(ofx_statement), "--provider", "ofx"],
    )
    assert ofx_import.exit_code == 0, ofx_import.output
    payload = json.loads(ofx_import.output)["result"]
    assert payload["imported"] == 0, payload
    assert payload["skipped"] == 4
    after = _invoke(["--format", "json", "app", "ledger", "list"])
    assert len(json.loads(after.output)["result"]["rows"]) == 4


def test_import_warns_on_likely_cross_format_duplicate(tmp_path: Path) -> None:
    """A same-date same-amount row with a divergent narrative is flagged.

    When a confident fingerprint match cannot be made but the date and
    amount coincide with an existing row, the row is imported and the
    operator is warned about a likely duplicate rather than silently
    double-counting it.
    """
    first = tmp_path / "first.csv"
    first.write_text(
        _N26_HEADER + "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    assert _invoke(["app", "ledger", "import", "--file", str(first), "--provider", "csv"]).exit_code == 0

    second = tmp_path / "second.csv"
    second.write_text(
        _N26_HEADER + "2026-04-15,Client SL,TRANSFER 99887766,121.00,EUR,xx-999\n",
        encoding="utf-8",
    )
    result = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(second), "--provider", "csv"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["imported"] == 1
    assert payload["likely_duplicates"] == 1
    assert "likely_duplicate_notice" in payload


def test_verify_source_hashes_the_named_file_only_when_verify_is_also_set(tmp_path: Path) -> None:
    """`--verify-source` only takes effect paired with `--verify`.

    `--file` names the statement to import; `--verify-source` names a
    separate original file to hash for provenance. Passing `--verify-source`
    alone is a no-op (matching the backend's `verify`-gated hashing), so the
    combination must be exercised explicitly to prove `--verify-source`
    reaches the backend at all.
    """
    statement = tmp_path / "statement.csv"
    statement.write_text(
        _N26_HEADER + "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    original = tmp_path / "original-export.csv"
    original.write_text(statement.read_text(encoding="utf-8"), encoding="utf-8")

    unverified = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "csv", "--dry-run"],
    )
    assert unverified.exit_code == 0, unverified.output
    unverified_source = json.loads(unverified.output)["result"]["source"]
    assert unverified_source["requested"] is False
    assert unverified_source["path"] is None
    assert unverified_source["sha256"] is None

    verify_without_source_file = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "import",
            "--file",
            str(statement),
            "--provider",
            "csv",
            "--dry-run",
            "--verify",
        ],
    )
    assert verify_without_source_file.exit_code == 0, verify_without_source_file.output
    verify_only_source = json.loads(verify_without_source_file.output)["result"]["source"]
    assert verify_only_source["requested"] is True
    assert verify_only_source["path"] is None
    assert verify_only_source["sha256"] is None

    verified = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "import",
            "--file",
            str(statement),
            "--provider",
            "csv",
            "--dry-run",
            "--verify",
            "--verify-source",
            str(original),
        ],
    )
    assert verified.exit_code == 0, verified.output
    verified_source = json.loads(verified.output)["result"]["source"]
    assert verified_source["requested"] is True
    assert verified_source["path"] == str(original.resolve())
    assert verified_source["sha256"] is not None
    assert verified_source["sha256"] != unverified_source["sha256"]

    verify_source_without_verify = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "import",
            "--file",
            str(statement),
            "--provider",
            "csv",
            "--dry-run",
            "--verify-source",
            str(original),
        ],
    )
    assert verify_source_without_verify.exit_code == 0, verify_source_without_verify.output
    ignored_source = json.loads(verify_source_without_verify.output)["result"]["source"]
    assert ignored_source["requested"] is False
    assert ignored_source["path"] is None
    assert ignored_source["sha256"] is None
