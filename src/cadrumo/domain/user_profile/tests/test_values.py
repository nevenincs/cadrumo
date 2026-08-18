"""Tests for strict user-profile value and snapshot records."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord, UserProfileSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PROFILE_ID = "8d87424d-0b5a-469e-b802-02ffdad316f1"
_ACTIVE_PROFILE_ID = "503a9d70-8308-4cf8-9f56-0dd357f88594"


def test_profile_record_is_strict_frozen_and_carries_setup_state() -> None:
    created_at = datetime(2026, 5, 7, 10, 0, tzinfo=UTC)
    profile = UserProfileRecord(
        profile_id=_PROFILE_ID,
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
        setup_state=ProfileSetupState.COMPLETE,
        created_at=created_at,
        updated_at=created_at,
    )

    assert profile.setup_state is ProfileSetupState.COMPLETE
    assert len(profile.content_digest) == 64

    with pytest.raises(ValidationError, match="frozen_instance"):
        profile.setup_state = ProfileSetupState.INCOMPLETE


@pytest.mark.parametrize(
    ("payload", "expected_message"),
    (
        (
            {
                "profile_id": _ACTIVE_PROFILE_ID,
                "status": "active",
            },
            "extra_forbidden",
        ),
        (
            {
                "profile_id": _ACTIVE_PROFILE_ID,
                "display_name": "Active",
            },
            "extra_forbidden",
        ),
    ),
)
def test_profile_record_rejects_removed_lifecycle_fields(
    payload: dict[str, object],
    expected_message: str,
) -> None:
    with pytest.raises(ValidationError, match=expected_message):
        UserProfileRecord.model_validate(payload)


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


@pytest.mark.parametrize(
    ("payload_json", "expected"),
    (
        (
            UserProfileFact(path="usage_ratios.business_ratio", value=Decimal("0.50")).model_dump_json(),
            Decimal("0.50"),
        ),
        (
            '{"path": "usage_ratios.business_ratio", "value": "0"}',
            Decimal("0"),
        ),
    ),
)
def test_json_restoration_still_recovers_canonical_decimal_and_zero(
    payload_json: str,
    expected: Decimal,
) -> None:
    """A genuine round-tripped Decimal (and a lone ``0``) is still restored.

    The leading-zero exclusion must not regress the original purpose of the
    restoration validator: a Decimal fact dumped to JSON as a string is
    reparsed back to ``Decimal``, and a canonical ``0`` integer-part value
    is a legitimate Decimal shape.
    """

    reloaded = UserProfileFact.model_validate_json(payload_json)
    assert reloaded.value == expected
    assert isinstance(reloaded.value, Decimal)


def test_snapshot_is_canonical_and_rejects_incomplete_profiles() -> None:
    created_at = datetime(2026, 5, 7, 10, 0, tzinfo=UTC)
    profile = UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
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

    with pytest.raises(ValueError, match="cannot snapshot an incomplete profile record"):
        UserProfileSnapshot.from_profile(
            profile.model_copy(update={"setup_state": ProfileSetupState.INCOMPLETE}),
            snapshot_id="snapshot-3",
        )


def test_snapshot_hash_is_canonical_for_duplicate_same_window_facts() -> None:
    created_at = datetime(2026, 5, 7, 10, 0, tzinfo=UTC)
    facts = (
        UserProfileFact(path="identity.name", value="Ada", source="manual_cli"),
        UserProfileFact(path="identity.name", value="Babbage", source="modelo_036_import"),
    )
    profile = UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
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
