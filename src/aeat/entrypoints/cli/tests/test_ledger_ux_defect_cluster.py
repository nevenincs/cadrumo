"""Real-behavior regressions for the ledger-UX defect cluster.

Each test reproduces one operator-facing failure surfaced by the
persona testimonials and pins the corrected behaviour:

- a discoverable, validated ``--category-id`` catalogue;
- a discoverable ``--provider`` value list;
- an explained zero-import result;
- a specific cause behind the previously opaque
  "command input failed validation" refusal on ``ledger add`` and
  ``ledger review`` (positional id).

The tests drive the real Typer app end to end against an isolated
``AEAT_LOCAL_STORAGE_ROOT`` — no mocks, no patched validators.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....domain.categories import SpendingCategory
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RUNNER = CliRunner()

_N26_HEADER = "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"

#: Profile id every test in this module creates via the CLI inside the span.
_PROFILE_ID = "tester"


@pytest.fixture(autouse=True)
def _open_bucket_session(tmp_path: Path) -> Iterator[None]:
    """Hold an active bucket session open across this module's in-process invokes.

    The active bucket session is a per-process/per-context ContextVar opened by
    the storage master-key provider. Profile identity is an immutable bucket id
    distinct from the display label, so these tests seed a real profile under
    the same id as the held storage span instead of opening a second
    UUID-backed in-process CLI create session.
    """
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_PROFILE_ID),
    ):
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id=_PROFILE_ID))
        try:
            yield
        finally:
            dispose_engine()


def _imported_transaction_id(tmp_path: Path) -> str:
    statement = tmp_path / "statement.csv"
    statement.write_text(
        _N26_HEADER + "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    imported = _RUNNER.invoke(app, ["app", "ledger", "import", str(statement), "--provider", "csv"])
    assert imported.exit_code == 0, imported.output
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    rows = payload.get("result", payload).get("rows", [])
    assert rows, listed.output
    return rows[0]["transaction_id"]


# --- M9: discoverable + validated --category-id -----------------------------


def test_categories_command_lists_the_canonical_spending_taxonomy(
    tmp_path: Path,
) -> None:
    """`ledger categories` enumerates every SpendingCategory id."""
    result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "categories"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    listed = set(payload["category_ids"])
    expected = {category.value for category in SpendingCategory}
    assert listed == expected
    # Every listed id must belong to a family group, never float free.
    grouped = {category_id for family in payload["families"] for category_id in family["category_ids"]}
    assert grouped == expected


def test_classify_rejects_an_invented_category_id(tmp_path: Path) -> None:
    """An id outside the closed taxonomy is refused, not silently kept."""
    txn = _imported_transaction_id(tmp_path)
    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "BUSINESS",
            "--category-id",
            "ventas_actividad",
        ],
    )
    assert result.exit_code != 0
    assert "ventas_actividad" in result.output
    assert "ledger categories" in result.output


def test_classify_accepts_a_canonical_category_id(tmp_path: Path) -> None:
    """A real SpendingCategory id still classifies successfully."""
    txn = _imported_transaction_id(tmp_path)
    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "BUSINESS",
            "--category-id",
            SpendingCategory.MATERIAL_OFICINA.value,
        ],
    )
    assert result.exit_code == 0, result.output
    transaction = json.loads(result.output)["result"]["transaction"]
    assert transaction["category_id"] == SpendingCategory.MATERIAL_OFICINA.value


def test_classify_reaffirm_json_output_is_a_single_envelope(tmp_path: Path) -> None:
    """`--reaffirm` must not print a plain-text notice before JSON output."""
    txn = _imported_transaction_id(tmp_path)
    first = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "BUSINESS",
        ],
    )
    assert first.exit_code == 0, first.output

    reaffirmed = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "100.00",
            "--reaffirm",
        ],
    )

    assert reaffirmed.exit_code == 0, reaffirmed.output
    assert reaffirmed.output.lstrip().startswith("{")
    payload = json.loads(reaffirmed.output)
    assert payload["command"] == "ledger.classify"
    assert payload["result"]["transaction"]["business_classification"] == "BUSINESS"
    assert payload["result"]["transaction"]["taxable_base"] == "100"


# --- M11: discoverable --provider list --------------------------------------


def test_import_help_lists_recognised_providers() -> None:
    """`import --help` enumerates the accepted --provider values."""
    result = _RUNNER.invoke(app, ["app", "ledger", "import", "--help"])
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
    result = _RUNNER.invoke(app, ["app", "ledger", "import", str(statement), "--provider", "quickbooks"])
    assert result.exit_code != 0
    assert "quickbooks" in result.output
    for provider in ("csv", "ofx", "xlsx", "n26"):
        assert provider in result.output


# --- M12: explained zero-import ---------------------------------------------


def test_import_of_a_headers_only_csv_explains_zero_rows(tmp_path: Path) -> None:
    """A parsed-but-empty CSV explains the zero result, never silently.

    A header-only N26 CSV fails provider validation outright with a
    specific "no data rows" reason. The operator must see that reason
    rather than a bare "imported 0" success line — the silent-success
    path is the defect.
    """
    statement = tmp_path / "empty.csv"
    statement.write_text(_N26_HEADER, encoding="utf-8")
    result = _RUNNER.invoke(app, ["app", "ledger", "import", str(statement), "--provider", "csv"])
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
    result = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv"],
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
    first = _RUNNER.invoke(app, ["app", "ledger", "import", str(statement), "--provider", "csv"])
    assert first.exit_code == 0, first.output
    second = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv"],
    )
    assert second.exit_code == 0, second.output
    payload = json.loads(second.output)["result"]
    assert payload["imported"] == 0
    assert payload["skipped"] == 1
    assert "empty_import_notice" in payload
    assert "duplicate" in payload["empty_import_notice"].lower()


# --- M8: specific cause behind the opaque add refusal -----------------------


def test_add_with_business_pct_on_a_business_row_surfaces_the_real_cause(
    tmp_path: Path,
) -> None:
    """The illegal --business-pct/--classification pair names the field.

    A non-MIXED classification forbids --business-pct. The refusal must
    name that exact rule rather than the misleading "run config repair".
    """
    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "121.00",
            "--direction",
            "OUTGOING",
            "--description",
            "Office chair",
            "--classification",
            "BUSINESS",
            "--business-pct",
            "1.0",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21.00",
        ],
    )
    assert result.exit_code != 0
    assert "business_pct" in result.output
    assert "MIXED" in result.output
    assert "config repair" not in result.output


def test_add_business_row_without_business_pct_succeeds(tmp_path: Path) -> None:
    """The same row minus --business-pct is legal and still works."""
    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "121.00",
            "--direction",
            "OUTGOING",
            "--description",
            "Office chair",
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21.00",
        ],
    )
    assert result.exit_code == 0, result.output
    transaction = json.loads(result.output)["result"]["transaction"]
    assert transaction["business_classification"] == "BUSINESS"


# --- M10: review positional id resolves a short prefix -------------------------------


def test_review_by_short_id_prefix_resolves_the_transaction(
    tmp_path: Path,
) -> None:
    """`review <prefix>` resolves the prefix instead of refusing."""
    txn = _imported_transaction_id(tmp_path)
    result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "review", txn[:8]])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["id"] == txn
    assert "config repair" not in result.output


def test_review_by_full_id_still_resolves_the_transaction(
    tmp_path: Path,
) -> None:
    """`review <full>` keeps working after the prefix-resolution fix."""
    txn = _imported_transaction_id(tmp_path)
    result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "review", txn])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["result"]["id"] == txn


# --- ledger view shows the full stored field set ----------------------------


def test_ledger_view_shows_iva_counterparty_and_notes_detail(
    tmp_path: Path,
) -> None:
    """`ledger view` must confirm every stored field, not just id / date /
    amount / description / review-state.

    An operator who entered IVA fields, a counterparty, and notes had no
    way to verify those persisted: the old view rendered five fields and
    dropped the rest. The full stored field set is now shown.
    """
    added = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "121.00",
            "--direction",
            "OUTGOING",
            "--description",
            "Office chair",
            "--counterparty",
            "Muebles SL",
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21.00",
            "--notes",
            "Q2 furniture",
        ],
    )
    assert added.exit_code == 0, added.output
    txn = json.loads(added.output)["result"]["transaction_id"]

    viewed = _RUNNER.invoke(app, ["app", "ledger", "view", txn[:8]])
    assert viewed.exit_code == 0, viewed.output
    output = viewed.output
    # The IVA triple the operator entered is visible for confirmation.
    # Decimal values are rendered in their normalized form.
    assert "Taxable base\t100" in output
    assert "IVA rate\t0.21" in output
    assert "IVA amount\t21" in output
    # Counterparty, classification, and notes are visible too.
    assert "Muebles SL" in output
    assert "BUSINESS" in output
    assert "Q2 furniture" in output


_MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def test_ledger_view_shows_the_linked_purchase_invoice_evidence_id(tmp_path: Path) -> None:
    """`ledger view` must surface the linked purchase-invoice evidence id.

    The evidence link is persisted and present on the JSON payload, but the
    text view dropped it, so an operator who ran ``evidence add`` then
    ``attach`` could not confirm from ``view`` that the invoice was linked.
    This drives the documented ``evidence add`` -> ``attach`` -> ``view`` flow
    end to end (the gap no in-tree test exercised) and pins the rendered id.
    """
    txn = _imported_transaction_id(tmp_path)

    pdf = tmp_path / "factura.pdf"
    pdf.write_bytes(_MINIMAL_PDF)
    added = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "evidence", "add", str(pdf), "--supplier", "Proveedor SL"],
    )
    assert added.exit_code == 0, added.output
    evidence_id = json.loads(added.output)["result"]["evidence_id"]

    attached = _RUNNER.invoke(
        app,
        ["app", "ledger", "attach", txn, "--purchase-invoice-evidence-id", evidence_id],
    )
    assert attached.exit_code == 0, attached.output

    viewed = _RUNNER.invoke(app, ["app", "ledger", "view", txn[:8]])
    assert viewed.exit_code == 0, viewed.output
    assert f"Purchase invoice evidence\t{evidence_id}" in viewed.output


def test_ledger_view_json_carries_the_full_transaction(tmp_path: Path) -> None:
    """The JSON payload exposes the typed transaction with every field,
    so the text view and the JSON contract agree."""
    added = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "242.00",
            "--direction",
            "OUTGOING",
            "--description",
            "Laptop",
            "--counterparty",
            "PC Shop SL",
            "--taxable-base",
            "200.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "42.00",
        ],
    )
    assert added.exit_code == 0, added.output
    txn = json.loads(added.output)["result"]["transaction_id"]

    viewed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "view", txn])
    assert viewed.exit_code == 0, viewed.output
    transaction = json.loads(viewed.output)["result"]["transaction"]
    assert transaction["counterparty"] == "PC Shop SL"
    # Decimal fields are carried in their normalized display form.
    assert transaction["taxable_base"] == "200"
    assert transaction["iva_rate"] == "0.21"
    assert transaction["iva_amount"] == "42"


# ---------------------------------------------------------------------------
# B1-B3: import dry-run preview + edit-stable / cross-format deduplication
# ---------------------------------------------------------------------------

_FOUR_ROW_CSV = (
    _N26_HEADER
    + "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n"
    + "2026-04-16,Proveedor SA,Compra material,-50.00,EUR,n26-002\n"
    + "2026-04-17,Cliente Dos,Factura dos,200.00,EUR,n26-003\n"
    + "2026-04-18,Cafe Oscar,Reunion negocios,-12.00,EUR,n26-004\n"
)

_FOUR_ROW_OFX = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX><BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS>\
<STMTRS><CURDEF>EUR<BANKACCTFROM><BANKID>0001<ACCTID>ES111<ACCTTYPE>CHECKING\
</BANKACCTFROM><BANKTRANLIST><DTSTART>20260401<DTEND>20260430\
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260415<TRNAMT>121.00<FITID>ofx-001\
<NAME>Client SL<MEMO>Invoice 1</STMTTRN>\
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260416<TRNAMT>-50.00<FITID>ofx-002\
<NAME>Proveedor SA<MEMO>Compra material</STMTTRN>\
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260417<TRNAMT>200.00<FITID>ofx-003\
<NAME>Cliente Dos<MEMO>Factura dos</STMTTRN>\
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260418<TRNAMT>-12.00<FITID>ofx-004\
<NAME>Cafe Oscar<MEMO>Reunion negocios</STMTTRN>\
</BANKTRANLIST><LEDGERBAL><BALAMT>259.00<DTASOF>20260430</LEDGERBAL>\
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


def test_import_dry_run_reports_the_real_would_import_count(tmp_path: Path) -> None:
    """`import --dry-run` previews the true count, never a flat zero.

    The defect: a dry run reported `imported 0` even when a real import
    of the same file added four rows. The preview must report what a
    real import would add.
    """
    statement = tmp_path / "statement.csv"
    statement.write_text(_FOUR_ROW_CSV, encoding="utf-8")

    dry_run = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv", "--dry-run"],
    )
    assert dry_run.exit_code == 0, dry_run.output
    payload = json.loads(dry_run.output)["result"]
    assert payload["dry_run"] is True
    assert payload["imported"] == 4
    assert payload["skipped"] == 0
    assert "dry_run_notice" in payload

    # A real import of the same file adds exactly what the preview said.
    real = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv"],
    )
    assert real.exit_code == 0, real.output
    assert json.loads(real.output)["result"]["imported"] == 4


def test_import_dry_run_counts_existing_rows_as_would_skip(tmp_path: Path) -> None:
    """After a real import the dry run previews every row as a would-skip."""
    statement = tmp_path / "statement.csv"
    statement.write_text(_FOUR_ROW_CSV, encoding="utf-8")

    first = _RUNNER.invoke(app, ["app", "ledger", "import", str(statement), "--provider", "csv"])
    assert first.exit_code == 0, first.output

    dry_run = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv", "--dry-run"],
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

    first = _RUNNER.invoke(app, ["app", "ledger", "import", str(statement), "--provider", "csv"])
    assert first.exit_code == 0, first.output

    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    rows = json.loads(listed.output)["result"]["rows"]
    assert len(rows) == 4
    target = rows[0]["transaction_id"]

    edited = _RUNNER.invoke(
        app,
        ["app", "ledger", "update", target, "--description", "Invoice 1 - corrected narrative"],
    )
    assert edited.exit_code == 0, edited.output

    reimport = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv"],
    )
    assert reimport.exit_code == 0, reimport.output
    payload = json.loads(reimport.output)["result"]
    assert payload["imported"] == 0, payload
    assert payload["skipped"] == 4
    # The catalogue still holds exactly four rows — no duplicate of the
    # edited transaction.
    after = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
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

    csv_import = _RUNNER.invoke(app, ["app", "ledger", "import", str(csv_statement), "--provider", "csv"])
    assert csv_import.exit_code == 0, csv_import.output

    ofx_import = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "import", str(ofx_statement), "--provider", "ofx"],
    )
    assert ofx_import.exit_code == 0, ofx_import.output
    payload = json.loads(ofx_import.output)["result"]
    assert payload["imported"] == 0, payload
    assert payload["skipped"] == 4
    after = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
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
    assert _RUNNER.invoke(app, ["app", "ledger", "import", str(first), "--provider", "csv"]).exit_code == 0

    # Same date and amount, deliberately different reference text.
    second = tmp_path / "second.csv"
    second.write_text(
        _N26_HEADER + "2026-04-15,Client SL,TRANSFER 99887766,121.00,EUR,xx-999\n",
        encoding="utf-8",
    )
    result = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "import", str(second), "--provider", "csv"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["imported"] == 1
    assert payload["likely_duplicates"] == 1
    assert "likely_duplicate_notice" in payload


# ---------------------------------------------------------------------------
# C1: classify surfaces the specific validator cause
# ---------------------------------------------------------------------------


def test_classify_with_negative_taxable_base_names_the_real_cause(
    tmp_path: Path,
) -> None:
    """A negative `--taxable-base` on classify surfaces the validator cause.

    The opaque "command input failed validation. Run config repair"
    refusal is replaced with the specific reason; `config repair`
    cannot fix a bad CLI argument and must not be suggested.
    """
    txn = _imported_transaction_id(tmp_path)
    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "classify", txn, "--classification", "BUSINESS", "--taxable-base", "-397.11"],
    )
    assert result.exit_code != 0
    assert "taxable_base" in result.output
    assert "config repair" not in result.output


def test_classify_with_valid_taxable_base_still_succeeds(tmp_path: Path) -> None:
    """A non-negative `--taxable-base` classifies the row normally."""
    txn = _imported_transaction_id(tmp_path)
    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "100.00",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["result"]["transaction"]["taxable_base"] == "100"


# ---------------------------------------------------------------------------
# C2: categories output is unambiguous about the --category-id value
# ---------------------------------------------------------------------------


def test_categories_output_names_the_category_id_column(tmp_path: Path) -> None:
    """The catalogue makes the exact `--category-id` value unmistakable."""
    result = _RUNNER.invoke(app, ["app", "ledger", "categories"])
    assert result.exit_code == 0, result.output
    output = result.output
    # A header row names the id column, and an example line shows the
    # bare-id shape so operators do not guess a compound key.
    assert "category-id" in output
    assert "--category-id" in output
    assert SpendingCategory.MATERIAL_OFICINA.value in output


def test_invalid_category_error_shows_a_concrete_valid_example(
    tmp_path: Path,
) -> None:
    """A rejected `--category-id` names one concrete valid id."""
    txn = _imported_transaction_id(tmp_path)
    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "BUSINESS",
            "--category-id",
            "office:material_oficina",
        ],
    )
    assert result.exit_code != 0
    valid_ids = {category.value for category in SpendingCategory}
    # The refusal demonstrates the bare-id shape with a real example.
    assert any(category_id in result.output for category_id in valid_ids)
    assert "ledger categories" in result.output


# ---------------------------------------------------------------------------
# C4: sibling-command consistency
# ---------------------------------------------------------------------------


def test_classify_accepts_business_pct_for_a_mixed_row(tmp_path: Path) -> None:
    """`classify --classification MIXED --business-pct` works in one step."""
    txn = _imported_transaction_id(tmp_path)
    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "MIXED",
            "--business-pct",
            "0.5",
        ],
    )
    assert result.exit_code == 0, result.output
    transaction = json.loads(result.output)["result"]["transaction"]
    assert transaction["business_classification"] == "MIXED"
    assert transaction["business_pct"] == "0.5"


def test_classify_mixed_without_business_pct_names_the_flag(tmp_path: Path) -> None:
    """`classify --classification MIXED` without the share names `--business-pct`."""
    txn = _imported_transaction_id(tmp_path)
    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "classify", txn, "--classification", "MIXED"],
    )
    assert result.exit_code != 0
    assert "--business-pct" in result.output
    assert "config repair" not in result.output


def test_classify_business_pct_on_non_mixed_row_is_refused(tmp_path: Path) -> None:
    """`--business-pct` with a non-MIXED classification is refused, not dropped."""
    txn = _imported_transaction_id(tmp_path)
    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "classify", txn, "--classification", "BUSINESS", "--business-pct", "0.5"],
    )
    assert result.exit_code != 0
    assert "--business-pct" in result.output
    assert "MIXED" in result.output


def test_history_accepts_the_id_positionally_like_view(tmp_path: Path) -> None:
    """`ledger history <id>` takes the id positionally, matching `ledger view`."""
    txn = _imported_transaction_id(tmp_path)
    result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "history", txn])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["transaction_id"] == txn
    assert payload["event_count"] >= 1


# ---------------------------------------------------------------------------
# B4: accented descriptions render identically in `list` and `view`
# ---------------------------------------------------------------------------


def test_list_and_view_render_accented_descriptions_identically(
    tmp_path: Path,
) -> None:
    """Accented Spanish / Catalan descriptions survive `list` and `view`.

    `ledger list` and `ledger view` must render the same stored
    narrative byte-for-byte; an operator must not see one surface
    corrupt accents the other shows correctly. The accented text is
    asserted present, intact, in both surfaces.
    """
    accented = "Reunió de negòcis amb Òscar à Lleida"
    statement = tmp_path / "accents.csv"
    statement.write_text(
        _N26_HEADER + f"2026-04-15,Proveedor SA,{accented},-50.00,EUR,n26-acc\n",
        encoding="utf-8",
    )
    imported = _RUNNER.invoke(app, ["app", "ledger", "import", str(statement), "--provider", "csv"])
    assert imported.exit_code == 0, imported.output

    listed = _RUNNER.invoke(app, ["app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    assert accented in listed.output
    assert "?" not in listed.output

    txn = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    transaction_id = json.loads(txn.output)["result"]["rows"][0]["transaction_id"]
    viewed = _RUNNER.invoke(app, ["app", "ledger", "view", transaction_id])
    assert viewed.exit_code == 0, viewed.output
    assert accented in viewed.output
