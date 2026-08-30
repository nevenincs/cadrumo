"""A two-rate structured document must survive parse -> confirm with both rates.

The structured parsers read an EN16931 document exactly: a two-rate invoice
yields two lines and a two-entry per-rate breakdown, because a single base and
cuota pair cannot represent a document that charges 21% on one part and 10% on
another. That exactness is only worth having if it survives the confirm
boundary, which is where a parsed draft becomes a persisted invoice.

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
from ....domain.invoices.enums import IvaRate
from ....domain.iva import InvoiceKind
from ..evidence_draft import confirm_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import seeded_filer_profile as seeded_filer_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

# The bundled EN16931 UBL fixture: 100,00 at 21% plus 50,00 at 10%, so base
# 150,00, cuota 26,00, total 176,00. Two rates is the minimum that can detect a
# collapse -- a single-rate document looks identical whether the breakdown
# survived or was rebuilt from the totals.
_TWO_RATE_FIXTURE = Path(__file__).parent / "_evidence_corpus" / "en16931_ubl_two_rate_invoice.xml"

_EXPECTED_BASE = Decimal("150.00")
_EXPECTED_IVA = Decimal("26.00")
_EXPECTED_TOTAL = Decimal("176.00")
# Keyed by the closed rate SLOT the invoice persists, not by a percentage: the
# slot is what a Modelo 303 tier is summed from, so asserting on it is asserting
# on the thing that reaches the declaration.
_EXPECTED_RATE_SPLIT = (
    (IvaRate.RATE_21, Decimal("100.00"), Decimal("21.00")),
    (IvaRate.RATE_10, Decimal("50.00"), Decimal("5.00")),
)


def _confirm_the_two_rate_document(
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
):
    source = tmp_path / "en16931_ubl_two_rate_invoice.xml"
    source.write_bytes(_TWO_RATE_FIXTURE.read_bytes())
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


def test_both_rates_survive_the_confirm_boundary(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The confirmed invoice carries a line per rate, not one collapsed line.

    The failure this guards is not a wrong total -- the totals agree either way,
    which is exactly why it is easy to miss. It is the loss of WHICH part of the
    base carried which rate. A Modelo 303 cuota devengada is summed per tier, so
    an invoice that reports 150,00 at a single rate declares into one tier what
    belongs in two, and the arithmetic still adds up.
    """
    result = _confirm_the_two_rate_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    lines = result.invoice.lines

    assert len(lines) == 2, f"the second rate was lost in transit: {[line.iva_rate for line in lines]}"
    observed = {(line.iva_rate, line.subtotal, line.iva_amount) for line in lines}
    assert observed == set(_EXPECTED_RATE_SPLIT)


def test_the_invoice_level_identity_holds_exactly_on_the_parsed_document(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """Grand total equals base plus IVA exactly, with no per-line rounding drift.

    Asserted at the INVOICE level rather than per line, because per-line
    rounding is where the drift would accumulate: two lines each rounded half a
    cent the same way put a full cent on the total, and a document whose parts
    are individually plausible stops reconciling against the paper.

    A retencion, when present, sits OUTSIDE this identity -- it is withheld from
    the payment, not deducted from the invoice -- so the identity is base plus
    cuota plus recargo, and this fixture carries neither.
    """
    result = _confirm_the_two_rate_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    invoice = result.invoice

    assert invoice.base_total == _EXPECTED_BASE
    assert invoice.iva_total == _EXPECTED_IVA
    assert invoice.grand_total == _EXPECTED_TOTAL
    assert invoice.grand_total == invoice.base_total + invoice.iva_total

    # The per-line parts must reconstitute the invoice-level figures, not merely
    # sit near them: this is what makes the identity above a real check rather
    # than three constants agreeing with each other.
    assert sum(line.subtotal for line in invoice.lines) == invoice.base_total
    assert sum(line.iva_amount for line in invoice.lines) == invoice.iva_total


def test_re_confirming_the_two_rate_document_is_a_guarded_no_op(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """A second confirm returns the existing invoice rather than refusing.

    ``invoice_id`` hashes ``grand_total``, and the guarded-retry lookup is done
    against a CANDIDATE invoice built separately from the one actually written.
    A candidate built without the per-rate lines totals 150,00 where the record
    it is meant to find totals 176,00, so the lookup hashes to an id nothing in
    the catalogue holds. The retry then falls through to the writer's
    duplicate-identity refusal -- an operator retry that raises instead of
    returning the invoice it already minted, which is precisely what the
    idempotency guard exists to prevent.
    """
    first = _confirm_the_two_rate_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    second = _confirm_the_two_rate_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )

    assert first.created is True
    assert second.created is False, "the retry refused or minted instead of matching the existing record"
    assert second.invoice.invoice_id == first.invoice.invoice_id
    assert second.invoice.iva_total == _EXPECTED_IVA
