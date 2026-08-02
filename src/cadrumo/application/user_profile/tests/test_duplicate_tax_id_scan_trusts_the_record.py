"""The duplicate-tax-id scan decides on the record, not the manifest mirror.

The scan skips tombstoned profiles, which is correct: a tombstoned profile has
left the live surface and its tax id is free to reuse, exactly as its display
name is. The defect was WHERE that status came from. ``list()`` reads the
plaintext ``manifest.toml`` mirror and never unlocks a bucket, so it
structurally cannot run ``verify_profile_integrity``; ``load()`` does. Skipping
on the manifest therefore made the decision on unverified data BEFORE the
verifying load -- and for a profile it skipped, the verification never ran at
all.

The escaping direction is a manifest saying ``tombstoned`` over an ``active``
record. ``_integrity`` already names the OPPOSITE polarity -- a manifest saying
``active`` over a tombstoned record letting the live surface serve a deleted
profile -- and that one is caught precisely because such a profile is not
skipped, so it reaches the load. The mirror image escaped *because skipping is
what avoids the load*.

The bar is low and does not need an attacker. ``manifest.toml`` is plaintext by
design, so the mirror can be read without a key. More importantly a torn write
between the encrypted record and its manifest leaves exactly this state, which
is why ``verify_profile_integrity`` exists.

Real storage root, real encrypted records, real manifests. The drift is written
by editing the manifest on disk, which is the state a torn write produces.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.bucket import bucket_paths, manifest_path
from ....domain.user_profile import UserProfileFact, UserProfileStatus
from ....tests.secure_sql import isolated_profile_storage_root
from .._integrity import ProfileIntegrityError
from .._orchestration import ProfileAlreadyRegisteredError, profile_create_storage_span
from .._profile_repository import ProfileRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# The full required fact set; a partial one is refused by the schema validator
# inside register, which would fail this module for a reason it does not test.
_TAX_ID = "00000000T"
_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value=_TAX_ID),
    UserProfileFact(path="identity.name", value="Persona Prueba"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="provenance.source", value="manual_cli"),
)


@pytest.fixture
def backend(tmp_path: Path) -> Iterator[Path]:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


def _create(repository: ProfileRepository, *, label: str, facts: tuple[UserProfileFact, ...]):
    from ....domain.user_profile import new_profile_id

    profile_id = new_profile_id()
    with profile_create_storage_span(profile_id):
        return repository.create(label=label, facts=facts, profile_id=profile_id)


def _mirror_status_on_disk(root: Path, profile_id: str, status: str) -> None:
    """Rewrite only the manifest's ``status`` mirror, leaving the record alone.

    This is the drift a torn write between the two stores produces: the
    encrypted record still says ``active``, the plaintext mirror says
    otherwise.
    """
    target = manifest_path(bucket_paths(root, profile_id))
    text = target.read_text(encoding="utf-8")
    rewritten = [f'status = "{status}"' if line.strip().startswith("status =") else line for line in text.splitlines()]
    target.write_text("\n".join(rewritten) + "\n", encoding="utf-8")


def test_a_second_profile_with_the_same_tax_id_is_refused(backend: Path) -> None:
    """Positive control: the guard fires on an untampered pair.

    Every refusal below is only evidence against this. It also proves the
    fixture reaches the guard at all -- a create that failed for an unrelated
    reason would otherwise read as a refusal.
    """
    repository = ProfileRepository()
    _create(repository, label="First", facts=_FACTS)

    with pytest.raises(ProfileAlreadyRegisteredError):
        _create(repository, label="Second", facts=_FACTS)


def test_a_tombstoned_profile_frees_its_tax_id(backend: Path) -> None:
    """The skip semantics are preserved: a genuinely tombstoned id is reusable.

    This is the behaviour the guard intends and the fix must not break. It is
    the discriminating control on the OTHER side: a fix that simply stopped
    skipping would refuse here, which would be a regression rather than a
    hardening.
    """
    from .. import active_profile_pointer_transaction
    from .._orchestration import profile_storage_session

    repository = ProfileRepository()
    created = _create(repository, label="Gone", facts=_FACTS)
    with active_profile_pointer_transaction(repository.root), profile_storage_session(created.profile_id):
        repository.delete(created.profile_id)

    # The tax id is free again now that the record itself is tombstoned.
    reused = _create(repository, label="Reused", facts=_FACTS)
    assert reused.profile_id != created.profile_id


def test_a_manifest_tombstone_over_an_active_record_does_not_free_the_tax_id(backend: Path) -> None:
    """The discriminating case: drift must not admit the duplicate.

    Before the fix the scan skipped this profile on the manifest's word and
    never loaded it, so the second registration was ADMITTED -- silently
    splitting one taxpayer's filing history, which is the harm the guard's own
    docstring names. The record is untouched and still ``active``; only the
    plaintext mirror was rewritten, which is the state a torn write leaves.
    """
    repository = ProfileRepository()
    created = _create(repository, label="Live Taxpayer", facts=_FACTS)

    _mirror_status_on_disk(backend, created.profile_id, UserProfileStatus.TOMBSTONED.value)

    with pytest.raises(ProfileAlreadyRegisteredError):
        _create(repository, label="Duplicate", facts=_FACTS)


def test_the_drift_state_is_real_and_the_record_still_says_active(backend: Path) -> None:
    """Anti-tautology: the fixture really does produce disagreeing stores.

    Without this, the refusal above could come from a manifest so mangled that
    the profile is unreadable -- which the guard skips with a warning, a
    different path entirely. This pins that the manifest parses, reports
    tombstoned, and the encrypted record underneath still reports active.
    """
    from ....adapters.persistence.storage.bucket import read_manifest
    from .._orchestration import profile_storage_session

    repository = ProfileRepository()
    created = _create(repository, label="Drifted", facts=_FACTS)
    _mirror_status_on_disk(backend, created.profile_id, UserProfileStatus.TOMBSTONED.value)

    manifest = read_manifest(bucket_paths(backend, created.profile_id))
    assert manifest.status is UserProfileStatus.TOMBSTONED

    # The record itself is untouched and still active. Read through the
    # record repository rather than ``ProfileRepository.load``, which asserts
    # manifest-versus-record integrity and refuses the drifted pair outright --
    # that refusal is real and is exactly what the scan must not swallow.
    with profile_storage_session(created.profile_id):
        record = repository._lifecycle_repository(created.profile_id).load(created.profile_id)
    assert record.status is UserProfileStatus.ACTIVE

    with pytest.raises(ProfileIntegrityError), profile_storage_session(created.profile_id):
        repository.load(created.profile_id)
