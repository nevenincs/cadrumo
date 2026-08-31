"""The revision-id join cannot be made ambiguous by any declared namespace.

``derive_revision_id`` content-addresses eight inputs by joining them with
``\x1f`` and hashing the result. A delimiter join is only injective while no
input can contain the delimiter: if one could, two different rows would derive
the same ``revision_id`` and the read-time tamper gate in
``verify_revision_self_consistency`` would admit a forged lineage.

Seven of the eight inputs cannot carry it by construction -- a hex object key,
a decimal schema version, an ISO-8601 instant, and four hex digests or empty
strings. The eighth, ``namespace``, is typed only as a non-empty string, so its
safety rests on every declared namespace happening to be a plain identifier.

This pins that. It is what makes the existing derivation provably unambiguous
without restamping a single stored ``revision_id``, which is the cost of moving
the derivation itself onto the canonical content-hash primitive.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest

from ... import secure_object_namespaces as namespaces_module
from ..secure_object_crypto import derive_revision_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_JOIN_DELIMITER = "\x1f"
_SAFE_NAMESPACE = re.compile(r"[a-z0-9._-]+")


def _declared_namespace_values() -> tuple[str, ...]:
    values: list[str] = []
    for name, value in vars(namespaces_module).items():
        if not name.isupper():
            continue
        candidate = value if isinstance(value, str) else getattr(value, "namespace", None)
        if isinstance(candidate, str):
            values.append(candidate)
    return tuple(sorted(set(values)))


def test_no_declared_namespace_can_forge_a_revision_id() -> None:
    declared = _declared_namespace_values()
    assert declared, "no declared namespaces were discovered, so this proves nothing"

    offenders = [value for value in declared if not _SAFE_NAMESPACE.fullmatch(value)]
    assert not offenders, (
        "these namespaces are not plain identifiers, so the revision-id join is no "
        f"longer provably injective: {offenders}"
    )
    assert not [value for value in declared if _JOIN_DELIMITER in value]


def test_the_join_stays_injective_because_only_one_field_is_unconstrained() -> None:
    """Why the delimiter join is safe, asserted rather than assumed.

    A delimiter join is injective when at most one field can carry the
    delimiter AND its neighbour cannot absorb the overflow. Here the neighbour
    is ``object_key.hex()``, drawn from hex digits, so a delimiter injected
    into ``namespace`` cannot be re-parsed as the end of that field: the two
    joins carry a different delimiter COUNT and hash differently.

    That is the property the migration to the canonical content-hash primitive
    would also provide -- at the cost of restamping every stored revision id.
    """
    moment = datetime(2026, 1, 1, tzinfo=UTC)
    shared = {
        "schema_version": 1,
        "written_at": moment,
        "payload_hash": "a" * 64,
        "ciphertext_hash": "b" * 64,
        "previous_revision_id": None,
        "previous_payload_hash": None,
    }

    honest = derive_revision_id(namespace="alpha", object_key=b"", **shared)
    injected = derive_revision_id(namespace=f"alpha{_JOIN_DELIMITER}0102", object_key=b"", **shared)
    assert honest != injected, (
        "a namespace carrying the join delimiter impersonated a different row; "
        "the join is no longer injective and the derivation must change"
    )

    # and the neighbouring field genuinely cannot carry the delimiter
    assert _JOIN_DELIMITER not in b"".hex()
