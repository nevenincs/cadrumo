"""A foreign-currency, foreign-language invoice must survive parse -> confirm.

Two properties the reading path is expected to have, neither of which any
bundled fixture could previously observe, because every invoice in the corpus
was printed in Spanish and denominated in euro.

**Foreign currency stays foreign.** The currency the document prints is carried
through the draft into the persisted :class:`~domain.invoices.Invoice`. The
alternative is not a cosmetic label error: an invoice minted at its face value
in euro declares 18500 euro where the document says 18500 kronor, and every
downstream modelo total then sums a figure roughly eleven times the real one.

**The reader does not depend on Spanish.** Base, cuota, both parties and the
statutory mention are recovered from a document whose free text is German and
whose supplier is Swedish. This runs on the STRUCTURED path, which reaches no
model at all, so the recovery is exact and the assertions are about the reader
rather than about a model's mood: language-independence is shown here, not
assumed.

Every expected value below is a figure or a string the fixture document itself
prints. Nothing is recomputed from the code under test.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.inbound.einvoice import parse_einvoice_document
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import IntracomOperationType
from ....core.config import Settings
from ....core.external_constants import DEFAULT_CURRENCY
from ....domain.iva.classification import InvoiceKind
from ..evidence_draft import confirm_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import seeded_filer_profile as seeded_filer_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

_FIXTURE = Path(__file__).parent / "_evidence_corpus" / "en16931_ubl_intracom_german_sek_invoice.xml"

# <cbc:DocumentCurrencyCode>SEK -- deliberately not the euro.
_PRINTED_CURRENCY = "SEK"
# <cbc:TaxExclusiveAmount currencyID="SEK">18500.00
_PRINTED_BASE = Decimal("18500.00")
# <cac:TaxTotal><cbc:TaxAmount currencyID="SEK">0.00 -- an intra-community
# supply carries no repercuted cuota (LIVA art. 25); the recipient self-assesses.
_PRINTED_CUOTA = Decimal("0.00")
# <cbc:TaxInclusiveAmount currencyID="SEK">18500.00
_PRINTED_TOTAL = Decimal("18500.00")
# <cac:AccountingSupplierParty> ... the party that issued the document.
_PRINTED_SUPPLIER_NAME = "Nordiska Verkstad AB"
_PRINTED_SUPPLIER_IVA = "SE556677889901"
# <cac:AccountingCustomerParty> ... the party billed.
_PRINTED_CUSTOMER_NAME = "Talleres Peninsulares SL"
_PRINTED_CUSTOMER_IVA = "ESB12345674"
# <cbc:Note> -- the statutory mention, in the issuer's own language.
_PRINTED_LEGEND = "Steuerfreie innergemeinschaftliche Lieferung"

# Every word of free text the document prints. Asserting that none of these is
# Spanish is what turns "the reader happens to work here" into "the reader did
# not read Spanish, because there was none to read".
_FREE_TEXT_ON_THE_DOCUMENT = (_PRINTED_LEGEND, "Hydraulikpumpe Ersatzteilsatz")


class _AlwaysSilentRateProvider:
    """A rate source that resolves nothing, for the currency-carry proofs.

    Deliberately silent rather than absent. These tests are about the CURRENCY
    reaching the record; supplying a rate would convert the invoice and let a
    euro-valued assertion pass for the wrong reason. It also keeps the confirm
    off the network, which the production default provider would otherwise
    reach for the moment a non-euro document appears.
    """

    @property
    def rate_source_id(self) -> str:
        return "test_silent"

    def get_eur_rate(self, currency: str, rate_date: object) -> Decimal | None:
        del currency, rate_date
        return None


def _confirm_the_foreign_document(
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    currency_override: str | None = None,
):
    """Confirm the fixture with no overrides beyond the direction and country.

    The operator is confirming what the reader found, which is the path on
    which a field the document states can go missing with nobody retyping it.
    """
    source = tmp_path / _FIXTURE.name
    source.write_bytes(_FIXTURE.read_bytes())
    svc = _make_svc(isolated_settings, secure_objects)
    record = svc.add(bucket_id=_BUCKET_ID, source_path=source).record
    return confirm_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_country="SE",
        evidence_id=record.evidence_id,
        currency=currency_override,
        counterparty_tax_id=_PRINTED_SUPPLIER_IVA,
        # The Modelo 349 clave. The document states the intra-community
        # category but no document states WHICH clave, so the writer demands it
        # and only the operator can answer -- an ordinary entrega (E) here.
        operation_type=IntracomOperationType.E,
        settings=isolated_settings,
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
        rate_provider=_AlwaysSilentRateProvider(),
    )


def test_the_printed_currency_reaches_the_persisted_invoice(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The confirmed invoice reports SEK, not the euro default.

    The failure this catches is silent by construction: an invoice defaulted to
    euro is a structurally valid record carrying plausible figures, and nothing
    downstream can tell it from a genuine euro invoice.
    """
    result = _confirm_the_foreign_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )

    assert result.draft.currency == _PRINTED_CURRENCY, "the parser did not read the currency off the document"
    assert result.invoice.currency == _PRINTED_CURRENCY, (
        f"the currency was read from the document but lost at the confirm boundary: {result.invoice.currency!r}"
    )
    assert result.invoice.currency != DEFAULT_CURRENCY, (
        "a foreign invoice recorded as euro is indistinguishable from a genuine euro one"
    )


def test_an_unconverted_foreign_invoice_reports_no_euro_value(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """No rate resolved means no euro figure, never the face value.

    Watches the OVER-declaration direction, which the rest of this repository's
    gates do not. 18500 SEK read as 18500 EUR overstates by roughly an order of
    magnitude, and an over-declared base is a figure the taxpayer pays on. The
    record must say it has no euro value rather than offer a foreign one.
    """
    result = _confirm_the_foreign_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )

    assert result.invoice.base_total == _PRINTED_BASE
    assert result.invoice.base_total_eur is None, (
        "an unconverted foreign invoice reported a euro base; the face value was declared as euro"
    )
    assert result.invoice.grand_total_eur is None
    assert result.invoice.fx_rate is None


def test_an_operator_override_still_outranks_the_printed_currency(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The document is the default, not the authority.

    The carry must not have been implemented by ignoring the operator: on every
    other field an explicit value wins, and currency is not special.
    """
    result = _confirm_the_foreign_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        currency_override="NOK",
    )

    assert result.invoice.currency == "NOK"


def test_the_reader_recovers_every_field_from_a_document_printing_no_spanish(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Base, cuota, both parties and the legend, off a German-language invoice.

    The legend matters most of the four. An intra-community supply prints a base
    and no cuota, which is exactly what an exempt and a zero-rated supply also
    print: strip the mention and the record is indistinguishable from an
    ordinary zero-cuota sale, and the recipient's self-assessed IVA is never
    assessed. Recovering it verbatim, in German, is what shows the mention is
    read as text the document carries rather than matched against a list of
    Spanish phrases.
    """
    result = _confirm_the_foreign_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    draft = result.draft

    assert draft.taxable_base == _PRINTED_BASE
    assert draft.iva_amount == _PRINTED_CUOTA
    assert draft.grand_total == _PRINTED_TOTAL
    assert draft.supplier_name == _PRINTED_SUPPLIER_NAME
    assert draft.supplier_tax_id == _PRINTED_SUPPLIER_IVA
    assert draft.customer_name == _PRINTED_CUSTOMER_NAME
    assert draft.customer_tax_id == _PRINTED_CUSTOMER_IVA
    assert draft.regime_legend == _PRINTED_LEGEND, (
        "the statutory mention the document prints did not survive the structured read"
    )
    assert result.invoice.base_total == _PRINTED_BASE
    assert result.invoice.iva_total == _PRINTED_CUOTA


def test_the_fixture_prints_no_spanish_for_the_reader_to_lean_on() -> None:
    """The control for the test above: the document really is Spanish-free.

    Without this, the language-independence claim rests on the fixture's name.
    A later edit that added a Spanish gloss to the item description would leave
    the recovery test passing while it no longer proved anything, and nobody
    would see the difference.
    """
    document = _FIXTURE.read_bytes().decode("utf-8")
    body = document[document.index("<Invoice") :]
    parsed = parse_einvoice_document(_FIXTURE.read_bytes())

    for phrase in _FREE_TEXT_ON_THE_DOCUMENT:
        assert phrase in body, f"the fixture no longer prints {phrase!r}; the recovery test is testing something else"
    # The one Spanish token on the document is the BILLED party's own company
    # name, which is a proper noun rather than a label the reader could key on.
    for spanish_label in ("Factura", "Base imponible", "Cuota", "Total factura", "IVA", "Fecha", "exenta"):
        assert spanish_label not in body, (
            f"the fixture prints the Spanish label {spanish_label!r}; it can no longer show language independence"
        )
    assert parsed.currency == _PRINTED_CURRENCY
