"""Tests for the ``ratios eligible`` and ``ratios validate`` extensions."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.errors import StorageValidationError
from ....domain.categories import SpendingCategory
from ....domain.usage_ratios import (
    ELIGIBLE_USAGE_RATIO_CATEGORIES,
    UsageRatioProfile,
)
from ....tests.secure_sql import isolated_runtime_profile
from ..ratios import (
    eligible_ratio_categories,
    list_eligible_ratios_for_bucket,
    set_usage_ratio,
    unset_usage_ratio,
    validate_ratios_for_bucket,
    validate_ratios_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "19191919-1919-4919-8919-191919191919"
_OTHER_BUCKET_ID = "20202020-2020-4020-8020-202020202020"


class TestEligible:
    def test_eligible_lists_every_eligible_category(self) -> None:
        empty_profile = UsageRatioProfile()
        rows = eligible_ratio_categories(empty_profile)
        assert {row.category for row in rows} == set(ELIGIBLE_USAGE_RATIO_CATEGORIES)

    def test_eligible_rows_are_sorted_by_category_value(self) -> None:
        rows = eligible_ratio_categories(UsageRatioProfile())
        category_values = [row.category.value for row in rows]
        assert category_values == sorted(category_values)

    def test_eligible_flags_override_presence(self) -> None:
        sample_category = next(iter(ELIGIBLE_USAGE_RATIO_CATEGORIES))
        profile = UsageRatioProfile(ratios={sample_category: Decimal("0.40")})
        rows = eligible_ratio_categories(profile)
        targeted = next(row for row in rows if row.category is sample_category)
        assert targeted.override_present is True
        others = [row for row in rows if row.category is not sample_category]
        assert all(row.override_present is False for row in others)

    def test_eligible_default_ratios_are_in_range_when_present(self) -> None:
        rows = eligible_ratio_categories(UsageRatioProfile())
        for row in rows:
            if row.default_ratio is not None:
                assert Decimal("0") <= row.default_ratio <= Decimal("1")


class TestValidate:
    def test_validate_empty_profile_is_clean(self) -> None:
        report = validate_ratios_profile(
            bucket_id=_BUCKET_ID,
            profile=UsageRatioProfile(),
        )
        assert report.bucket_id == _BUCKET_ID
        assert report.profile_present is False
        assert report.overrides_count == 0
        assert report.findings == ()
        assert report.missing_overrides == ()

    def test_validate_reports_missing_required_overrides(self) -> None:
        categories = tuple(ELIGIBLE_USAGE_RATIO_CATEGORIES)
        # The eligible-ratio catalogue currently lists >= 2 entries; a
        # future drop below that threshold should fail this test loudly
        # rather than silently skip — the no-skip rule. If the
        # catalogue ever shrinks to one or zero entries the test must
        # be rewritten, not gated.
        assert len(categories) >= 2, (
            f"ELIGIBLE_USAGE_RATIO_CATEGORIES has {len(categories)} entries; "
            "this test needs at least two and the production catalogue "
            "is expected to satisfy that. Update the test if the "
            "catalogue is intentionally shrinking."
        )
        present, absent = categories[0], categories[1]
        profile = UsageRatioProfile(ratios={present: Decimal("0.30")})
        report = validate_ratios_profile(
            bucket_id=_BUCKET_ID,
            profile=profile,
            require_overrides_for=(present, absent),
        )
        assert report.profile_present is True
        assert report.overrides_count == 1
        assert report.missing_overrides == (absent,)
        # The present override is not flagged
        assert report.findings == ()

    def test_validate_flags_non_eligible_required_category(self) -> None:
        # Find a category that is NOT eligible for user ratios.
        all_categories = set(SpendingCategory)
        non_eligible = next(c for c in all_categories if c not in ELIGIBLE_USAGE_RATIO_CATEGORIES)
        profile = UsageRatioProfile()
        report = validate_ratios_profile(
            bucket_id=_BUCKET_ID,
            profile=profile,
            require_overrides_for=(non_eligible,),
        )
        assert any(f.kind == "not_eligible" for f in report.findings)

    def test_validate_clean_when_all_required_categories_have_overrides(self) -> None:
        categories = tuple(ELIGIBLE_USAGE_RATIO_CATEGORIES)
        # See sibling test rationale: silently skipping on an empty
        # eligible-ratio catalogue would mask a real catalogue
        # regression. The production catalogue ships with >= 2
        # entries today; assert that loudly.
        assert categories, (
            "ELIGIBLE_USAGE_RATIO_CATEGORIES is empty; this test "
            "requires at least one eligible category and the production "
            "catalogue is expected to satisfy that. Update the test if "
            "the catalogue is intentionally being emptied."
        )
        required = categories[:2] if len(categories) >= 2 else categories[:1]
        profile = UsageRatioProfile(ratios={c: Decimal("0.50") for c in required})
        report = validate_ratios_profile(
            bucket_id=_BUCKET_ID,
            profile=profile,
            require_overrides_for=required,
        )
        assert report.missing_overrides == ()
        assert report.findings == ()


class TestReportFields:
    def test_report_eligible_count_matches_domain_set(self) -> None:
        report = validate_ratios_profile(bucket_id=_BUCKET_ID, profile=UsageRatioProfile())
        assert report.eligible_count == len(ELIGIBLE_USAGE_RATIO_CATEGORIES)


class TestRuntimeFacade:
    def test_bucket_wrappers_round_trip_through_active_runtime_bucket(self, tmp_path: Path) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
            prior = set_usage_ratio(
                bucket_id=profile.bucket_id,
                category=SpendingCategory.TELEFONIA_MOVIL,
                ratio=Decimal("0.42"),
            )

            assert prior is None

            report = validate_ratios_for_bucket(bucket_id=profile.bucket_id)
            assert report.profile_present is True
            assert report.overrides_count == 1

            rows = list_eligible_ratios_for_bucket(bucket_id=profile.bucket_id)
            targeted = next(row for row in rows if row.category is SpendingCategory.TELEFONIA_MOVIL)
            assert targeted.override_present is True

            cleared = unset_usage_ratio(bucket_id=profile.bucket_id, category=SpendingCategory.TELEFONIA_MOVIL)
            assert cleared == Decimal("0.42")
            assert validate_ratios_for_bucket(bucket_id=profile.bucket_id).profile_present is False

    def test_bucket_wrappers_fail_closed_for_inactive_runtime_bucket(self, tmp_path: Path) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
            with pytest.raises(StorageValidationError, match=r"errors\.storage\.runtime\.not_ready"):
                set_usage_ratio(
                    bucket_id=_OTHER_BUCKET_ID,
                    category=SpendingCategory.TELEFONIA_MOVIL,
                    ratio=Decimal("0.42"),
                )

            with pytest.raises(StorageValidationError, match=r"errors\.storage\.runtime\.not_ready"):
                validate_ratios_for_bucket(bucket_id=_OTHER_BUCKET_ID)
