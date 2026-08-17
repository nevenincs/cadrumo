"""Tests for :data:`~core.identity.BucketId`.

Covers the four boundary properties the alias contract pins: a valid
value constructs cleanly, an empty value is rejected, a value longer
than 128 characters is rejected, and surrounding whitespace is stripped
on construction.

See Also:
    :mod:`~core.identity._bucket`
        Pydantic-ready bucket identity alias under test.
    :class:`~application.workflow.ProfileBucketPointer`
        Workflow-facing pointer that carries the bucket identity and mutable
        operator label separately.
    :mod:`~application.bucket_maintenance`
        Application service layer that composes bucket lifecycle operations
        without owning the identity constraint.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from .. import BucketId, canonical_bucket_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Container(BaseModel):
    bucket_id: BucketId


@pytest.mark.parametrize(
    ("bucket_id", "expected"),
    (
        pytest.param("profile-7b9c-bucket", "profile-7b9c-bucket", id="label"),
        pytest.param("x" * 128, "x" * 128, id="max-length"),
        pytest.param("  profile-bucket  ", "profile-bucket", id="trimmed"),
    ),
)
def test_bucket_id_constraint_accepts_valid_values(bucket_id: str, expected: str) -> None:
    container = _Container(bucket_id=bucket_id)
    assert container.bucket_id == expected


@pytest.mark.parametrize(
    "bucket_id",
    (
        pytest.param("", id="empty"),
        pytest.param("x" * 129, id="too-long"),
        pytest.param("   ", id="blank-after-trim"),
    ),
)
def test_bucket_id_constraint_rejects_invalid_values(bucket_id: str) -> None:
    with pytest.raises(ValidationError):
        _Container(bucket_id=bucket_id)


@pytest.mark.parametrize(
    ("supplied", "expected"),
    (
        pytest.param("profile-bucket", "profile-bucket", id="already-canonical"),
        pytest.param("  profile-bucket  ", "profile-bucket", id="trimmed"),
        pytest.param("\tprofile-bucket\n", "profile-bucket", id="trimmed-whitespace-class"),
        pytest.param("x" * 128, "x" * 128, id="max-length"),
    ),
)
def test_canonical_bucket_id_returns_the_alias_spelling(supplied: str, expected: str) -> None:
    """The helper answers exactly what the pydantic boundary would answer.

    This is the property four separate call sites depended on while each kept
    its own copy of the rule: an address keyed on a bucket must not depend on
    which spelling of that bucket the caller happened to hold.
    """
    assert canonical_bucket_id(supplied) == expected


def test_canonical_bucket_id_agrees_with_the_pydantic_boundary() -> None:
    """The helper and the alias cannot drift: the same input yields the same answer.

    Stated as an agreement rather than a literal, because the value that
    matters is that the two stay equal, not what either currently returns.
    """
    for supplied in ("bucket", "  bucket  ", "x" * 128):
        assert canonical_bucket_id(supplied) == _Container(bucket_id=supplied).bucket_id


@pytest.mark.parametrize(
    "supplied",
    (
        pytest.param("", id="empty"),
        pytest.param("   ", id="blank-after-trim"),
        pytest.param("x" * 129, id="too-long"),
    ),
)
def test_canonical_bucket_id_refuses_what_the_alias_refuses(supplied: str) -> None:
    """A value the storage boundary would reject must not yield a usable address.

    The refusal is the plain builtin on purpose: each caller translates it into
    its own typed error, so the shared rule does not impose one surface's error
    class on every other.
    """
    with pytest.raises(ValueError, match="not a canonical bucket identity"):
        canonical_bucket_id(supplied)
