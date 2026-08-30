"""A plain rated document must ground, without anyone inventing its tier.

A structured document that charges an ordinary rate states the UNTDID category
code for "standard rate", which by design carries no special treatment: the rate
itself is the meaning. The record was therefore minted with no IVA category at
all, and a record with no declared treatment fails the invoice decomposition
contract as undeclared.

That failure is not an exclusion, which is what makes it quiet. The renta
sales-evidence path still counts the row, but it contributes the bank cash it was
paid rather than the ingresos íntegros the casilla asks for -- the invoice's
base, its cuota and its retención are all dropped from the figure that reaches
the declaration.

The repair is a resolution, not a guess. ``rate_kinds_for_declared_rate`` answers
"which tier was this declared rate, on this date" against the registered rate
records, and ``domestic_categories_by_rate_kind`` is the single authority for
which domestic category a tier denotes. Both already ship, both are grounded, and
the first returns a TUPLE precisely because the question can have more than one
answer -- so a caller detects ambiguity instead of picking.

Three cases deliberately resolve to nothing rather than to a best effort, and
each has its own proof below: a multi-rate document, a recargo-bearing document,
and a rate that was not a registered Spanish rate on the day the document was
issued. Leaving the category undeclared in those cases is visible downstream --
the decomposition reports it and the renta path raises an advisory -- whereas a
guess would not be.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.invoices.decomposition import decompose_invoice
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory, IvaRateKind
from ..evidence_draft import (
    InvoiceDraft,
    InvoiceDraftRateBreakdown,
    confirm_invoice_draft_from_evidence,
    domestic_rate_tier_from_the_document,
)
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import seeded_filer_profile as seeded_filer_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

_CORPUS = Path(__file__).parent / "_evidence_corpus"

# Single rate, 21% on a 2026 invoice date, no recargo: the ordinary case.
_PLAIN_RATED = _CORPUS / "facturae_32_series_and_parties_invoice.xml"
# Two rates, so one category field has two answers.
_TWO_RATE = _CORPUS / "en16931_ubl_two_rate_invoice.xml"
# Single rate, but the document also charges a recargo de equivalencia.
_RECARGO = _CORPUS / "facturae_32_recargo_invoice.xml"


def _confirm(
    fixture: Path,
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
):
    """Confirm *fixture* with no operator overrides at all."""
    source = tmp_path / fixture.name
    source.write_bytes(fixture.read_bytes())
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


def test_a_plain_rated_document_grounds_through_the_decomposition_contract(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The ordinary case reaches a declarable figure instead of being refused.

    Asserted on the decomposition verdict rather than only on the category,
    because the verdict is what the renta sales-evidence path actually consults.
    A category that resolved but left the record ungrounded would satisfy a
    field check and change nothing about the declaration.
    """
    result = _confirm(
        _PLAIN_RATED,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    verdict = decompose_invoice(result.invoice)

    assert result.invoice.iva_category is IvaCategory.DOMESTIC_GENERAL, (
        f"the 21% tier was not resolved from the document: {result.invoice.iva_category!r}"
    )
    assert verdict.is_grounded, (
        "the confirmed invoice is still refused by the decomposition contract, so the renta "
        f"income path contributes bank cash instead of ingresos integros: {[d.value for d in verdict.defects]}"
    )


def test_a_two_rate_document_leaves_the_category_undeclared(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """One category field cannot hold a two-tier document's answer.

    Pinned as a deliberate limit rather than left to chance. Picking either tier
    would declare part of the invoice under a rate it was not charged at, and
    picking by size would be an invention. Which category a multi-rate invoice
    takes is a modelling decision this resolution does not make, so the record
    stays undeclared and visibly so.
    """
    result = _confirm(
        _TWO_RATE,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )

    assert result.invoice.iva_category is None
    # The two rates still survive as lines: leaving the invoice-level category
    # undeclared must not be achieved by flattening the document.
    assert len(result.invoice.lines) == 2


def test_a_recargo_document_leaves_the_category_undeclared(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """A recargo invoice's category is a legal choice the rate does not answer.

    The rate resolves cleanly here -- the document charges a single 21% -- so
    this case is excluded on purpose rather than by accident. A supply carrying a
    recargo de equivalencia may belong to the ordinary domestic tier or to the
    recargo category, and the decomposition contract accepts BOTH, so a wrong
    pick would not be caught anywhere downstream. That is precisely the shape
    that must not be guessed.
    """
    result = _confirm(
        _RECARGO,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )

    assert result.invoice.recargo_amount == Decimal("5.20")
    assert result.invoice.iva_category is None


def test_a_rate_unregistered_on_the_issue_date_resolves_to_nothing() -> None:
    """The refusal branch, observed refusing rather than assumed to.

    Spain's general tier stood at 16 % until mid-2010 and reached 21 % only on
    1 September 2012, so a 21 % document issued in 2010 states a rate that was
    not a registered Spanish tier on its own issue date. The resolution must
    decline rather than fall back to today's meaning of 21 %, which is the whole
    reason the lookup takes a date.

    The dates are keyed to the statute rather than to how far the shipped rate
    records happen to reach. An earlier revision of this test asserted the
    refusal at 2023 on the belief that the records began in 2024; they were
    since extended backwards and the assertion became a claim about the fixture
    instead of about the law.

    Asserted on the TIER rather than on a category, because the resolution now
    stops at the tier: it hands that axis to the rule table's criteria, where
    ``R05`` applies the tier-to-category mapping this resolution used to copy.
    The declines are unchanged; only what they decline to produce is.

    Exercised here rather than through a confirm because no document in the
    bundled corpus predates the rate records, so the end-to-end route cannot
    reach this branch. The draft and the lookup are both real; only the calling
    layer is skipped.
    """
    draft = InvoiceDraft(iva_breakdown=(InvoiceDraftRateBreakdown(iva_rate=Decimal("21")),))

    assert domestic_rate_tier_from_the_document(draft, invoice_date=date(2010, 11, 20)) is None
    # The same draft on a date the rate WAS registered resolves, so the refusal
    # above is attributable to the date and not to the draft being unusable.
    assert domestic_rate_tier_from_the_document(draft, invoice_date=date(2015, 11, 20)) is IvaRateKind.GENERAL
