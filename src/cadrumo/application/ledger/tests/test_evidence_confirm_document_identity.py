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

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.invoices.errors import InvoiceValidationError
from ....domain.invoices.models import Invoice
from ....domain.iva.classification import InvoiceKind
from ..evidence_draft import (
    _INVOICE_FIELDS_A_CONFIRM_DOES_NOT_AUTHOR,
    InvoiceConfirmationResult,
    _fields_a_reconfirm_would_change,
    confirm_invoice_draft_from_evidence,
)
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import seeded_filer_profile as seeded_filer_profile
from ._ledger_value_fixtures import isolated_settings, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

# A structured document, so the reading lane is the deterministic Facturae
# parser: every re-read resolves the same figures, which is what makes a second
# confirm a statement about the SAME document rather than a different reading.
_FIXTURE = Path(__file__).parent / "_evidence_corpus" / "facturae_32_recargo_invoice.xml"


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
) -> InvoiceConfirmationResult:
    """Confirm the attached document, optionally restating what the operator saw."""
    return confirm_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_country="ES",
        evidence_id=evidence_id,
        settings=isolated_settings,
        invoice_repository=repository,
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

    first = _confirm(evidence_id=evidence_id, isolated_settings=isolated_settings, repository=repository)
    second = _confirm(evidence_id=evidence_id, isolated_settings=isolated_settings, repository=repository)

    assert first.created is True
    assert second.created is False
    assert second.invoice.invoice_id == first.invoice.invoice_id
    assert len(repository.load().invoices) == 1


def test_a_reconfirm_correcting_an_identity_field_refuses_instead_of_duplicating(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
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
    first = _confirm(evidence_id=evidence_id, isolated_settings=isolated_settings, repository=repository)

    with pytest.raises(InvoiceValidationError) as refusal:
        _confirm(
            evidence_id=evidence_id,
            isolated_settings=isolated_settings,
            repository=repository,
            invoice_number="CORRECTED-0001",
        )

    assert "invoice_number" in str(refusal.value)
    assert first.invoice.invoice_id in str(refusal.value)
    assert len(repository.load().invoices) == 1


def test_a_reconfirm_correcting_a_field_outside_the_hash_is_not_swallowed(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
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
    _confirm(evidence_id=first_evidence, isolated_settings=isolated_settings, repository=repository)

    with pytest.raises(InvoiceValidationError):
        _confirm(
            evidence_id=second_evidence,
            isolated_settings=isolated_settings,
            repository=repository,
            invoice_number="CORRECTED-0001",
        )

    assert len(repository.load().invoices) == 1


def test_the_match_covers_every_invoice_field_the_confirm_authors(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """No persisted field falls outside the comparison by omission.

    The contract's named subtle failure is a match over a SUBSET. The comparison
    is therefore derived from the model rather than hand-listed, and this proves
    the derivation covers the model: every field is either compared or named in
    the excluded set, and the excluded set names only fields a LATER verb owns.
    """
    evidence_id = _attach_the_document(
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    repository = InvoiceCatalogueRepository(objects=secure_objects)
    stored = _confirm(evidence_id=evidence_id, isolated_settings=isolated_settings, repository=repository).invoice

    compared: set[str] = set()
    for name in Invoice.model_fields:
        if name in _INVOICE_FIELDS_A_CONFIRM_DOES_NOT_AUTHOR:
            continue
        mutated = stored.model_copy(update={name: _a_different_value_for(stored, name)})
        if _fields_a_reconfirm_would_change(mutated, stored) == (name,):
            compared.add(name)

    uncovered = set(Invoice.model_fields) - compared - set(_INVOICE_FIELDS_A_CONFIRM_DOES_NOT_AUTHOR)
    assert uncovered == set(), f"persisted fields outside the match: {sorted(uncovered)}"
    assert set(Invoice.model_fields) >= _INVOICE_FIELDS_A_CONFIRM_DOES_NOT_AUTHOR


def _a_different_value_for(invoice: Invoice, name: str) -> object:
    """Return a value for *name* that differs from the one *invoice* carries.

    Built by perturbing the live value rather than by a per-field table, so a
    field added to the model needs no entry here and cannot quietly drop out of
    the coverage proof above.
    """
    current = getattr(invoice, name)
    if current is None:
        return "differs"
    if isinstance(current, bool):
        return not current
    if isinstance(current, Decimal):
        return current + Decimal("1")
    if isinstance(current, tuple):
        return (*current, "differs")
    if isinstance(current, str):
        return f"{current}-differs"
    return None
