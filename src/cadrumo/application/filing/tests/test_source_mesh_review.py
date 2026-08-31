"""Approval-basis staleness coverage for the invoice calculation source.

Exercises the ``invoice_catalogue_fingerprint`` added to
:class:`~domain.filing.ModeloApprovalBasis`: an ``APROBADO`` draft must go stale with
:attr:`~application.filing.ModeloApprovalStaleReason.INVOICE_CATALOGUE_CHANGED`
when the bucket's upstream issued/received invoices change, and must not be flagged
when they are unchanged. The invoice catalogue is a calculation source resolved
through the source mesh; before this fingerprint only the ledger transaction
catalogue was covered, so an invoice edit could silently invalidate a filing draft.

Real behaviour: the fingerprint is self-loaded from the encrypted
:class:`InvoiceCatalogueRepository`, mirroring the transaction-catalogue path, so
stale detection is reproducible at refresh time without running the source mesh in
the review layer.

See Also:
    :func:`~application.filing.compute_current_approval_basis`
        Builds the current review fingerprints, including the invoice catalogue.
    :func:`~application.filing.approval_stale_reasons`
        Compares the stored approval basis with the current invoice digest.
    :func:`~application.filing.draft_review._invoice_catalogue_fingerprint`
        Stable, order-independent digest over invoice catalogue records.
    :class:`~adapters.persistence.profile.invoices.InvoiceCatalogueRepository`
        Encrypted invoice store self-loaded by the review layer.
    :class:`~application.invoices.InvoiceCatalogueSourceResolver`
        Calculation source resolver for the same invoice catalogue surface.
    :mod:`~application.filing.tests.test_source_mesh_review_unit`
        Registry-free unit coverage for the fingerprint helper.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....core.period import Period
from ....domain.filing.protocols import CasillaSchemaProvider
from ....domain.filing.schema import ModeloDraft
from ....domain.invoices.models import Invoice, InvoiceCatalogue
from ....domain.iva.classification import InvoiceKind
from ....domain.submission.models import ModeloDraftStatus
from ....tests.secure_sql import TestRuntimeProfile
from ...invoices.catalogue_creation import build_catalogue_invoice
from .._draft_construction import build_draft
from ..draft_review import ModeloApprovalStaleReason, approval_stale_reasons, approve_draft
from ..runtime import ModeloOperatorProfile, build_runtime_schema_provider

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PERIOD = Period.from_year_and_code(2026, "1T")
# The filing conftest's module-scope ``_active_bucket_runtime`` activates this
# bucket; integration tests below route their invoice repository, approval, and
# staleness checks through it (via ``runtime.bucket_id``) so the self-load lands
# in the active session. The pure-fingerprint unit tests never touch storage, so
# they use it only as the invoice-record stamp.
_RUNTIME_BUCKET_ID = "0fab7c94-777c-4598-ae8f-c4b539f300c3"  # was 'filing-test'
_COUNTERPARTY_CIF = "A58818501"


def _schema_provider() -> CasillaSchemaProvider:
    return build_runtime_schema_provider(modelos=("130",), filing_year=_PERIOD.filing_year, period=_PERIOD)


def _ready_draft(schema_provider: CasillaSchemaProvider) -> ModeloDraft:
    return build_draft(
        modelo="130",
        period=_PERIOD,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Source mesh review test"),
        inputs={
            "01": Decimal("100"),
            "02": Decimal("25"),
            "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        schema_provider=schema_provider,
    )


def _invoice(invoice_number: str, *, taxable_base: Decimal, bucket_id: str = _RUNTIME_BUCKET_ID) -> Invoice:
    return build_catalogue_invoice(
        bucket_id=bucket_id,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id=_COUNTERPARTY_CIF,
        counterparty_country="ES",
        invoice_number=invoice_number,
        issued_at=date(2026, 3, 10),
        taxable_base=taxable_base,
        iva_rate=Decimal("21"),
        currency="EUR",
    )


def test_approval_goes_stale_when_invoice_source_data_changes(
    _active_bucket_runtime: TestRuntimeProfile,
) -> None:
    bucket_id = _active_bucket_runtime.bucket_id
    schema_provider = _schema_provider()
    draft = _ready_draft(schema_provider)
    repository = InvoiceCatalogueRepository(bucket_id=bucket_id)

    repository.save(
        InvoiceCatalogue.from_invoices([_invoice("2026-0001", taxable_base=Decimal("100.00"), bucket_id=bucket_id)]),
    )
    approved = approve_draft(
        draft,
        bucket_id=bucket_id,
        approved_by="operator",
        schema_provider=schema_provider,
    )
    assert approved.status is ModeloDraftStatus.APROBADO
    assert approved.approval_basis is not None
    assert approved.approval_basis.invoice_catalogue_fingerprint  # populated, non-empty

    # Mutate ONLY the invoice source: a different taxable base yields a different
    # invoice, so the self-loaded catalogue fingerprint must change.
    repository.save(
        InvoiceCatalogue.from_invoices([_invoice("2026-0001", taxable_base=Decimal("250.00"), bucket_id=bucket_id)]),
    )

    reasons = approval_stale_reasons(approved, bucket_id=bucket_id, schema_provider=schema_provider)

    # Only the invoice source changed: the draft, transactions, category profiles,
    # and schema are all unchanged, so INVOICE_CATALOGUE_CHANGED is the sole reason.
    assert reasons == (ModeloApprovalStaleReason.INVOICE_CATALOGUE_CHANGED,)


def test_approval_not_stale_when_invoice_source_unchanged(
    _active_bucket_runtime: TestRuntimeProfile,
) -> None:
    """Anti-tautology: an unchanged invoice catalogue produces NO stale reason.

    If :func:`approval_stale_reasons` returned INVOICE_CATALOGUE_CHANGED
    regardless of whether the invoices actually changed, the stale signal would be
    meaningless. Approving and then re-checking against the identical catalogue
    must yield an empty reason tuple.
    """
    bucket_id = _active_bucket_runtime.bucket_id
    schema_provider = _schema_provider()
    draft = _ready_draft(schema_provider)
    repository = InvoiceCatalogueRepository(bucket_id=bucket_id)

    repository.save(
        InvoiceCatalogue.from_invoices([_invoice("2026-0001", taxable_base=Decimal("100.00"), bucket_id=bucket_id)]),
    )
    approved = approve_draft(
        draft,
        bucket_id=bucket_id,
        approved_by="operator",
        schema_provider=schema_provider,
    )

    # No mutation to any source between approval and the staleness check.
    reasons = approval_stale_reasons(approved, bucket_id=bucket_id, schema_provider=schema_provider)

    assert ModeloApprovalStaleReason.INVOICE_CATALOGUE_CHANGED not in reasons
    assert reasons == ()
