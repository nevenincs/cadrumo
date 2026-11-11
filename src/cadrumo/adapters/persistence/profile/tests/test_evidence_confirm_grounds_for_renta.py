"""An invoice confirmed from a structured document is legally interpretable.

The renta sales-evidence path refuses a linked invoice whose own figures cannot
be interpreted, and it asks exactly one question to decide: whether
``decompose_invoice`` grounds the record. An invoice read from a structured
document carries everything that contract needs -- its base resolves in euro and
its IVA treatment is stated by the document rather than guessed -- so it must
ground, and the sales-evidence path must contribute its figures instead of
reporting an ungrounded-decomposition verdict.

Asserted end to end from the document bytes rather than on a hand-built
``Invoice``, because the failure this guards against lives in the confirm
boundary: the parser reads a category the persisted record then drops, and a
constructed fixture would carry the category the constructor was handed and
prove nothing about that hop.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.core.config import Settings
from cadrumo.domain.invoices.decomposition import InvoiceDecompositionDefect, decompose_invoice
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from .....application.aggregation.renta_income_evidence import income_withheld_amount, sales_invoice_evidence_payload
from .....application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from .....core.aggregation import LedgerWithholdingDerivation
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.iva.schema import InvoiceKind
from .....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from .....domain.transactions.models import Transaction
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .confirm_from_evidence_support import confirm_invoice_draft_from_evidence
from .invoice_confirmation_test_support import (
    BUCKET_ID,
    EVIDENCE_CORPUS,
    InvoiceAuthorityFixture,
    invoice_confirmation_kwargs,
    isolated_settings,
    make_svc,
    secure_objects,
    seed_filer_profile,
)
from .invoice_confirmation_test_support import runtime_profile as runtime_profile

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

# Single-rate on purpose. A multi-rate document has no single domestic category
# to declare, so it grounds for a different and legitimate reason -- using one
# here would have tested the multi-rate carve-out rather than the confirm hop.
_SINGLE_RATE_FIXTURE = EVIDENCE_CORPUS / "facturae_32_series_and_parties_invoice.xml"
# The document's seller party. Confirming it as ISSUED is only honest when the
# filer is that seller; any other filer is refused before grounding is reached.
_FIXTURE_SELLER_TAX_ID = "00001004S"


@pytest.fixture(autouse=True)
def seeded_filer_profile(
    secure_objects: SecureObjectRepository,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    """Seed the filer as the document's issuer."""
    del secure_objects, invoice_authority
    seed_filer_profile(tax_id=_FIXTURE_SELLER_TAX_ID)


def _confirm_as_issued(
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    authority: InvoiceAuthorityFixture,
):
    """Confirm the structured document as an ISSUED invoice, with no overrides.

    The absence of an ``iva_category`` argument is the point: whatever grounds
    the record has to come from the document, which is the claim under test.
    """
    source = tmp_path / "facturae_32_series_and_parties_invoice.xml"
    source.write_bytes(_SINGLE_RATE_FIXTURE.read_bytes())
    svc = make_svc(isolated_settings, secure_objects)
    record = svc.add(bucket_id=BUCKET_ID, source_path=source).record
    return confirm_invoice_draft_from_evidence(
        counterparty_country="ES",
        # Supplied because this document states no name. The claim under test is
        # grounding, and an operator-supplied name is the ordinary confirm path,
        # so withholding it would fail on an unrelated precondition.
        counterparty_name="Cliente SL",
        bucket_id=BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        evidence_id=record.evidence_id,
        settings=isolated_settings,
        **invoice_confirmation_kwargs(bucket_id=BUCKET_ID, authority=authority),
    )


def test_a_structured_confirm_grounds_through_the_decomposition_contract(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    """The step's red condition: the renta path must not refuse this as ungrounded.

    ``sales_invoice_evidence_payload`` returns
    ``SalesInvoiceEvidenceRefusal.UNGROUNDED_DECOMPOSITION`` when and only when
    ``decompose_invoice(invoice).is_grounded`` is false, so grounding the
    decomposition IS the absence of that verdict. Asserting the contract
    directly keeps the proof on the fact that decides the outcome rather than on
    a linkage fixture that could pass for unrelated reasons.
    """
    result = _confirm_as_issued(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        authority=invoice_authority,
    )

    decomposition = decompose_invoice(result.invoice)

    assert decomposition.is_grounded, (
        "an invoice read from a structured document must be legally interpretable; "
        f"the renta sales-evidence path refuses it as ungrounded. Defects: {decomposition.defects}"
    )


def test_the_grounding_rests_on_a_declared_treatment_not_a_defaulted_one(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    """Name the defect that would otherwise fire, so the proof cannot pass hollowly.

    ``IVA_TREATMENT_UNDECLARED`` is the defect a structured confirm trips when
    the category is read from the document and then lost at the persistence
    boundary. Asserting its absence by name means a future change that grounds
    the record some other way -- by defaulting a category, say -- does not
    silently satisfy the test above while reintroducing exactly the guess the
    structured reader exists to remove.
    """
    result = _confirm_as_issued(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        authority=invoice_authority,
    )

    defects = set(decompose_invoice(result.invoice).defects)

    assert InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED not in defects
    assert InvoiceDecompositionDefect.FX_UNRESOLVED not in defects
    # The invoice carries real figures, so a grounding that rode on empty totals
    # would be a different thing passing under the same assertion.
    assert result.invoice.base_total > Decimal("0")


def test_an_unreadable_document_is_not_grounded_by_this_path(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    """The discriminator: grounding must come from the document, not from confirming.

    Without this, a confirm boundary that stamped every record grounded would
    satisfy both assertions above. An invoice whose treatment nothing declares
    must still carry the undeclared defect, so the tests are reading the
    document's contribution rather than the act of persisting it.
    """
    invoice = _confirm_as_issued(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        authority=invoice_authority,
    ).invoice

    stripped = invoice.model_copy(update={"iva_category": None})

    assert InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED in set(decompose_invoice(stripped).defects), (
        "removing the declared treatment must reintroduce the defect; if it does not, the "
        "grounding assertions above are not reading the category at all"
    )


def test_a_read_retention_makes_the_net_cash_match_the_linked_invoice(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    """From the document's bytes to the income path: 1255.00 - 150.00 = 1105.00 reaches the bank.

    The declared figure is the document's, and it comes back once: the derivation is
    the invoice's rather than an inference from the cash added to it.
    """
    # The specimen prints its seller with the VAT prefix; the filer's profile holds the NIF.
    source = tmp_path / "facturae_32_retencion_suplidos_invoice.xml"
    source.write_bytes((EVIDENCE_CORPUS / source.name).read_bytes())
    record = make_svc(isolated_settings, secure_objects).add(bucket_id=BUCKET_ID, source_path=source).record
    invoice = confirm_invoice_draft_from_evidence(
        counterparty_country="ES",
        bucket_id=BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        evidence_id=record.evidence_id,
        settings=isolated_settings,
        **invoice_confirmation_kwargs(bucket_id=BUCKET_ID, authority=invoice_authority),
    ).invoice
    transaction = Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id="cobro-1",
                booked_date=invoice.issued_at,
                value_date=invoice.issued_at,
                amount=Decimal("1105.00"),
                currency="EUR",
                counterparty="Cliente Ejemplo SA",
                description="cobro factura",
                provenance=RawProvenance(
                    source_path=source,
                    source_sha256="d" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(_YEAR, 4, 6, 12, 0, tzinfo=UTC),
                    provider_name="CSV provider",
                ),
                raw_fields={},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": "actividad_economica",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_YEAR, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )
    linked_invoice = invoice.model_copy(update={"linked_transaction_ids": (transaction.transaction_id,)})
    linked_transaction = transaction.model_copy(update={"invoice_id": invoice.invoice_id})

    payload, refusal = sales_invoice_evidence_payload(
        invoices=build_invoice_catalogue((linked_invoice,)),
        bucket_id=BUCKET_ID,
        transaction=linked_transaction,
    )
    withheld = income_withheld_amount(linked_transaction, evidence=payload)

    assert refusal is None
    assert invoice.suplido_amount == Decimal("45.00")
    assert invoice.grand_total == Decimal("1255.00")
    # A suplido is no part of the taxable base or the cuota.
    assert payload.taxable_base == Decimal("1000.00")
    assert payload.iva_amount == Decimal("210.00")
    assert payload.retencion_amount == Decimal("150.00")
    assert withheld[0] == Decimal("150.00")
    assert withheld[1] is LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE


def test_an_issued_document_printing_another_issuer_is_still_refused(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    """Stripping the country prefix is not a way past the check: a different NIF stays another issuer."""
    source = tmp_path / "facturae_32_retencion_suplidos_invoice.xml"
    printed = (EVIDENCE_CORPUS / source.name).read_text(encoding="utf-8")
    source.write_text(printed.replace(f">ES{_FIXTURE_SELLER_TAX_ID}<", ">ESB00015016<", 1), encoding="utf-8")
    record = make_svc(isolated_settings, secure_objects).add(bucket_id=BUCKET_ID, source_path=source).record

    with pytest.raises(PurchaseInvoiceEvidenceInputError, match="another issuer"):
        confirm_invoice_draft_from_evidence(
            counterparty_country="ES",
            bucket_id=BUCKET_ID,
            kind=InvoiceKind.ISSUED,
            evidence_id=record.evidence_id,
            settings=isolated_settings,
            **invoice_confirmation_kwargs(bucket_id=BUCKET_ID, authority=invoice_authority),
        )
