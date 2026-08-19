"""Real-behavior tests for the :data:`ProfileId` alias.

The suite pins ``ProfileId`` as the canonical lowercase UUIDv4 identity used by
profile aggregates, bucket manifests, active-profile resolution, and secure
storage routing. Operator labels are deliberately rejected here because label to
UUID resolution belongs above this core identity boundary.

See Also:
    :mod:`~core.identity._profile`
        Alias definition under test.
    :class:`~application.user_profile.CommittedProfileView`
        Application aggregate that carries the immutable profile UUID alongside
        mutable operator-facing labels.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from ....tests.fixtures.identity_holder import single_field_holder
from .. import ProfileId, canonical_profile_bucket_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_Holder = single_field_holder("profile_id", ProfileId)
_VALID_PROFILE_ID = str(uuid4())
_UPPERCASE_PROFILE_ID = str(uuid4()).upper()
_EXTRA_SUFFIX_PROFILE_ID = f"{uuid4()}-extra"


@pytest.mark.parametrize(
    ("profile_id", "expected"),
    (
        pytest.param(_VALID_PROFILE_ID, _VALID_PROFILE_ID, id="canonical"),
        pytest.param(f"  {_VALID_PROFILE_ID}  ", _VALID_PROFILE_ID, id="trimmed"),
    ),
)
def test_profile_id_constraint_accepts_valid_values(profile_id: str, expected: str) -> None:
    assert _Holder.value_of(_Holder.build(profile_id)) == expected


@pytest.mark.parametrize(
    "profile_id",
    (
        pytest.param("operator", id="plain-label"),
        pytest.param(_UPPERCASE_PROFILE_ID, id="uppercase-uuid"),
        pytest.param("", id="empty"),
        pytest.param(_EXTRA_SUFFIX_PROFILE_ID, id="extra-suffix"),
        pytest.param("bad/id", id="slash"),
        pytest.param(" leading-space-after-strip-still-bad?", id="invalid-after-trim"),
    ),
)
def test_profile_id_constraint_rejects_invalid_values(profile_id: str) -> None:
    with pytest.raises(ValidationError):
        _Holder.build(profile_id)


def test_canonical_profile_bucket_id_returns_the_canonical_spelling() -> None:
    """Either spelling of a profile id yields the one canonical bucket string."""
    canonical = "00000000-0000-4000-8000-000000000000"
    assert canonical_profile_bucket_id(canonical) == canonical
    assert canonical_profile_bucket_id(UUID(canonical)) == canonical


def test_canonical_profile_bucket_id_agrees_with_the_pydantic_boundary() -> None:
    """The helper and the ProfileId alias cannot drift."""
    canonical = "00000000-0000-4000-8000-000000000000"
    assert canonical_profile_bucket_id(canonical) == ProfileId(canonical)


def test_canonical_profile_bucket_id_refuses_non_v4_identities() -> None:
    """A non-v4 or malformed uuid is refused, not re-typed."""
    for bad in ("00000000-0000-0000-0000-000000000000", "not-a-uuid", ""):
        with pytest.raises(ValueError):
            canonical_profile_bucket_id(bad)
