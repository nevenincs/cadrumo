"""Real-CLI proof that what a confirm RESOLVED reaches the operator.

The confirm path settles which IVA treatment an invoice gets, on which rung that
treatment stands, and what territorial questions it leaves open. All of it was
computed on every confirm and read by no production caller: the payload was built
from the invoice, the draft, the provenance and the confirmation id, and never
touched the resolution. So a record whose category rested on the weakest rung
available was indistinguishable from one the rule table placed outright, and a
document whose category was WITHHELD reached the catalogue with no treatment and
nothing said about it.

**The trap this suite exists to avoid.** Asserting that a notice was constructed
reproduces the exact defect: every one of these signals was constructed correctly
and read by nobody. So each case drives the real Typer tree end to end and reads
the shipped envelope --- the notices an operator receives and the result fields a
consumer parses --- never the resolution model.

The documents are structured e-invoices, and that is not incidental: the IVA
treatment a document DECLARES is a UNTDID 5305 code only a structured reader can
recover, so the withheld-relief case is unreachable from a text-read page.

Assertions are on codes, severities and structure --- never on prose, which is
localised.

See Also:
    :func:`~entrypoints.cli._ledger_evidence_confirm_notices.confirm_resolution_notices`
        The projection under test.
    :class:`~core.IvaCategoryOutcome`
        The rung axis the outcome field reports.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final

import pytest
from click.testing import Result

from ....application.ledger.filer_establishment import FILER_POSTCODE_FACT_PATH
from ....core import STR_KEYED_MAPPING_ADAPTER, IvaCategoryOutcome
from ....domain.iva.schema import IvaCategory
from ....domain.user_profile.values import UserProfileFact
from ....tests.profile_capsule import set_active_test_profile_facts
from ._ledger_ux_support import _invoke, _open_bucket_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session"]

_RELIEF_NOTICE: Final = "ledger.evidence.confirm.category_unsupported_relief"
_INFERRED_NOTICE: Final = "ledger.evidence.confirm.category_rate_inferred"
_ESTABLISHMENT_NOTICE: Final = "ledger.evidence.confirm.review_undetermined_establishment"

_SUPPLIER_NAME: Final = "Acme Suministros SL"
_SUPPLIER_IVA: Final = "ESB12345674"


def _ubl(*, category: str, percent: str, cuota: str, payable: str, number: str) -> str:
    """Return one EN16931 UBL invoice stating a tax category and no country.

    No party address block at all, which is the shape that matters here: the
    country and postal evidence the establishment ladder consults is genuinely
    absent, exactly as it is on the bundled intra-community specimen, so the
    counterparty's territory is a gap rather than a wrong value.
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:CustomizationID>urn:cen.eu:en16931:2017</cbc:CustomizationID>
  <cbc:ID>{number}</cbc:ID>
  <cbc:IssueDate>2026-03-11</cbc:IssueDate>
  <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty><cac:Party>
    <cac:PartyName><cbc:Name>{_SUPPLIER_NAME}</cbc:Name></cac:PartyName>
    <cac:PartyTaxScheme><cbc:CompanyID schemeID="VA">{_SUPPLIER_IVA}</cbc:CompanyID>
      <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:PartyTaxScheme>
  </cac:Party></cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty><cac:Party>
    <cac:PartyName><cbc:Name>Nordiska Verkstad AB</cbc:Name></cac:PartyName>
  </cac:Party></cac:AccountingCustomerParty>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="EUR">{cuota}</cbc:TaxAmount>
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="EUR">1000.00</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="EUR">{cuota}</cbc:TaxAmount>
      <cac:TaxCategory><cbc:ID>{category}</cbc:ID><cbc:Percent>{percent}</cbc:Percent>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:TaxCategory>
    </cac:TaxSubtotal>
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="EUR">1000.00</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="EUR">1000.00</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="EUR">{payable}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="EUR">{payable}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  <cac:InvoiceLine>
    <cbc:ID>1</cbc:ID>
    <cbc:InvoicedQuantity unitCode="C62">1</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="EUR">1000.00</cbc:LineExtensionAmount>
    <cac:Item><cbc:Name>Komponenter</cbc:Name>
      <cac:ClassifiedTaxCategory><cbc:ID>{category}</cbc:ID><cbc:Percent>{percent}</cbc:Percent>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:ClassifiedTaxCategory></cac:Item>
    <cac:Price><cbc:PriceAmount currencyID="EUR">1000.00</cbc:PriceAmount></cac:Price>
  </cac:InvoiceLine>
</Invoice>
"""


_INTRA_COMMUNITY = _ubl(category="K", percent="0.00", cuota="0.00", payable="1000.00", number="IC-2026-000019")
"""UNTDID 5305 ``K``: the intra-community exemption of LIVA art. 25.

A relief from Spanish output IVA that rests entirely on where the counterparty is
established --- and this document establishes nothing about that.
"""

_DOMESTIC_STANDARD = _ubl(category="S", percent="21.00", cuota="210.00", payable="1210.00", number="ES-2026-000019")
"""UNTDID 5305 ``S`` at the standard tier: the ordinary domestic document.

The control for every severity assertion below. It reaches the SAME unestablished
counterparty --- it prints no country either --- so the two cases differ only in
what the document declared, which is exactly the axis under test.
"""


def _undeclare_the_filers_postcode() -> None:
    """Blank the filer's fiscal-address postcode for the current session.

    A blank is undeclared rather than unreadable, which is the state under test:
    nothing was stated, so the operator's action is to supply the fact rather
    than to correct it, and the two refusals send them different places.
    """
    set_active_test_profile_facts((UserProfileFact(path=FILER_POSTCODE_FACT_PATH, value=""),))


def _confirm_raw(tmp_path: Path, document: str, *, name: str) -> Result:
    """Add one structured document as evidence and confirm it, returning the result.

    Kept apart from :func:`_confirmed` so a case about a REFUSAL does not have
    to route around an assertion that the confirm succeeded.
    """
    path = tmp_path / f"{name}.xml"
    path.write_text(document, encoding="utf-8")
    added = _invoke(["--format", "json", "app", "ledger", "evidence", "add", str(path), "--supplier", _SUPPLIER_NAME])
    assert added.exit_code == 0, added.output
    evidence_id = json.loads(added.output)["result"]["evidence_id"]
    return _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", _SUPPLIER_NAME,
        ],
    )  # fmt: skip


def _confirmed(tmp_path: Path, document: str, *, name: str) -> dict[str, object]:
    """Add one structured document as evidence and confirm it, returning the envelope."""
    confirmed = _confirm_raw(tmp_path, document, name=name)
    assert confirmed.exit_code == 0, confirmed.output
    return STR_KEYED_MAPPING_ADAPTER.validate_json(confirmed.output)


def _redacted(tax_id: str) -> str:
    """Return the form an operator-facing envelope carries a tax identity in.

    Composed here from the documented rule -- ``sha256:`` plus the first eight
    hex characters of the digest -- rather than by calling the redaction funnel,
    which would assert the code against its own output and pass however the
    funnel behaved.
    """
    return f"sha256:{hashlib.sha256(tax_id.encode('utf-8')).hexdigest()[:8]}"


def _notices(envelope: dict[str, object], code: str) -> list[dict[str, object]]:
    notices = envelope["notices"]
    assert isinstance(notices, list)
    return [notice for notice in notices if isinstance(notice, dict) and notice.get("code") == code]


def _notice(envelope: dict[str, object], code: str) -> dict[str, object]:
    matching = _notices(envelope, code)
    assert len(matching) == 1, matching
    return matching[0]


def _by_field(envelope: dict[str, object], code: str, field: str) -> dict[str, object]:
    """Return the one notice of *code* raised about *field*.

    The establishment questions arrive one per party, and they are different
    questions: the counterparty's territory is a document fact and the filer's
    own is a profile fact. Selecting on the field keeps a case that means one of
    them from passing on the other.
    """
    matching = [notice for notice in _notices(envelope, code) if _context(notice).get("field") == field]
    assert len(matching) == 1, matching
    return matching[0]


def _context(notice: dict[str, object]) -> dict[str, object]:
    """Return one notice's context, asserting the envelope actually carried one."""
    context = notice["context"]
    assert isinstance(context, dict), notice
    return STR_KEYED_MAPPING_ADAPTER.validate_python(context)


def _codes(envelope: dict[str, object]) -> set[str]:
    notices = envelope["notices"]
    assert isinstance(notices, list)
    return {str(notice["code"]) for notice in notices if isinstance(notice, dict)}


def test_a_withheld_relief_reaches_the_operator_as_a_warning(tmp_path: Path) -> None:
    """The signal the whole row is about: a real, correct document told nothing.

    This shape confirms cleanly and lands on record with NO IVA treatment, so
    before this the only evidence anything happened was a category that silently
    was not there.
    """
    envelope = _confirmed(tmp_path, _INTRA_COMMUNITY, name="intracom")

    notice = _notice(envelope, _RELIEF_NOTICE)
    assert notice["severity"] == "warning"
    assert envelope["status"] == "warning"
    context = notice["context"]
    assert isinstance(context, dict)
    # The claim the operator has to contest is named, not merely alluded to.
    assert context["outcome"] == IvaCategoryOutcome.UNSUPPORTED_RELIEF.value
    assert context["declared_category"] == IvaCategory.INTRA_COMMUNITY_SUPPLY.value
    assert str(context["note"]).strip()


def test_the_withheld_treatment_is_readable_from_the_result_not_only_the_prose(tmp_path: Path) -> None:
    """A consumer enumerating untreated records must not have to parse a sentence."""
    body = _confirmed(tmp_path, _INTRA_COMMUNITY, name="intracom")["result"]

    assert isinstance(body, dict)
    assert body["created"] is True
    assert body["iva_category"] is None
    assert body["iva_category_outcome"] == IvaCategoryOutcome.UNSUPPORTED_RELIEF.value


def test_a_rate_inferred_category_is_distinguishable_from_a_placed_one(tmp_path: Path) -> None:
    """The rung is the whole point: both records carry `domestic_general`.

    Only the outcome tells an inferred placement from a rule-table one, and
    before this field the difference existed nowhere an operator could query.
    """
    body = _confirmed(tmp_path, _DOMESTIC_STANDARD, name="domestic")["result"]

    assert isinstance(body, dict)
    assert body["iva_category"] == IvaCategory.DOMESTIC_GENERAL.value
    assert body["iva_category_outcome"] == IvaCategoryOutcome.RATE_INFERRED.value


def test_an_ordinary_document_reports_its_rung_without_raising_a_warning(tmp_path: Path) -> None:
    """Visibility without fatigue, and the two cases prove it is not a constant.

    A Spanish invoice printing no postal code is the commonest document there
    is, and it reaches the same unestablished counterparty as the case above. A
    warning on every one of them would train an operator to skip the channel the
    withheld-relief case needs. So the severity tracks whether the record ended
    up with a treatment --- and this pins the INFO side against the WARNING side.
    """
    envelope = _confirmed(tmp_path, _DOMESTIC_STANDARD, name="domestic")

    assert _notice(envelope, _INFERRED_NOTICE)["severity"] == "info"
    assert _by_field(envelope, _ESTABLISHMENT_NOTICE, "supplier_tax_id")["severity"] == "info"
    assert envelope["status"] == "success"


def test_the_unread_establishment_question_reaches_the_operator_naming_the_party(tmp_path: Path) -> None:
    """The ladder's carried items had no reader at all; this is that reader.

    The detail is asserted to NAME the counterparty rather than merely to exist:
    an item that cannot say who it is about is one an operator cannot answer.
    """
    envelope = _confirmed(tmp_path, _INTRA_COMMUNITY, name="intracom")

    notice = _by_field(envelope, _ESTABLISHMENT_NOTICE, "supplier_tax_id")
    assert notice["severity"] == "warning"
    context = notice["context"]
    assert isinstance(context, dict)
    assert context["reason"] == "undetermined_establishment"
    # The identity reaches the operator through the redaction funnel, so the item
    # names the party by the digest of its identifier rather than verbatim. That
    # still answers "which party" -- the digest is derived from the identifier and
    # is stable per counterparty -- while keeping a trading partner's tax identity
    # off an output surface. Expected value derived from the documented rule (the
    # first eight hex characters of the SHA-256 digest), never read back from the
    # funnel, which would assert the code against itself.
    assert _redacted(_SUPPLIER_IVA) in str(context["detail"])
    # The id is the review gate's own derivation, so an item raised here
    # addresses identically to one a deterministic check raised.
    assert str(context["finding_id"]).strip()


def test_the_filer_s_own_profile_gap_reaches_the_operator_as_a_separate_question(tmp_path: Path) -> None:
    """The filer's own setup gap, and it is not about the document at all.

    The taxpayer's own IVA territory is a profile fact that separates the
    peninsula from Canarias and from Ceuta y Melilla, and it is never read off
    an invoice. An operator re-reading documents would never find the setup gap
    that was actually stopping them, so it must arrive naming the profile fact.

    THE GAP IS CONSTRUCTED HERE, and re-pointed at the state a real operator
    reaches. It used to arrive for free from a shared harness that declared no
    postcode -- so every other case in every ledger CLI suite also ran against
    an incomplete profile, and this one case was the sole beneficiary. Once the
    harness registers a complete profile, blanking the fact exposes what was
    two different states wearing one name: with NO resolvable profile the
    confirm carries a review notice, and with a profile that simply does not
    declare the postcode it REFUSES, typed, before any review. The second is
    the reachable one -- an operator who set up a profile has one -- and it is
    the stronger answer: a typed refusal carrying the failed condition and its
    evidence, rather than an advisory beside a completed confirm.
    """
    _undeclare_the_filers_postcode()
    refused = _confirm_raw(tmp_path, _INTRA_COMMUNITY, name="intracom")

    assert refused.exit_code != 0, refused.output
    error = json.loads(refused.output)["error"]
    assert FILER_POSTCODE_FACT_PATH in str(error["message"])
    assert error["action"]["failed_condition_id"] == "ledger.filer.postcode_valid"
    # The evidence distinguishes an UNDECLARED fact from an unreadable one. An
    # operator told a malformed value is "missing" re-supplies the same value.
    evidence = error["action"]["evidence"][0]["values"]
    assert evidence["filer_postcode_present"] is False


def test_a_document_that_places_its_counterparty_raises_neither_question(tmp_path: Path) -> None:
    """The negative control: these notices are not emitted unconditionally.

    The bundled Facturae specimen carries a full address block, so the ladder
    settles the counterparty's territory and neither the withheld-relief notice
    nor the counterparty establishment question fires.

    The FILER's own question is now asserted absent too, which it could not be
    while the harness left the postcode undeclared -- that item was genuinely
    open then, so suppressing it would have been the wrong assertion. With a
    complete profile the control is the stronger one it was always meant to be:
    NEITHER question fires on a document that places its counterparty.
    """
    corpus = Path(__file__).resolve().parents[3] / "application" / "ledger" / "tests" / "_evidence_corpus"
    document = (corpus / "facturae_32_series_and_parties_invoice.xml").read_text(encoding="utf-8")
    path = tmp_path / "placed.xml"
    path.write_text(document, encoding="utf-8")
    added = _invoke(["--format", "json", "app", "ledger", "evidence", "add", str(path), "--supplier", "Emisor"])
    assert added.exit_code == 0, added.output
    evidence_id = json.loads(added.output)["result"]["evidence_id"]
    confirmed = _invoke(
        [
            "--format", "json", "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", "Emisor",
        ],
    )  # fmt: skip
    assert confirmed.exit_code == 0, confirmed.output

    envelope = json.loads(confirmed.output)
    assert _RELIEF_NOTICE not in _codes(envelope)
    raised_about = {str(_context(notice).get("field")) for notice in _notices(envelope, _ESTABLISHMENT_NOTICE)}
    assert "supplier_tax_id" not in raised_about
    # The filer's own question, now that the harness declares a complete
    # profile. Asserting it absent is what makes this a control rather than a
    # partial one: an item that fires on every document proves nothing about
    # the document.
    assert FILER_POSTCODE_FACT_PATH not in raised_about


def test_the_text_surface_carries_the_same_resolution_as_the_json_one(tmp_path: Path) -> None:
    """A terminal operator is told what a JSON consumer is told."""
    path = tmp_path / "intracom.xml"
    path.write_text(_INTRA_COMMUNITY, encoding="utf-8")
    added = _invoke(["--format", "json", "app", "ledger", "evidence", "add", str(path), "--supplier", _SUPPLIER_NAME])
    assert added.exit_code == 0, added.output
    evidence_id = json.loads(added.output)["result"]["evidence_id"]
    result = _invoke(
        [
            "app", "ledger", "evidence", "confirm",
            "--country-code", "ES",
            "--evidence-id", evidence_id,
            "--kind", "received",
            "--counterparty-name", _SUPPLIER_NAME,
        ],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert f"iva_category\t-\t{IvaCategoryOutcome.UNSUPPORTED_RELIEF.value}" in result.output
    assert "review_item\tundetermined_establishment\tsupplier_tax_id\t" in result.output


def test_no_bespoke_advisory_field_appears_on_the_confirm_payload(tmp_path: Path) -> None:
    """The notice channel stayed the only diagnostic channel.

    ``iva_category`` and its outcome are the write's own data --- what treatment
    the record got --- while the operator's instruction about it rides
    ``notices``. A ``*_advisory`` bag beside them would be the forked contract.
    """
    body = _confirmed(tmp_path, _INTRA_COMMUNITY, name="intracom")["result"]

    assert isinstance(body, dict)
    assert not [key for key in body if "advisor" in key or key in {"next", "suggestion"}]
