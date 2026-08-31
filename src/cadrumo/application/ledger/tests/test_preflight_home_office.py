"""Home-office censo ratio tests for ledger modelo-readiness preflight."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.profile.usage_ratios import save_usage_ratios
from ....domain.categories.spending_category import SpendingCategory
from ....domain.transactions.enums import BusinessClassification
from ....domain.transactions.models import TransactionCatalogue
from ....domain.usage_ratios._model import UsageRatioProfile
from ....tests.secure_sql import isolated_runtime_profile
from ..preflight import LedgerPreflightIssueReason, preflight_ledger_tax_readiness
from ._preflight_test_support import (
    _BUCKET_ID,
    _HOME_OFFICE_PROFILE_ID,
    _Q2_2026,
    _apply_home_office_censo,
    _declare_home_office_m2,
    _transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_declaring_vivienda_office_facts_clears_the_missing_censo_refusal(tmp_path: Path) -> None:
    """Retirement regression: the ``config profile edit`` instruction is live.

    With the live censo scrape retired, ``bound_raw_afectacion_ratio`` derives
    from the operator-declared ``vivienda_office`` m² facts. A persisted
    HOME_OFFICE override with those facts ABSENT must refuse and name
    ``config profile edit``; declaring the facts through the real profile
    write path must then CLEAR the refusal — proving the operator instruction
    is not a dead instruction.
    """
    category = SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_HOME_OFFICE_PROFILE_ID) as profile:
        save_usage_ratios(
            UsageRatioProfile(ratios={category: Decimal("0.060")}),
            bucket_id=profile.bucket_id,
        )
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    _transaction(
                        "row-home-office-instruction",
                        business_classification=BusinessClassification.MIXED,
                        business_pct=Decimal("0.060"),
                        category_id=category.value,
                        usage_ratio_id=category.value,
                    ),
                ),
            ),
        )

        before = preflight_ledger_tax_readiness(
            bucket_id=profile.bucket_id,
            period=_Q2_2026,
            transaction_repository=repository,
        )
        assert before.ready is False
        assert [issue.reason for issue in before.issues] == [LedgerPreflightIssueReason.CENSO_RATIO_MISMATCH]
        assert "aeat config profile edit" in before.issues[0].detail

        _declare_home_office_m2(profile.bucket_id)

        after = preflight_ledger_tax_readiness(
            bucket_id=profile.bucket_id,
            period=_Q2_2026,
            transaction_repository=repository,
        )
        assert after.ready is True
        assert after.issues == ()


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
    assert "aeat config profile edit" in report.issues[0].detail


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


def test_preflight_flags_a_home_office_category_with_no_usage_ratio_id(tmp_path: Path) -> None:
    """The unguarded path: the category is set and ``--usage-ratio-id`` is not.

    Leaving ``--usage-ratio-id`` unset is the CLI default, so this is the
    ordinary way an operator classifies a utility bill -- not an exotic case.

    The screen used to test ``usage_ratio_id`` and saw nothing here, while the
    expense aggregation keys the override on the CATEGORY
    (``usage_ratios.get(fact.category, ...)``) and applied it regardless. An
    operator could persist a censo-divergent ratio -- which the write permits
    deliberately, to model a planned afectación change -- and carry it to a
    filing with nothing refusing at any step. LIRPF art. 30.2.5.b caps the
    suministros deduction at 30% of the afectación proportion, so the divergent
    override deducted the full amount.

    The row carries NO ``usage_ratio_id``, which is what makes this test
    discriminate: it fails against the id-keyed screen and passes against the
    category-keyed one.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        category = SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET
        save_usage_ratios(
            UsageRatioProfile(ratios={category: Decimal("1.00")}),
            bucket_id=profile.bucket_id,
        )
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    _transaction(
                        "row-category-only",
                        business_classification=BusinessClassification.BUSINESS,
                        business_pct=None,
                        category_id=category.value,
                        usage_ratio_id=None,
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
    assert LedgerPreflightIssueReason.CENSO_RATIO_MISMATCH in [issue.reason for issue in report.issues]
    # Exactly one row in the period, and the advisory attached to it rather
    # than being raised for the period and landing nowhere.
    assert report.checked_transaction_count == 1
    mismatch = next(issue for issue in report.issues if issue.reason is LedgerPreflightIssueReason.CENSO_RATIO_MISMATCH)
    assert mismatch.transaction_id
    assert "persisted HOME_OFFICE overrides require an applied censo" in mismatch.detail


def test_preflight_stays_silent_for_a_non_home_office_category(tmp_path: Path) -> None:
    """The other direction, so the screen is not simply always-on.

    A category outside the home-office families takes no such override, so a
    divergent home-office ratio in the profile is none of its business. A
    screen that fired here would attach a censo advisory to every expense in
    the ledger and train the operator to ignore it.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        save_usage_ratios(
            UsageRatioProfile(ratios={SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET: Decimal("1.00")}),
            bucket_id=profile.bucket_id,
        )
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    _transaction(
                        "row-unrelated",
                        business_classification=BusinessClassification.BUSINESS,
                        business_pct=None,
                        category_id=SpendingCategory.CUOTAS_AUTONOMOS_SS.value,
                        usage_ratio_id=None,
                    ),
                ),
            ),
        )

        report = preflight_ledger_tax_readiness(
            bucket_id=profile.bucket_id,
            period=_Q2_2026,
            transaction_repository=repository,
        )

    assert LedgerPreflightIssueReason.CENSO_RATIO_MISMATCH not in [issue.reason for issue in report.issues]
