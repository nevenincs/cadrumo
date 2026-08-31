"""Contract parity between ledger status/import application results and their CLI shells.

``LedgerStatusResult`` and ``LedgerImportPayload`` (plus its nested
``LedgerImportTransactionRefPayload`` / ``LedgerImportDiagnosticPayload``
rows) must refuse the malformed bucket identity, ref, diagnostic, and
count shapes the canonical ``LedgerStatusReport`` / ``LedgerSourceImportResult``
/ ``BucketTransactionRef`` / ``LedgerImportDiagnosticReport`` models already
refuse.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._ledger_payloads import (
    LedgerImportDiagnosticPayload,
    LedgerImportPayload,
    LedgerImportSourcePayload,
    LedgerImportTransactionRefPayload,
    LedgerImportValidationPayload,
    LedgerStatusResult,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _status_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "bucket_id": "bucket-1",
        "total_count": 3,
        "active_count": 2,
        "archived_count": 1,
        "stashed_count": 0,
        "pending_review_count": 1,
        "reviewed_count": 2,
        "skipped_count": 0,
    }
    base.update(overrides)
    return base


def test_status_result_accepts_a_real_projection() -> None:
    """A genuine status projection validates cleanly."""
    result = LedgerStatusResult.model_validate(_status_kwargs())

    assert result.bucket_id == "bucket-1"


def test_status_result_rejects_a_blank_bucket_id() -> None:
    """A blank bucket id is refused, matching the canonical ``BucketId`` constraint."""
    with pytest.raises(ValidationError):
        LedgerStatusResult.model_validate(_status_kwargs(bucket_id=""))


@pytest.mark.parametrize(
    "field",
    [
        "total_count",
        "active_count",
        "archived_count",
        "stashed_count",
        "pending_review_count",
        "reviewed_count",
        "skipped_count",
    ],
)
def test_status_result_rejects_a_negative_count(field: str) -> None:
    """Every status count must stay non-negative, matching ``LedgerStatusReport``."""
    with pytest.raises(ValidationError):
        LedgerStatusResult.model_validate(_status_kwargs(**{field: -1}))


def _import_ref(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {"bucket_id": "bucket-1", "transaction_id": "a" * 64}
    base.update(overrides)
    return base


def test_import_transaction_ref_rejects_a_blank_bucket_id() -> None:
    """A blank bucket id on a nested import ref is refused."""
    with pytest.raises(ValidationError):
        LedgerImportTransactionRefPayload.model_validate(_import_ref(bucket_id=""))


def test_import_transaction_ref_rejects_a_malformed_transaction_id() -> None:
    """A malformed transaction id on a nested import ref is refused."""
    with pytest.raises(ValidationError):
        LedgerImportTransactionRefPayload.model_validate(_import_ref(transaction_id="not-a-valid-id"))


def test_import_transaction_ref_accepts_a_real_ref() -> None:
    """A genuine bucket-qualified ref round-trips cleanly."""
    ref = LedgerImportTransactionRefPayload.model_validate(_import_ref())

    assert ref.transaction_id == "a" * 64


def test_import_diagnostic_rejects_a_blank_message() -> None:
    """A blank diagnostic message is refused, matching ``LedgerImportDiagnosticReport``."""
    with pytest.raises(ValidationError):
        LedgerImportDiagnosticPayload(kind="warning", severity="info", message="")


def test_import_diagnostic_accepts_a_real_row() -> None:
    """A genuine diagnostic row round-trips cleanly."""
    diagnostic = LedgerImportDiagnosticPayload(kind="duplicate", severity="info", message="likely duplicate row")

    assert diagnostic.kind == "duplicate"


def _import_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "rows": 5,
        "imported": 3,
        "skipped": 2,
        "dry_run": False,
        "verify": False,
        "bucket_id": "bucket-1",
        # Lists: a directory import folds one report per file, and the fold used
        # to keep only the first.
        "validations": [LedgerImportValidationPayload(valid=True)],
        "sources": [LedgerImportSourcePayload(requested=False)],
    }
    base.update(overrides)
    return base


def test_import_payload_accepts_a_real_projection() -> None:
    """A genuine import result projects and validates cleanly."""
    result = LedgerImportPayload.model_validate(_import_kwargs())

    assert result.bucket_id == "bucket-1"


def test_import_payload_rejects_a_blank_bucket_id() -> None:
    """A blank bucket id on the import envelope is refused."""
    with pytest.raises(ValidationError):
        LedgerImportPayload.model_validate(_import_kwargs(bucket_id=""))


@pytest.mark.parametrize("field", ["rows", "imported", "skipped", "likely_duplicates"])
def test_import_payload_rejects_a_negative_count(field: str) -> None:
    """Every import count must stay non-negative, matching ``LedgerSourceImportResult``."""
    with pytest.raises(ValidationError):
        LedgerImportPayload.model_validate(_import_kwargs(**{field: -1}))


def test_import_payload_rejects_a_malformed_nested_ref() -> None:
    """A malformed nested imported-transaction ref is refused."""
    with pytest.raises(ValidationError):
        LedgerImportPayload.model_validate(
            _import_kwargs(imported_transaction_refs=[{"bucket_id": "", "transaction_id": "t" * 64}]),
        )
