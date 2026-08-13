"""Facturae's declared class reaches confirmation without losing its meaning."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import DraftDiscrepancyKind, FindingResolutionAction
from ....core.config import Settings
from ....domain.invoices import InvoiceClass
from ....domain.iva import InvoiceKind
from .. import (
    FindingResolution,
    confirm_invoice_draft_from_evidence,
    confirmation_blockers,
    extract_invoice_draft_from_evidence,
)
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import isolated_settings as isolated_settings
from ._evidence_test_support import runtime_profile as runtime_profile
from ._evidence_test_support import secure_objects as secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects"]

_CORPUS = Path(__file__).parent / "_evidence_corpus"
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


def _resolutions(*, evidence_id: str, isolated_settings: Settings) -> tuple[FindingResolution, ...]:
    draft = extract_invoice_draft_from_evidence(
        bucket_id=_BUCKET_ID,
        evidence_id=evidence_id,
        settings=isolated_settings,
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
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
        resolutions=_resolutions(evidence_id=evidence_id, isolated_settings=isolated_settings),
    )


def test_the_existing_oo_corpus_record_confirms_as_ordinary(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    result = _confirm(
        _OO.read_bytes(),
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )

    assert result.invoice.invoice_class is InvoiceClass.ORDINARIA


def test_the_existing_or_corpus_record_confirms_as_corrective(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    result = _confirm(
        _OR.read_bytes(),
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )

    assert result.invoice.invoice_class is InvoiceClass.RECTIFICATIVA
    assert result.invoice.rectifies_invoice_number == "0028"


def test_a_record_declaring_no_class_keeps_the_corrective_reference_fallback(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    data = _OR.read_bytes().replace(b"<InvoiceClass>OR</InvoiceClass>", b"")
    assert data != _OR.read_bytes()

    result = _confirm(
        data,
        isolated_settings=isolated_settings,
        secure_objects=secure_objects,
        tmp_path=tmp_path,
    )

    assert result.invoice.invoice_class is InvoiceClass.RECTIFICATIVA


def test_a_declared_ordinary_class_does_not_silently_take_the_corrective_inference(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
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
    )

    assert DraftDiscrepancyKind.INVOICE_CLASS_CONTRADICTED in {finding.kind for finding in draft.discrepancies}
    with pytest.raises(ValidationError, match="only applies to a factura rectificativa"):
        confirm_invoice_draft_from_evidence(
            bucket_id=_BUCKET_ID,
            kind=InvoiceKind.RECEIVED,
            counterparty_country="ES",
            evidence_id=evidence_id,
            settings=isolated_settings,
            invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
            resolutions=_resolutions(evidence_id=evidence_id, isolated_settings=isolated_settings),
        )
