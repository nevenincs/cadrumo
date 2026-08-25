"""The counterparty side is selected by direction, and never by falling back.

An invoice prints two parties. Which one a downstream informativa needs depends
on the document's direction, and the reader does not know the direction -- the
operator supplies it at confirm as ``--kind``. So the side is chosen there.

The choice used to be "the customer if it is set, otherwise the supplier", and
because the text and vision readers could not report a customer at all, every
ISSUED document resolved to the supplier -- who, on a document the filer issued,
IS the filer. That value is checksum-valid, so every identity check downstream
passes it, and it is bound for the Modelo 347 / 349 totals AEAT reconciles
against the other party's own declaration.

**Why these cases run on a bucket with no taxpayer profile.** Two guards in the
confirm path already refuse a counterparty that names the filer, and they are
good guards. Both load the taxpayer profile, and both return without refusing
when it is absent or carries no tax id -- deliberately, because a guard that
cannot run must not block a path it cannot judge. That means a gate written on a
normally-configured bucket would pass whether or not the selection is correct,
and would be measuring the guards rather than the selection. Green from a
neighbouring guard is indistinguishable from green from the code under test, and
unlike a spurious red nobody investigates it.

So every case here runs in the configuration where the guards are inert, and
:func:`test_the_guards_this_gate_deliberately_excludes_are_inert_here` asserts
that they are. What survives is the selection alone.

See Also:
    :func:`~application.ledger.confirm_invoice_draft_from_evidence`
        The confirm step whose side selection these cases pin.
    :class:`~application.ledger.InvoiceDraft`
        Carries the two printed parties the selection chooses between.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.iva import InvoiceKind
from ....tests.pdf_fixtures import text_pdf_bytes
from .._evidence import PurchaseInvoiceEvidenceInputError
from .._evidence_draft import confirm_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import seeded_filer_profile as seeded_filer_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects
from ._loopback_reader import serving_a_loopback_reader

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

# Two DIFFERENT checksum-valid identifiers. A fixture reusing one for both
# parties cannot fail when the sides are confused, which is the only failure
# this module exists to catch.
_ISSUER_CIF = "B12345674"
_BILLED_NIF = "12345678Z"

_BOTH_PARTIES_PRINTED = (
    "Factura de Acme Suministros SL",
    f"CIF emisor: {_ISSUER_CIF}",
    f"NIF cliente: {_BILLED_NIF}",
    "Numero de factura: 2026-0500",
    "Fecha: 10/03/2026",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)

# The same document as read by a reader that recovered only ONE party. This is
# the real state of the text and vision lanes for any document that prints the
# billed party in a form the reader could not attribute.
_ONE_PARTY_PRINTED = (
    "Factura de Acme Suministros SL",
    f"CIF emisor: {_ISSUER_CIF}",
    "Numero de factura: 2026-0501",
    "Fecha: 10/03/2026",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)

_COMMON_FIGURES = {
    "invoice_date": "2026-03-10",
    "invoice_date_anchor": "10/03/2026",
    "taxable_base": "100,00",
    "taxable_base_anchor": "100,00",
    "iva_rate": "21",
    "iva_rate_anchor": "21%",
    "iva_amount": "21,00",
    "iva_amount_anchor": "21,00",
    "grand_total": "121,00",
    "grand_total_anchor": "121,00",
    "currency": "EUR",
}

_BOTH_PARTIES_FIELDS = {
    "supplier_tax_id": _ISSUER_CIF,
    "supplier_tax_id_anchor": f"CIF emisor: {_ISSUER_CIF}",
    "customer_tax_id": _BILLED_NIF,
    "customer_tax_id_anchor": f"NIF cliente: {_BILLED_NIF}",
    "invoice_number": "2026-0500",
    "invoice_number_anchor": "2026-0500",
    **_COMMON_FIGURES,
}

_ONE_PARTY_FIELDS = {
    "supplier_tax_id": _ISSUER_CIF,
    "supplier_tax_id_anchor": f"CIF emisor: {_ISSUER_CIF}",
    "invoice_number": "2026-0501",
    "invoice_number_anchor": "2026-0501",
    **_COMMON_FIGURES,
}


@pytest.fixture(autouse=True)
def _loopback_reader() -> Iterator[None]:
    """Serve a real reading endpoint, keyed on each document's own number."""
    with serving_a_loopback_reader(
        (
            ("2026-0500", _BOTH_PARTIES_FIELDS),
            ("2026-0501", _ONE_PARTY_FIELDS),
        ),
    ):
        yield


def _stored_evidence(
    lines: tuple[str, ...],
    *,
    settings: Settings,
    objects: SecureObjectRepository,
    tmp_path: Path,
    name: str,
) -> str:
    pdf_path = tmp_path / name
    pdf_path.write_bytes(text_pdf_bytes(lines))
    record = _make_svc(settings, objects).add(bucket_id=_BUCKET_ID, source_path=pdf_path).record
    return record.evidence_id


def test_the_guards_this_gate_deliberately_excludes_are_inert_here(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
) -> None:
    """The premise of every other case in this module, asserted rather than assumed.

    Takes the same fixtures the confirm cases do, so it observes the bucket they
    actually run in rather than a different one. If a taxpayer profile ever
    became part of that fixture, the cases below would start passing for a
    reason none of them names, and the selection could regress silently behind a
    guard that happened to catch it.
    """
    from ...wizard import WizardStatusError, load_active_taxpayer_profile
    from cadrumo.application.workflow.persistence import workflow_state_repository

    # The refusal both guards swallow. Raising it here is what makes them return
    # without refusing, which is precisely the state this module needs.
    with pytest.raises(WizardStatusError):
        load_active_taxpayer_profile(workflow_state_repository().load())


def test_an_issued_document_records_the_billed_party_not_the_issuer(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """On a document the filer issued, the counterparty is the party billed."""
    evidence_id = _stored_evidence(
        _BOTH_PARTIES_PRINTED,
        settings=isolated_settings,
        objects=secure_objects,
        tmp_path=tmp_path,
        name="issued.pdf",
    )

    confirmation = confirm_invoice_draft_from_evidence(
        counterparty_country="ES",
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        evidence_id=evidence_id,
        counterparty_name="Cliente Ejemplo SL",
        settings=isolated_settings,
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
    )

    assert confirmation.invoice.counterparty_tax_id == _BILLED_NIF
    # Stated as its own assertion rather than implied by the one above: the
    # failure this gate exists to catch is specifically the ISSUER landing here.
    assert confirmation.invoice.counterparty_tax_id != _ISSUER_CIF


def test_a_received_document_records_the_issuing_party(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The mirror direction, so the fix cannot be a blanket swap of the sides."""
    evidence_id = _stored_evidence(
        _BOTH_PARTIES_PRINTED,
        settings=isolated_settings,
        objects=secure_objects,
        tmp_path=tmp_path,
        name="received.pdf",
    )

    confirmation = confirm_invoice_draft_from_evidence(
        counterparty_country="ES",
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        evidence_id=evidence_id,
        counterparty_name="Acme Suministros SL",
        settings=isolated_settings,
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
    )

    assert confirmation.invoice.counterparty_tax_id == _ISSUER_CIF


def test_an_issued_document_with_no_billed_party_read_refuses_rather_than_substituting(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The load-bearing case: an unread counterparty is asked for, never guessed.

    This is where the fallback did its damage. The reader recovered one party,
    the issuer, and the confirm path used it because the customer side was unset
    -- naming the filer as their own counterparty. Refusing converts a silent
    wrong answer into an explicit ask, and the operator supplies the real
    identifier with an override.

    Both guards are inert here, so nothing but the selection can produce this
    refusal.
    """
    repository = InvoiceCatalogueRepository(objects=secure_objects)
    evidence_id = _stored_evidence(
        _ONE_PARTY_PRINTED,
        settings=isolated_settings,
        objects=secure_objects,
        tmp_path=tmp_path,
        name="issued-one-party.pdf",
    )

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        confirm_invoice_draft_from_evidence(
            counterparty_country="ES",
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.ISSUED,
            evidence_id=evidence_id,
            counterparty_name="Cliente Ejemplo SL",
            settings=isolated_settings,
            invoice_repository=repository,
        )

    assert "counterparty_tax_id" in str(raised.value)
    # Nothing was written: a refused confirm must not leave a record naming the
    # filer, which is the outcome the fallback produced.
    assert len(InvoiceCatalogueRepository(objects=secure_objects).load()) == 0


def test_an_operator_override_supplies_the_counterparty_the_reader_could_not(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The refusal above is a door, not a wall -- the documented way through it."""
    evidence_id = _stored_evidence(
        _ONE_PARTY_PRINTED,
        settings=isolated_settings,
        objects=secure_objects,
        tmp_path=tmp_path,
        name="issued-override.pdf",
    )

    confirmation = confirm_invoice_draft_from_evidence(
        counterparty_country="ES",
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        evidence_id=evidence_id,
        counterparty_name="Cliente Ejemplo SL",
        counterparty_tax_id=_BILLED_NIF,
        settings=isolated_settings,
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
    )

    assert confirmation.invoice.counterparty_tax_id == _BILLED_NIF
    assert confirmation.invoice.base_total == Decimal("100.00")
