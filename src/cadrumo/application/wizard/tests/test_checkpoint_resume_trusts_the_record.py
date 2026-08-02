"""Resume eligibility is decided by the encrypted record, not the manifest mirror.

``complete_setup`` writes the encrypted record FIRST and the plaintext manifest
mirror SECOND, and its own docstring calls the intermediate state "the safe
direction" because surfaces "treat the profile as not-yet-workable until the
manifest write lands". That reasoning holds for every surface that EXCLUDES on
``SETUP_INCOMPLETE``. It inverts here, where ``SETUP_INCOMPLETE`` is a positive
GRANT: under a torn completion the mirror still says the profile is in progress
while the record is already ``ACTIVE``.

Reading the mirror therefore offered a resume on a COMPLETED profile,
re-projected its on-record answers, and let them be written back over the live
record -- failing only at the final commit, after the writes had landed. The
manifest may be used to EXCLUDE a profile; it may not be used to GRANT a
capability.

The gate that catches the divergence already existed and already worked; it was
positioned too late. Deciding eligibility through the one load that runs
``verify_profile_integrity`` moves it before the re-projection rather than
adding a second authority beside it.

The sibling site that resolves a create-mode profile id still grants on the
mirror, and is deliberately left alone: with this refusal raising, that grant
reaches no write on any demonstrated path. If it is ever revisited it must be
VERIFIED, not dropped -- a genuinely interrupted setup (record and manifest
agreeing on ``SETUP_INCOMPLETE``, nothing torn) resolves through that grant,
and the duplicate-label helper refuses the same label, so removing it would
make an ordinary save-and-exit unresumable.

Two limits, stated because the scenario is a crash window:

* the torn state is produced by writing the manifest directly rather than by
  interrupting a live ``complete_setup``. The design's own documented write
  ordering is the evidence that a crash produces this state, and the manifest is
  plaintext-reachable regardless.
* nobody has measured how long the window is open. The claim is that nothing
  prevents the state and nothing caught it until after the writes -- not that it
  is likely.

Real storage root, real encrypted records, real manifests, real lifecycle
authority. Nothing is mocked.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.bucket import bucket_paths
from ....adapters.persistence.storage.bucket._manifest_io import read_manifest, write_manifest
from ....core.flows import FlowMode
from ....domain.user_profile import ProfileNotFoundError, UserProfileStatus, new_profile_id
from ....tests.secure_sql import isolated_profile_storage_root
from ...user_profile import ProfileIntegrityError, ProfileRepository, profile_storage_session
from ...workflow import workflow_state_repository
from .. import ProfileFactsCheckpointStore
from .._catalogue import SETUP_FLOW

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LABEL = "operator"


@pytest.fixture
def backend(tmp_path: Path) -> Iterator[Path]:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


def _store(profile_id: str) -> ProfileFactsCheckpointStore:
    return ProfileFactsCheckpointStore(SETUP_FLOW, profile_id=profile_id, profile_name=_LABEL)


def _committed_answers() -> dict[str, str]:
    """A full, schema-valid answer map from a scripted individual-declaration walk.

    A partial map is refused by the schema validator at completion, which would
    fail these tests for a reason none of them is about.
    """
    from ...flows import flow_definition_from_wizard_flow, run_scripted_flow
    from .._commands import _SETUP_CHECKPOINT
    from .test_setup_runtime import _scripted_answers_for_individual_declaration

    definition = flow_definition_from_wizard_flow(SETUP_FLOW, checkpoint=dict(_SETUP_CHECKPOINT))
    state, _projection = run_scripted_flow(
        definition,
        list(_scripted_answers_for_individual_declaration()),
        mode=FlowMode.CREATE,
    )
    return dict(state.answers)


def _mint_incomplete() -> str:
    """Mint a genuinely in-progress profile through the real checkpoint save."""
    profile_id = new_profile_id()
    _store(profile_id).save(SETUP_FLOW.id, _committed_answers())
    return profile_id


def _complete(profile_id: str) -> None:
    from ...user_profile import complete_setup_with_lifecycle_span

    complete_setup_with_lifecycle_span(profile_id)


def _tear_manifest(root: Path, profile_id: str) -> None:
    """Rewrite ONLY the mirror, leaving the encrypted record untouched.

    This is the artefact the documented record-first/manifest-second ordering
    leaves behind when it is interrupted between the two writes.
    """
    paths = bucket_paths(root, profile_id)
    manifest = read_manifest(paths)
    write_manifest(paths, manifest.model_copy(update={"status": UserProfileStatus.SETUP_INCOMPLETE}))


def _record_status(profile_id: str) -> UserProfileStatus | None:
    with profile_storage_session(profile_id):
        record = workflow_state_repository().load().active_profile_record()
    return None if record is None else record.status


def test_an_in_progress_profile_still_resumes(backend: Path) -> None:
    """CONTROL on the permissive side: the capability this method exists for.

    Without this, every refusal below is satisfied by a method that resumes
    nothing at all, and the fix would read as correct while having removed
    save-and-exit re-entry entirely.
    """
    profile_id = _mint_incomplete()
    assert _record_status(profile_id) is UserProfileStatus.SETUP_INCOMPLETE

    answers = _store(profile_id).load(SETUP_FLOW.id)

    assert answers is not None
    assert answers


def test_a_completed_profile_offers_no_resume(backend: Path) -> None:
    """CONTROL on the restrictive side, with the stores in agreement."""
    profile_id = _mint_incomplete()
    _complete(profile_id)
    assert _record_status(profile_id) is UserProfileStatus.ACTIVE

    assert _store(profile_id).load(SETUP_FLOW.id) is None


def test_the_torn_state_is_real(backend: Path) -> None:
    """ANTI-VACUITY: the fixture genuinely produces divergent stores.

    Without this, the refusal below could be satisfied by a tear that never
    happened -- the profile simply being complete.
    """
    profile_id = _mint_incomplete()
    _complete(profile_id)
    _tear_manifest(backend, profile_id)

    assert read_manifest(bucket_paths(backend, profile_id)).status is UserProfileStatus.SETUP_INCOMPLETE
    assert _record_status(profile_id) is UserProfileStatus.ACTIVE


def test_a_torn_manifest_refuses_instead_of_resuming(backend: Path) -> None:
    """THE DISCRIMINATING CASE: no resume is offered on the mirror's word.

    Before the fix this returned a populated answer map re-projected from a
    COMPLETED profile, and the walk then wrote those answers back onto the live
    record. The refusal must arrive HERE, before any re-projection.
    """
    profile_id = _mint_incomplete()
    _complete(profile_id)
    _tear_manifest(backend, profile_id)

    with pytest.raises(ProfileIntegrityError):
        _store(profile_id).load(SETUP_FLOW.id)


def test_the_integrity_refusal_is_not_reported_as_no_resume(backend: Path) -> None:
    """The refusal must not be swallowed by the absent-profile arm.

    ``ProfileIntegrityError`` SUBCLASSES ``ProfileNotFoundError``, so a single
    ``except ProfileNotFoundError`` around the load would convert "the stores
    disagree" into "no resume available" -- silently restoring the defect while
    every other test here still passed. Pinned as a subclass relationship AND as
    behaviour, because the hazard is created by the hierarchy and realised by
    the handler.
    """
    assert issubclass(ProfileIntegrityError, ProfileNotFoundError)

    profile_id = _mint_incomplete()
    _complete(profile_id)
    _tear_manifest(backend, profile_id)

    with pytest.raises(ProfileIntegrityError):
        _store(profile_id).load(SETUP_FLOW.id)


def test_an_absent_profile_is_reported_as_no_resume(backend: Path) -> None:
    """The genuine absent case stays a ``None``, not a raise.

    The narrow ordering above must not turn every missing profile into an
    error: absence is an ordinary "nothing to resume". Another profile is
    minted first so the backend is provisioned and the only thing missing is
    the requested id -- otherwise this would pass on an unprovisioned-key
    failure that has nothing to do with resume eligibility.
    """
    _mint_incomplete()

    assert _store(new_profile_id()).load(SETUP_FLOW.id) is None


def test_the_verifying_load_is_what_refuses(backend: Path) -> None:
    """The refusal comes from the existing integrity authority, not a new check.

    Asserted against ``ProfileRepository.load`` directly so a future refactor
    that reintroduces a second, parallel status comparison in the checkpoint
    store fails here rather than passing quietly.
    """
    profile_id = _mint_incomplete()
    _complete(profile_id)
    _tear_manifest(backend, profile_id)

    with pytest.raises(ProfileIntegrityError), profile_storage_session(profile_id):
        ProfileRepository().load(profile_id)
