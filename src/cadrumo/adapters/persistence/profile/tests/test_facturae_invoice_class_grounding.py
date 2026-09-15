"""Facturae's declared class reaches confirmation without losing its meaning."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.confirmation_gate import FindingResolution, confirmation_blockers
from cadrumo.application.ledger.invoice_confirmation import confirm_invoice_draft_from_evidence
from cadrumo.application.ledger.invoice_draft_extraction import extract_invoice_draft_from_evidence
from cadrumo.core.config import Settings
from cadrumo.core.confirmation_gate import FindingResolutionAction
from cadrumo.core.draft_discrepancy import DraftDiscrepancyKind
from cadrumo.domain.invoices.enums import InvoiceClass
from cadrumo.domain.iva.classification import InvoiceKind

from ._invoice_confirmation_test_support import (
    _BUCKET_ID,
    _EVIDENCE_CORPUS,
    InvoiceAuthorityFixture,
    _make_svc,
    invoice_confirmation_kwargs,
    invoice_draft_extraction_kwargs,
    isolated_settings,
    secure_objects,
)
from ._invoice_confirmation_test_support import runtime_profile as runtime_profile
from ._invoice_confirmation_test_support import seeded_filer_profile as seeded_filer_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects", "seeded_filer_profile"]

_CORPUS = _EVIDENCE_CORPUS
_OO = _CORPUS / "facturae_32_recargo_invoice.xml"
_OR = _CORPUS / "facturae_32_series_and_parties_invoice.xml"


def _store(
    data: bytes,
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> str:
    source = tmp_path / "invoice.xml"
    source.write_bytes(data)
    return _make_svc(isolated_settings, secure_objects).add(bucket_id=_BUCKET_ID, source_path=source).record.evidence_id


def _resolutions(
    *,
    evidence_id: str,
    isolated_settings: Settings,
    authority: InvoiceAuthorityFixture,
) -> tuple[FindingResolution, ...]:
    draft = extract_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        evidence_id=evidence_id,
        settings=isolated_settings,
        **invoice_draft_extraction_kwargs(bucket_id=_BUCKET_ID, authority=authority),
    )
    return tuple(
        FindingResolution(
            blocker_id=blocker.blocker_id,
            action=FindingResolutionAction.ATTEST,
            note="reviewed against the committed Facturae corpus specimen",
        )
        for blocker in confirmation_blockers(draft)
    )


def _confirm(
    data: bytes,
    *,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_class: InvoiceClass | None = None,
    authority: InvoiceAuthorityFixture,
):
    evidence_id = _store(
        data,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    return confirm_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_country="ES",
        evidence_id=evidence_id,
        settings=isolated_settings,
        **invoice_confirmation_kwargs(bucket_id=_BUCKET_ID, authority=authority),
        resolutions=_resolutions(
            evidence_id=evidence_id,
            isolated_settings=isolated_settings,
            authority=authority,
        ),
        invoice_class=invoice_class,
    )


def _with_declared_class(data: bytes, *, current: bytes, replacement: bytes) -> bytes:
    anchor = b"<InvoiceClass>" + current + b"</InvoiceClass>"
    assert data.count(anchor) == 1
    return data.replace(anchor, b"<InvoiceClass>" + replacement + b"</InvoiceClass>")


def _without_corrective_reference(data: bytes) -> bytes:
    start = data.index(b"        <Corrective>")
    end = data.index(b"        </Corrective>", start) + len(b"        </Corrective>\n")
    return data[:start] + data[end:]


def test_the_existing_oo_corpus_record_confirms_as_ordinary(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    result = _confirm(
        _OO.read_bytes(),
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        authority=invoice_authority,
    )

    assert result.invoice.invoice_class is InvoiceClass.from_registry("ORDINARIA")


def test_the_existing_or_corpus_record_confirms_as_corrective(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    result = _confirm(
        _OR.read_bytes(),
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        authority=invoice_authority,
    )

    assert result.invoice.invoice_class is InvoiceClass.from_registry("RECTIFICATIVA")
    assert result.invoice.rectifies_invoice_number == "0028"


def test_a_record_declaring_no_class_keeps_the_corrective_reference_fallback(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    data = _OR.read_bytes().replace(b"<InvoiceClass>OR</InvoiceClass>", b"")
    assert data != _OR.read_bytes()

    result = _confirm(
        data,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        authority=invoice_authority,
    )

    assert result.invoice.invoice_class is InvoiceClass.from_registry("RECTIFICATIVA")


def test_a_declared_ordinary_class_does_not_silently_take_the_corrective_inference(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    data = _OR.read_bytes().replace(b"<InvoiceClass>OR</InvoiceClass>", b"<InvoiceClass>OO</InvoiceClass>")
    evidence_id = _store(
        data,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    draft = extract_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        evidence_id=evidence_id,
        settings=isolated_settings,
        **invoice_draft_extraction_kwargs(bucket_id=_BUCKET_ID, authority=invoice_authority),
    )

    assert DraftDiscrepancyKind.INVOICE_CLASS_CONTRADICTED in {finding.kind for finding in draft.discrepancies}
    with pytest.raises(ValidationError, match="only applies to a factura rectificativa"):
        confirm_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            counterparty_country="ES",
            evidence_id=evidence_id,
            settings=isolated_settings,
            **invoice_confirmation_kwargs(bucket_id=_BUCKET_ID, authority=invoice_authority),
            resolutions=_resolutions(
                evidence_id=evidence_id,
                isolated_settings=isolated_settings,
                authority=invoice_authority,
            ),
        )


def test_the_copy_of_an_ordinary_invoice_keeps_the_ordinary_domain_class(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    data = _with_declared_class(_OO.read_bytes(), current=b"OO", replacement=b"CO")

    result = _confirm(
        data,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        authority=invoice_authority,
    )

    assert result.invoice.invoice_class is InvoiceClass.from_registry("ORDINARIA")


def test_the_copy_of_a_corrective_invoice_keeps_the_corrective_domain_class(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    data = _with_declared_class(_OR.read_bytes(), current=b"OR", replacement=b"CR")

    result = _confirm(
        data,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
        authority=invoice_authority,
    )

    assert result.invoice.invoice_class is InvoiceClass.from_registry("RECTIFICATIVA")
    assert result.invoice.rectifies_invoice_number == "0028"


@pytest.mark.parametrize("declared", [b"OC", b"CC"])
def test_a_summary_declaration_is_reported_without_overwriting_the_operator_class(
    declared: bytes,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    data = _with_declared_class(_OO.read_bytes(), current=b"OO", replacement=declared)
    evidence_id = _store(
        data,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    draft = extract_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        evidence_id=evidence_id,
        settings=isolated_settings,
        **invoice_draft_extraction_kwargs(bucket_id=_BUCKET_ID, authority=invoice_authority),
    )

    assert DraftDiscrepancyKind.INVOICE_CLASS_UNMODELLED in {finding.kind for finding in draft.discrepancies}
    result = confirm_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_country="ES",
        evidence_id=evidence_id,
        settings=isolated_settings,
        **invoice_confirmation_kwargs(bucket_id=_BUCKET_ID, authority=invoice_authority),
        resolutions=_resolutions(
            evidence_id=evidence_id,
            isolated_settings=isolated_settings,
            authority=invoice_authority,
        ),
        invoice_class=InvoiceClass.from_registry("SIMPLIFICADA"),
    )

    assert result.invoice.invoice_class is InvoiceClass.from_registry("SIMPLIFICADA")


@pytest.mark.parametrize("declared", [b"OR", b"CR"])
def test_a_corrective_declaration_without_a_corrective_reference_is_contradicted(
    declared: bytes,
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
    invoice_authority: InvoiceAuthorityFixture,
) -> None:
    data = _without_corrective_reference(_OR.read_bytes())
    data = _with_declared_class(data, current=b"OR", replacement=declared)
    evidence_id = _store(
        data,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )
    draft = extract_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        evidence_id=evidence_id,
        settings=isolated_settings,
        **invoice_draft_extraction_kwargs(bucket_id=_BUCKET_ID, authority=invoice_authority),
    )

    assert DraftDiscrepancyKind.INVOICE_CLASS_CONTRADICTED in {finding.kind for finding in draft.discrepancies}
