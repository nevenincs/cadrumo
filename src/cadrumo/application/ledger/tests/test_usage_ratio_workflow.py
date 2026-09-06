"""Setting a usage ratio records it, and checks it against the declared Censo.

Three things have to happen together when an operator overrides a category's
business/personal split: the value is persisted, the change is recorded with
its before and after, and the override is compared against the afectación ratio
the profile declared to the AEAT. A surface that did the write and skipped the
comparison would let a stored override silently contradict the Censo, which is
the fact a later deduction rests on.

Known and NOT fixed here: the ratio store and the event history are separate
secure objects with no shared commit, so a failure after the write leaves a
persisted override with no audit event. These tests pin the composition, not an
atomicity the code does not yet have.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from ....domain.categories.spending_category import SpendingCategory
from ....domain.usage_ratios.errors import UsageRatioValidationError
from ....tests.secure_sql import isolated_runtime_profile
from ..ratios import (
    apply_usage_ratio_override,
    clear_usage_ratio_override,
    eligible_ratio_categories,
)
from ..usage_ratio_repository import load_usage_ratio_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "12121212-1212-4212-8212-121212121212"
_YEAR = 2026


def _eligible_category() -> SpendingCategory:
    """One category the register actually admits an override for.

    Chosen from the live eligibility rule rather than hardcoded: a category the
    domain rejects would make every assertion below a validation failure.
    """
    with _profile():
        rows = eligible_ratio_categories(load_usage_ratio_profile(bucket_id=_BUCKET), year=_YEAR)
    return rows[0].category


@contextmanager
def _profile() -> Iterator[None]:
    """Real encrypted storage: the write, the lock and the event all need it."""
    with TemporaryDirectory() as tmp, isolated_runtime_profile(tmp_path=Path(tmp), bucket_id=_BUCKET):
        yield


def test_setting_an_override_persists_it_and_reports_no_prior() -> None:
    """A first override has nothing before it, which the outcome must say."""
    category = _eligible_category()
    with _profile():
        outcome = apply_usage_ratio_override(
            bucket_id=_BUCKET,
            category=category,
            ratio=Decimal("0.40"),
            year=_YEAR,
        )
        stored = load_usage_ratio_profile(bucket_id=_BUCKET).ratios.get(category)

    assert outcome.prior_ratio is None
    assert outcome.new_ratio == Decimal("0.40")
    assert stored == Decimal("0.40")


def test_replacing_an_override_reports_the_value_it_displaced() -> None:
    """The before/after pair is what the audit record is built from."""
    category = _eligible_category()
    with _profile():
        apply_usage_ratio_override(bucket_id=_BUCKET, category=category, ratio=Decimal("0.40"), year=_YEAR)
        outcome = apply_usage_ratio_override(
            bucket_id=_BUCKET,
            category=category,
            ratio=Decimal("0.75"),
            year=_YEAR,
        )

    assert outcome.prior_ratio == Decimal("0.40")
    assert outcome.new_ratio == Decimal("0.75")


def test_no_censo_ratio_means_no_override_warning() -> None:
    """An undeclared afectación is unknown, not a contradiction.

    Warning on an absent Censo figure would tell an operator their override
    disagrees with a number nobody supplied.
    """
    category = _eligible_category()
    with _profile():
        outcome = apply_usage_ratio_override(
            bucket_id=_BUCKET,
            category=category,
            ratio=Decimal("0.40"),
            year=_YEAR,
            profile_id="profile-1",
            raw_afectacion_ratio=None,
        )

    assert outcome.censo_override_warning is None


def test_a_censo_ratio_without_a_bound_profile_raises_no_warning() -> None:
    """Both halves are required: an unbound profile has no declaration to compare."""
    category = _eligible_category()
    with _profile():
        outcome = apply_usage_ratio_override(
            bucket_id=_BUCKET,
            category=category,
            ratio=Decimal("0.40"),
            year=_YEAR,
            profile_id=None,
            raw_afectacion_ratio=Decimal("0.90"),
        )

    assert outcome.censo_override_warning is None


def test_clearing_an_override_returns_the_value_it_removed() -> None:
    """The cleared value is the audit record's 'prior'; new is absent."""
    category = _eligible_category()
    with _profile():
        apply_usage_ratio_override(bucket_id=_BUCKET, category=category, ratio=Decimal("0.40"), year=_YEAR)
        outcome = clear_usage_ratio_override(bucket_id=_BUCKET, category=category)
        remaining = load_usage_ratio_profile(bucket_id=_BUCKET).ratios.get(category)

    assert outcome.prior_ratio == Decimal("0.40")
    assert outcome.new_ratio is None
    assert remaining is None


def test_clearing_an_absent_override_refuses() -> None:
    """Nothing to clear is a refusal, not a silent success.

    Reporting a clearance that removed nothing would put an audit event in the
    history for a change that never happened.
    """
    category = _eligible_category()
    with _profile(), pytest.raises(UsageRatioValidationError):
        clear_usage_ratio_override(bucket_id=_BUCKET, category=category)
