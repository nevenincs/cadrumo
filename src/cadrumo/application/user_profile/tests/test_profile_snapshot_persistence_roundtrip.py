"""Strict roundtrip and anti-tautology proof for the profile-snapshot boundary.

The immutable filing-time snapshot is the frozen profile state a tax filing
was prepared against: one encrypted ``user-profile-snapshot`` row written and
read through :class:`UserProfileSnapshotRepository`. Every filing-time
consumer assumes that boundary hands back exactly what it was given, and an
equality roundtrip alone cannot demonstrate that -- it passes just as happily
when the load side validates nothing.

Every adapter here is real: a genuine bucket runtime with its own on-disk
SQLite database, the real master-key provider behind
:class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`, and the
production ``model_dump_json`` / ``model_validate_json`` pair. Nothing is
mocked, stubbed or patched.

Two things the sibling record proof does NOT cover live here, because the
snapshot's shape differs from the record's:

* The snapshot's own defaultable surface is almost empty -- ``schema_id`` is
  pinned and ``created_at`` is clock-defaulted -- so the honest sweep runs
  over every persisted :class:`UserProfileFact` as well. That is where a
  save-drops-field regression would actually hide.
* ``created_at`` and ``snapshot_id`` are deliberately outside the canonical
  hash, so the load side cannot refuse a payload that lost ``created_at``.
  The anti-tautology proof for that field is therefore strict INEQUALITY
  rather than a refusal, and it is asserted as such instead of being quietly
  omitted.

The fixture material is shared with :mod:`_profile_record_boundary_support`
so both boundaries prove their claims about the same populated facts.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage import (
    USER_PROFILE_SNAPSHOT_NAMESPACE as USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE,
)
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    UserProfileSnapshot,
    new_profile_snapshot_id,
)
from ....tests.secure_sql import isolated_runtime_profile
from ..repository import UserProfileSnapshotRepository, user_profile_snapshot_object_key
from ._profile_record_boundary_support import defaultable_fields_at_default, populated_facts

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PROFILE_ID = "6c1f9a48-2d35-4b7e-9f80-51ac37e2d604"
_SNAPSHOT_CREATED_AT = datetime(2024, 3, 11, 7, 45, 13, tzinfo=UTC)
_REWRITTEN_AT = datetime(2024, 3, 12, 9, 15, 0, tzinfo=UTC)

_SNAPSHOT_EXCLUDED_FROM_SWEEP = frozenset({"schema_id", "created_at"})
"""Snapshot fields whose non-default proof is carried by a dedicated case.

``schema_id`` is pinned by ``_validate_payload_schema`` to exactly the
canonical identifier, so a "non-default" value for it is not a stronger
fixture but an unconstructible snapshot; that pinning is asserted by
:func:`test_schema_identity_is_pinned_not_merely_defaulted`. ``created_at``
defaults from the clock, so comparing a loaded value against a freshly
evaluated default would differ for any snapshot whatsoever and prove nothing;
what proves it is exact reproduction of a pinned instant across the boundary.
"""


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Yield a real secure-object repository over a real bucket database."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID) as profile:
        yield profile.repository


def _populated_snapshot() -> UserProfileSnapshot:
    """Return a snapshot whose every nested defaultable field is non-default.

    The facts come from the shared record fixture: each declares a distinct
    non-default provenance token and a closed effective-dated window, so a
    boundary that dropped a fact's window or re-defaulted its provenance
    cannot survive the equality assertion.
    """
    record = UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=_PROFILE_ID, facts=populated_facts())
    return UserProfileSnapshot.from_profile(
        record,
        snapshot_id=new_profile_snapshot_id(_PROFILE_ID, created_at=_SNAPSHOT_CREATED_AT),
        created_at=_SNAPSHOT_CREATED_AT,
    )


def _repository(objects: SecureObjectRepository) -> UserProfileSnapshotRepository:
    return UserProfileSnapshotRepository(bucket_id=_PROFILE_ID, objects=objects)


def _rewrite_persisted_snapshot(
    objects: SecureObjectRepository,
    snapshot_id: str,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    """Apply *mutate* to the decrypted snapshot and write it back encrypted.

    The mutation travels the production write path -- same namespace, same
    object key, same classification and schema version the repository's own
    ``save`` stamps -- so the only thing that differs on disk is the snapshot
    payload itself. A mutation that bypassed the encryption would prove
    nothing about the real load.
    """
    object_key = user_profile_snapshot_object_key(_PROFILE_ID, snapshot_id)
    stored = objects.load(
        USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.namespace,
        object_key,
        expected_class=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.sensitivity,
        max_supported_version=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.schema_version,
    )
    assert stored is not None
    envelope = json.loads(stored.payload)
    mutate(envelope["payload"])
    objects.save(
        namespace=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.namespace,
        object_key=object_key,
        classification=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.sensitivity,
        schema_version=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.schema_version,
        written_at=_REWRITTEN_AT,
        payload=json.dumps(envelope).encode("utf-8"),
    )


def test_populated_snapshot_survives_the_encrypted_boundary_unchanged(
    secure_objects: SecureObjectRepository,
) -> None:
    """Strict pydantic equality across the real save / load cycle."""
    snapshot = _populated_snapshot()
    repository = _repository(secure_objects)

    repository.save(snapshot)
    loaded = repository.load(snapshot.snapshot_id)

    assert loaded == snapshot


def test_every_defaultable_field_is_populated_non_default_across_the_boundary(
    secure_objects: SecureObjectRepository,
) -> None:
    """Keep the fixture honest: no defaultable field may sit at its default.

    Without this the roundtrip degrades silently. Someone simplifies the
    fixture, a field falls back to its default, and the save-drops /
    load-re-defaults regression for that field becomes invisible again while
    the equality assertion still passes.

    The sweep is derived from each model's own fields, so a newly added
    defaultable field is covered the day it lands. It runs over the persisted
    facts as well as the snapshot itself: the snapshot's own defaultable
    surface is two special-cased fields, so a snapshot-only sweep would be
    vacuous, while the fact model carries three genuinely defaultable fields
    and is where the regression would actually hide.
    """
    snapshot = _populated_snapshot()
    repository = _repository(secure_objects)
    repository.save(snapshot)

    loaded = repository.load(snapshot.snapshot_id)

    at_default = defaultable_fields_at_default(loaded, excluded=_SNAPSHOT_EXCLUDED_FROM_SWEEP)
    assert not at_default, (
        "these snapshot fields sit at their model default across the boundary, so a "
        "save-drops-field / load-re-defaults-field regression in them would be invisible: "
        f"{sorted(at_default)}"
    )
    assert loaded.facts, "a snapshot with no facts makes the per-fact sweep below vacuous"
    for fact in loaded.facts:
        fact_at_default = defaultable_fields_at_default(fact, excluded=frozenset())
        assert not fact_at_default, (
            f"fact {fact.path!r} carries defaultable fields at their model default across the "
            f"boundary, so a regression in them would be invisible: {sorted(fact_at_default)}"
        )
    # The clock-defaulted field is proven by exact reproduction instead.
    assert loaded.created_at == _SNAPSHOT_CREATED_AT


def test_schema_identity_is_pinned_not_merely_defaulted() -> None:
    """Prove the excluded ``schema_id`` is unconstructible, not just untested.

    The sweep above skips ``schema_id``. That exclusion is only legitimate
    while the model genuinely refuses any other value; the moment the pinning
    is relaxed it becomes an ordinary defaultable field the sweep should have
    been covering.

    The refusal surfaces as a pydantic ``ValidationError`` rather than the
    domain's ``UserProfileValidationError``: the domain type subclasses
    ``ValueError`` so a model validator can raise it, and pydantic wraps any
    ``ValueError`` from a validator into its own error.

    The candidate is decoded through ``model_validate_json``, the same call
    the repository's load path uses, because the model's strict config
    refuses the string and array forms a Python-object round of the JSON
    dump would present.
    """
    payload = _populated_snapshot().model_dump(mode="json")

    with pytest.raises(ValidationError) as refusal:
        UserProfileSnapshot.model_validate_json(json.dumps({**payload, "schema_id": "cadrumo.user_profile.other"}))

    assert "is not the canonical profile schema" in str(refusal.value)


def test_load_refuses_a_persisted_snapshot_with_a_required_field_deleted(
    secure_objects: SecureObjectRepository,
) -> None:
    """Anti-tautology: dropping a required field must not load cleanly.

    ``canonical_hash`` carries no default, so its absence is unrecoverable
    and the strict decode must refuse. If this ever loads, the boundary is
    not validating on read and every roundtrip assertion above is vacuous.
    """
    snapshot = _populated_snapshot()
    repository = _repository(secure_objects)
    repository.save(snapshot)
    _rewrite_persisted_snapshot(secure_objects, snapshot.snapshot_id, lambda payload: payload.pop("canonical_hash"))

    with pytest.raises(ValidationError) as refusal:
        repository.load(snapshot.snapshot_id)

    assert "canonical_hash" in str(refusal.value)


def test_load_refuses_a_persisted_snapshot_whose_facts_were_substituted(
    secure_objects: SecureObjectRepository,
) -> None:
    """Anti-tautology: mutated content must not load behind the stored hash.

    This is the content-addressing guarantee the whole snapshot exists for.
    A filing-time snapshot whose facts drift post-save while its
    ``canonical_hash`` stays put would hand a later audit the wrong answer to
    "what was this filing prepared against". The load side re-derives the
    hash from the persisted facts and refuses on mismatch.
    """
    snapshot = _populated_snapshot()
    repository = _repository(secure_objects)
    repository.save(snapshot)

    def _substitute_first_fact_value(payload: dict[str, Any]) -> None:
        payload["facts"][0]["value"] = "9999"

    _rewrite_persisted_snapshot(secure_objects, snapshot.snapshot_id, _substitute_first_fact_value)

    with pytest.raises(ValidationError) as refusal:
        repository.load(snapshot.snapshot_id)

    assert "does not match the derived hash" in str(refusal.value)


def test_load_refuses_a_persisted_snapshot_with_a_defaultable_fact_field_deleted(
    secure_objects: SecureObjectRepository,
) -> None:
    """Anti-tautology: dropping a DEFAULTABLE field must not load cleanly either.

    This is the harder half and the specific regression the populated fixture
    exists for. A fact's ``valid_to`` has a default, so a naive strict model
    would happily re-default it and hand back a snapshot that differs from
    what was written without raising -- the silent shape of the bug. The
    canonical hash is what makes that impossible here: it is computed over
    the full fact dump, so a dropped window bound re-derives a hash that no
    longer matches the persisted one and the load refuses instead of lying.
    """
    snapshot = _populated_snapshot()
    assert snapshot.facts[0].valid_to != UserProfileFact.model_fields["valid_to"].default, (
        "the fixture must not persist the default valid_to, or deleting it proves nothing"
    )
    repository = _repository(secure_objects)
    repository.save(snapshot)
    _rewrite_persisted_snapshot(
        secure_objects,
        snapshot.snapshot_id,
        lambda payload: payload["facts"][0].pop("valid_to"),
    )

    with pytest.raises(ValidationError) as refusal:
        repository.load(snapshot.snapshot_id)

    assert "does not match the derived hash" in str(refusal.value)


def test_a_dropped_created_at_survives_the_load_and_surfaces_as_inequality(
    secure_objects: SecureObjectRepository,
) -> None:
    """Anti-tautology for the one field the canonical hash does NOT cover.

    ``created_at`` is deliberately outside the canonical-hash payload -- the
    hash addresses the profile's CONTENT, not when the snapshot was taken --
    so the load side has nothing to refuse with and re-defaults the field
    from the clock. The rule's other branch applies: the corruption must at
    least surface as strict inequality rather than being absorbed silently.

    Asserting this is what keeps the field honest. A future change that
    silently pinned ``created_at`` to something reconstructed, or that made
    the load fabricate the written instant, would break this assertion rather
    than sail past a suite that only ever checked the refusing fields.
    """
    snapshot = _populated_snapshot()
    repository = _repository(secure_objects)
    repository.save(snapshot)
    _rewrite_persisted_snapshot(secure_objects, snapshot.snapshot_id, lambda payload: payload.pop("created_at"))

    loaded = repository.load(snapshot.snapshot_id)

    assert loaded != snapshot
    assert loaded.created_at != _SNAPSHOT_CREATED_AT
    # Everything the hash DOES cover still crossed intact, so the inequality
    # above is attributable to the dropped field and not to a broken decode.
    assert loaded.facts == snapshot.facts
    assert loaded.canonical_hash == snapshot.canonical_hash
