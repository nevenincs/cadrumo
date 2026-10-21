"""Ledger reads use real encrypted catalogues without constructing write services."""

from __future__ import annotations

import cProfile
from pathlib import Path

import pytest

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.ledger.history_query import LedgerHistoryQuery, read_ledger_history
from ...application.ledger.list_query import LedgerTransactionListQuery, query_ledger_transaction_list
from ...application.review.filter import LedgerReviewFilterSpec
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..ledger_action_composition import compose_ledger_read_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET = "33333333-3333-4333-8333-333333333333"


def test_read_composition_and_history_reuse_real_encrypted_catalogue(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """Observe real calls: no evidence hydration and no second transaction load."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET):
        profile = cProfile.Profile()
        with profile:
            ports = compose_ledger_read_ports(bucket_id=_BUCKET, operation=authority_operation)
            catalogue = ports.transaction_repository.load()
            history = read_ledger_history(
                LedgerHistoryQuery(transaction_id="a" * 64),
                bucket_id=_BUCKET,
                transaction_repository=ports.transaction_repository,
                bucket_event_repository=ports.bucket_event_repository,
                transaction_catalogue=catalogue,
            )
        calls = profile.getstats()
        assert sum(row.callcount for row in calls if row.code is TransactionCatalogueRepository.load.__code__) == 1
        forbidden = {
            "load_usage_ratios",
            "build_ledger_evidence_ports",
            "bind_calculation_revision_persistence_from_profile",
        }
        assert not any(not isinstance(row.code, str) and row.code.co_name in forbidden for row in calls)
        assert history.bucket_id == _BUCKET
        assert history.object_ids == ("a" * 64,)
        assert history.events == ()
        page = query_ledger_transaction_list(
            LedgerTransactionListQuery(spec=LedgerReviewFilterSpec.from_strings(())),
            bucket_id=_BUCKET,
            ports=ports,
        )
        assert page.total == 0
        assert page.results == ()
