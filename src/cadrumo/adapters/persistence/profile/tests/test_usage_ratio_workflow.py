"""Setting a usage ratio records it, and checks it against the declared Censo.

Three things have to happen together when an operator overrides a category's
business/personal split: the value is persisted, the change is recorded with
its before and after, and the override is compared against the afectación ratio
the profile declared to the AEAT. A surface that did the write and skipped the
comparison would let a stored override silently contradict the Censo, which is
the fact a later deduction rests on.

The override row and its audit events share the bucket's one secure-object
database and are written in a single batch, so a refused event write leaves no
override behind. The last tests pin that against the real storage guard.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import override

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.bucket_event_repository import (
    bind_bucket_event_history_repository_factory,
    bucket_event_history_repository,
)
from cadrumo.application.ledger.persistence_ports import LedgerPersistenceConflictError
from cadrumo.application.ledger.ratios import (
    apply_usage_ratio_override,
    clear_usage_ratio_override,
    eligible_ratio_categories,
)
from cadrumo.application.ledger.usage_ratio_repository import load_usage_ratio_profile
from cadrumo.core.secure_object_write import SecureObjectWrite
from cadrumo.domain.buckets.event import BucketEvent, BucketEventHistoryCatalogue, BucketEventType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.usage_ratios.errors import UsageRatioValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "12121212-1212-4212-8212-121212121212"
_YEAR = 2026


def _eligible_category() -> SpendingCategory:
    """One category the register actually admits an override for.

    Chosen from the live eligibility rule rather than hardcoded: a category the
    domain rejects would make every assertion below a validation failure.
    """
    with _profile() as operation:
        rows = eligible_ratio_categories(
            load_usage_ratio_profile(bucket_id=_BUCKET, operation=operation),
            year=_YEAR,
            operation=operation,
        )
    return rows[0].category


@contextmanager
def _profile() -> Generator[PinnedAuthorityOperation]:
    """Lease the published facts while retaining encrypted storage."""
    with (
        bundled_indexed_authority().operation() as operation,
        TemporaryDirectory() as tmp,
        isolated_runtime_profile(tmp_path=Path(tmp), bucket_id=_BUCKET),
    ):
        yield operation


def test_setting_an_override_persists_it_and_reports_no_prior() -> None:
    """A first override has nothing before it, which the outcome must say."""
    category = _eligible_category()
    with _profile() as operation:
        outcome = apply_usage_ratio_override(
            bucket_id=_BUCKET,
            category=category,
            ratio=Decimal("0.40"),
            year=_YEAR,
            operation=operation,
        )
        stored = load_usage_ratio_profile(bucket_id=_BUCKET, operation=operation).ratios.get(category)

    assert outcome.prior_ratio is None
    assert outcome.new_ratio == Decimal("0.40")
    assert stored == Decimal("0.40")


def test_replacing_an_override_reports_the_value_it_displaced() -> None:
    """The before/after pair is what the audit record is built from."""
    category = _eligible_category()
    with _profile() as operation:
        apply_usage_ratio_override(
            bucket_id=_BUCKET,
            category=category,
            ratio=Decimal("0.40"),
            year=_YEAR,
            operation=operation,
        )
        outcome = apply_usage_ratio_override(
            bucket_id=_BUCKET,
            category=category,
            ratio=Decimal("0.75"),
            year=_YEAR,
            operation=operation,
        )

    assert outcome.prior_ratio == Decimal("0.40")
    assert outcome.new_ratio == Decimal("0.75")


def test_no_censo_ratio_means_no_override_warning() -> None:
    """An undeclared afectación is unknown, not a contradiction.

    Warning on an absent Censo figure would tell an operator their override
    disagrees with a number nobody supplied.
    """
    category = _eligible_category()
    with _profile() as operation:
        outcome = apply_usage_ratio_override(
            bucket_id=_BUCKET,
            category=category,
            ratio=Decimal("0.40"),
            year=_YEAR,
            profile_id="profile-1",
            raw_afectacion_ratio=None,
            operation=operation,
        )

    assert outcome.censo_override_warning is None


def test_a_censo_ratio_without_a_bound_profile_raises_no_warning() -> None:
    """Both halves are required: an unbound profile has no declaration to compare."""
    category = _eligible_category()
    with _profile() as operation:
        outcome = apply_usage_ratio_override(
            bucket_id=_BUCKET,
            category=category,
            ratio=Decimal("0.40"),
            year=_YEAR,
            profile_id=None,
            raw_afectacion_ratio=Decimal("0.90"),
            operation=operation,
        )

    assert outcome.censo_override_warning is None


def test_clearing_an_override_returns_the_value_it_removed() -> None:
    """The cleared value is the audit record's 'prior'; new is absent."""
    category = _eligible_category()
    with _profile() as operation:
        apply_usage_ratio_override(
            bucket_id=_BUCKET,
            category=category,
            ratio=Decimal("0.40"),
            year=_YEAR,
            operation=operation,
        )
        outcome = clear_usage_ratio_override(bucket_id=_BUCKET, category=category, operation=operation)
        remaining = load_usage_ratio_profile(bucket_id=_BUCKET, operation=operation).ratios.get(category)

    assert outcome.prior_ratio == Decimal("0.40")
    assert outcome.new_ratio is None
    assert remaining is None


def test_clearing_an_absent_override_refuses() -> None:
    """Nothing to clear is a refusal, not a silent success.

    Reporting a clearance that removed nothing would put an audit event in the
    history for a change that never happened.
    """
    category = _eligible_category()
    with _profile() as operation, pytest.raises(UsageRatioValidationError):
        clear_usage_ratio_override(bucket_id=_BUCKET, category=category, operation=operation)


def test_the_audit_events_name_the_actor_that_set_and_cleared_an_override() -> None:
    """A person's session records the default label; any other actor is recorded as given."""
    category = _eligible_category()
    with _profile() as operation:
        apply_usage_ratio_override(
            bucket_id=_BUCKET, category=category, ratio=Decimal("0.40"), year=_YEAR, operation=operation
        )
        apply_usage_ratio_override(
            bucket_id=_BUCKET,
            category=category,
            ratio=Decimal("0.60"),
            year=_YEAR,
            actor="automation:external-client.attended.synthetic",
            operation=operation,
        )
        clear_usage_ratio_override(
            bucket_id=_BUCKET,
            category=category,
            actor="automation:external-client.attended.synthetic",
            operation=operation,
        )
        events = tuple(bucket_event_history_repository(bucket_id=_BUCKET).load().events.values())

    def actors(event_type: BucketEventType) -> list[str]:
        return sorted(event.actor for event in events if event.event_type is event_type)

    assert actors(BucketEventType.LEDGER_RATIOS_SET) == ["automation:external-client.attended.synthetic", "operator"]
    assert actors(BucketEventType.LEDGER_RATIOS_UNSET) == ["automation:external-client.attended.synthetic"]


_STALE_REVISION = "f" * 64


class _StaleGuardEvents(BucketEventHistoryRepository):
    """The real event repository, whose first ``stale_attempts`` writes carry a lost revision race."""

    def __init__(self, *, stale_attempts: int) -> None:
        super().__init__(objects=secure_object_repository_for_bucket(_BUCKET))
        self._remaining = stale_attempts

    @override
    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        if self._remaining > 0:
            self._remaining -= 1
            return super().to_secure_object_write(catalogue, expected_revision_id=_STALE_REVISION)
        return super().to_secure_object_write(catalogue, expected_revision_id=expected_revision_id)


def _ratio_events() -> list[BucketEvent]:
    return [
        event
        for event in bucket_event_history_repository(bucket_id=_BUCKET).load().events.values()
        if event.event_type in {BucketEventType.LEDGER_RATIOS_SET, BucketEventType.LEDGER_RATIOS_UNSET}
    ]


def test_a_refused_event_write_leaves_no_override_behind() -> None:
    """The override and its event commit together: losing the event race rolls both back."""
    category = _eligible_category()
    with _profile() as operation:
        with (
            bind_bucket_event_history_repository_factory(lambda *, bucket_id: _StaleGuardEvents(stale_attempts=99)),
            pytest.raises(LedgerPersistenceConflictError),
        ):
            apply_usage_ratio_override(
                bucket_id=_BUCKET, category=category, ratio=Decimal("0.40"), year=_YEAR, operation=operation
            )
        stored = load_usage_ratio_profile(bucket_id=_BUCKET, operation=operation).ratios.get(category)
        events = _ratio_events()

    assert stored is None
    assert events == []


def test_a_refused_event_write_leaves_the_override_in_place_when_clearing() -> None:
    category = _eligible_category()
    with _profile() as operation:
        apply_usage_ratio_override(
            bucket_id=_BUCKET, category=category, ratio=Decimal("0.40"), year=_YEAR, operation=operation
        )
        with (
            bind_bucket_event_history_repository_factory(lambda *, bucket_id: _StaleGuardEvents(stale_attempts=99)),
            pytest.raises(LedgerPersistenceConflictError),
        ):
            clear_usage_ratio_override(bucket_id=_BUCKET, category=category, operation=operation)
        stored = load_usage_ratio_profile(bucket_id=_BUCKET, operation=operation).ratios.get(category)
        events = _ratio_events()

    assert stored == Decimal("0.40")
    assert [event.event_type for event in events] == [BucketEventType.LEDGER_RATIOS_SET]


def test_a_lost_event_race_is_retried_and_commits_one_override_with_one_event() -> None:
    category = _eligible_category()
    with _profile() as operation:
        with bind_bucket_event_history_repository_factory(lambda *, bucket_id: _StaleGuardEvents(stale_attempts=2)):
            apply_usage_ratio_override(
                bucket_id=_BUCKET, category=category, ratio=Decimal("0.40"), year=_YEAR, operation=operation
            )
        stored = load_usage_ratio_profile(bucket_id=_BUCKET, operation=operation).ratios.get(category)
        events = _ratio_events()

    assert stored == Decimal("0.40")
    assert len(events) == 1
    assert events[0].payload == {"category": category.value, "prior": "", "new": "0.40"}
