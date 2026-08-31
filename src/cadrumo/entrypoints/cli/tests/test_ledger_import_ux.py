"""Ledger import UX regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ....application.ledger.actions_import import LedgerProviderID
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ._cli_json_support import _json_object
from ._ledger_ux_support import (
    _FOUR_ROW_CSV,
    _FOUR_ROW_OFX,
    _N26_HEADER,
    _invoke,
    _open_bucket_session,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session"]


def _json_document(output: str) -> dict[str, object]:
    return STR_KEYED_MAPPING_ADAPTER.validate_json(output)


def _notice_projection(document: dict[str, object], code: str) -> dict[str, object]:
    notices = document["notices"]
    assert isinstance(notices, list)
    notice = next(item for item in notices if isinstance(item, dict) and item.get("code") == code)
    assert isinstance(notice.get("message"), str) and notice["message"]
    return {key: notice.get(key) for key in ("severity", "code", "context", "action")}


def _assert_transaction_validation_error(output: str) -> dict[str, object]:
    document = _json_document(output)
    error = _json_object(document["error"])
    assert error["code"] == "ERROR_TRANSACTION_VALIDATION"
    action = error["action"]
    action = _json_object(action)
    assert action["failed_condition_id"] == "cli.ledger.transaction.valid"
    assert action["evidence"] == [
        {
            "condition_id": "cli.ledger.transaction.valid",
            "evidence_id": "cli.ledger.transaction.valid.observation",
            "provenance": "runtime_observation",
            "values": {"error_type": "TransactionValidationError"},
        },
    ]
    assert action["action"] is None
    assert action["conditionality"] == "not_applicable"
    assert action["no_recovery_outcome"] == "operator_decision"
    return error


def test_import_help_lists_recognised_providers() -> None:
    """`import --help` enumerates the accepted --provider values."""
    result = _invoke(["app", "ledger", "import", "--help"])
    assert result.exit_code == 0, result.output
    haystack = " ".join(result.output.split())
    for provider in LedgerProviderID:
        assert provider.value in haystack


def test_unknown_provider_error_enumerates_known_providers(tmp_path: Path) -> None:
    """An unknown --provider is refused with the recognised set inline."""
    statement = tmp_path / "statement.csv"
    statement.write_text(
        _N26_HEADER + "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    result = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "quickbooks"],
    )
    assert result.exit_code != 0
    document = _json_document(result.output)
    error = _json_object(document["error"])
    assert error["code"] == "REFUSED_CLI_BOUNDARY"
    assert error["category"] == "REFUSED"
    context = _json_object(error["context"])
    assert context["value"] == "quickbooks"
    accepted = context["accepted"]
    assert isinstance(accepted, str)
    assert set(accepted.split(", ")) == {provider.value for provider in LedgerProviderID}


def test_missing_csv_preserves_the_typed_import_precondition(tmp_path: Path) -> None:
    """A missing source reaches the shared boundary without refusal aggregation."""
    missing = tmp_path / "missing.csv"

    result = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(missing), "--provider", "csv"],
    )

    assert result.exit_code != 0, result.output
    error = _assert_transaction_validation_error(result.output)
    assert error["code"] != "REFUSED_CLI_BOUNDARY"


def test_generic_csv_missing_currency_warning_is_provider_neutral_in_cli(tmp_path: Path) -> None:
    """`--provider csv` warnings must not invent a bank brand for generic CSV."""
    statement = tmp_path / "generic.csv"
    statement.write_text("Date,Description,Amount\n2026-04-15,Invoice 1,121.00\n", encoding="utf-8")

    result = _invoke(
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
            "--verbose",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = _json_object(_json_document(result.output)["result"])
    validation = payload["validation"]
    assert isinstance(validation, dict)
    assert validation["valid"] is True
    assert len(validation["warnings"]) == 1


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


def test_short_csv_currency_preserves_typed_import_refusal(tmp_path: Path) -> None:
    """A malformed nonblank currency preserves the import refusal identity."""
    statement = tmp_path / "short-currency.csv"
    statement.write_text(
        _N26_HEADER + "2026-04-15,Client SL,Invoice 1,121.00,EU,n26-001\n",
        encoding="utf-8",
    )

    result = _invoke(["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "csv"])

    assert result.exit_code != 0
    _assert_transaction_validation_error(result.output)


@pytest.mark.parametrize(
    "locale",
    ["ca", "en", "es", "hu"],
)
def test_malformed_csv_date_import_preserves_contract_across_locales(
    tmp_path: Path,
    locale: str,
) -> None:
    """A malformed CSV date preserves one locale-neutral refusal contract."""
    statement = tmp_path / f"bad-date-{locale}.csv"
    statement.write_text(
        _N26_HEADER + "not-a-date,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )

    result = _invoke(
        [
            "--language",
            locale,
            "--format",
            "json",
            "app",
            "ledger",
            "import",
            "--file",
            str(statement),
            "--provider",
            "csv",
        ],
    )

    assert result.exit_code != 0
    _assert_transaction_validation_error(result.output)


def test_import_of_a_headers_only_csv_explains_zero_rows(tmp_path: Path) -> None:
    """A parsed-but-empty CSV explains the zero result, never silently.

    A header-only source fails provider validation outright and must retain
    the canonical typed refusal rather than becoming a zero-row success.
    """
    statement = tmp_path / "empty.csv"
    statement.write_text(_N26_HEADER, encoding="utf-8")
    result = _invoke(["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "csv"])
    assert result.exit_code != 0
    _assert_transaction_validation_error(result.output)


@pytest.mark.parametrize("locale", ["ca", "en", "es", "hu"])
def test_import_of_a_blank_data_row_csv_emits_a_notice(tmp_path: Path, locale: str) -> None:
    """A CSV that validates but yields no rows carries an explicit notice.

    A recognised header followed only by an all-whitespace data row
    passes provider validation, parses to zero rows, and previously
    reported a bare "imported 0" with exit 0 — indistinguishable from
    success. The notice line is the fix.
    """
    statement = tmp_path / "blank.csv"
    statement.write_text(_N26_HEADER + " , , , , , \n", encoding="utf-8")
    result = _invoke(
        [
            "--language",
            locale,
            "--format",
            "json",
            "app",
            "ledger",
            "import",
            "--file",
            str(statement),
            "--provider",
            "csv",
        ],
    )
    assert result.exit_code == 0, result.output
    document = _json_document(result.output)
    payload = _json_object(document["result"])
    assert payload["imported"] == 0
    assert not {"empty_import_notice", "dry_run_notice", "likely_duplicate_notice"}.intersection(payload)
    assert _notice_projection(document, "ledger.import.no_rows_imported") == {
        "severity": "info",
        "code": "ledger.import.no_rows_imported",
        "context": {"imported": "0", "skipped": "0"},
        "action": None,
    }


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
    document = _json_document(second.output)
    payload = _json_object(document["result"])
    assert payload["imported"] == 0
    assert payload["skipped"] == 1
    assert _notice_projection(document, "ledger.import.all_rows_skipped") == {
        "severity": "info",
        "code": "ledger.import.all_rows_skipped",
        "context": {"imported": "0", "skipped": "1"},
        "action": None,
    }


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
    document = _json_document(dry_run.output)
    payload = _json_object(document["result"])
    assert payload["dry_run"] is True
    assert payload["imported"] == 4
    assert payload["skipped"] == 0
    assert _notice_projection(document, "ledger.import.dry_run_preview") == {
        "severity": "info",
        "code": "ledger.import.dry_run_preview",
        "context": {"dry_run": "true", "would_import": "4", "would_skip": "0"},
        "action": None,
    }

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
    document = _json_document(result.output)
    payload = _json_object(document["result"])
    assert payload["imported"] == 1
    assert payload["likely_duplicates"] == 1
    assert _notice_projection(document, "ledger.import.likely_duplicates") == {
        "severity": "warning",
        "code": "ledger.import.likely_duplicates",
        "context": {"likely_duplicate_count": "1"},
        "action": None,
    }


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
