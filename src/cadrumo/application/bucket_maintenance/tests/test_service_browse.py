"""Service-contract tests for ``BucketMaintenanceService.browse``.

Exercises the namespace-inventory composition against a real
secure-object repository. The test bootstraps a bucket, writes a
small set of secure objects across two namespaces, and asserts the
service returns one inventory row per namespace with the correct
row count. A substring-filter case pins the ``namespace_filter``
behaviour. Read-only verb: no bucket event is asserted.

Authority: workflow-composition contract, ``browse`` verb: namespace-level
inventory only; key-level browse with ``SensitivityClass`` redaction remains
outside this contract.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage import (
    Envelope,
    SecureObjectWrite,
    SensitivityClass,
)
from ....domain.user_profile import UserProfileFact
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .. import BrowseBucketCommand, BucketMaintenanceService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_BUCKET_ID = "1f6b0000-0000-4000-8000-000000000b0b"
_OBJECT_WRITTEN_AT = datetime(2026, 5, 28, 11, 30, 0, tzinfo=UTC)


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label="Browse target",
    ) as profile:
        yield profile


def _write_object(runtime: TestRuntimeProfile, namespace: str, object_key: str) -> None:
    envelope = Envelope[UserProfileFact](
        schema_version=1,
        written_at=_OBJECT_WRITTEN_AT,
        classification=SensitivityClass.FINANCIAL,
        payload=UserProfileFact(path="placeholder.key", value="x"),
    )
    runtime.repository.save_many(
        (
            SecureObjectWrite(
                namespace=namespace,
                object_key=object_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=_OBJECT_WRITTEN_AT,
                payload=envelope.model_dump_json().encode("utf-8"),
            ),
        ),
    )


# Use already-registered domain namespaces so the registry-validated
# repository accepts the writes without ad-hoc namespace registration.
# Both declare a templated (multi-key) object_key_grammar -- unlike a
# "catalogue"/"state" singleton namespace, which admits only its one
# declared literal key and so cannot hold the multiple distinct rows
# these tests need to prove per-namespace counting.
_PURCHASE_INVOICE_EVIDENCE_NAMESPACE = "cadrumo.application.ledger.purchase_invoice_evidence"
_FILING_DRAFTS_NAMESPACE = "cadrumo.domain.filing.drafts"


def test_browse_returns_one_row_per_namespace_with_counts(runtime: TestRuntimeProfile) -> None:
    """Namespace inventory returns each populated namespace with its row count."""
    _write_object(runtime, namespace=_PURCHASE_INVOICE_EVIDENCE_NAMESPACE, object_key="key-a1")
    _write_object(runtime, namespace=_PURCHASE_INVOICE_EVIDENCE_NAMESPACE, object_key="key-a2")
    _write_object(runtime, namespace=_FILING_DRAFTS_NAMESPACE, object_key="key-b1")

    result = BucketMaintenanceService().browse(BrowseBucketCommand(bucket_id=runtime.bucket_id))

    row_by_ns = {row.namespace: row.row_count for row in result.rows}
    assert row_by_ns.get(_PURCHASE_INVOICE_EVIDENCE_NAMESPACE) == 2
    assert row_by_ns.get(_FILING_DRAFTS_NAMESPACE) == 1


def test_browse_namespace_filter_restricts_returned_rows(runtime: TestRuntimeProfile) -> None:
    """The substring filter limits the inventory to matching namespaces only."""
    _write_object(runtime, namespace=_PURCHASE_INVOICE_EVIDENCE_NAMESPACE, object_key="key-a1")
    _write_object(runtime, namespace=_FILING_DRAFTS_NAMESPACE, object_key="key-b1")

    result = BucketMaintenanceService().browse(
        BrowseBucketCommand(bucket_id=runtime.bucket_id, namespace_filter="purchase_invoice"),
    )

    returned_namespaces = {row.namespace for row in result.rows}
    assert _PURCHASE_INVOICE_EVIDENCE_NAMESPACE in returned_namespaces
    assert _FILING_DRAFTS_NAMESPACE not in returned_namespaces


def test_browse_on_empty_bucket_returns_empty_rows(runtime: TestRuntimeProfile) -> None:
    """A bucket with no writes beyond the profile record shows only that record.

    The provisioning door publishes the capsule AND writes the profile record
    as a secure-object row, so a freshly provisioned bucket is never empty;
    the browse inventory must show exactly the record row and nothing else.
    """
    result = BucketMaintenanceService().browse(BrowseBucketCommand(bucket_id=runtime.bucket_id))

    assert result.bucket_id == runtime.bucket_id
    assert [row.namespace for row in result.rows] == [
        "cadrumo.application.user_profile.value",
        "cadrumo.domain.buckets.event_history",
    ]
