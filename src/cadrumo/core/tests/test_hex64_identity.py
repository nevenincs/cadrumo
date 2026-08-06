"""Real-behavior tests for the canonical :data:`~core.Hex64Str` primitive.

Every unrelated hex-64 identity concept the codebase carries (a registry
snapshot id, a ledger transaction id, a content digest, plus siblings owned
outside ``core`` such as a bucket event id and a durable auth-operation id)
is declared FROM this one primitive rather than each re-declaring its own
``StringConstraints(...)`` call, so the shape (lowercase, exactly 64 hex
characters) cannot drift between them. This suite covers the primitive
itself and the three ``core``-owned semantic aliases; the siblings owned by
``domain.buckets`` and ``application`` are pinned in their own test suites
(:mod:`~domain.buckets.tests.test_event_id`) to keep this ``core``-level
module importing only what ``core`` owns.

See Also:
    :mod:`~core._hex`
        Primitive definition under test.
    :data:`~core.identity.SnapshotId`, :data:`~core.identity.TransactionId`,
    :mod:`~core.identity._digest`
        The three ``core.identity`` semantic aliases derived from it.
"""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from ...tests.fixtures.identity_holder import single_field_holder
from .. import Hex64Str
from ..identity import ContentDigest, SnapshotId, TransactionId

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CANONICAL_DIGEST = hashlib.sha256(b"payload").hexdigest()

_INVALID_HEX64 = (
    pytest.param(_CANONICAL_DIGEST.upper(), id="uppercase"),
    pytest.param("a" * 63, id="too-short"),
    pytest.param("a" * 65, id="too-long"),
    pytest.param("g" * 64, id="non-hex"),
    pytest.param("", id="empty"),
)

# Every public alias this consolidation binds to the one canonical primitive.
# Adding a sixth hex-64 identity concept to the codebase should add its alias
# here too, proving it stayed on the shared shape.
_ALIASES = {
    "Hex64Str": Hex64Str,
    "SnapshotId": SnapshotId,
    "TransactionId": TransactionId,
    "ContentDigest": ContentDigest,
}


@pytest.mark.parametrize("name", sorted(_ALIASES))
def test_alias_accepts_the_canonical_digest_shape(name: str) -> None:
    holder = single_field_holder("value", _ALIASES[name])
    built = holder.build(_CANONICAL_DIGEST)
    assert holder.value_of(built) == _CANONICAL_DIGEST


@pytest.mark.parametrize("name", sorted(_ALIASES))
@pytest.mark.parametrize("invalid", _INVALID_HEX64)
def test_alias_rejects_the_same_malformed_shapes(name: str, invalid: str) -> None:
    holder = single_field_holder("value", _ALIASES[name])
    with pytest.raises(ValidationError):
        holder.build(invalid)


def test_every_alias_is_defined_from_the_one_canonical_primitive() -> None:
    # "Defined from" means literal reuse of the same Annotated object, not a
    # second call to StringConstraints(...) that happens to match today and
    # can silently drift tomorrow.
    for name, alias in _ALIASES.items():
        if name == "Hex64Str":
            continue
        assert alias is Hex64Str, f"{name} must be Hex64Str itself, not a re-declared equivalent"
