"""Real-CLI regression: an invoice cannot name the filer as its own counterparty.

The evidence reader identifies a counterparty by scanning for the first
checksum-valid Spanish tax id, and the on-host vision prompt asks for "the
supplier's NIF/NIE/CIF". On a RECEIVED invoice that lands on the supplier. On an
ISSUED one the issuer IS the filer, so the same scan returns the filer's own
identifier -- checksum-valid, so every identity check downstream passes it, and
bound for the Modelo 347 / 349 counterparty totals AEAT reconciles against what
the counterparty declared.

These tests drive the real Typer CLI, a real encrypted bucket session, and a
real reportlab-generated PDF. The filer's own tax id is read from the live
profile rather than hardcoded, so the test cannot drift from the harness.

See Also:
    :func:`~application.invoices.counterparty_is_the_filer`
        The profile-derived predicate under test.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest

from ....application.wizard import load_active_taxpayer_profile
from ....application.workflow import workflow_state_repository
from ._ledger_ux_support import _invoke, _open_ledger_ux_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# A real Spanish CIF distinct from any profile identifier: the legitimate
# counterparty on a received invoice.
_SUPPLIER_CIF = "B12345674"


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


def _invoice_lines(tax_id: str, *, number: str) -> tuple[str, ...]:
    return (
        "Factura",
        f"NIF: {tax_id}",
        f"Numero de factura: {number}",
        "Fecha: 10/03/2026",
        "Base imponible: 100,00",
        "IVA 21%",
        "Cuota IVA: 21,00",
        "Total factura: 121,00",
    )


@pytest.fixture(autouse=True)
def _open_bucket_session(tmp_path: Path) -> Iterator[None]:
    with _open_ledger_ux_session(tmp_path):
        yield


def _own_tax_id() -> str:
    """Return the active profile's own tax id, as the running app sees it."""
    return str(load_active_taxpayer_profile(workflow_state_repository().load()).tax_id)


def _add_evidence(tmp_path: Path, lines: tuple[str, ...], *, filename: str) -> str:
    pdf = tmp_path / filename
    pdf.write_bytes(_text_pdf_bytes(lines))
    added = _invoke(["--format", "json", "app", "ledger", "evidence", "add", str(pdf), "--supplier", "Acme SL"])
    assert added.exit_code == 0, added.output
    return json.loads(added.output)["result"]["evidence_id"]


def test_an_invoice_reading_back_the_filers_own_nif_is_refused(tmp_path: Path) -> None:
    """The issued-invoice failure: the letterhead identifier is the filer's own.

    Before this guard the confirm succeeded and recorded the filer as their own
    counterparty -- a fabricated counterparty identity, valid-looking because
    the filer's NIF passes the checksum, and destined for an informativa AEAT
    cross-checks against the counterparty's own filing.
    """
    own = _own_tax_id()
    evidence_id = _add_evidence(tmp_path, _invoice_lines(own, number="2026-0001"), filename="issued.pdf")

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--evidence-id", evidence_id,
            "--kind", "issued",
            "--counterparty-name", "Cliente SL",
        ],
    )  # fmt: skip

    assert confirmed.exit_code != 0, confirmed.output
    # The refusal names the fix, not merely the fault: the operator is told to
    # supply the OTHER party's identifier.
    assert "counterparty-nif" in confirmed.output


def test_a_genuine_third_party_counterparty_still_confirms(tmp_path: Path) -> None:
    """The negative control: the guard must not block an ordinary received invoice."""
    evidence_id = _add_evidence(
        tmp_path,
        _invoice_lines(_SUPPLIER_CIF, number="2026-0142"),
        filename="received.pdf",
    )

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
        ],
    )  # fmt: skip

    assert confirmed.exit_code == 0, confirmed.output
    assert json.loads(confirmed.output)["result"]["created"] is True


def test_an_operator_confirming_the_misread_identifier_is_still_refused(tmp_path: Path) -> None:
    """Agreeing with the misread must not be a way past the guard.

    The document carries the filer's own NIF and the operator supplies the same
    value, so ``_agreed_counterparty_tax_id`` is satisfied -- the two sides
    agree. That earlier check answers "do these match?", not "is this a real
    counterparty?", so only this guard stands between an operator who rubber-
    stamps the misread and a self-dealing row.

    Constructed deliberately so the two identifiers AGREE: an override that
    merely DIFFERED from the extracted value would be refused by the
    disagreement check instead, and would prove nothing about this guard.
    """
    own = _own_tax_id()
    evidence_id = _add_evidence(
        tmp_path,
        _invoice_lines(own, number="2026-0143"),
        filename="override.pdf",
    )

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-nif", own,
            "--counterparty-name", "Yo Mismo",
        ],
    )  # fmt: skip

    assert confirmed.exit_code != 0, confirmed.output
    assert "counterparty-nif" in confirmed.output
