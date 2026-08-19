"""Direct domain tests: the export's outer stamp obeys the inner contract.

``CarriedSecureObject.written_at`` validates against the canonical UTC
helper, and sealed-archive headers enforce the same policy, but the sibling
``UserProfilePortableExport.exported_at`` was a bare ``datetime``. One export
boundary therefore transported two competing timestamp contracts: the outer
provenance stamp accepted a naive or offset value that every row it wrapped
would have refused.

That asymmetry is the interesting part. Nothing about the outer field looked
wrong -- it was simply declared the ordinary way, and the enrolled fields
around it were the exception rather than the rule.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ....domain.user_profile import ProfileSetupState
from .._portable_export import UserProfilePortableExport
from .._values import UserProfileFact, UserProfileRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Fixture value pinning the shape under test. The model carries no default
#: because the current write version belongs to the bundle lineage, which
#: this layer cannot see; this claims nothing about what production stamps.
_SHAPE_UNDER_TEST = 3
_PROFILE_ID = "a4f1c2e0-1111-4222-8333-444455556666"
_UTC_INSTANT = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
_NAIVE_INSTANT = datetime(2026, 1, 1, 10, 0, 0)
_OFFSET_INSTANT = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone(timedelta(hours=1)))


def _profile() -> UserProfileRecord:
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )


@pytest.mark.parametrize("instant", (_NAIVE_INSTANT, _OFFSET_INSTANT), ids=("naive", "offset"))
def test_export_refuses_a_non_utc_outer_stamp(instant: datetime) -> None:
    with pytest.raises(ValidationError):
        UserProfilePortableExport(bundle_schema_version=_SHAPE_UNDER_TEST, exported_at=instant, profile=_profile())


def test_export_refuses_a_non_utc_outer_stamp_from_serialized_text() -> None:
    """The refusal has to hold on the import path, which is where a bundle arrives."""
    payload = UserProfilePortableExport(
        bundle_schema_version=_SHAPE_UNDER_TEST, exported_at=_UTC_INSTANT, profile=_profile()
    ).model_dump(mode="json")
    payload["exported_at"] = "2026-01-01T10:00:00"

    with pytest.raises(ValidationError):
        UserProfilePortableExport.model_validate(payload)


def test_a_utc_export_round_trips_canonically() -> None:
    export = UserProfilePortableExport(
        bundle_schema_version=_SHAPE_UNDER_TEST, exported_at=_UTC_INSTANT, profile=_profile()
    )

    restored = UserProfilePortableExport.model_validate_json(export.model_dump_json())

    assert restored.exported_at == _UTC_INSTANT
    assert restored.exported_at.utcoffset() == timedelta(0)


def test_the_outer_stamp_and_the_carried_rows_share_one_policy() -> None:
    """The point of the fix: one boundary, one instant contract."""
    from .._portable_export import CarriedSecureObject

    with pytest.raises(ValidationError):
        CarriedSecureObject(
            namespace="cadrumo.application.workflow.runs",
            object_key="run-1",
            classification="financial",
            schema_version=1,
            written_at=_NAIVE_INSTANT,
            payload_b64="eyJhIjogMX0=",
        )
    with pytest.raises(ValidationError):
        UserProfilePortableExport(
            bundle_schema_version=_SHAPE_UNDER_TEST, exported_at=_NAIVE_INSTANT, profile=_profile()
        )
