"""Anti-tautology proof: a failed atomic create rolls back cleanly.

Disaster rollback contract gives the atomic provisioner an all-or-nothing
contract: the five-write sequence (directory, manifest, session,
encrypted record, pointer) must reverse steps 1-3 if the encrypted-
record write fails, so the operator never sees a half-created profile.

These tests force a *real* failure at the encrypted-record write
step. The trigger is an incomplete fact set: a record missing a
schema-required field makes ``ProfileLifecycleService.register``
raise ``ProfileSchemaValidationError`` before the record is
persisted. No mock, no patched failure injection — the rejection is
the genuine schema-validation path that ``register`` runs ahead of
its ``repository.save`` call.

The anti-tautology guard is the second test: it proves the rollback
assertions are not vacuously true by showing the *successful* create
leaves exactly the artifacts the failed create must not. If the
rollback ever silently no-ops, the first test's "absent" assertions
would still pass against a phantom bucket — the success-path test is
what closes that hole.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from ....adapters.persistence.storage.bucket._layout import bucket_paths
from ....adapters.persistence.storage.bucket._manifest_io import manifest_path
from ....core import read_pointer
from ....core.config import load_settings
from ....domain.user_profile import ProfileSchemaValidationError, UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from ...user_profile._orchestration import (
    profile_create_storage_span,
    register_active_profile,
)
from ...workflow._persistence import workflow_state_repository
from ...workflow._profile_bucket_scan import read_profile_bucket

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# The minimum schema-valid fact set the user-profile schema accepts.
_VALID_FACTS: Mapping[str, str] = {
    "identity.tax_id": "00000000T",
    "identity.name": "Test Operator",
    "tax_residence.ccaa": "madrid",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "provenance.source": "manual_cli",
}
# An incomplete fact set (a required field dropped) makes the schema
# validator reject the record at the encrypted-record-write step of
# the atomic create.
_INCOMPLETE_FACTS: Mapping[str, str] = {key: value for key, value in _VALID_FACTS.items() if key != "iva.regime"}
_VICTIM_PROFILE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_SURVIVOR_PROFILE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


@pytest.fixture
def _backend(tmp_path: Path) -> Iterator[Path]:
    """Per-bucket storage root with file-backed custody."""

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


def _register(profile_id: str, *, facts: Mapping[str, str]) -> None:
    """Run the atomic create for ``profile_id`` against ``facts``.

    Mirrors the production cold-start sequence: the active-profile
    pointer is written early so ``workflow_state_repository()`` resolves
    its per-bucket engine, and the whole span is wrapped in a
    ``try``/``except`` that restores the captured prior pointer on any
    failure — closing the window the repository's own rollback cannot
    see. ``ProfileRepository.create`` itself owns the rollback of the
    bucket directory, manifest, and pointer for failures inside the
    create.
    """

    fact_tuple = tuple(UserProfileFact(path=path, value=value) for path, value in facts.items())
    with profile_create_storage_span(profile_id) as routing_profile_id:
        workflow_state_repository().update(
            lambda state: register_active_profile(
                state,
                profile_id=profile_id,
                display_name=profile_id.capitalize(),
                facts=fact_tuple,
                routing_profile_id=routing_profile_id,
            ),
        )


def test_failed_atomic_create_raises_and_leaves_no_profile(_backend: Path) -> None:
    """An encrypted-record-write failure rolls back the manifest and pointer.

        The incomplete fact set makes the schema validator reject the
        record inside ``ProfileLifecycleService.register`` — the
    disaster contract step-4 failure. The rollback must clear the manifest
        and the active-profile pointer so neither the manifest scan nor
        the pointer chain reports a phantom ``victim`` profile.
    """

    with pytest.raises(ProfileSchemaValidationError):
        _register(_VICTIM_PROFILE_ID, facts=_INCOMPLETE_FACTS)

    root = load_settings().aeat_local_storage_root
    paths = bucket_paths(root, _VICTIM_PROFILE_ID)

    # The existence claims are gone: no manifest, no pointer.
    assert not manifest_path(paths).is_file(), "rollback left a manifest behind"
    assert read_pointer(root) is None, "rollback left a dangling active-profile pointer"

    # The manifest-scan oracle reports no such profile — `profile list`
    # would show nothing.
    assert read_profile_bucket(_VICTIM_PROFILE_ID) is None, "rollback left a phantom profile in the manifest scan"


def test_successful_atomic_create_lands_the_artifacts_a_failure_clears(_backend: Path) -> None:
    """Anti-tautology proof: a *successful* create lands what a failure must not.

    If the rollback under test silently no-opped, the absent-artifact
    assertions in :func:`test_failed_atomic_create_raises_and_leaves_no_profile`
    would still pass against a never-created profile. This test pins
    the positive contract — manifest present, pointer present,
    profile visible to the scan — so the failure test's assertions
    are proven non-vacuous: the artifacts genuinely exist on success
    and genuinely do not on rollback.
    """

    _register(_SURVIVOR_PROFILE_ID, facts=_VALID_FACTS)

    root = load_settings().aeat_local_storage_root
    paths = bucket_paths(root, _SURVIVOR_PROFILE_ID)

    assert manifest_path(paths).is_file()
    pointer = read_pointer(root)
    assert pointer is not None
    assert pointer.bucket_id == _SURVIVOR_PROFILE_ID
    scanned = read_profile_bucket(_SURVIVOR_PROFILE_ID)
    assert scanned is not None
    assert scanned.bucket_id == _SURVIVOR_PROFILE_ID
