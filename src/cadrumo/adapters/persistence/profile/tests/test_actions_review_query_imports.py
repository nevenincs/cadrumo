"""Ledger review-row import and diagnostic query tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.inbound.financial.ledger_import import build_ledger_import_ports
from cadrumo.adapters.persistence.profile.tests.ledger_action_create_support import ledger_ports_for_test
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.actions_import import import_ledger_source
from cadrumo.application.ledger.actions_manual import query_ledger_review_rows
from cadrumo.application.ledger.models import LedgerReviewQuery, LedgerSourceImportCommand
from cadrumo.core.period import Period
from cadrumo.domain.buckets.event import BucketEventType

from .ledger_action_persistence_support import (
    _BUCKET_ID,
    _repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
def test_query_ledger_review_rows_filters_quarter_import_and_issue_events(
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    transaction_repository, event_repository = _repositories(secure_objects, bucket_id=_BUCKET_ID)
    statement = tmp_path / "bank.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n"
        "2026-06-16,SaaS Vendor,Subscription,-48.40,EUR,n26-002\n",
        encoding="utf-8",
    )

    import_ports = build_ledger_import_ports()
    first_import = import_ledger_source(
        LedgerSourceImportCommand(
            bucket_id=_BUCKET_ID,
            path=statement,
            provider="csv",
            verify=True,
            source=statement,
            actor="operator-A",
        ),
        ports=import_ports,
    )
    duplicate_import = import_ledger_source(
        LedgerSourceImportCommand(
            bucket_id=_BUCKET_ID,
            path=statement,
            provider="csv",
            verify=True,
            actor="operator-A",
        ),
        ports=import_ports,
    )

    assert first_import.import_batch_id is not None
    assert duplicate_import.import_batch_id is not None
    assert first_import.imported == 2
    assert duplicate_import.skipped == 2
    assert {diagnostic.kind for diagnostic in duplicate_import.diagnostics} == {"duplicate", "gap"}
    assert BucketEventType.LEDGER_IMPORT_DIAGNOSTIC_RECORDED in {
        event.event_type for event in event_repository.load().for_bucket(_BUCKET_ID)
    }

    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        quarter_rows = query_ledger_review_rows(
            LedgerReviewQuery(bucket_id=_BUCKET_ID, period=Period.from_year_and_code(2026, "2T")),
            ports=ports,
        )
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        imported_rows = query_ledger_review_rows(
            LedgerReviewQuery(bucket_id=_BUCKET_ID, import_id=first_import.import_batch_id),
            ports=ports,
        )
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        duplicate_rows = query_ledger_review_rows(
            LedgerReviewQuery(bucket_id=_BUCKET_ID, issue="duplicate", import_id=duplicate_import.import_batch_id),
            ports=ports,
        )
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        gap_rows = query_ledger_review_rows(
            LedgerReviewQuery(bucket_id=_BUCKET_ID, issue="gap", import_id=first_import.import_batch_id),
            ports=ports,
        )

    assert [row.description for row in quarter_rows.rows] == ["Invoice 1", "Subscription"]
    assert [row.description for row in imported_rows.rows] == ["Invoice 1", "Subscription"]
    assert [row.description for row in duplicate_rows.rows] == ["Invoice 1", "Subscription"]
    assert [row.description for row in gap_rows.rows] == ["Invoice 1", "Subscription"]
    assert duplicate_rows.filters == (
        "issue=duplicate",
        f"import={duplicate_import.import_batch_id}",
    )
