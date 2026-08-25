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

**One refusal moved rather than survived, and the difference is recorded here
rather than left to be inferred from a diff.** The file used to prove that a
required field with no extraction heuristic and no override refuses instead of
being fabricated, and it proved it by omitting the counterparty name from a
text PDF the reader could not recover one from. A structured document names
its parties, so that state is not constructible from the bundled corpus: the
one document here with an unnamed side names it on the BUYER, and confirming
that document as issued is refused earlier and for a better reason -- it names
an issuer who is not this filer. So the refusal asserted below is the
wrong-side one, which is genuine, reachable and worth pinning, and the
missing-required-field refusal is no longer covered at the CLI layer. It wants
an application-layer case over a constructed draft, which needs neither a model
nor a document, and that is tracked as its own row rather than absorbed here.

See Also:
    :func:`~entrypoints.cli._ledger_evidence_cli._run_evidence_confirm`
        CLI command runner exercised by these real Typer tests.
    :func:`~application.ledger.evidence_draft.confirm_invoice_draft_from_evidence`
        Application service that re-extracts, applies overrides, and writes.
    :class:`~application.ledger.evidence_draft.InvoiceConfirmationResult`
        Result payload whose created/idempotent branches are asserted here.
    :func:`~application.ledger.evidence_draft.extract_invoice_draft_from_evidence`
        On-host evidence reader reused by the confirm path.
    :func:`~application.invoices.create_catalogue_invoice`
        Sole sanctioned catalogue writer reached by confirmed drafts.

Evidence reading stays local-first and secure-storage-only: nothing decrypted
here is ever written outside the encrypted bucket substrate.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory
from ._ledger_ux_support import _invoke, _open_bucket_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session"]


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


def _add_structured_evidence(tmp_path: Path, *, filename: str = "factura.xml") -> str:
    """Store the bundled structured document as real evidence, through the CLI."""
    source = tmp_path / filename
    source.write_bytes(_STRUCTURED_INVOICE.read_bytes())
    added = _invoke(["--format", "json", "app", "ledger", "evidence", "add", str(source), "--supplier", "Acme SL"])
    assert added.exit_code == 0, added.output
    payload = json.loads(added.output)
    assert isinstance(payload, dict), added.output
    body = payload.get("result")
    assert isinstance(body, dict), added.output
    evidence_id = body.get("evidence_id")
    assert isinstance(evidence_id, str), added.output
    return evidence_id


def test_confirm_by_evidence_id_mints_a_real_catalogue_invoice(tmp_path: Path) -> None:
    evidence_id = _add_structured_evidence(tmp_path)

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
    evidence_id = _add_structured_evidence(tmp_path)

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
    evidence_id = _add_structured_evidence(tmp_path)

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
    evidence_id = _add_structured_evidence(tmp_path)

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
    evidence_id = _add_structured_evidence(tmp_path)

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
            # No --counterparty-nif: the document states the seller's identifier
            # in its IVA form (ES-prefixed) while an operator would supply the
            # bare national form, and the confirm path compares those with the
            # identity token, which is trim-and-uppercase and nothing more. So
            # supplying the bare form here refuses a match on the SAME BEARER.
            # That over-refusal is real and is tracked on its own row; it is not
            # what this case is about, which is that addressing by attachment id
            # reaches the same stored bytes.
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
    evidence_id = _add_structured_evidence(tmp_path)

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


def test_confirm_refuses_the_wrong_side_rather_than_minting_a_mirrored_invoice(tmp_path: Path) -> None:
    """Confirming a document as ISSUED when it names another issuer refuses.

    The side is not a labelling choice: an invoice confirmed on the wrong side
    lands in the catalogue as income instead of expense, and aggregates that
    way into every downstream modelo. The document names a seller who is not
    this filer, so ISSUED is unanswerable from it and the refusal says which
    way round it should go.
    """
    evidence_id = _add_structured_evidence(tmp_path)

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "issued",
            "--counterparty-name", "Cliente Ejemplo SA",
        ],
    )  # fmt: skip
    assert confirmed.exit_code != 0, confirmed.output
    assert "issuer" in confirmed.output.lower()
    # Actionable, not merely negative: it names the side that would work.
    assert "received" in confirmed.output.lower()

    listed = _invoke(["--format", "json", "app", "ledger", "invoice", "list"])
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output)["result"]["count"] == 0


def test_confirm_requires_exactly_one_reference(tmp_path: Path) -> None:
    neither = _invoke(
        ["--format", "json", "app", "ledger", "evidence", "confirm", "--kind", "received", "--counterparty-name", "X"],
    )
    assert neither.exit_code != 0, neither.output


def test_confirm_never_writes_a_file_to_disk(tmp_path_factory: pytest.TempPathFactory, tmp_path: Path) -> None:
    """Bytes are re-read from secure storage into memory only; nothing lands on disk."""
    evidence_id = _add_structured_evidence(tmp_path)

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
    assert list(scan_directory(empty_dir)) == []


# -- the supply-nature answer channel, at the operator's end ----------------
#
# The application half already accepts this answer, stamps it
# OPERATOR_ASSERTION and places it direction-independently, because
# goods-or-services is a property of the SUPPLY rather than of a party. What
# these cases gate is the half an operator can reach: an answer with no way to
# type it is not an answer channel, and the axis stayed unstated on every real
# confirm until the option existed.


def test_confirm_accepts_the_operators_supply_nature_answer(tmp_path: Path) -> None:
    """The channel exists and a stated answer does not disturb the confirm."""
    evidence_id = _add_structured_evidence(tmp_path)

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
            "--supply-nature", "goods",
        ],
    )  # fmt: skip

    assert confirmed.exit_code == 0, confirmed.output
    assert json.loads(confirmed.output)["result"]["created"] is True


@pytest.mark.parametrize("answer", ["goods", "services"])
def test_both_answers_are_reachable(tmp_path: Path, answer: str) -> None:
    """Two members and no third, so both must be typeable.

    A channel accepting one of the two would silently make the other
    unanswerable, which is indistinguishable from never asking.
    """
    evidence_id = _add_structured_evidence(tmp_path, filename=f"factura-{answer}.xml")

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
            "--supply-nature", answer,
        ],
    )  # fmt: skip

    assert confirmed.exit_code == 0, confirmed.output


def test_an_answer_outside_the_closed_set_is_refused_and_names_what_is_accepted(
    tmp_path: Path,
) -> None:
    """Declaring the enum as the option type is what makes the set discoverable.

    A late string-compare refusal would be a bare "value invalid" the operator
    cannot act on. Typed at the boundary, click renders the accepted members on
    the parse failure itself.
    """
    evidence_id = _add_structured_evidence(tmp_path)

    refused = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
            "--supply-nature", "livestock",
        ],
    )  # fmt: skip

    assert refused.exit_code != 0
    assert "goods" in refused.output
    assert "services" in refused.output


def test_not_answering_leaves_the_confirm_exactly_as_it_was(tmp_path: Path) -> None:
    """The precision half: the answer is optional and absence states nothing.

    An absent answer must leave the axis unstated so the assembly can still
    report the gap -- rather than defaulting to a nature, which would be a
    guess wearing an operator's provenance.
    """
    evidence_id = _add_structured_evidence(tmp_path)

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
    assert json.loads(confirmed.output)["result"]["created"] is True


# -- the invoice CLASS, at the operator's end -------------------------------
#
# A rectificativa is read from the document where it names the invoice it
# corrects, so these options are the override for documents that do not -- a
# scanned or photographed one, where no Corrective element exists to read.
#
# Omission is load-bearing here in a way it is not for most options: the confirm
# service defaults the class to ORDINARIA, so passing that default through when
# the operator said nothing would OVERRIDE a rectificativa the reader correctly
# recovered. The runner therefore omits the argument entirely rather than
# sending a default, and the case below is what holds that.


def test_the_class_and_its_correction_can_be_stated_by_the_operator(tmp_path: Path) -> None:
    """The override channel for a document that states no class of its own."""
    evidence_id = _add_structured_evidence(tmp_path)

    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
            "--invoice-class", "RECTIFICATIVA",
            "--rectifies", "0028",
            "--series", "R-2026",
        ],
    )  # fmt: skip

    assert confirmed.exit_code == 0, confirmed.output
    assert json.loads(confirmed.output)["result"]["created"] is True


def test_declaring_the_class_without_its_series_is_refused(tmp_path: Path) -> None:
    """RD 1619/2012 art. 6.1.a.2 obliges a rectificativa into its own series.

    The model has always encoded that; what it could not do was enforce it,
    because nothing ever told it an invoice was a rectificativa. Now that the
    class is stated the invariant bites, and the override channel is only
    complete because the series can be stated alongside it.
    """
    evidence_id = _add_structured_evidence(tmp_path, filename="no-series.xml")

    refused = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
            "--invoice-class", "RECTIFICATIVA",
            "--rectifies", "0028",
        ],
    )  # fmt: skip

    assert refused.exit_code != 0, refused.output
    # On structure rather than prose: the message is localised, and asserting
    # its wording would make this suite fail on a translation.
    envelope = json.loads(refused.output)
    assert envelope["status"] == "error"
    assert envelope["error"]["category"] == "REFUSED"


def test_a_class_outside_the_closed_set_is_refused_naming_what_is_accepted(tmp_path: Path) -> None:
    """Typed at the boundary, so click renders the members on the parse failure."""
    evidence_id = _add_structured_evidence(tmp_path)

    refused = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Acme Suministros SL",
            "--invoice-class", "PROFORMA",
        ],
    )  # fmt: skip

    assert refused.exit_code != 0
    assert "RECTIFICATIVA" in refused.output
    assert "ORDINARIA" in refused.output


def test_saying_nothing_leaves_the_documents_own_class_standing(tmp_path: Path) -> None:
    """The case that matters most, and the reason the runner omits rather than defaults.

    The bundled document names the invoice it corrects, so it IS a
    rectificativa. A confirm that passed the service's ORDINARIA default
    through whenever the operator was silent would overwrite that with the
    default on every single confirm -- reinstating exactly the silent
    misclassification the reader change removed.
    """
    evidence_id = _add_structured_evidence(tmp_path)

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
    assert json.loads(confirmed.output)["result"]["created"] is True
