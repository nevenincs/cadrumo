"""A create onto an existing bucket names WHY it refuses.

The refusal is not in question: a bucket already carrying a manifest is never
created over. What this pins is WHICH refusal the operator sees.

``complete_setup`` writes the encrypted record first and the plaintext manifest
second, so an interruption between the two leaves the mirror saying
``setup_incomplete`` over an ``ACTIVE`` record. The wizard's create-mode
resolver reads that mirror, resolves to the existing bucket, and arrives here --
where the operator was told the profile was NOT FOUND, about a profile that
demonstrably exists, with nothing naming the divergence. The resume path already
reports that honestly; this makes the create path agree.

Two guards cover this scenario and neither knows about the other: the resume
path refuses through the checkpoint store's verifying load, and the
non-interactive path (``--quiet`` / ``--accept-defaults``, which builds no
checkpoint store at all) refuses here. That is a coincidence that currently
holds rather than designed defence in depth, so this module pins the
non-interactive half explicitly -- whoever changes this refusal should know the
resume path is not covering it for them.

The torn state is written by rewriting the manifest directly rather than by
interrupting a live completion; the documented write ordering is the evidence
that a crash produces it, and the mirror is plaintext-reachable regardless. How
long the window stays open is unmeasured.

Real storage root, real encrypted records, real manifests. Nothing is mocked.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.bucket import bucket_paths, manifest_path
from ....domain.user_profile import ProfileNotFoundError, UserProfileFact, UserProfileStatus, new_profile_id
from ....tests.secure_sql import isolated_profile_storage_root
from .._integrity import ProfileIntegrityError
from .._orchestration import ProfileAlreadyRegisteredError, profile_create_storage_span
from .._profile_repository import ProfileRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
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


def _create(repository: ProfileRepository, *, label: str, profile_id: str | None = None) -> str:
    resolved = profile_id if profile_id is not None else new_profile_id()
    with profile_create_storage_span(resolved):
        repository.create(label=label, facts=_FACTS, profile_id=resolved)
    return resolved


def _tear_manifest(root: Path, profile_id: str) -> None:
    """Rewrite only the mirror, leaving the encrypted record ``ACTIVE``."""
    target = manifest_path(bucket_paths(root, profile_id))
    text = target.read_text(encoding="utf-8")
    status = UserProfileStatus.SETUP_INCOMPLETE.value
    rewritten = [f'status = "{status}"' if line.strip().startswith("status =") else line for line in text.splitlines()]
    target.write_text("\n".join(rewritten) + "\n", encoding="utf-8")


def test_a_healthy_registered_bucket_still_refuses_as_already_registered(backend: Path) -> None:
    """CONTROL: the ordinary case keeps its existing refusal.

    Without this, the change below could be satisfied by reporting a
    divergence for every collision, which would be a different lie.
    """
    repository = ProfileRepository()
    profile_id = _create(repository, label="Alpha")

    with pytest.raises(ProfileNotFoundError) as caught, profile_create_storage_span(profile_id):
        repository.create(label="Alpha Again", facts=_FACTS, profile_id=profile_id)

    assert not isinstance(caught.value, ProfileIntegrityError)


def test_a_duplicate_label_still_refuses_as_already_registered(backend: Path) -> None:
    """CONTROL: the label collision path is untouched by this change."""
    repository = ProfileRepository()
    _create(repository, label="Alpha")

    with pytest.raises(ProfileAlreadyRegisteredError):
        _create(repository, label="Alpha")


def test_the_torn_state_is_real(backend: Path) -> None:
    """ANTI-VACUITY: the fixture genuinely diverges the two stores."""
    repository = ProfileRepository()
    profile_id = _create(repository, label="Alpha")
    _tear_manifest(backend, profile_id)

    from ....adapters.persistence.storage.bucket import read_manifest

    assert read_manifest(bucket_paths(backend, profile_id)).status is UserProfileStatus.SETUP_INCOMPLETE
    with pytest.raises(ProfileIntegrityError), profile_create_storage_span(profile_id):
        repository.load(profile_id)


def test_a_torn_bucket_refuses_by_naming_the_divergence(backend: Path) -> None:
    """THE DISCRIMINATING CASE: the operator is told what is actually wrong.

    Before this change the same call raised the generic already-registered
    refusal -- typed ``ProfileNotFoundError``, about a profile that exists.
    """
    repository = ProfileRepository()
    profile_id = _create(repository, label="Alpha")
    _tear_manifest(backend, profile_id)

    with pytest.raises(ProfileIntegrityError), profile_create_storage_span(profile_id):
        repository.create(label="Alpha", facts=_FACTS, profile_id=profile_id)


def test_the_divergence_refusal_is_not_masked_by_the_generic_arm(backend: Path) -> None:
    """The precise refusal must survive the broader arm that follows it.

    ``ProfileIntegrityError`` SUBCLASSES ``ProfileNotFoundError``, and the
    helper's fallback catches ``CadrumoError`` -- a superclass of both. Ordered
    the other way the divergence is swallowed and reported as the generic
    refusal it exists to replace, with every other test here still passing.
    """
    assert issubclass(ProfileIntegrityError, ProfileNotFoundError)

    repository = ProfileRepository()
    profile_id = _create(repository, label="Alpha")
    _tear_manifest(backend, profile_id)

    with pytest.raises(ProfileIntegrityError), profile_create_storage_span(profile_id):
        repository.create(label="Alpha", facts=_FACTS, profile_id=profile_id)


def test_the_torn_bucket_is_not_created_over(backend: Path) -> None:
    """The refusal still refuses: no write lands on the live record."""
    repository = ProfileRepository()
    profile_id = _create(repository, label="Alpha")
    _tear_manifest(backend, profile_id)

    with pytest.raises(ProfileIntegrityError), profile_create_storage_span(profile_id):
        repository.create(label="Overwritten", facts=_FACTS, profile_id=profile_id)

    from ....adapters.persistence.storage.bucket import read_manifest

    assert read_manifest(bucket_paths(backend, profile_id)).label == "Alpha"
