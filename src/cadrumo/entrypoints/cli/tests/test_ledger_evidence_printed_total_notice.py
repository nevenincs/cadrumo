"""Real-CLI regression: the printed-total mismatch reaches the operator envelope.

``evidence confirm`` DERIVES the invoice total from the taxable base and the
registry-resolved rate slot; the figure printed on the document never overwrites
it. When the two disagree the operator must be told, because the difference is
an amount the record could not represent -- a recargo de equivalencia (LIVA
art. 161) is the worked case, and before this notice the surcharge simply
vanished behind a valid-looking invoice.

The diagnostic travels on the typed ``notices`` channel of the shared envelope
spine (``cli-notices-are-the-only-diagnostic-channel``), never as a bespoke
field inside ``result``.

Drives the real Typer CLI tree, a real encrypted bucket session, and a real
reportlab-generated text-bearing PDF. No mocks.

See Also:
    :class:`~application.ledger.PrintedTotalDiscrepancy`
        The record the notice is projected from.
    :func:`~entrypoints.cli._ledger_evidence_cli._run_evidence_confirm`
        CLI runner that emits the notice.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from ._ledger_ux_support import _invoke, _open_ledger_ux_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SUPPLIER_CIF = "B12345674"

_MISMATCH_NOTICE_CODE = "ledger.evidence.confirm.printed_total_mismatch"

# base 100,00 + cuota 21,00 = 121,00; the printed total agrees.
_COHERENT_INVOICE_LINES = (
    "Factura de Acme Suministros SL",
    f"NIF: {_SUPPLIER_CIF}",
    "Numero de factura: 2026-0142",
    "Fecha: 10/03/2026",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)

# A recargo de equivalencia invoice: the document totals 126,20 while
# base + cuota is 121,00.
_RECARGO_INVOICE_LINES = (
    "Factura de Acme Suministros SL",
    f"NIF: {_SUPPLIER_CIF}",
    "Numero de factura: 2026-0199",
    "Fecha: 11/03/2026",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Recargo de equivalencia 5,2%: 5,20",
    "Total factura: 126,20",
)


def _text_pdf_bytes(lines: tuple[str, ...]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    page = canvas.Canvas(buf, pagesize=A4)
    y = 760
    for line in lines:
        page.drawString(72, y, line)
        y -= 20
    page.save()
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _open_bucket_session(tmp_path: Path) -> Iterator[None]:
    with _open_ledger_ux_session(tmp_path):
        yield


def _add_evidence(tmp_path: Path, lines: tuple[str, ...], *, filename: str) -> str:
    pdf = tmp_path / filename
    pdf.write_bytes(_text_pdf_bytes(lines))
    added = _invoke(["--format", "json", "app", "ledger", "evidence", "add", str(pdf), "--supplier", "Acme SL"])
    assert added.exit_code == 0, added.output
    return json.loads(added.output)["result"]["evidence_id"]


def _confirm(evidence_id: str) -> dict[str, Any]:
    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
        ],
    )  # fmt: skip
    assert confirmed.exit_code == 0, confirmed.output
    return json.loads(confirmed.output)


def test_a_recargo_invoice_warns_that_the_printed_total_disagrees(tmp_path: Path) -> None:
    evidence_id = _add_evidence(tmp_path, _RECARGO_INVOICE_LINES, filename="factura_recargo.pdf")

    envelope = _confirm(evidence_id)

    # The derived total is what was recorded; the printed figure did not overwrite it.
    assert envelope["result"]["grand_total"] == "121.00"

    notices = {notice["code"]: notice for notice in envelope.get("notices", [])}
    assert _MISMATCH_NOTICE_CODE in notices, f"expected the mismatch warning, got {sorted(notices)}"
    notice = notices[_MISMATCH_NOTICE_CODE]
    assert notice["severity"] == "warning"
    # The operator is given both figures and the gap, so they can find the 5,20
    # on the document rather than being told only that something is wrong.
    assert notice["context"]["printed_total"] == "126.20"
    assert notice["context"]["recorded_total"] == "121.00"
    assert notice["context"]["difference"] == "5.20"


def test_a_coherent_invoice_emits_no_mismatch_warning(tmp_path: Path) -> None:
    """The negative control: an advisory that fires on a clean document is noise."""
    evidence_id = _add_evidence(tmp_path, _COHERENT_INVOICE_LINES, filename="factura.pdf")

    envelope = _confirm(evidence_id)

    notice_codes = {notice["code"] for notice in envelope.get("notices", [])}
    assert _MISMATCH_NOTICE_CODE not in notice_codes
