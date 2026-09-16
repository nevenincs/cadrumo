"""Persistence-backed tests for the usage-ratio runtime facade."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.errors import StorageValidationError
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.ledger.ratios import (
    list_eligible_ratios_for_bucket,
    set_usage_ratio,
    unset_usage_ratio,
    validate_ratios_for_bucket,
)
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.categories.spending_category import SpendingCategory

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "19191919-1919-4919-8919-191919191919"
_OTHER_BUCKET_ID = "20202020-2020-4020-8020-202020202020"


class TestRuntimeFacade:
    def test_bucket_wrappers_round_trip_through_active_runtime_bucket(self, tmp_path: Path) -> None:
        with (
            isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile,
            bundled_indexed_authority().operation() as operation,
        ):
            prior = set_usage_ratio(
                bucket_id=profile.bucket_id,
                category=SpendingCategory.from_registry("telefonia_movil"),
                ratio=Decimal("0.42"),
                operation=operation,
            )

            assert prior is None

            report = validate_ratios_for_bucket(bucket_id=profile.bucket_id, operation=operation)
            assert report.profile_present is True
            assert report.overrides_count == 1

            rows = list_eligible_ratios_for_bucket(bucket_id=profile.bucket_id, year=2025, operation=operation)
            targeted = next(row for row in rows if row.category == SpendingCategory.from_registry("telefonia_movil"))
            assert targeted.override_present is True

            cleared = unset_usage_ratio(
                bucket_id=profile.bucket_id,
                category=SpendingCategory.from_registry("telefonia_movil"),
                operation=operation,
            )
            assert cleared == Decimal("0.42")
            assert validate_ratios_for_bucket(bucket_id=profile.bucket_id, operation=operation).profile_present is False

    def test_bucket_wrappers_fail_closed_for_inactive_runtime_bucket(self, tmp_path: Path) -> None:
        with (
            isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID),
            bundled_indexed_authority().operation() as operation,
        ):
            with pytest.raises(StorageValidationError, match=r"errors\.storage\.runtime\.not_ready"):
                set_usage_ratio(
                    bucket_id=_OTHER_BUCKET_ID,
                    category=SpendingCategory.from_registry("telefonia_movil"),
                    ratio=Decimal("0.42"),
                    operation=operation,
                )

            with pytest.raises(StorageValidationError, match=r"errors\.storage\.runtime\.not_ready"):
                validate_ratios_for_bucket(bucket_id=_OTHER_BUCKET_ID, operation=operation)
