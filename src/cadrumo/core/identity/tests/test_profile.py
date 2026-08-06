"""Real-behavior tests for the :data:`ProfileId` alias.

The suite pins ``ProfileId`` as the canonical lowercase UUIDv4 identity used by
profile aggregates, bucket manifests, active-profile resolution, and secure
storage routing. Operator labels are deliberately rejected here because label to
UUID resolution belongs above this core identity boundary.

See Also:
    :mod:`~core.identity._profile`
        Alias definition under test.
    :class:`~application.user_profile.ProfileAggregate`
        Application aggregate that carries the immutable profile UUID alongside
        mutable operator-facing labels.
    :func:`~application.user_profile.verify_profile_integrity`
        Cross-store read gate that compares profile UUID copies across physical
        stores.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from ....tests.fixtures.identity_holder import single_field_holder
from .. import ProfileId

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
