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

The version is bounded above rather than pinned, and the last test here pins
that choice: pinning would refuse the defaulted records this codebase writes.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._loader import load_user_profile_schema
from .._values import (
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


def _facts() -> tuple[UserProfileFact, ...]:
    return (UserProfileFact(path="identity.tax_id", value="12345678Z"),)


def _record(**overrides: object) -> UserProfileRecord:
    return UserProfileRecord.model_validate(
        {
            "profile_id": _PROFILE_ID,
            "display_name": "schema-identity-operator",
            "facts": _facts(),
            **overrides,
        },
    )


def test_record_refuses_an_unknown_schema_id() -> None:
    with pytest.raises(ValidationError, match=_SCHEMA_REFUSAL):
        _record(schema_id="bogus.profile")


def test_record_refuses_a_future_schema_version() -> None:
    canonical = load_user_profile_schema()

    with pytest.raises(ValidationError, match=_SCHEMA_REFUSAL):
        _record(schema_version=canonical.version + 1)


def _snapshot_payload(**overrides: object) -> dict[str, object]:
    """Return a snapshot payload whose ONLY defect is its schema metadata.

    The canonical hash covers schema_id and schema_version, so simply editing
    them in a dumped payload would also break the hash and the resulting
    refusal would prove nothing about the schema guard. Re-deriving the hash
    over the overridden metadata leaves the identity claim as the one thing
    wrong with the payload.
    """
    payload = UserProfileSnapshot.from_profile(
        _record(),
        snapshot_id=new_profile_snapshot_id(_PROFILE_ID),
    ).model_dump()
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

    with pytest.raises(ValidationError, match=_SCHEMA_REFUSAL):
        UserProfileSnapshot.model_validate(_snapshot_payload(schema_version=canonical.version + 1))


def test_the_canonical_identity_is_accepted() -> None:
    canonical = load_user_profile_schema()

    record = _record(schema_id=canonical.id, schema_version=canonical.version)

    assert record.schema_id == canonical.id
    assert record.schema_version == canonical.version


def test_the_version_is_bounded_above_not_pinned() -> None:
    """Pinning would refuse the defaulted records this codebase actually writes."""
    canonical = load_user_profile_schema()
    defaulted = _record()

    assert defaulted.schema_version < canonical.version
    assert defaulted.schema_id == canonical.id
