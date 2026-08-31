"""Purchase invoice evidence secure-storage and error-path tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ..evidence import PurchaseInvoiceEvidencePatch
from ..evidence_errors import PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceNotFoundError
from ..preconditions import LedgerPreconditionCondition
from ._evidence_test_support import _BUCKET_ID, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._ledger_value_fixtures import isolated_settings, pdf_file, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "pdf_file", "runtime_profile", "secure_objects"]


class TestEvidenceSecureStorage:
    def test_purchase_invoice_evidence_persists_in_secure_object_store(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        pdf_file: Path,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)

        result = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_file, supplier="Acme S.L.")
        records = svc.list_all(bucket_id=_BUCKET_ID)

        assert records == (result.record,)
        raw_records = tuple(secure_objects.iter_all_records_raw())
        assert any(row.namespace == "cadrumo.application.ledger.purchase_invoice_evidence" for row in raw_records)


class TestEvidenceErrorPaths:
    def test_add_rejects_missing_file(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)
        with pytest.raises(PurchaseInvoiceEvidenceInputError) as exc_info:
            svc.add(bucket_id=_BUCKET_ID, source_path=tmp_path / "ghost.pdf")
        assert exc_info.value.terminal_precondition_verdict is not None
        assert exc_info.value.terminal_precondition_verdict.failed_condition_id == (
            LedgerPreconditionCondition.EVIDENCE_FILE_READABLE.value
        )

    def test_add_rejects_unsupported_extension(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        txt_file = tmp_path / "note.txt"
        txt_file.write_text("hello")
        svc = _make_svc(isolated_settings, secure_objects)
        with pytest.raises(PurchaseInvoiceEvidenceInputError) as exc_info:
            svc.add(bucket_id=_BUCKET_ID, source_path=txt_file)

        # Both evidence-input refusals now share one translated key, so the key
        # alone no longer tells the two apart -- an unreadable file would satisfy
        # it just as well. The failed condition is what still discriminates.
        assert exc_info.value.translated_message == "errors.refused.refused_ledger_evidence_input"
        assert exc_info.value.terminal_precondition_verdict is not None
        assert exc_info.value.terminal_precondition_verdict.failed_condition_id == (
            LedgerPreconditionCondition.EVIDENCE_FILE_EXTENSION_SUPPORTED.value
        )

    def test_update_raises_on_missing_id(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)
        with pytest.raises(PurchaseInvoiceEvidenceNotFoundError):
            svc.update(
                bucket_id=_BUCKET_ID,
                evidence_id="doesnotexist",
                patch=PurchaseInvoiceEvidencePatch(notes="x"),
            )

    def test_remove_raises_on_missing_id(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)
        with pytest.raises(PurchaseInvoiceEvidenceNotFoundError):
            svc.remove(bucket_id=_BUCKET_ID, evidence_id="doesnotexist")
