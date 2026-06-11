"""Tests for strict user-profile value and snapshot records."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from .. import UserProfileFact, UserProfileRecord, UserProfileSnapshot, UserProfileStatus

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_profile_record_is_strict_frozen_and_tombstones_live_root() -> None:
    created_at = datetime(2026, 5, 7, 10, 0, tzinfo=UTC)
    removed_at = datetime(2026, 5, 7, 11, 0, tzinfo=UTC)
    profile = UserProfileRecord(
        profile_id="default",
        display_name="Default",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
        created_at=created_at,
        updated_at=created_at,
    )

    tombstoned = profile.tombstone(removed_at=removed_at)

    assert tombstoned.status is UserProfileStatus.TOMBSTONED
    assert tombstoned.removed_at == removed_at
    assert tombstoned.updated_at == removed_at
    assert profile.status is UserProfileStatus.ACTIVE

    with pytest.raises(ValidationError, match="frozen_instance"):
        profile.display_name = "Changed"


def test_profile_record_rejects_invalid_lifecycle_state() -> None:
    with pytest.raises(ValidationError, match="tombstoned profiles must carry removed_at"):
        UserProfileRecord.model_validate(
            {
                "profile_id": "removed",
                "display_name": "Removed",
                "status": "tombstoned",
            },
        )

    with pytest.raises(ValidationError, match="active profiles must not carry removed_at"):
        UserProfileRecord(
            profile_id="active",
            display_name="Active",
            removed_at=datetime(2026, 5, 7, tzinfo=UTC),
        )


def test_profile_fact_rejects_invalid_effective_window() -> None:
    with pytest.raises(ValidationError, match="valid_from is after valid_to"):
        UserProfileFact(
            path="tax_residence.ccaa",
            value="madrid",
            valid_from=date(2026, 1, 2),
            valid_to=date(2026, 1, 1),
        )


def test_leading_zero_identifier_stays_a_string() -> None:
    """A zero-significant identifier (a 5-digit postcode) must not be int-coerced.

    The JSON-restoration validator inspects bare digit strings to recover
    Decimal facts lost across ``model_dump_json``. A Spanish postcode such
    as ``08001`` is all-digits but is never a canonical Decimal — Decimal
    normalises away the leading zero (``08001`` -> ``8001``), so a
    round-tripped Decimal fact never carries one. The validator must leave
    ``08001`` as a ``str`` end to end.
    """

    fact = UserProfileFact(path="contact.postcode", value="08001")
    assert fact.value == "08001"
    assert isinstance(fact.value, str)

    reloaded = UserProfileFact.model_validate_json(fact.model_dump_json())
    assert reloaded.value == "08001"
    assert isinstance(reloaded.value, str)
    assert reloaded == fact


def test_json_restoration_still_recovers_canonical_decimal_and_zero() -> None:
    """A genuine round-tripped Decimal (and a lone ``0``) is still restored.

    The leading-zero exclusion must not regress the original purpose of the
    restoration validator: a Decimal fact dumped to JSON as a string is
    reparsed back to ``Decimal``, and a canonical ``0`` integer-part value
    is a legitimate Decimal shape.
    """

    decimal_fact = UserProfileFact(path="usage_ratios.business_ratio", value=Decimal("0.50"))
    reloaded = UserProfileFact.model_validate_json(decimal_fact.model_dump_json())
    assert reloaded.value == Decimal("0.50")
    assert isinstance(reloaded.value, Decimal)

    zero_fact = UserProfileFact.model_validate_json('{"path": "usage_ratios.business_ratio", "value": "0"}')
    assert zero_fact.value == Decimal("0")
    assert isinstance(zero_fact.value, Decimal)


def test_snapshot_is_canonical_and_rejects_tombstoned_profiles() -> None:
    created_at = datetime(2026, 5, 7, 10, 0, tzinfo=UTC)
    profile = UserProfileRecord(
        profile_id="default",
        display_name="Default",
        facts=(
            UserProfileFact(path="usage_ratios.business_ratio", value=Decimal("0.50")),
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
        ),
        created_at=created_at,
        updated_at=created_at,
    )

    first = UserProfileSnapshot.from_profile(profile, snapshot_id="snapshot-1", created_at=created_at)
    second = UserProfileSnapshot.from_profile(
        profile.model_copy(update={"facts": tuple(reversed(profile.facts))}),
        snapshot_id="snapshot-2",
        created_at=created_at,
    )

    assert first.canonical_hash == second.canonical_hash
    assert [fact.path for fact in first.facts] == ["identity.tax_id", "usage_ratios.business_ratio"]

    with pytest.raises(ValueError, match="cannot snapshot a tombstoned profile"):
        UserProfileSnapshot.from_profile(profile.tombstone(removed_at=created_at), snapshot_id="snapshot-3")


def test_snapshot_hash_is_canonical_for_duplicate_same_window_facts() -> None:
    created_at = datetime(2026, 5, 7, 10, 0, tzinfo=UTC)
    facts = (
        UserProfileFact(path="identity.name", value="Ada", source="manual_cli"),
        UserProfileFact(path="identity.name", value="Babbage", source="modelo_036_import"),
    )
    profile = UserProfileRecord(
        profile_id="default",
        display_name="Default",
        facts=facts,
        created_at=created_at,
        updated_at=created_at,
    )

    first = UserProfileSnapshot.from_profile(profile, snapshot_id="snapshot-1", created_at=created_at)
    second = UserProfileSnapshot.from_profile(
        profile.model_copy(update={"facts": tuple(reversed(facts))}),
        snapshot_id="snapshot-2",
        created_at=created_at,
    )

    assert first.canonical_hash == second.canonical_hash
    assert [fact.value for fact in first.facts] == [fact.value for fact in second.facts]
