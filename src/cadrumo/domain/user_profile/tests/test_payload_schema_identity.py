"""Direct domain tests: persisted payload schema metadata names a real authority.

``schema_id`` and ``schema_version`` declare the authority a persisted
profile payload claims to have been written under, and both were free: any
non-empty id and any integer at or above one validated, were hashed into the
canonical snapshot digest, and were read back later as if current.

An unknown authority is not a value with a typo in it. It is a record
asserting a contract nothing in this codebase defines, and because the
repositories validate only the outer secure-object envelope, nothing between
construction and re-read ever compared the claim against the schema that was
actually loaded.

The version is pinned to exactly the loaded schema's, so both directions
refuse: a FUTURE version was written by something newer than this code, and a
PRE-CURRENT one under a contract this code no longer implements. The tests
below exercise both directions against the record and the snapshot, and pin
the default a freshly constructed record carries to the canonical version.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._loader import load_user_profile_schema
from .._values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    UserProfileSnapshot,
    _derive_canonical_hash,
    new_profile_snapshot_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PROFILE_ID = "a4f1c2e0-1111-4222-8333-444455556666"
# The model validator raises the domain error, which pydantic wraps. Matching
# on the field name keeps the assertion about the schema refusal rather than
# about any other way these models can refuse a payload.
_SCHEMA_REFUSAL = "schema_id|schema_version"
# A version refusal is matched on the message the schema guard raises rather
# than on the field name: the field also carries a ``ge=1`` bound whose
# pydantic error names ``schema_version`` too, so a field-name match would let
# a boundary case pass for the wrong reason.
_VERSION_REFUSAL = "is not the canonical profile schema version"


def _facts() -> tuple[UserProfileFact, ...]:
    return (UserProfileFact(path="identity.tax_id", value="12345678Z"),)


def _record(**overrides: object) -> UserProfileRecord:
    return UserProfileRecord.model_validate(
        {
            "profile_id": _PROFILE_ID,
            "facts": _facts(),
            "setup_state": ProfileSetupState.COMPLETE,
            **overrides,
        },
    )


def _pre_current_version(canonical_version: int) -> int:
    """Return a version older than the canonical one, refusing a vacuous fixture.

    A pre-current version only exists once the schema has advanced past its
    first revision. Failing loudly here keeps the refusal tests from passing
    against ``0``, which the field's ``ge=1`` bound rejects for an unrelated
    reason and which would prove nothing about the schema guard.
    """
    assert canonical_version > 1, "the profile schema is at version 1; there is no pre-current version to refuse"
    return canonical_version - 1


def test_record_refuses_an_unknown_schema_id() -> None:
    with pytest.raises(ValidationError, match=_SCHEMA_REFUSAL):
        _record(schema_id="bogus.profile")


def test_record_refuses_a_future_schema_version() -> None:
    canonical = load_user_profile_schema()

    with pytest.raises(ValidationError, match=_VERSION_REFUSAL):
        _record(schema_version=canonical.version + 1)


def test_record_refuses_a_pre_current_schema_version() -> None:
    canonical = load_user_profile_schema()

    with pytest.raises(ValidationError, match=_VERSION_REFUSAL):
        _record(schema_version=_pre_current_version(canonical.version))


def _snapshot_payload(**overrides: object) -> dict[str, object]:
    """Return a snapshot payload whose ONLY defect is its schema metadata.

    The canonical hash covers schema_id and schema_version, so simply editing
    them in a dumped payload would also break the hash and the resulting
    refusal would prove nothing about the schema guard. Re-deriving the hash
    over the overridden metadata leaves the identity claim as the one thing
    wrong with the payload.
    """
    raw_payload = UserProfileSnapshot.from_profile(
        _record(),
        snapshot_id=new_profile_snapshot_id(_PROFILE_ID),
    ).model_dump()
    assert isinstance(raw_payload, dict)
    payload: dict[str, object] = {}
    for key, value in raw_payload.items():
        assert isinstance(key, str)
        payload[key] = value
    payload.update(overrides)
    payload["canonical_hash"] = _derive_canonical_hash(
        schema_id=str(payload["schema_id"]),
        schema_version=int(str(payload["schema_version"])),
        profile_id=str(payload["profile_id"]),
        facts=_facts(),
    )
    return payload


def test_snapshot_refuses_an_unknown_schema_id() -> None:
    with pytest.raises(ValidationError, match=_SCHEMA_REFUSAL):
        UserProfileSnapshot.model_validate(_snapshot_payload(schema_id="bogus.profile"))


def test_snapshot_refuses_a_future_schema_version() -> None:
    canonical = load_user_profile_schema()

    with pytest.raises(ValidationError, match=_VERSION_REFUSAL):
        UserProfileSnapshot.model_validate(_snapshot_payload(schema_version=canonical.version + 1))


def test_snapshot_refuses_a_pre_current_schema_version() -> None:
    canonical = load_user_profile_schema()

    with pytest.raises(ValidationError, match=_VERSION_REFUSAL):
        UserProfileSnapshot.model_validate(
            _snapshot_payload(schema_version=_pre_current_version(canonical.version)),
        )


def test_the_canonical_identity_is_accepted() -> None:
    canonical = load_user_profile_schema()

    record = _record(schema_id=canonical.id, schema_version=canonical.version)

    assert record.schema_id == canonical.id
    assert record.schema_version == canonical.version


def test_the_current_schema_hydrates_through_the_snapshot() -> None:
    """A canonical payload survives the record and the snapshot untouched."""
    canonical = load_user_profile_schema()

    snapshot = UserProfileSnapshot.model_validate(_snapshot_payload())

    assert snapshot.schema_id == canonical.id
    assert snapshot.schema_version == canonical.version
    assert snapshot.facts == _facts()


def test_a_defaulted_record_carries_the_canonical_version() -> None:
    """The default this codebase writes is the current schema, not a stale one."""
    canonical = load_user_profile_schema()

    defaulted = _record()

    assert defaulted.schema_version == canonical.version
    assert defaulted.schema_id == canonical.id
