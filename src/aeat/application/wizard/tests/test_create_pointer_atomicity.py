"""A failed wizard ``profile create`` must not strand the active-profile pointer.

The wizard ``create`` path delegates the whole cross-store create —
bucket directory, manifest, encrypted record, AND the active-profile
pointer — to ``ProfileRepository.create`` as one unit of work. The
pointer write is part of that unit; a failure rolls it back to its
pre-create state. There is no early caller-side pointer write to
strand, so the ``missing_profile_record`` torn state (pointer aimed at
a profile whose record was never persisted) is unreachable.

These tests force a *real* failure inside the create: the wizard
``create`` targets a display label that already belongs to a live
profile, so the repository's duplicate-label guard raises. No mock, no
patched failure — the rejection is the genuine guard. The contract
under test: a refused ``create`` leaves the active-profile pointer
exactly as it was found.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core import read_pointer
from ....core.config import load_settings
from ....domain.user_profile import new_profile_id
from ....tests.secure_sql import isolated_profile_storage_root
from ...user_profile._orchestration import ProfileAlreadyRegisteredError
from .._catalogue import SETUP_FLOW
from .._commands import _run_full_flow

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def _backend(tmp_path: Path) -> Iterator[Path]:
    """Per-bucket storage root with file-backed custody."""

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


_QUIET_CREATE_FLAGS = {"tax-id": "00000000T", "activity": "Servicios"}


def _quiet_create(profile_name: str) -> None:
    """Drive a non-interactive ``profile create`` through the wizard helper."""

    _run_full_flow(
        SETUP_FLOW,
        dict(_QUIET_CREATE_FLAGS),
        _prompter=None,
        quiet=True,
        accept_defaults=False,
        profile_name=profile_name,
        profile_id=new_profile_id(),
        mode="create",
    )


def test_first_run_create_succeeds_and_points_at_the_new_profile(_backend: Path) -> None:
    """Anti-tautology baseline: a clean first-run create lands a live pointer.

    Pins the positive contract so the failure test's "pointer unchanged"
    assertion is proven non-vacuous — the pointer genuinely moves on a
    successful create and genuinely does not on a failed one.
    """

    _quiet_create("Primero")

    pointer = read_pointer(load_settings().aeat_local_storage_root)
    assert pointer is not None
    first_id = pointer.bucket_id

    # The pointer resolves to a real, registered profile bucket.
    from ...workflow._profile_bucket_scan import read_profile_bucket_by_id

    assert read_profile_bucket_by_id(first_id) is not None


def test_failed_create_restores_the_prior_active_profile_pointer(_backend: Path) -> None:
    """A create that fails inside register must not move the pointer.

    The first create succeeds and the pointer aims at it. The second
    create targets the SAME display label; ``register_active_profile``'s
    duplicate-label guard raises after the wizard has already written
    the early load-order pointer. The failure path must restore the
    pointer to the first profile — never strand it at the second
    create's freshly minted UUID, whose record was never persisted.
    """

    _quiet_create("Clash")
    root = load_settings().aeat_local_storage_root
    before = read_pointer(root)
    assert before is not None
    surviving_id = before.bucket_id

    dispose_engine()
    with pytest.raises(ProfileAlreadyRegisteredError):
        _quiet_create("Clash")

    after = read_pointer(root)
    assert after is not None, "the failed create cleared the prior active-profile pointer"
    assert after.bucket_id == surviving_id, "the failed create stranded the pointer at the never-persisted profile"

    # The surviving pointer still resolves to a registered, readable
    # profile — no `missing_profile_record` torn state.
    from ...workflow._profile_bucket_scan import read_profile_bucket_by_id

    assert read_profile_bucket_by_id(surviving_id) is not None
