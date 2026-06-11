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


_BUCKET_ID = "bucket-maintenance-browse-test"


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label="Browse target",
    ) as profile:
        yield profile


def _write_object(runtime: TestRuntimeProfile, namespace: str, object_key: str) -> None:
    now = datetime.now(UTC)
    envelope = Envelope[UserProfileFact](
        schema_version=1,
        written_at=now,
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
                written_at=now,
                payload=envelope.model_dump_json().encode("utf-8"),
            ),
        ),
    )


# Use already-registered domain namespaces so the registry-validated
# repository accepts the writes without ad-hoc namespace registration.
_EVENT_HISTORY_NAMESPACE = "aeat.domain.buckets.event_history"
_INVOICE_NAMESPACE = "aeat.domain.invoices"


def test_browse_returns_one_row_per_namespace_with_counts(runtime: TestRuntimeProfile) -> None:
    """Namespace inventory returns each populated namespace with its row count."""
    _write_object(runtime, namespace=_EVENT_HISTORY_NAMESPACE, object_key="key-a1")
    _write_object(runtime, namespace=_EVENT_HISTORY_NAMESPACE, object_key="key-a2")
    _write_object(runtime, namespace=_INVOICE_NAMESPACE, object_key="key-b1")

    result = BucketMaintenanceService().browse(BrowseBucketCommand(bucket_id=runtime.bucket_id))

    row_by_ns = {row.namespace: row.row_count for row in result.rows}
    assert row_by_ns.get(_EVENT_HISTORY_NAMESPACE) == 2
    assert row_by_ns.get(_INVOICE_NAMESPACE) == 1


def test_browse_namespace_filter_restricts_returned_rows(runtime: TestRuntimeProfile) -> None:
    """The substring filter limits the inventory to matching namespaces only."""
    _write_object(runtime, namespace=_EVENT_HISTORY_NAMESPACE, object_key="key-a1")
    _write_object(runtime, namespace=_INVOICE_NAMESPACE, object_key="key-b1")

    result = BucketMaintenanceService().browse(
        BrowseBucketCommand(bucket_id=runtime.bucket_id, namespace_filter="buckets"),
    )

    returned_namespaces = {row.namespace for row in result.rows}
    assert _EVENT_HISTORY_NAMESPACE in returned_namespaces
    assert _INVOICE_NAMESPACE not in returned_namespaces


def test_browse_on_empty_bucket_returns_empty_rows(runtime: TestRuntimeProfile) -> None:
    """A bucket with no secure-object writes yields an empty inventory."""
    result = BucketMaintenanceService().browse(BrowseBucketCommand(bucket_id=runtime.bucket_id))

    assert result.bucket_id == runtime.bucket_id
    assert result.rows == ()
