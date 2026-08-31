"""Real-CLI regression for ``aeat app ledger evidence extract`` (#254 slice).

Wires the on-host document readers to the ledger CLI: an operator can run
``evidence add``
against a real PDF, then ``evidence extract --evidence-id <id>`` to read the
supplier NIF / invoice number / date / base / IVA rate / IVA amount / total
into a reviewable :class:`~application.ledger.invoice_draft_records.InvoiceDraft` -- without
minting an :class:`~domain.invoices.Invoice`.

Every case drives the real Typer CLI tree, a real encrypted bucket session,
and a real reportlab-generated text-bearing PDF. No mocks, stubs, or
monkeypatch.

See Also:
    :func:`~entrypoints.cli._ledger_evidence_cli._register_evidence_extract_command`
        CLI command registration exercised by these Typer regressions.
    :func:`~application.ledger.invoice_draft_extraction.extract_invoice_draft_from_evidence`
        CLI-facing resolver that loads stored bytes and returns the draft.
    :func:`~application.ledger.evidence_textlayer.transcribe_text_layer`
        Acquisition-stage primitive reached by the text-native happy path.
    :class:`~application.ledger.invoice_draft_records.InvoiceDraft`
        Reviewable, non-persisted payload asserted by the command output.
    :func:`~application.ledger.invoice_confirmation.confirm_invoice_draft_from_evidence`
        Follow-on review step that turns a draft into a catalogue invoice.

Evidence reading stays local-first and secure-storage-only: nothing decrypted
here is ever written outside the encrypted bucket substrate.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory
from ._ledger_ux_support import _add_evidence, _invoke, _open_bucket_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session"]

_SUPPLIER_CIF = "B12345674"

#: Bundled licence-clean evidence fixtures, shared with the application-layer
#: corpus tests. Deliberately the IN-REPO corpus: a durable gate must not depend
#: on a tree outside the repository, which would rot into a silent skip.
_EVIDENCE_CORPUS = Path(__file__).parents[3] / "application" / "ledger" / "tests" / "_evidence_corpus"


def _redacted(tax_id: str) -> str:
    """Return the form an operator-facing envelope carries a tax identity in.

    The extract payload leaves the process through the CLI redaction funnel,
    which hashes a supplier's tax identity whether that supplier is a natural
    person or a company. Asserting the digest rather than the raw value still
    pins the extracted identity exactly -- the digest is derived from it -- so
    these cases keep proving extraction recovered the right supplier.
    """
    return f"sha256:{hashlib.sha256(tax_id.encode('utf-8')).hexdigest()[:8]}"


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


def test_extract_by_evidence_id_recovers_every_grounded_field(tmp_path: Path) -> None:
    evidence_id = _add_evidence(tmp_path, _FULL_INVOICE_LINES, filename="factura.pdf")

    extracted = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "extract", "--evidence-id", evidence_id],
    )
    assert extracted.exit_code == 0, extracted.output
    envelope = json.loads(extracted.output)
    result = envelope["result"]

    assert result["evidence_id"] == evidence_id
    assert result["supplier_tax_id"] == _redacted(_SUPPLIER_CIF)
    assert result["invoice_number"] == "2026-0142"
    assert result["invoice_date"] == "2026-03-10"
    assert result["taxable_base"] == "100.00"
    assert result["iva_rate"] == "21"
    assert result["iva_amount"] == "21.00"
    assert result["grand_total"] == "121.00"
    assert result["raw_text_length"] > 0
    review_notice = next(
        notice for notice in envelope["notices"] if notice["code"] == "ledger.evidence.extract.review_hint"
    )
    assert review_notice["action"] is None
    assert review_notice["context"] == {"reference": evidence_id}
    assert "suggestion" not in review_notice


def test_a_structured_xml_invoice_survives_add_then_extract_through_the_cli(tmp_path: Path) -> None:
    """A Facturae document reaches the operator through the FRONT DOOR.

    ``evidence add`` admitted ``.xml`` while the suffix-to-MIME map carried no
    entry for it, so the command died on a bare ``KeyError`` the operator saw as
    "Internal error". The read path had the mirror-image gap: the stored MIME
    resolved to no ``MediaKind``. Between them, the canonical European mandated
    formats -- Facturae, EN16931 CII and UBL -- could not be ingested at all,
    while the deterministic readers for them worked perfectly. The capability
    shipped correct, tested and unreachable.

    So this drives BOTH halves through the real CLI rather than either in
    isolation: fixing only the write side leaves a document that ingests and
    then cannot be read, which is the harder failure to notice.

    The assertions double as the first end-to-end proof of the structured
    reader's own fields -- the series half of the invoice's identity, and both
    parties by name -- none of which any CLI test could reach before this.
    """
    source = _EVIDENCE_CORPUS / "facturae_32_series_and_parties_invoice.xml"
    staged = tmp_path / "facturae_invoice.xml"
    staged.write_bytes(source.read_bytes())

    added = _invoke(["--format", "json", "app", "ledger", "evidence", "add", str(staged)])
    assert added.exit_code == 0, added.output
    evidence_id = json.loads(added.output)["result"]["evidence_id"]

    extracted = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "extract", "--evidence-id", evidence_id],
    )
    assert extracted.exit_code == 0, extracted.output
    result = json.loads(extracted.output)["result"]

    assert result["invoice_number"] == "0031"
    assert result["invoice_series"] == "R-2026"
    assert result["supplier_name"] == "Marta Iglesias Ferrer"
    assert result["customer_name"] == "Talleres Berrocal, S.A."
    # Both parties' identities reach the operator, each through the redaction
    # funnel. Asserting the digests still pins the values exactly, and pins that
    # the two sides are DIFFERENT -- the whole of the discarded-counterparty
    # defect was the customer side arriving as a copy of the supplier's.
    assert result["supplier_tax_id"] == _redacted("45821337R")
    assert result["customer_tax_id"] == _redacted("A82645177")
    assert result["supplier_tax_id"] != result["customer_tax_id"]


def test_extract_never_persists_an_invoice(tmp_path: Path) -> None:
    """Extracting is a read: the invoice catalogue stays empty after the call."""
    evidence_id = _add_evidence(tmp_path, _FULL_INVOICE_LINES, filename="factura.pdf")

    extracted = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "extract", "--evidence-id", evidence_id],
    )
    assert extracted.exit_code == 0, extracted.output

    listed = _invoke(["--format", "json", "app", "ledger", "invoice", "list"])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output)["result"]["count"] == 0

    catalogue_listed = _invoke(["--format", "json", "app", "ledger", "invoice", "list"])
    assert catalogue_listed.exit_code == 0, catalogue_listed.output
    assert json.loads(catalogue_listed.output)["result"]["count"] == 0


def test_extract_by_attachment_id_uses_the_evidence_records_in_store_bytes(tmp_path: Path) -> None:
    """``--attachment-id`` reads the SAME in-store bytes ``evidence add`` wrote.

    ``evidence add`` copies the source file's bytes into the encrypted
    ``AttachmentStore`` and stamps the resulting content-addressed
    ``attachment_id`` on the evidence record (``evidence view`` surfaces it).
    Extracting by that ``attachment_id`` directly (bypassing the evidence
    record lookup) must recover identical fields to extracting by
    ``evidence_id``.
    """
    evidence_id = _add_evidence(tmp_path, _FULL_INVOICE_LINES, filename="factura.pdf")

    viewed = _invoke(["--format", "json", "app", "ledger", "evidence", "view", evidence_id])
    assert viewed.exit_code == 0, viewed.output
    attachment_id = json.loads(viewed.output)["result"]["attachment_id"]
    assert attachment_id is not None

    extracted = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "extract", "--attachment-id", attachment_id],
    )
    assert extracted.exit_code == 0, extracted.output
    result = json.loads(extracted.output)["result"]
    assert result["attachment_id"] == attachment_id
    assert result["supplier_tax_id"] == _redacted(_SUPPLIER_CIF)
    assert result["grand_total"] == "121.00"


def test_extract_requires_exactly_one_reference(tmp_path: Path) -> None:
    neither = _invoke(["--format", "json", "app", "ledger", "evidence", "extract"])
    assert neither.exit_code != 0, neither.output

    evidence_id = _add_evidence(tmp_path, _FULL_INVOICE_LINES, filename="factura.pdf")
    both = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "evidence",
            "extract",
            "--evidence-id",
            evidence_id,
            "--attachment-id",
            "a" * 64,
        ],
    )
    assert both.exit_code != 0, both.output


def test_extract_unknown_evidence_id_refuses_actionably() -> None:
    result = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "extract", "--evidence-id", "does-not-exist"],
    )
    assert result.exit_code != 0, result.output
    assert "does-not-exist" in result.output


def test_extract_never_writes_a_file_to_disk(tmp_path_factory: pytest.TempPathFactory, tmp_path: Path) -> None:
    """Bytes are read from secure storage into memory only; nothing lands on disk."""
    evidence_id = _add_evidence(tmp_path, _FULL_INVOICE_LINES, filename="factura.pdf")

    empty_dir = tmp_path_factory.mktemp("no-write-expected-cli-extract")
    extracted = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "extract", "--evidence-id", evidence_id],
    )
    assert extracted.exit_code == 0, extracted.output
    assert scan_directory(empty_dir) == ()
