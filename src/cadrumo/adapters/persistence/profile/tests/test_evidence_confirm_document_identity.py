"""One document must not become two catalogue records, nor swallow a correction.

The confirm path derived its idempotency from the invoice's own identity hash,
which folds six resolved fields. That answers "is there already a record with
these figures", never "has this document already been turned into a record" --
so a re-confirm that resolved any of the six differently hashed to a new id and
minted a SECOND invoice from one document. Both then aggregate into Modelo 303,
347 and 390, and AEAT reconciles some of those against the counterparty's own
declaration, which makes it a filing-grade error the taxpayer cannot explain.

The mirror failure is quieter and worse. A re-confirm differing only on a field
the hash does NOT fold -- the counterparty's name, the IVA category, a retencion
-- addressed the stored record and was returned unchanged, so the correction
vanished with nothing surfaced.

Every test here runs the real path: real encrypted bucket, real attachment
store, real Facturae parser, real invoice catalogue. The identity basis under
test is the attachment's content address, so nothing is asserted about a
hand-built draft.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.invoice_confirmation import (
    InvoiceConfirmationResult,
    confirm_invoice_draft_from_evidence,
)
from cadrumo.core.config import Settings
from cadrumo.domain.invoices.errors import InvoiceValidationError
from cadrumo.domain.iva.classification import InvoiceKind

from ._invoice_confirmation_test_support import (
    _BUCKET_ID,
    _EVIDENCE_CORPUS,
    InvoiceAuthorityFixture,
    _make_svc,
    invoice_confirmation_kwargs,
    isolated_settings,
    secure_objects,
)
from ._invoice_confirmation_test_support import runtime_profile as runtime_profile
from ._invoice_confirmation_test_support import seeded_filer_profile as seeded_filer_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

# A structured document, so the reading lane is the deterministic Facturae
# parser: every re-read resolves the same figures, which is what makes a second
# confirm a statement about the SAME document rather than a different reading.
_FIXTURE = _EVIDENCE_CORPUS / "facturae_32_recargo_invoice.xml"


def _attach_the_document(
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    file_name: str = "invoice.xml",
) -> str:
    """Store the fixture as real evidence and return its evidence id."""
    source = tmp_path / file_name
    source.write_bytes(_FIXTURE.read_bytes())
    svc = _make_svc(isolated_settings, secure_objects)
    return svc.add(bucket_id=_BUCKET_ID, source_path=source).record.evidence_id


def _confirm(
    *,
    evidence_id: str,
    isolated_settings: Settings,
    repository: InvoiceCatalogueRepository,
    counterparty_name: str | None = None,
    invoice_number: str | None = None,
    retention_rate: Decimal | None = None,
    retention_amount: Decimal | None = None,
    notes: str = "",
    authority: InvoiceAuthorityFixture,
) -> InvoiceConfirmationResult:
    """Confirm the attached document, optionally restating what the operator saw."""
    return confirm_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_country="ES",
        evidence_id=evidence_id,
        settings=isolated_settings,
        **invoice_confirmation_kwargs(bucket_id=_BUCKET_ID, authority=authority),
        counterparty_name=counterparty_name,
        invoice_number=invoice_number,
        retention_rate=retention_rate,
        retention_amount=retention_amount,
        notes=notes,
    )


def test_an_unchanged_reconfirm_returns_the_stored_invoice_as_a_no_op(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    """The retry outcome: same document, same resolved fields, one record.

    This is the outcome an autonomous operator's retry must reach. A guard that
    only ever refused would be safe and useless, so the no-op is proven first.
    """
    evidence_id = _attach_the_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    repository = InvoiceCatalogueRepository(objects=secure_objects)

    first = _confirm(
        evidence_id=evidence_id,
        isolated_settings=isolated_settings,
        repository=repository,
        authority=invoice_authority,
    )
    second = _confirm(
        evidence_id=evidence_id,
        isolated_settings=isolated_settings,
        repository=repository,
        authority=invoice_authority,
    )

    assert first.created is True
    assert second.created is False
    assert second.invoice.invoice_id == first.invoice.invoice_id
    assert len(repository.load().invoices) == 1


def test_a_reconfirm_correcting_an_identity_field_refuses_instead_of_duplicating(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    """The duplication outcome: a corrected invoice number must not mint a second record.

    The invoice number is one of the six fields the id folds, so before the
    document-identity guard this call hashed to a fresh id, passed the same-id
    check, and left two invoices in the catalogue -- both reachable by every
    downstream aggregation.
    """
    evidence_id = _attach_the_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    repository = InvoiceCatalogueRepository(objects=secure_objects)
    first = _confirm(
        evidence_id=evidence_id,
        isolated_settings=isolated_settings,
        repository=repository,
        authority=invoice_authority,
    )

    with pytest.raises(InvoiceValidationError) as refusal:
        _confirm(
            evidence_id=evidence_id,
            isolated_settings=isolated_settings,
            repository=repository,
            invoice_number="CORRECTED-0001",
            authority=invoice_authority,
        )

    assert "invoice_number" in str(refusal.value)
    assert first.invoice.invoice_id in str(refusal.value)
    assert len(repository.load().invoices) == 1


def test_a_reconfirm_correcting_a_field_outside_the_hash_is_not_swallowed(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    """The subtle outcome the contract names: a changed field must never vanish.

    None of these fields is folded into the invoice id, so all three resolve to
    the stored record's own identity. Returning it unchanged would report
    success while discarding a corrected counterparty, a declared retencion and
    the operator's notes -- a silent loss, which is worse than the duplicate the
    other guard prevents because nothing surfaces to find later.
    """
    evidence_id = _attach_the_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    repository = InvoiceCatalogueRepository(objects=secure_objects)
    first = _confirm(
        evidence_id=evidence_id,
        isolated_settings=isolated_settings,
        repository=repository,
        counterparty_name="Mistyped Proveedor SL",
        authority=invoice_authority,
    )

    with pytest.raises(InvoiceValidationError) as refusal:
        _confirm(
            evidence_id=evidence_id,
            isolated_settings=isolated_settings,
            repository=repository,
            counterparty_name="Corrected Proveedor SL",
            retention_rate=Decimal("0.15"),
            retention_amount=Decimal("15.00"),
            notes="corrected after checking the paper",
            authority=invoice_authority,
        )

    message = str(refusal.value)
    assert "counterparty_name" in message
    assert "retention_rate" in message
    assert "retention_amount" in message
    assert "notes" in message
    stored = repository.load().get(first.invoice.invoice_id)
    assert stored is not None
    assert stored.counterparty_name == "Mistyped Proveedor SL"


def test_the_same_bytes_re_attached_under_a_new_evidence_id_are_one_document(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    """Identity is the document's bytes, not the evidence record wrapping them.

    An operator who re-runs an ingest gets a fresh evidence record over the same
    file. The attachment store is content-addressed, so both evidence records
    resolve to one address -- which is why the guard is keyed there rather than
    on the evidence id, and why an evidence-id-keyed guard would miss this
    entirely.
    """
    first_evidence = _attach_the_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        file_name="scan-monday.xml",
    )
    second_evidence = _attach_the_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        file_name="scan-tuesday.xml",
    )
    assert second_evidence != first_evidence

    repository = InvoiceCatalogueRepository(objects=secure_objects)
    _confirm(
        evidence_id=first_evidence,
        isolated_settings=isolated_settings,
        repository=repository,
        authority=invoice_authority,
    )

    with pytest.raises(InvoiceValidationError):
        _confirm(
            evidence_id=second_evidence,
            isolated_settings=isolated_settings,
            repository=repository,
            invoice_number="CORRECTED-0001",
            authority=invoice_authority,
        )

    assert len(repository.load().invoices) == 1


def test_public_confirmation_overrides_are_checked_on_reconfirm(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    """A changed public confirmation statement is refused rather than swallowed."""
    evidence_id = _attach_the_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    repository = InvoiceCatalogueRepository(objects=secure_objects)
    _confirm(
        evidence_id=evidence_id,
        isolated_settings=isolated_settings,
        repository=repository,
        counterparty_name="Original Proveedor SL",
        authority=invoice_authority,
    )

    corrections: tuple[tuple[str, Callable[[], InvoiceConfirmationResult]], ...] = (
        (
            "counterparty_name",
            lambda: _confirm(
                evidence_id=evidence_id,
                isolated_settings=isolated_settings,
                repository=repository,
                authority=invoice_authority,
                counterparty_name="Corrected Proveedor SL",
            ),
        ),
        (
            "invoice_number",
            lambda: _confirm(
                evidence_id=evidence_id,
                isolated_settings=isolated_settings,
                repository=repository,
                authority=invoice_authority,
                invoice_number="CORRECTED-0001",
            ),
        ),
        (
            "retention_rate",
            lambda: _confirm(
                evidence_id=evidence_id,
                isolated_settings=isolated_settings,
                repository=repository,
                authority=invoice_authority,
                retention_rate=Decimal("0.15"),
                retention_amount=Decimal("15.00"),
            ),
        ),
        (
            "notes",
            lambda: _confirm(
                evidence_id=evidence_id,
                isolated_settings=isolated_settings,
                repository=repository,
                authority=invoice_authority,
                notes="corrected after checking the paper",
            ),
        ),
    )
    for field, confirm_correction in corrections:
        with pytest.raises(InvoiceValidationError) as refusal:
            confirm_correction()
        assert field in str(refusal.value)

    assert len(repository.load().invoices) == 1
