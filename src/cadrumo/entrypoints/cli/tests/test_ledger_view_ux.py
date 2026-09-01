"""Ledger view UX regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .ledger_ux_support import _MINIMAL_PDF, _N26_HEADER, _imported_transaction_id, _invoke

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.usefixtures("open_bucket_cli_backend"),
]


def test_ledger_view_shows_iva_counterparty_and_notes_detail(
    tmp_path: Path,
) -> None:
    """`ledger view` must confirm every stored field, not just id / date /
    amount / description / review-state.

    An operator who entered IVA fields, a counterparty, and notes had no
    way to verify those persisted: the old view rendered five fields and
    dropped the rest. The full stored field set is now shown.
    """
    added = _invoke(
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

    viewed = _invoke(["app", "ledger", "view", txn[:8]])
    assert viewed.exit_code == 0, viewed.output
    output = viewed.output
    assert "Taxable base\t100" in output
    assert "IVA rate\t0.21" in output
    assert "IVA amount\t21" in output
    assert "Muebles SL" in output
    assert "BUSINESS" in output
    assert "Q2 furniture" in output


def test_ledger_view_shows_the_linked_purchase_invoice_evidence_id(tmp_path: Path) -> None:
    """`ledger view` must surface the linked purchase-invoice evidence id.

    The evidence link is persisted and present on the JSON payload, but the
    text view dropped it, so an operator who ran ``evidence add`` then
    ``attach`` could not confirm from ``view`` that the invoice was linked.
    This drives the documented ``evidence add`` -> ``attach`` -> ``view`` flow
    end to end and pins the rendered id.
    """
    txn = _imported_transaction_id(tmp_path)

    pdf = tmp_path / "factura.pdf"
    pdf.write_bytes(_MINIMAL_PDF)
    added = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "add", str(pdf), "--supplier", "Proveedor SL"],
    )
    assert added.exit_code == 0, added.output
    evidence_id = json.loads(added.output)["result"]["evidence_id"]

    attached = _invoke(
        ["app", "ledger", "attach", txn, "--purchase-invoice-evidence-id", evidence_id],
    )
    assert attached.exit_code == 0, attached.output

    viewed = _invoke(["app", "ledger", "view", txn[:8]])
    assert viewed.exit_code == 0, viewed.output
    assert f"Purchase invoice evidence\t{evidence_id}" in viewed.output


def test_ledger_history_shows_post_hoc_purchase_invoice_evidence_attach(tmp_path: Path) -> None:
    """A post-hoc supplier invoice attach must be visible in ledger history."""
    added_txn = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-02-15",
            "--amount",
            "121.00",
            "--direction",
            "OUTGOING",
            "--description",
            "Q1 supplier invoice",
            "--counterparty",
            "Proveedor SL",
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21.00",
            "--iva-category",
            "domestic_general",
        ],
    )
    assert added_txn.exit_code == 0, added_txn.output
    txn = json.loads(added_txn.output)["result"]["transaction_id"]

    pdf = tmp_path / "factura-q1.pdf"
    pdf.write_bytes(_MINIMAL_PDF)
    added_evidence = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "add", str(pdf), "--supplier", "Proveedor SL"],
    )
    assert added_evidence.exit_code == 0, added_evidence.output
    evidence_id = json.loads(added_evidence.output)["result"]["evidence_id"]

    attached = _invoke(
        ["app", "ledger", "attach", txn, "--purchase-invoice-evidence-id", evidence_id],
    )
    assert attached.exit_code == 0, attached.output

    viewed = _invoke(["--format", "json", "app", "ledger", "view", txn])
    assert viewed.exit_code == 0, viewed.output
    transaction = json.loads(viewed.output)["result"]["transaction"]
    assert transaction["purchase_invoice_evidence_id"] == evidence_id

    history = _invoke(["--format", "json", "app", "ledger", "history", txn])
    assert history.exit_code == 0, history.output
    events = json.loads(history.output)["result"]["events"]
    attach_events = [
        event
        for event in events
        if event["event_type"] == "purchase_invoice_evidence.attached"
        and event["object_type"] == "purchase_invoice_evidence"
        and event["object_id"] == evidence_id
    ]
    assert attach_events, history.output
    assert attach_events[0]["payload"]["transaction_id"] == txn

    text_history = _invoke(["app", "ledger", "history", txn])
    assert text_history.exit_code == 0, text_history.output
    assert "purchase_invoice_evidence.attached" in text_history.output


def test_ledger_view_json_carries_the_full_transaction(tmp_path: Path) -> None:
    """The JSON payload exposes the typed transaction with every field,
    so the text view and the JSON contract agree."""
    added = _invoke(
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

    viewed = _invoke(["--format", "json", "app", "ledger", "view", txn])
    assert viewed.exit_code == 0, viewed.output
    transaction = json.loads(viewed.output)["result"]["transaction"]
    assert transaction["counterparty"] == "PC Shop SL"
    assert transaction["taxable_base"] == "200"
    assert transaction["iva_rate"] == "0.21"
    assert transaction["iva_amount"] == "42"


def test_classify_can_correct_and_view_iva_category(tmp_path: Path) -> None:
    """IVA category corrections are observable mutations, not no-ops.

    A persona run marked a row ``erroneous_invoice`` while investigating a
    corrective invoice, then could not change it back to ``domestic_general``:
    the mutation signature ignored ``iva_category`` and ``ledger view`` hid the
    stored value. This reproduces that flow through the real CLI and confirms
    the list surface shows the same operator-visible category.
    """
    txn = _imported_transaction_id(tmp_path)
    first = _invoke(
        [
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21.00",
            "--iva-category",
            "erroneous_invoice",
        ],
    )
    assert first.exit_code == 0, first.output
    viewed_first = _invoke(["app", "ledger", "view", txn[:8]])
    assert viewed_first.exit_code == 0, viewed_first.output
    assert "IVA category\terroneous_invoice" in viewed_first.output

    corrected = _invoke(
        [
            "app",
            "ledger",
            "classify",
            txn[:8],
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21.00",
            "--iva-category",
            "domestic_general",
            "--reaffirm",
        ],
    )
    assert corrected.exit_code == 0, corrected.output
    assert "manual ledger update must change at least one ledger field" not in corrected.output

    viewed = _invoke(["--format", "json", "app", "ledger", "view", txn])
    assert viewed.exit_code == 0, viewed.output
    transaction = json.loads(viewed.output)["result"]["transaction"]
    assert transaction["iva_category"] == "domestic_general"
    text_view = _invoke(["app", "ledger", "view", txn[:8]])
    assert text_view.exit_code == 0, text_view.output
    assert "IVA category\tdomestic_general" in text_view.output

    listed = _invoke(["app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    header = next(line for line in listed.output.splitlines() if "\tfull_id\t" in line)
    assert header.split("\t") == [
        "id",
        "full_id",
        "date",
        "amount",
        "description",
        "IVA category",
        "review_status",
    ]
    listed_row = next(line for line in listed.output.splitlines() if txn in line)
    assert listed_row.split("\t")[5] == "domestic_general"

    listed_es = _invoke(["--language", "es", "app", "ledger", "list"])
    assert listed_es.exit_code == 0, listed_es.output
    header_es = next(line for line in listed_es.output.splitlines() if "\tid_completo\t" in line)
    assert header_es.split("\t") == [
        "id",
        "id_completo",
        "fecha",
        "importe",
        "descripción",
        "Categoría de IVA",
        "estado_revisión",
    ]
    listed_es_row = next(line for line in listed_es.output.splitlines() if txn in line)
    assert listed_es_row.split("\t")[5] == "domestic_general"


def test_ledger_view_surfaces_manual_decision_provenance(tmp_path: Path) -> None:
    """`ledger view` must answer "why was this classified" for a manual decision.

    A manual classify with ``--reason`` persists the free-text rationale on
    the transaction's active decision; ``view`` must expose ``classified_by``,
    ``classified_at``, ``classification_confidence``, and
    ``classification_reason`` on both the text and JSON surfaces so an
    operator can read the "why" from a single command.
    """
    txn = _imported_transaction_id(tmp_path)

    classified = _invoke(
        [
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "BUSINESS",
            "--reason",
            "matches counterparty + amount-range rule",
        ],
    )
    assert classified.exit_code == 0, classified.output

    viewed_json = _invoke(["--format", "json", "app", "ledger", "view", txn])
    assert viewed_json.exit_code == 0, viewed_json.output
    transaction = json.loads(viewed_json.output)["result"]["transaction"]
    assert transaction["classified_by"] == "manual"
    assert transaction["classification_reason"] == "matches counterparty + amount-range rule"
    assert transaction["classification_confidence"] == "1"
    assert transaction["classified_at"]

    viewed_text = _invoke(["app", "ledger", "view", txn])
    assert viewed_text.exit_code == 0, viewed_text.output
    assert "Classified by\tmanual" in viewed_text.output
    assert "Classification reason\tmatches counterparty + amount-range rule" in viewed_text.output
    assert "Classification confidence\t1" in viewed_text.output
    assert "Classified at\t" in viewed_text.output


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
    imported = _invoke(["app", "ledger", "import", "--file", str(statement), "--provider", "csv"])
    assert imported.exit_code == 0, imported.output

    listed = _invoke(["app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    assert accented in listed.output
    assert "?" not in listed.output

    txn = _invoke(["--format", "json", "app", "ledger", "list"])
    transaction_id = json.loads(txn.output)["result"]["rows"][0]["transaction_id"]
    viewed = _invoke(["app", "ledger", "view", transaction_id])
    assert viewed.exit_code == 0, viewed.output
    assert accented in viewed.output
