"""Ledger view UX regression tests."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ._ledger_ux_support import _MINIMAL_PDF, _N26_HEADER, _imported_transaction_id, _invoke, _open_ledger_ux_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _open_bucket_session(tmp_path: Path) -> Iterator[None]:
    with _open_ledger_ux_session(tmp_path):
        yield


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
    corrective invoice, then could not change it back to ``domestic_general_21``:
    the mutation signature ignored ``iva_category`` and ``ledger view`` hid the
    stored value. This reproduces that flow through the real CLI.
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
            "domestic_general_21",
            "--reaffirm",
        ],
    )
    assert corrected.exit_code == 0, corrected.output
    assert "manual ledger update must change at least one ledger field" not in corrected.output

    viewed = _invoke(["--format", "json", "app", "ledger", "view", txn])
    assert viewed.exit_code == 0, viewed.output
    transaction = json.loads(viewed.output)["result"]["transaction"]
    assert transaction["iva_category"] == "domestic_general_21"
    text_view = _invoke(["app", "ledger", "view", txn[:8]])
    assert text_view.exit_code == 0, text_view.output
    assert "IVA category\tdomestic_general_21" in text_view.output


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
    imported = _invoke(["app", "ledger", "import", str(statement), "--provider", "csv"])
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
