"""Home-office censo ratio tests for ledger modelo-readiness preflight."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from decimal import Decimal
from pathlib import Path
from types import FrameType

import pytest

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.profile.usage_ratios import (
    load_usage_ratios,
    save_usage_ratios_with_secure_object_writes,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.ledger.preflight import LedgerPreflightIssueReason, preflight_ledger_tax_readiness
from cadrumo.application.user_profile.capsule_record import ProfileRecordStore
from cadrumo.application.user_profile.censo_sync import bound_raw_afectacion_ratio
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.transactions.enums import BusinessClassification
from cadrumo.domain.transactions.models import TransactionCatalogue
from cadrumo.domain.usage_ratios.model import UsageRatioProfile
from cadrumo.domain.usage_ratios.service import derive_home_office_ratios_from_censo
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record

from .preflight_transaction_support import preflight_transaction

_BUCKET_ID = "22222222-2222-4222-8222-222222222222"
_HOME_OFFICE_PROFILE_ID = "11111111-1111-4111-8111-111111111111"
_Q2_2026 = Period.from_year_and_code(2026, "2T")


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    """Expose the published facts and profile schema through one leased operation."""
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _declare_home_office_m2(bucket_id: str, *, operation: PinnedAuthorityOperation) -> None:
    """Persist the operator-declared ``vivienda_office`` m² facts."""
    facts = tuple(
        UserProfileFact(path=path, value=Decimal(value))
        for path, value in {
            "vivienda_office.total_m2": "100",
            "vivienda_office.office_m2": "20",
        }.items()
    )
    seed_test_profile_record(
        create_user_profile_record(
            context=operation.profile_create_context(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=facts,
        ),
    )


def _apply_home_office_censo(bucket_id: str, *, operation: PinnedAuthorityOperation) -> None:
    """Persist declared m² facts and the ratios derived from their binding."""
    _declare_home_office_m2(bucket_id, operation=operation)
    raw = bound_raw_afectacion_ratio(
        bucket_id=bucket_id,
        profile_id=bucket_id,
        operation=operation,
    )
    assert raw is not None
    derived = derive_home_office_ratios_from_censo(raw, year=2025, operation=operation)
    merged = dict(load_usage_ratios(bucket_id=bucket_id, operation=operation).ratios)
    merged.update(derived.ratios)
    save_usage_ratios_with_secure_object_writes(UsageRatioProfile(ratios=merged), (), bucket_id=bucket_id)


pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_declaring_vivienda_office_facts_clears_the_missing_censo_refusal(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
) -> None:
    """Retirement regression: the ``config profile edit`` instruction is live.

    With the live censo scrape retired, ``bound_raw_afectacion_ratio`` derives
    from the operator-declared ``vivienda_office`` m² facts. A persisted
    HOME_OFFICE override with those facts ABSENT must refuse and name
    ``config profile edit``; declaring the facts through the real profile
    write path must then CLEAR the refusal — proving the operator instruction
    is not a dead instruction.
    """
    category = SpendingCategory.from_registry("suministros_home_office_internet")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_HOME_OFFICE_PROFILE_ID) as profile:
        save_usage_ratios_with_secure_object_writes(
            UsageRatioProfile(ratios={category: Decimal("0.060")}),
            (),
            bucket_id=profile.bucket_id,
        )
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    preflight_transaction(
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
            usage_ratio_profile_loader=load_usage_ratios,
            invoice_reader=InvoiceCatalogueRepository(bucket_id=profile.bucket_id),
            operation=operation,
            transaction_repository=repository,
        )
        assert before.ready is False
        assert [issue.reason for issue in before.issues] == [LedgerPreflightIssueReason.CENSO_RATIO_MISMATCH]
        assert "aeat config profile edit" in before.issues[0].detail

        _declare_home_office_m2(profile.bucket_id, operation=operation)

        after = preflight_ledger_tax_readiness(
            bucket_id=profile.bucket_id,
            period=_Q2_2026,
            usage_ratio_profile_loader=load_usage_ratios,
            invoice_reader=InvoiceCatalogueRepository(bucket_id=profile.bucket_id),
            operation=operation,
            transaction_repository=repository,
        )
        assert after.ready is True
        assert after.issues == ()


def test_preflight_flags_home_office_ratio_without_applied_censo(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        category = SpendingCategory.from_registry("suministros_home_office_internet")
        save_usage_ratios_with_secure_object_writes(
            UsageRatioProfile(ratios={category: Decimal("0.30")}),
            (),
            bucket_id=profile.bucket_id,
        )
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    preflight_transaction(
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
            usage_ratio_profile_loader=load_usage_ratios,
            invoice_reader=InvoiceCatalogueRepository(bucket_id=profile.bucket_id),
            operation=operation,
            transaction_repository=repository,
        )

    assert report.ready is False
    assert report.checked_transaction_count == 1
    assert [issue.reason for issue in report.issues] == [LedgerPreflightIssueReason.CENSO_RATIO_MISMATCH]
    assert "persisted HOME_OFFICE overrides require an applied censo" in report.issues[0].detail
    assert "aeat config profile edit" in report.issues[0].detail


def test_preflight_accepts_home_office_ratio_after_matching_censo_apply(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_HOME_OFFICE_PROFILE_ID) as profile:
        _apply_home_office_censo(profile.bucket_id, operation=operation)
        category = SpendingCategory.from_registry("suministros_home_office_internet")
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    preflight_transaction(
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
            usage_ratio_profile_loader=load_usage_ratios,
            invoice_reader=InvoiceCatalogueRepository(bucket_id=profile.bucket_id),
            operation=operation,
            transaction_repository=repository,
        )

    assert report.ready is True
    assert report.checked_transaction_count == 1
    assert report.issues == ()


def test_preflight_flags_home_office_ratio_that_disagrees_with_applied_censo(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_HOME_OFFICE_PROFILE_ID) as profile:
        _apply_home_office_censo(profile.bucket_id, operation=operation)
        category = SpendingCategory.from_registry("suministros_home_office_internet")
        save_usage_ratios_with_secure_object_writes(
            UsageRatioProfile(ratios={category: Decimal("0.30")}),
            (),
            bucket_id=profile.bucket_id,
        )
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    preflight_transaction(
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
            usage_ratio_profile_loader=load_usage_ratios,
            invoice_reader=InvoiceCatalogueRepository(bucket_id=profile.bucket_id),
            operation=operation,
            transaction_repository=repository,
        )

    assert report.ready is False
    assert report.checked_transaction_count == 1
    assert [issue.reason for issue in report.issues] == [LedgerPreflightIssueReason.CENSO_RATIO_MISMATCH]
    assert "persisted HOME_OFFICE overrides disagree with the bound censo" in report.issues[0].detail
    assert "persisted=0.30" in report.issues[0].detail
    assert "censo=0.060" in report.issues[0].detail


def test_preflight_flags_a_home_office_category_with_no_usage_ratio_id(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
) -> None:
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
        category = SpendingCategory.from_registry("suministros_home_office_internet")
        save_usage_ratios_with_secure_object_writes(
            UsageRatioProfile(ratios={category: Decimal("1.00")}),
            (),
            bucket_id=profile.bucket_id,
        )
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    preflight_transaction(
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
            usage_ratio_profile_loader=load_usage_ratios,
            invoice_reader=InvoiceCatalogueRepository(bucket_id=profile.bucket_id),
            operation=operation,
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


def test_preflight_stays_silent_for_a_non_home_office_category(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
) -> None:
    """The other direction, so the screen is not simply always-on.

    A category outside the home-office families takes no such override, so a
    divergent home-office ratio in the profile is none of its business. A
    screen that fired here would attach a censo advisory to every expense in
    the ledger and train the operator to ignore it.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        save_usage_ratios_with_secure_object_writes(
            UsageRatioProfile(
                ratios={SpendingCategory.from_registry("suministros_home_office_internet"): Decimal("1.00")}
            ),
            (),
            bucket_id=profile.bucket_id,
        )
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    preflight_transaction(
                        "row-unrelated",
                        business_classification=BusinessClassification.BUSINESS,
                        business_pct=None,
                        category_id=SpendingCategory.from_registry("cuotas_autonomos_ss").value,
                        usage_ratio_id=None,
                    ),
                ),
            ),
        )

        report = preflight_ledger_tax_readiness(
            bucket_id=profile.bucket_id,
            period=_Q2_2026,
            usage_ratio_profile_loader=load_usage_ratios,
            invoice_reader=InvoiceCatalogueRepository(bucket_id=profile.bucket_id),
            operation=operation,
            transaction_repository=repository,
        )

    assert LedgerPreflightIssueReason.CENSO_RATIO_MISMATCH not in [issue.reason for issue in report.issues]


def _profile_record_reads(action: Callable[[], object]) -> int:
    """Count decrypting reads of the encrypted profile record, observing without replacing the store."""
    load_code = ProfileRecordStore.load.__code__
    reads = 0
    previous = sys.getprofile()

    def observe(frame: FrameType, event: str, arg: object) -> None:
        nonlocal reads
        del arg
        if event == "call" and frame.f_code is load_code:
            reads += 1

    sys.setprofile(observe)
    try:
        action()
    finally:
        sys.setprofile(previous)
    return reads


def test_preflight_with_home_office_rows_decrypts_the_profile_once(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
) -> None:
    """Both home-office checks read the dwelling m2 from one decrypted record."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_HOME_OFFICE_PROFILE_ID) as profile:
        _apply_home_office_censo(profile.bucket_id, operation=operation)
        category = SpendingCategory.from_registry("suministros_home_office_internet")
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(
            TransactionCatalogue.from_transactions(
                (
                    preflight_transaction(
                        "row-home-office-once",
                        business_classification=BusinessClassification.MIXED,
                        business_pct=Decimal("0.060"),
                        category_id=category.value,
                        usage_ratio_id=category.value,
                    ),
                ),
            ),
        )
        reports: list[object] = []

        reads = _profile_record_reads(
            lambda: reports.append(
                preflight_ledger_tax_readiness(
                    bucket_id=profile.bucket_id,
                    period=_Q2_2026,
                    usage_ratio_profile_loader=load_usage_ratios,
                    invoice_reader=InvoiceCatalogueRepository(bucket_id=profile.bucket_id),
                    operation=operation,
                    transaction_repository=repository,
                )
            )
        )
        # The counter sees every decrypting read: two direct lookups count two.
        detector_reads = _profile_record_reads(
            lambda: [
                bound_raw_afectacion_ratio(
                    bucket_id=profile.bucket_id, profile_id=profile.bucket_id, operation=operation
                )
                for _ in range(2)
            ]
        )

    assert reads == 1
    assert detector_reads == 2
    (report,) = reports
    assert getattr(report, "issues", None) == ()
