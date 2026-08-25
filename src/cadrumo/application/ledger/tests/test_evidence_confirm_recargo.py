"""A recargo de equivalencia stated by the document must survive parse -> confirm.

The Facturae parser reads ``EquivalenceSurchargeAmount`` exactly, and
:func:`~application.invoices.create_catalogue_invoice` already models the
recargo as riding INSIDE the invoice total (LIVA art. 161), re-checking the
``base + cuota + recargo`` identity on the way in. The confirm boundary between
them read neither: it forwarded only the operator's ``--recargo-amount``
override, so a document that states its own recargo lost it whenever the
operator did not retype the figure they were confirming.

These are the round-trip proofs. They run against the real bundled corpus
fixture rather than a hand-built draft, so the parser and the confirm boundary
are exercised together and neither can be satisfied by a stub of the other.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.iva import InvoiceKind
from .._evidence_draft import confirm_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import seeded_filer_profile as seeded_filer_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

# The bundled Facturae 3.2.2 fixture: a wholesaler billing a recargo-de-
# equivalencia retailer. Every expected figure below is the one the document
# itself prints, never one recomputed from the base and a rate -- recomputing
# would assert the code's own arithmetic against itself.
_RECARGO_FIXTURE = Path(__file__).parent / "_evidence_corpus" / "facturae_32_recargo_invoice.xml"

# <TaxableBase><TotalAmount>100.00
_PRINTED_BASE = Decimal("100.00")
# <TaxAmount><TotalAmount>21.00
_PRINTED_IVA = Decimal("21.00")
# <EquivalenceSurchargeAmount><TotalAmount>5.20
_PRINTED_RECARGO = Decimal("5.20")
# <InvoiceTotal>126.20 -- the figure on the paper the operator is confirming.
_PRINTED_TOTAL = Decimal("126.20")


def _confirm_the_recargo_document(
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
):
    """Confirm the fixture with NO operator overrides at all.

    The absence of overrides is the whole point: the operator is confirming what
    the reader found, which is the path on which a field the document states can
    go missing without anyone retyping it.
    """
    source = tmp_path / "facturae_32_recargo_invoice.xml"
    source.write_bytes(_RECARGO_FIXTURE.read_bytes())
    svc = _make_svc(isolated_settings, secure_objects)
    record = svc.add(bucket_id=_BUCKET_ID, source_path=source).record
    return confirm_invoice_draft_from_evidence(
        counterparty_country="ES",
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        evidence_id=record.evidence_id,
        settings=isolated_settings,
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
    )


def test_the_recargo_the_document_states_reaches_the_persisted_invoice(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The confirmed invoice carries the document's own recargo figure.

    A recargo de equivalencia is a real cuota the wholesaler owes (LIVA art.
    161) and Modelo 303 sums it in its own devengado tiers, separate from the
    IVA repercutido tiers. Dropping it at the confirm boundary removes the whole
    figure from every downstream aggregation while leaving an invoice that looks
    complete.
    """
    result = _confirm_the_recargo_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )

    assert result.draft.recargo_amount == _PRINTED_RECARGO, "the parser did not read the recargo off the document"
    assert result.invoice.recargo_amount == _PRINTED_RECARGO, (
        f"the recargo was read from the document but lost at the confirm boundary: {result.invoice.recargo_amount!r}"
    )


def test_the_confirmed_total_reconciles_with_the_total_on_the_paper(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Grand total equals the printed total, with the recargo inside it.

    This is the check that makes the loss visible as an amount rather than as a
    missing field: the recargo rides INSIDE the invoice total, so an invoice
    that dropped it reconciles to 121,00 against a document that prints 126,20.
    ``total_discrepancy`` is asserted absent for the same reason -- the confirm
    already computes that cross-check, and it firing here means the record no
    longer matches the evidence it was minted from.
    """
    result = _confirm_the_recargo_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    invoice = result.invoice

    assert invoice.base_total == _PRINTED_BASE
    assert invoice.iva_total == _PRINTED_IVA
    assert invoice.grand_total == _PRINTED_TOTAL
    assert invoice.grand_total == invoice.base_total + invoice.iva_total + (invoice.recargo_amount or Decimal("0"))
    assert result.total_discrepancy is None, (
        f"the record no longer reconciles with the document it was minted from: {result.total_discrepancy!r}"
    )


def test_re_confirming_the_same_document_is_a_guarded_no_op(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """A second confirm returns the existing invoice instead of refusing.

    The guarded-retry lookup hashes the CANDIDATE invoice's derived identity,
    and that identity includes the totals. A candidate built without the lines
    and the recargo that the real record carries hashes to an id nothing in the
    catalogue holds, so the lookup misses and the retry falls through to the
    writer's duplicate-identity refusal -- a retry that raises rather than
    returning the record it already minted.
    """
    first = _confirm_the_recargo_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    second = _confirm_the_recargo_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )

    assert first.created is True
    assert second.created is False, "the retry minted or refused instead of matching the existing record"
    assert second.invoice.invoice_id == first.invoice.invoice_id
    assert second.invoice.recargo_amount == _PRINTED_RECARGO
