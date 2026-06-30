"""Home-office censo ratio tests for ledger modelo-readiness preflight."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.categories import SpendingCategory
from ....domain.transactions import BusinessClassification, TransactionCatalogue, TransactionCatalogueRepository
from ....domain.usage_ratios import UsageRatioProfile, save_usage_ratios
from ....tests.secure_sql import isolated_runtime_profile
from .. import LedgerPreflightIssueReason, preflight_ledger_tax_readiness
from ._preflight_test_support import (
    _BUCKET_ID,
    _HOME_OFFICE_PROFILE_ID,
    _Q2_2026,
    _apply_home_office_censo,
    _transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_preflight_flags_home_office_ratio_without_applied_censo(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        category = SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET
        save_usage_ratios(
            UsageRatioProfile(ratios={category: Decimal("0.30")}),
            bucket_id=profile.bucket_id,
        )
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    _transaction(
                        "row-home-office",
                        business_classification=BusinessClassification.MIXED,
                        business_pct=Decimal("0.30"),
                        category_id=category.value,
                        usage_ratio_id=category.value,
                    ),
                ),
            ),
        )

        report = preflight_ledger_tax_readiness(
            bucket_id=profile.bucket_id,
            period=_Q2_2026,
            transaction_repository=repository,
        )

    assert report.ready is False
    assert report.checked_transaction_count == 1
    assert [issue.reason for issue in report.issues] == [LedgerPreflightIssueReason.CENSO_RATIO_MISMATCH]
    assert "persisted HOME_OFFICE overrides require an applied censo" in report.issues[0].detail
    assert "aeat config profile censo" in report.issues[0].detail


def test_preflight_accepts_home_office_ratio_after_matching_censo_apply(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_HOME_OFFICE_PROFILE_ID) as profile:
        _apply_home_office_censo(profile.bucket_id)
        category = SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    _transaction(
                        "row-home-office-censo",
                        business_classification=BusinessClassification.MIXED,
                        business_pct=Decimal("0.060"),
                        category_id=category.value,
                        usage_ratio_id=category.value,
                    ),
                ),
            ),
        )

        report = preflight_ledger_tax_readiness(
            bucket_id=profile.bucket_id,
            period=_Q2_2026,
            transaction_repository=repository,
        )

    assert report.ready is True
    assert report.checked_transaction_count == 1
    assert report.issues == ()


def test_preflight_flags_home_office_ratio_that_disagrees_with_applied_censo(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_HOME_OFFICE_PROFILE_ID) as profile:
        _apply_home_office_censo(profile.bucket_id)
        category = SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET
        save_usage_ratios(
            UsageRatioProfile(ratios={category: Decimal("0.30")}),
            bucket_id=profile.bucket_id,
        )
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    _transaction(
                        "row-home-office-stale-censo",
                        business_classification=BusinessClassification.MIXED,
                        business_pct=Decimal("0.30"),
                        category_id=category.value,
                        usage_ratio_id=category.value,
                    ),
                ),
            ),
        )

        report = preflight_ledger_tax_readiness(
            bucket_id=profile.bucket_id,
            period=_Q2_2026,
            transaction_repository=repository,
        )

    assert report.ready is False
    assert report.checked_transaction_count == 1
    assert [issue.reason for issue in report.issues] == [LedgerPreflightIssueReason.CENSO_RATIO_MISMATCH]
    assert "persisted HOME_OFFICE overrides disagree with the bound censo" in report.issues[0].detail
    assert "persisted=0.30" in report.issues[0].detail
    assert "censo=0.060" in report.issues[0].detail


def test_preflight_does_not_attach_home_office_censo_mismatch_to_unrelated_ratio(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        save_usage_ratios(
            UsageRatioProfile(
                ratios={
                    SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET: Decimal("0.30"),
                    SpendingCategory.TELEFONIA_MOVIL: Decimal("0.60"),
                },
            ),
            bucket_id=profile.bucket_id,
        )
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    _transaction(
                        "row-phone",
                        business_classification=BusinessClassification.MIXED,
                        business_pct=Decimal("0.60"),
                        category_id=SpendingCategory.TELEFONIA_MOVIL.value,
                        usage_ratio_id=SpendingCategory.TELEFONIA_MOVIL.value,
                    ),
                ),
            ),
        )

        report = preflight_ledger_tax_readiness(
            bucket_id=profile.bucket_id,
            period=_Q2_2026,
            transaction_repository=repository,
        )

    assert report.ready is True
    assert report.checked_transaction_count == 1
    assert report.issues == ()
