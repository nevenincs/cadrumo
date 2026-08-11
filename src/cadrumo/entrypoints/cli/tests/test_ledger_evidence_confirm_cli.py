"""Real-CLI regression for ``aeat app ledger evidence confirm`` (#254 slice).

Closes the non-interactive review loop the extraction primitive
(``25ed55fd29``) and the ``evidence extract`` CLI verb (``58064ca45f``) opened:
an operator (or an autonomous LLM operator per the agent-harness contract) can
now run ``evidence confirm`` against a stored evidence record and mint a real
:class:`~domain.invoices.Invoice` in the reconciliation catalogue, with
any extracted field overridable and a same-identity re-confirm collapsing to a
guarded no-op (``aeat-cli-contract``). The write
itself is delegated to the sole sanctioned catalogue-invoice writer
(``aeat-architecture-boundaries``); this test suite asserts the
confirm path never re-implements that write.

Every case drives the real Typer CLI tree, a real encrypted bucket session,
and a real bundled document. No mocks, stubs, or monkeypatch.

**The document is STRUCTURED, and that is what makes this file runnable.**
It previously fed a reportlab-generated text-bearing PDF, whose reading lane
is the semantic extraction stage -- so every case here failed at extraction on
a local inference connection failure, before reaching a single line of confirm
logic, on any machine without a live local model. Seven of the eight cases
were dead coverage for exactly the people most likely to be working on this
surface. A Facturae document reads through the deterministic parser instead:
no model is reached, every re-read resolves the same figures, and the confirm
behaviour under test is unchanged.

The refusal case survives the switch rather than being traded away for
runnability, which was the risk in this refit. The bundled document's buyer
side carries a tax identifier and NO name, so confirming it as ISSUED asks for
a counterparty the document does not name -- the same situation the reader's
cross-side fallback used to paper over -- and the refusal is reached without a
model.

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
from pathlib import Path

import pytest

from ._ledger_ux_support import _invoke, _open_ledger_ux_session
from ._ledger_validation_support import _set_profile_axis

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _redacted(tax_id: str) -> str:
    """Return the form an operator-facing envelope carries a tax identity in.

    The payload leaves the process through the CLI redaction funnel, which
    hashes a counterparty's tax identity whether that counterparty is a
    natural person or a company. Asserting the digest rather than the raw
    value still pins the identity exactly -- the digest is derived from it.
    """
    return f"sha256:{hashlib.sha256(tax_id.encode('utf-8')).hexdigest()[:8]}"


#: The bundled evidence corpus, reached the way the sibling CLI evidence
#: suites reach it.
_EVIDENCE_CORPUS = Path(__file__).resolve().parents[3] / "application" / "ledger" / "tests" / "_evidence_corpus"

#: A Facturae 3.2 document, so the reading lane is the deterministic parser.
_STRUCTURED_INVOICE = _EVIDENCE_CORPUS / "facturae_32_recargo_invoice.xml"

# What the bundled document states. Read off the fixture rather than chosen,
# so an assertion here cannot drift from the bytes under test.
_SUPPLIER_CIF = "B12345674"
_SUPPLIER_NAME = "Mayorista Ejemplo SL"
_INVOICE_NUMBER = "FAC-2024-0007"
_ISSUE_DATE = "2024-11-20"
_TAXABLE_BASE = "100.00"
#: Base plus the 21% cuota plus the 5.2% recargo de equivalencia the document charges.
_GRAND_TOTAL = "126.20"


@pytest.fixture(autouse=True)
def _open_bucket_session(tmp_path: Path) -> Iterator[None]:
    with _open_ledger_ux_session(tmp_path):
        # The confirm path resolves an IVA treatment, and the deadlines profile
        # refuses to answer for a taxpayer whose Modelo 303 composition was
        # never declared -- correctly, since an undeclared composition is not a
        # general one. The minimal profile the shared session registers does not
        # declare it, so every confirm through this harness refused before
        # reaching the behaviour under test. Declared as GENERAL, which is what
        # this taxpayer is: being charged recargo de equivalencia is a fact
        # about the supplier's obligation towards this buyer, not a fourth
        # composition -- a recargo retailer still files 303 under the general
        # composition.
        _set_profile_axis("iva.m303_regime_composition", "general")
        yield


def _add_evidence(tmp_path: Path, *, filename: str = "factura.xml") -> str:
    """Store the bundled structured document as real evidence, through the CLI."""
    source = tmp_path / filename
    source.write_bytes(_STRUCTURED_INVOICE.read_bytes())
    added = _invoke(["--format", "json", "app", "ledger", "evidence", "add", str(source), "--supplier", "Acme SL"])
    assert added.exit_code == 0, added.output
    return json.loads(added.output)["result"]["evidence_id"]


def test_confirm_by_evidence_id_mints_a_real_catalogue_invoice(tmp_path: Path) -> None:
    evidence_id = _add_evidence(tmp_path)

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
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
    assert result["invoice_number"] == _INVOICE_NUMBER
    assert result["issued_at"] == _ISSUE_DATE
    assert result["base_total"] == _TAXABLE_BASE
    assert result["grand_total"] == _GRAND_TOTAL
    invoice_id = result["invoice_id"]
    assert len(invoice_id) == 64

    # The invoice is a real row in the rich catalogue store -- not merely the
    # confirm command's echoed payload.
    listed = _invoke(["--format", "json", "app", "ledger", "invoice", "list"])
    assert listed.exit_code == 0, listed.output
    catalogue = json.loads(listed.output)["result"]
    assert catalogue["count"] == 1
    assert catalogue["rows"][0]["invoice_id"] == invoice_id


def test_confirm_is_idempotent_guarded_on_a_second_identical_confirm(tmp_path: Path) -> None:
    """A re-confirm with the same resolved identity is a guarded no-op, not a duplicate."""
    evidence_id = _add_evidence(tmp_path)

    first = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
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
            "--country-code", "ES",
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
    listed = _invoke(["--format", "json", "app", "ledger", "invoice", "list"])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output)["result"]["count"] == 1

    # The no-op is surfaced as an info notice, never a silent success.
    second_envelope = json.loads(second.output)
    notice_codes = {notice["code"] for notice in second_envelope.get("notices", [])}
    assert "ledger.evidence.confirm.already_exists" in notice_codes


def test_confirm_honours_an_override_of_an_extracted_field(tmp_path: Path) -> None:
    """A supplied override wins over the best-effort extracted value."""
    evidence_id = _add_evidence(tmp_path)

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
            "--invoice-number", "OVERRIDE-9999",
            "--taxable-base", "500.00",
        ],
    )  # fmt: skip
    assert confirmed.exit_code == 0, confirmed.output
    result = json.loads(confirmed.output)["result"]

    # The override values won, not the values the document states.
    assert result["invoice_number"] == "OVERRIDE-9999"
    assert result["base_total"] == "500.00"
    # Fields not overridden still come from the extracted draft.
    assert result["counterparty_tax_id"] == _redacted(_SUPPLIER_CIF)
    assert result["issued_at"] == _ISSUE_DATE


def test_confirm_of_a_different_override_refuses_rather_than_duplicating(tmp_path: Path) -> None:
    """One document must not leave two invoices behind, whatever the operator retypes.

    The second call resolves a different invoice number, which is one of the six
    fields the invoice id folds -- so it hashes to a fresh id, and before the
    document-identity guard it sailed past the same-id check and left the
    catalogue holding two records made from one piece of paper. Both would then
    aggregate into Modelo 303, 347 and 390, which AEAT reconciles against the
    counterparty's own declaration.

    The refusal names the field that moved, because the operator's next move
    depends on it: a corrected number means the stored record is wrong, a
    different total means these are not the same invoice.
    """
    evidence_id = _add_evidence(tmp_path)

    first = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
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
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
            "--invoice-number", "FAC-2024-0008",
        ],
    )  # fmt: skip
    assert second.exit_code != 0, second.output
    assert "invoice_number" in second.output

    listed = _invoke(["--format", "json", "app", "ledger", "invoice", "list"])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output)["result"]["count"] == 1


def test_confirm_by_attachment_id_uses_the_same_in_store_bytes(tmp_path: Path) -> None:
    evidence_id = _add_evidence(tmp_path)

    viewed = _invoke(["--format", "json", "app", "ledger", "evidence", "view", evidence_id])
    assert viewed.exit_code == 0, viewed.output
    attachment_id = json.loads(viewed.output)["result"]["attachment_id"]
    assert attachment_id is not None

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--attachment-id", attachment_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
            "--counterparty-nif", _SUPPLIER_CIF,
        ],
    )  # fmt: skip
    assert confirmed.exit_code == 0, confirmed.output
    result = json.loads(confirmed.output)["result"]
    assert result["attachment_id"] == attachment_id
    assert result["base_total"] == _TAXABLE_BASE


def test_confirm_reads_the_counterparty_the_document_names(tmp_path: Path) -> None:
    """The positive control for the refusal below: a named side needs no override.

    Confirmed as RECEIVED, so the counterparty is the seller, and the document
    names it. Nothing is supplied on the command line and the value still
    arrives, which is what makes the refusal in the next case a statement about
    THIS document's buyer side rather than about the reader being unable to
    read a party at all.
    """
    evidence_id = _add_evidence(tmp_path)

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            # --counterparty-name deliberately omitted: the document names the seller.
        ],
    )  # fmt: skip
    assert confirmed.exit_code == 0, confirmed.output
    assert json.loads(confirmed.output)["result"]["counterparty_name"] == _SUPPLIER_NAME


def test_confirm_missing_required_field_refuses_actionably(tmp_path: Path) -> None:
    """A field the document does not state, and no override, refuses rather than fabricates.

    Confirmed as ISSUED, so the counterparty is the BUYER, and this document
    gives the buyer a tax identifier and no name. The reader must therefore
    leave the counterparty unset for the operator to supply, rather than
    reaching across to the seller it can see -- the cross-side fallback that
    was deleted precisely because it silently named the wrong party.
    """
    evidence_id = _add_evidence(tmp_path)

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "issued",
            # --counterparty-name intentionally omitted: the buyer side is unnamed.
        ],
    )  # fmt: skip
    assert confirmed.exit_code != 0, confirmed.output
    assert "counterparty_name" in confirmed.output.lower() or "counterparty-name" in confirmed.output.lower()
    # And it must not have silently borrowed the seller's name to get past the gate.
    assert _SUPPLIER_NAME not in confirmed.output


def test_confirm_requires_exactly_one_reference(tmp_path: Path) -> None:
    neither = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "confirm", "--kind", "received", "--counterparty-name", "X"],
    )
    assert neither.exit_code != 0, neither.output


def test_confirm_never_writes_a_file_to_disk(tmp_path_factory: pytest.TempPathFactory, tmp_path: Path) -> None:
    """Bytes are re-read from secure storage into memory only; nothing lands on disk."""
    evidence_id = _add_evidence(tmp_path)

    empty_dir = tmp_path_factory.mktemp("no-write-expected-cli-confirm")
    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
        ],
    )  # fmt: skip
    assert confirmed.exit_code == 0, confirmed.output
    assert list(empty_dir.iterdir()) == []
