"""Real-behavior tests for the review-queue confidence-below filter.

Exercises the full projection -> aggregator -> adapter -> encrypted
repository path: transactions are persisted at varying
``classification_confidence`` and the projection is asked to surface
only the rows whose confidence sits strictly below a threshold.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core.config import Settings
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....tests.profile_capsule import open_test_profile_session
from ....tests.user_profile import register_minimal_profile
from ..enums import ReviewState
from ..operator import project_review_queue

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "23232323-2323-4232-8232-232323232323"


def _build_settings(tmp_path: Path) -> Settings:
    return Settings(
        cadrumo_financial_txs_dir=tmp_path / "transactions",
        cadrumo_invoices_dir=tmp_path / "invoices",
        cadrumo_attachments_dir=tmp_path / "attachments",
        cadrumo_drafts_dir=tmp_path / "probe-drafts",
    )


def _raw(*, source_row_index: int) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=f"prov-{source_row_index}",
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=Decimal("12.34"),
        currency="EUR",
        counterparty=None,
        description=f"Row {source_row_index}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=source_row_index,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            provider_name="csv",
        ),
        raw_fields={"Concepto": f"Row {source_row_index}"},
    )


def _transaction(*, source_row_index: int, confidence: Decimal | None) -> Transaction:
    payload: dict[str, object] = {
        "raw": _raw(source_row_index=source_row_index),
        "direction": TransactionDirection.OUTGOING,
        "group_label": None,
        "source_jurisdiction": "ES",
        # A classified row: the confidence filter is independent of the
        # classification state and must surface low-confidence decisions
        # regardless of disposition.
        "business_classification": BusinessClassification.BUSINESS,
        "classified_at": datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
        "classification_confidence": confidence,
    }
    return Transaction.model_validate(payload)


def _seed(tmp_path: Path) -> tuple[Settings, dict[str, str]]:
    """Persist five transactions at distinct confidences; return id-by-label map."""
    settings = _build_settings(tmp_path)
    low = _transaction(source_row_index=1, confidence=Decimal("0.10"))
    boundary = _transaction(source_row_index=2, confidence=Decimal("0.50"))
    high = _transaction(source_row_index=3, confidence=Decimal("0.90"))
    perfect = _transaction(source_row_index=4, confidence=Decimal("1.00"))
    unscored = _transaction(source_row_index=5, confidence=None)
    catalogue = TransactionCatalogue.from_transactions((low, boundary, high, perfect, unscored))
    with open_test_profile_session(_PROFILE_ID):
        # The engine refuses to materialise a bucket custody never published,
        # so the capsule is registered before any repository is constructed.
        register_minimal_profile(profile_id=_PROFILE_ID, overrides={"identity.tax_id": "00000000T"})
        TransactionCatalogueRepository(bucket_id=_PROFILE_ID).save(catalogue)
    ids = {
        "low": low.transaction_id,
        "boundary": boundary.transaction_id,
        "high": high.transaction_id,
        "perfect": perfect.transaction_id,
        "unscored": unscored.transaction_id,
    }
    return settings, ids


def test_confidence_below_includes_only_strictly_lower_rows(tmp_path: Path) -> None:
    settings, ids = _seed(tmp_path)
    with open_test_profile_session(_PROFILE_ID):
        # The engine refuses to materialise a bucket custody never published,
        # so the capsule is registered before any repository is constructed.
        register_minimal_profile(profile_id=_PROFILE_ID, overrides={"identity.tax_id": "00000000T"})
        report = project_review_queue(
            settings=settings,
            state=ReviewState.ALL,
            confidence_below=Decimal("0.5"),
        )
    surfaced = {row.item_id for row in report.rows}
    assert surfaced == {ids["low"]}
    # Boundary value (== threshold) is excluded by the strictly-below predicate.
    assert ids["boundary"] not in surfaced
    assert ids["high"] not in surfaced
    assert ids["perfect"] not in surfaced
    # A None-confidence row has no claim to filter against.
    assert ids["unscored"] not in surfaced


def test_confidence_below_one_surfaces_every_scored_row_under_one(tmp_path: Path) -> None:
    settings, ids = _seed(tmp_path)
    with open_test_profile_session(_PROFILE_ID):
        # The engine refuses to materialise a bucket custody never published,
        # so the capsule is registered before any repository is constructed.
        register_minimal_profile(profile_id=_PROFILE_ID, overrides={"identity.tax_id": "00000000T"})
        report = project_review_queue(
            settings=settings,
            state=ReviewState.ALL,
            confidence_below=Decimal("1.0"),
        )
    surfaced = {row.item_id for row in report.rows}
    assert surfaced == {ids["low"], ids["boundary"], ids["high"]}
    # Exactly 1.00 is not strictly below 1.0; None never matches.
    assert ids["perfect"] not in surfaced
    assert ids["unscored"] not in surfaced


def test_confidence_below_zero_surfaces_nothing(tmp_path: Path) -> None:
    settings, _ids = _seed(tmp_path)
    with open_test_profile_session(_PROFILE_ID):
        # The engine refuses to materialise a bucket custody never published,
        # so the capsule is registered before any repository is constructed.
        register_minimal_profile(profile_id=_PROFILE_ID, overrides={"identity.tax_id": "00000000T"})
        report = project_review_queue(
            settings=settings,
            state=ReviewState.ALL,
            confidence_below=Decimal("0"),
        )
    assert report.rows == ()


def test_no_confidence_filter_includes_non_transaction_kinds(tmp_path: Path) -> None:
    """Without the filter the queue is not narrowed to the low-confidence source."""
    settings, ids = _seed(tmp_path)
    with open_test_profile_session(_PROFILE_ID):
        # The engine refuses to materialise a bucket custody never published,
        # so the capsule is registered before any repository is constructed.
        register_minimal_profile(profile_id=_PROFILE_ID, overrides={"identity.tax_id": "00000000T"})
        unfiltered = project_review_queue(settings=settings, state=ReviewState.ALL)
        filtered = project_review_queue(
            settings=settings,
            state=ReviewState.ALL,
            confidence_below=Decimal("0.5"),
        )
    # The default queue draws from transactions_pending (classified BUSINESS
    # rows are a final disposition and do not appear there), so the two
    # surfaces are genuinely distinct code paths rather than the same set.
    assert {row.item_id for row in filtered.rows} == {ids["low"]}
    assert ids["low"] not in {row.item_id for row in unfiltered.rows}
