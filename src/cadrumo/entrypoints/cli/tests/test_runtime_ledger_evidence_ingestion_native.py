"""Exact-profile worker acceptance for the evidence batch."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import cast

import pytest
from click.testing import Result

from ....adapters.persistence.profile.extraction_drafts import ExtractionDraftRepository
from ....adapters.persistence.profile.purchase_invoice_evidence import PurchaseInvoiceEvidenceRepository
from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....application.ledger.evidence_ingestion_contracts import LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID
from ....core.config import load_settings
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import unwrap_cli_result
from .cli_runner import invoke_cached_cli
from .native_api_cli_support import NativeApiCliSession
from .test_runtime_invoice_add import native_invoice_runtime_session, password_profile_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_CORPUS = Path(__file__).parents[3] / "application" / "ledger" / "tests" / "_evidence_corpus"
_STRUCTURED_INVOICE = "facturae_32_series_and_parties_invoice.xml"
_PROFILE_OPERATIONS = frozenset({LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID})


def _invoke(
    session: NativeApiCliSession[None],
    *command: str,
    output_format: str = "json",
) -> Result:
    """Invoke one protected-stdin command with the enrolled profile secret."""
    close_active_bucket_session()
    result = invoke_cached_cli(
        (
            "--language",
            "en",
            "--format",
            output_format,
            "--profile",
            session.profile_label,
            "--profile-secrets-stdin",
            *command,
        ),
        input=json.dumps({"profile_passphrase": PROFILE_INPUT}),
    )
    assert PROFILE_INPUT not in result.output
    return result


def _result_rows(result: Result) -> list[dict[str, object]]:
    payload = unwrap_cli_result(result)
    rows = payload["items"]
    assert isinstance(rows, list)
    return [cast(dict[str, object], row) for row in rows]


def test_native_evidence_ingestion_uses_exact_profile_and_preserves_batch_and_refusal_facts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Commit a structured batch once, resume it, and keep each document's refusal facts."""
    caller = tmp_path / "caller"
    storage_root = (tmp_path / "cadrumo-storage").resolve()
    assert caller.resolve() != storage_root
    assert storage_root not in caller.resolve().parents
    invoice_directory = caller / "invoices"
    invoice_directory.mkdir(parents=True)
    invoice_path = invoice_directory / _STRUCTURED_INVOICE
    shutil.copyfile(_CORPUS / _STRUCTURED_INVOICE, invoice_path)
    invoice_bytes = invoice_path.read_bytes()
    invoice_digest = hashlib.sha256(invoice_bytes).hexdigest()
    monkeypatch.chdir(caller)

    with native_invoice_runtime_session(
        tmp_path,
        operation_ids=_PROFILE_OPERATIONS,
        profile_value_operation_ids=_PROFILE_OPERATIONS,
        authority_operation=authority_operation,
    ) as session:
        empty = _invoke(session, "app", "ledger", "evidence", "batch", "--kind", "received")
        assert empty.exit_code != 0, "a batch without a source must refuse instead of returning an empty success"

        first = _invoke(session, "app", "ledger", "evidence", "batch", "invoices", "--kind", "received")
        assert first.exit_code == 0, first.output
        first_rows = _result_rows(first)
        assert len(first_rows) == 1
        first_row = first_rows[0]
        assert first_row["source_name"] == _STRUCTURED_INVOICE
        assert first_row["content_address"] == invoice_digest
        assert first_row["status"] in {"ingested", "pending_review"}

        bucket_id = str(session.profile_id)
        with password_profile_session(session.profile_id, authority_operation):
            attachment_store = AttachmentStore(bucket_id=bucket_id)
            manifest = attachment_store.load_manifest(invoice_digest)
            assert manifest.bucket_id == bucket_id
            assert attachment_store.read_bytes(invoice_digest) == invoice_bytes

            objects = secure_object_repository_for_active_bucket()
            evidence = PurchaseInvoiceEvidenceRepository(objects=objects).load(bucket_id)
            assert evidence is not None
            matching = tuple(row for row in evidence.records if row.source_sha256 == invoice_digest)
            assert len(matching) == 1
            assert Path(matching[0].source_path) == Path("invoices") / _STRUCTURED_INVOICE
            drafts = ExtractionDraftRepository(bucket_id=bucket_id, settings=load_settings()).load(bucket_id)
            assert drafts is not None and len(drafts.drafts) == 1
            assert drafts.drafts[0].evidence_reference == matching[0].evidence_id
            assert drafts.drafts[0].draft.supplier_tax_id is not None

        replay = _invoke(session, "app", "ledger", "evidence", "batch", "invoices", "--kind", "received")
        assert replay.exit_code == 0, replay.output
        replay_rows = _result_rows(replay)
        assert len(replay_rows) == 1
        assert replay_rows[0]["identity"] == first_row["identity"]
        assert replay_rows[0]["status"] == "no_op"

        malformed = invoice_directory / "malformed.pdf"
        malformed.write_bytes(b"not a PDF document")
        mixed = _invoke(
            session,
            "app",
            "ledger",
            "evidence",
            "batch",
            "--kind",
            "received",
            "--file",
            f"invoices/{_STRUCTURED_INVOICE}",
            "--file",
            "invoices/malformed.pdf",
        )
        assert mixed.exit_code == 1, mixed.output
        mixed_rows = {str(row["source_name"]): row for row in _result_rows(mixed)}
        assert mixed_rows[_STRUCTURED_INVOICE]["status"] == "no_op"
        assert mixed_rows["malformed.pdf"]["status"] == "refused"
        assert mixed_rows["malformed.pdf"]["refusal_facts"]
        assert mixed_rows["malformed.pdf"]["refusal_action"]
        mixed_envelope = json.loads(mixed.output)
        assert isinstance(mixed_envelope, dict)
        notices = mixed_envelope["notices"]
        assert isinstance(notices, list)
        assert all(not str(notice["code"]).startswith("ledger.evidence.batch.item.") for notice in notices)

        text = _invoke(
            session,
            "app",
            "ledger",
            "evidence",
            "batch",
            "--kind",
            "received",
            "--file",
            f"invoices/{_STRUCTURED_INVOICE}",
            "--file",
            "invoices/malformed.pdf",
            output_format="text",
        )
        assert text.exit_code == 1, text.output
        progress = [line for line in text.output.splitlines() if "ledger.evidence.batch.item." in line]
        assert len(progress) == 2, f"expected one progress line per document, got: {progress}"
        assert any("ledger.evidence.batch.item.refused" in line for line in progress)
        assert any("ledger.evidence.batch.items_refused" in line for line in text.output.splitlines())
