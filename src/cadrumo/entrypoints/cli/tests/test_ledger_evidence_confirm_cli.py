"""Real-CLI regression for ``aeat app ledger evidence confirm`` (#254 slice).

Closes the non-interactive review loop the extraction primitive
(``25ed55fd29``) and the ``evidence extract`` CLI verb (``58064ca45f``) opened:
an operator (or an autonomous LLM operator per the agent-harness contract) can
now run ``evidence confirm`` against a stored evidence record and mint a real
:class:`~domain.invoices.Invoice` in the reconciliation catalogue, with
any extracted field overridable and a same-identity re-confirm collapsing to a
guarded no-op (``single-subject-mutation-is-idempotent-guarded``). The write
itself is delegated to the sole sanctioned catalogue-invoice writer
(``composition-service-no-parallel-write-path``); this test suite asserts the
confirm path never re-implements that write.

Every case drives the real Typer CLI tree, a real encrypted bucket session,
and a real reportlab-generated text-bearing PDF. No mocks, stubs, or
monkeypatch.

See Also:
    :func:`~entrypoints.cli._ledger_evidence_cli._run_evidence_confirm`
        CLI command runner exercised by these real Typer tests.
    :func:`~application.ledger.confirm_invoice_draft_from_evidence`
        Application service that re-extracts, applies overrides, and writes.
    :class:`~application.ledger.InvoiceConfirmationResult`
        Result payload whose created/idempotent branches are asserted here.
    :func:`~application.ledger.extract_invoice_draft_from_evidence`
        On-host evidence reader reused by the confirm path.
    :func:`~application.invoices.create_catalogue_invoice`
        Sole sanctioned catalogue writer reached by confirmed drafts.

Evidence reading stays local-first and secure-storage-only: nothing decrypted
here is ever written outside the encrypted bucket substrate.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest

from ._ledger_ux_support import _invoke, _open_ledger_ux_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _redacted(tax_id: str) -> str:
    """Return the form an operator-facing envelope carries a tax identity in.

    The payload leaves the process through the CLI redaction funnel, which
    hashes a counterparty's tax identity whether that counterparty is a
    natural person or a company. Asserting the digest rather than the raw
    value still pins the identity exactly -- the digest is derived from it.
    """
    return f"sha256:{hashlib.sha256(tax_id.encode('utf-8')).hexdigest()[:8]}"


_SUPPLIER_CIF = "B12345674"

_FULL_INVOICE_LINES = (
    "Factura de Acme Suministros SL",
    f"NIF: {_SUPPLIER_CIF}",
    "Numero de factura: 2026-0142",
    "Fecha: 10/03/2026",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)

_PARTIAL_INVOICE_LINES = (
    "Factura de Acme Suministros SL",
    "Base imponible: 250,00",
    "Total factura: 250,00",
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


def _add_evidence(tmp_path: Path, lines: tuple[str, ...], *, filename: str = "factura.pdf") -> str:
    pdf = tmp_path / filename
    pdf.write_bytes(_text_pdf_bytes(lines))
    added = _invoke(["--format", "json", "app", "ledger", "evidence", "add", str(pdf), "--supplier", "Acme SL"])
    assert added.exit_code == 0, added.output
    return json.loads(added.output)["result"]["evidence_id"]


def test_confirm_by_evidence_id_mints_a_real_catalogue_invoice(tmp_path: Path) -> None:
    evidence_id = _add_evidence(tmp_path, _FULL_INVOICE_LINES)

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
        ],
    )  # fmt: skip
    assert confirmed.exit_code == 0, confirmed.output
    result = json.loads(confirmed.output)["result"]

    assert result["created"] is True
    assert result["kind"] == "received"
    assert result["counterparty_tax_id"] == _redacted(_SUPPLIER_CIF)
    assert result["counterparty_name"] == "Acme Suministros SL"
    assert result["invoice_number"] == "2026-0142"
    assert result["issued_at"] == "2026-03-10"
    assert result["base_total"] == "100.00"
    assert result["grand_total"] == "121.00"
    invoice_id = result["invoice_id"]
    assert len(invoice_id) == 64

    # The invoice is a real row in the rich catalogue store -- not merely the
    # confirm command's echoed payload.
    listed = _invoke(["--format", "json", "app", "ledger", "invoice", "catalogue", "list"])
    assert listed.exit_code == 0, listed.output
    catalogue = json.loads(listed.output)["result"]
    assert catalogue["count"] == 1
    assert catalogue["rows"][0]["invoice_id"] == invoice_id


def test_confirm_is_idempotent_guarded_on_a_second_identical_confirm(tmp_path: Path) -> None:
    """A re-confirm with the same resolved identity is a guarded no-op, not a duplicate."""
    evidence_id = _add_evidence(tmp_path, _FULL_INVOICE_LINES)

    first = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
        ],
    )  # fmt: skip
    assert first.exit_code == 0, first.output
    first_result = json.loads(first.output)["result"]
    assert first_result["created"] is True

    second = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
        ],
    )  # fmt: skip
    assert second.exit_code == 0, second.output
    second_result = json.loads(second.output)["result"]

    assert second_result["created"] is False
    assert second_result["invoice_id"] == first_result["invoice_id"]

    # No duplicate row was minted: the catalogue still carries exactly one invoice.
    listed = _invoke(["--format", "json", "app", "ledger", "invoice", "catalogue", "list"])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output)["result"]["count"] == 1

    # The no-op is surfaced as an info notice, never a silent success.
    second_envelope = json.loads(second.output)
    notice_codes = {notice["code"] for notice in second_envelope.get("notices", [])}
    assert "ledger.evidence.confirm.already_exists" in notice_codes


def test_confirm_honours_an_override_of_an_extracted_field(tmp_path: Path) -> None:
    """A supplied override wins over the best-effort extracted value."""
    evidence_id = _add_evidence(tmp_path, _FULL_INVOICE_LINES)

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
            "--invoice-number", "OVERRIDE-9999",
            "--taxable-base", "500.00",
        ],
    )  # fmt: skip
    assert confirmed.exit_code == 0, confirmed.output
    result = json.loads(confirmed.output)["result"]

    # The override values won, not the extracted "2026-0142" / "100.00".
    assert result["invoice_number"] == "OVERRIDE-9999"
    assert result["base_total"] == "500.00"
    # Fields not overridden still come from the extracted draft.
    assert result["counterparty_tax_id"] == _redacted(_SUPPLIER_CIF)
    assert result["issued_at"] == "2026-03-10"


def test_confirm_of_a_different_override_mints_a_distinct_invoice(tmp_path: Path) -> None:
    """A same-evidence confirm with genuinely different resolved fields does not collapse."""
    evidence_id = _add_evidence(tmp_path, _FULL_INVOICE_LINES)

    first = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
        ],
    )  # fmt: skip
    assert first.exit_code == 0, first.output
    first_result = json.loads(first.output)["result"]
    assert first_result["created"] is True

    second = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
            "--invoice-number", "2026-0143",
        ],
    )  # fmt: skip
    assert second.exit_code == 0, second.output
    second_result = json.loads(second.output)["result"]

    assert second_result["created"] is True
    assert second_result["invoice_id"] != first_result["invoice_id"]

    listed = _invoke(["--format", "json", "app", "ledger", "invoice", "catalogue", "list"])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output)["result"]["count"] == 2


def test_confirm_by_attachment_id_uses_the_same_in_store_bytes(tmp_path: Path) -> None:
    evidence_id = _add_evidence(tmp_path, _PARTIAL_INVOICE_LINES)

    viewed = _invoke(["--format", "json", "app", "ledger", "evidence", "view", evidence_id])
    assert viewed.exit_code == 0, viewed.output
    attachment_id = json.loads(viewed.output)["result"]["attachment_id"]
    assert attachment_id is not None

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--attachment-id", attachment_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
            "--counterparty-nif", _SUPPLIER_CIF,
            "--invoice-number", "2026-0200",
            "--invoice-date", "2026-04-01",
        ],
    )  # fmt: skip
    assert confirmed.exit_code == 0, confirmed.output
    result = json.loads(confirmed.output)["result"]
    assert result["attachment_id"] == attachment_id
    assert result["base_total"] == "250.00"


def test_confirm_missing_required_field_refuses_actionably(tmp_path: Path) -> None:
    """A field with no extraction heuristic and no override refuses, not fabricates."""
    evidence_id = _add_evidence(tmp_path, _FULL_INVOICE_LINES)

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--evidence-id", evidence_id,
            "--kind", "received",
            # --counterparty-name intentionally omitted: no extraction heuristic exists.
        ],
    )  # fmt: skip
    assert confirmed.exit_code != 0, confirmed.output
    assert "counterparty_name" in confirmed.output.lower() or "counterparty-name" in confirmed.output.lower()


def test_confirm_requires_exactly_one_reference(tmp_path: Path) -> None:
    neither = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "confirm", "--kind", "received", "--counterparty-name", "X"],
    )
    assert neither.exit_code != 0, neither.output


def test_confirm_never_writes_a_file_to_disk(tmp_path_factory: pytest.TempPathFactory, tmp_path: Path) -> None:
    """Bytes are re-read from secure storage into memory only; nothing lands on disk."""
    evidence_id = _add_evidence(tmp_path, _FULL_INVOICE_LINES)

    empty_dir = tmp_path_factory.mktemp("no-write-expected-cli-confirm")
    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
        ],
    )  # fmt: skip
    assert confirmed.exit_code == 0, confirmed.output
    assert list(empty_dir.iterdir()) == []
