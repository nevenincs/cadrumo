"""The IVA category a structured document states must survive parse -> confirm.

The UNTDID 5305 tax-category code is a fact only a structured reader can
recover: it is IN the document's own record, and no regex or vision reader can
supply it. The parser maps it onto :class:`~domain.iva.IvaCategory` for exactly
that reason.

A domestic reverse-charge supply (LIVA art. 84.Uno.2) is the case where losing
it costs a declaration. Reverse charge, exempt and zero-rated all print a
taxable base and no cuota, so once the category code is gone the record is
indistinguishable from an ordinary zero-cuota supply -- and the recipient's
self-assessed output IVA, which Modelo 303 collects in its own inversion-del-
sujeto-pasivo tier, is never assessed at all. The document said so; the record
did not.

The proof runs against a bundled corpus fixture, so the parser and the confirm
boundary are exercised together and neither can be satisfied by a stub of the
other. The asserted value is the category the DOCUMENT states, not a figure
recomputed from anything the code under test derives.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.iva import InvoiceKind, IvaCategory
from ..evidence_draft import confirm_invoice_draft_from_evidence
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import seeded_filer_profile as seeded_filer_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

# UNTDID 5305 code AE on a 2.000,00 base with a 0,00 cuota.
_REVERSE_CHARGE_FIXTURE = Path(__file__).parent / "_evidence_corpus" / "en16931_ubl_reverse_charge_invoice.xml"

_PRINTED_BASE = Decimal("2000.00")


def _confirm_the_reverse_charge_document(
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
):
    """Confirm with NO ``iva_category`` override.

    The omission is the point: the operator is confirming what the reader found,
    and the reader found the category in the document's own record.
    """
    source = tmp_path / "en16931_ubl_reverse_charge_invoice.xml"
    source.write_bytes(_REVERSE_CHARGE_FIXTURE.read_bytes())
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


def test_the_reverse_charge_category_reaches_the_persisted_invoice(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """The record carries the reverse-charge category the document declared.

    Without it the invoice is an ordinary zero-cuota supply, and the
    self-assessed output IVA that a reverse charge obliges is never declared.
    """
    result = _confirm_the_reverse_charge_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )

    assert result.draft.iva_category == IvaCategory.DOMESTIC_REVERSE_CHARGE.value, (
        f"the parser did not read the category off the document: {result.draft.iva_category!r}"
    )
    assert result.invoice.iva_category is IvaCategory.DOMESTIC_REVERSE_CHARGE, (
        f"the category was read from the document but lost at the confirm boundary: {result.invoice.iva_category!r}"
    )
    # The amounts are asserted alongside so a future change cannot satisfy the
    # category check by mangling the figures it rides with.
    assert result.invoice.base_total == _PRINTED_BASE
    assert result.invoice.iva_total == Decimal("0.00")


def test_an_operator_supplied_category_still_wins(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """An explicit override outranks the document-read category.

    Same layering as every other field on this path: the reader is best-effort
    and the operator, holding the document, is the final authority.
    """
    source = tmp_path / "en16931_ubl_reverse_charge_invoice.xml"
    source.write_bytes(_REVERSE_CHARGE_FIXTURE.read_bytes())
    svc = _make_svc(isolated_settings, secure_objects)
    record = svc.add(bucket_id=_BUCKET_ID, source_path=source).record

    result = confirm_invoice_draft_from_evidence(
        counterparty_country="ES",
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        evidence_id=record.evidence_id,
        iva_category=IvaCategory.DOMESTIC_EXEMPT,
        settings=isolated_settings,
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
    )

    assert result.invoice.iva_category is IvaCategory.DOMESTIC_EXEMPT


# UNTDID 5305 code G (export outside the Community, LIVA art. 21) on a 2.000,00
# base with a 0,00 cuota, printing NO counterparty country at all.
_EXPORT_NO_COUNTRY_FIXTURE = Path(__file__).parent / "_evidence_corpus" / "en16931_ubl_export_third_country_invoice.xml"


def test_an_export_claim_with_no_establishment_does_not_reach_the_record(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """A declared code survives confirm, EXCEPT where it relieves on an absent fact.

    The counter-case to the module's other tests, and the reason the rule is
    "carry what the document declared" rather than "trust what the document
    declared". An export zero-rates the supply purely on where the parties are
    established (LIVA art. 21), and this document prints no country for either
    of them -- so the rule table cannot place the operation, the rate-tier
    corroboration is silent on every non-domestic category by construction, and
    nothing else in the chain disagrees. The code would otherwise have been
    honoured and a zero-rated supply recorded for parties nobody could locate.

    Confirmed as RECEIVED because the guard turns on an unestablished residency
    and not on which side is missing, and this fixture prints a name for the
    supplier only. An export code arriving on a received document is itself
    unusual, which is beside the point: the treatment it claims rests on
    establishment evidence either way, and neither party has any.

    Asserted on the PERSISTED record rather than on the resolution, because the
    record is what a filing is built from: a withholding that stopped short of
    the catalogue would satisfy an internal check and change no declaration.

    The parse assertion beside it is a positive control. Were the reader to stop
    emitting the code, the category would be absent for an entirely different
    reason and this test would pass while proving nothing.
    """
    source = tmp_path / _EXPORT_NO_COUNTRY_FIXTURE.name
    source.write_bytes(_EXPORT_NO_COUNTRY_FIXTURE.read_bytes())
    svc = _make_svc(isolated_settings, secure_objects)
    record = svc.add(bucket_id=_BUCKET_ID, source_path=source).record

    result = confirm_invoice_draft_from_evidence(
        counterparty_country="ES",
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        evidence_id=record.evidence_id,
        # The document prints no name for this party, which is ordinary and is
        # not what is under test. Supplied so the confirm reaches the
        # classification rather than refusing earlier for an unrelated reason.
        counterparty_name="Exportadora Peninsular SL",
        settings=isolated_settings,
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
    )

    assert result.draft.iva_category == IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED.value, (
        "positive control: the reader must still be emitting the export code, or the "
        f"withholding below is attributable to the parser instead: {result.draft.iva_category!r}"
    )
    assert result.invoice.iva_category is not IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED, (
        "a zero-rated export reached the record for a counterparty whose establishment "
        "the classification recorded as a gap"
    )
    assert result.invoice.iva_category is None
    # The figures still land: withholding the treatment must not be achieved by
    # discarding what the document said about the money.
    assert result.invoice.base_total == _PRINTED_BASE
