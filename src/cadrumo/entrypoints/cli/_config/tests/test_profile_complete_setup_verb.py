"""``config profile complete-setup`` promotes setup state, and only once.

Before this verb existed nothing in production advanced a profile to
``COMPLETE``: the transition lived on ``ProfileRecordRepository.complete_setup``
and was called only from tests, so ``aeat app modelo work create`` refused on
every profile and calculate, verify and export were unreachable behind it. These
cover the door that opened that path.
"""

from __future__ import annotations

import json

import pytest

from .....application.user_profile.profile_record_repository import ProfileRecordRepository
from .....domain.user_profile.values import ProfileSetupState
from .....tests.cli_runner import invoke_cached_cli
from .....tests.user_profile import register_cli_profile
from ._isolated_storage_fixture import config_check_backend as config_check_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _envelope(result) -> dict[str, object]:
    """Return the success envelope parsed from stdout.

    The whole of stdout is the document: ``--format json`` emits one envelope and
    nothing else, so scanning for a line that merely starts with a brace would
    pick up pretty-printed inner members instead.
    """
    assert result.stdout.strip(), f"expected a JSON envelope on stdout, got {result.stderr[:400]!r}"
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, dict)
    return parsed


def _stored_state(profile_id: str) -> tuple[ProfileSetupState, int]:
    """Read the setup state and record revision straight from the repository."""
    from uuid import UUID

    identity = UUID(profile_id)
    record = ProfileRecordRepository.for_current_session(identity).load(identity)
    return record.setup_state, record.record_revision


def test_complete_setup_promotes_an_incomplete_profile(config_check_backend: None) -> None:
    """The promotion happens, and the precondition is asserted rather than assumed.

    ``complete=False`` leaves a profile whose required facts ARE satisfiable but
    whose stored state is still ``INCOMPLETE`` -- exactly the state every profile
    was stuck in. Asserting that state first is what stops this passing on a
    profile that was already complete for some other reason.
    """
    profile_id = register_cli_profile(label="promote-me", complete=False)
    before_state, before_revision = _stored_state(profile_id)
    assert before_state is ProfileSetupState.INCOMPLETE, "precondition: the profile must start incomplete"

    result = invoke_cached_cli(["--format", "json", "config", "profile", "complete-setup"])

    assert result.exit_code == 0, result.stdout + result.stderr
    payload = _envelope(result)["result"]
    assert isinstance(payload, dict)
    assert payload["setup_state"] == ProfileSetupState.COMPLETE.value
    assert payload["already_complete"] is False
    assert payload["missing_required_paths"] == []

    after_state, after_revision = _stored_state(profile_id)
    assert after_state is ProfileSetupState.COMPLETE
    assert after_revision > before_revision, "a real promotion must advance the record revision"


def test_a_second_complete_setup_writes_nothing(config_check_backend: None) -> None:
    """The retry is an idempotent no-op, not a second promotion.

    An autonomous operator retries, and a verb that re-stamped the record on every
    call would bump the revision each time -- so the revision is what this asserts,
    not just the reported flag.
    """
    profile_id = register_cli_profile(label="promote-once", complete=False)
    first = invoke_cached_cli(["--format", "json", "config", "profile", "complete-setup"])
    assert first.exit_code == 0, first.stdout + first.stderr
    _state, revision_after_first = _stored_state(profile_id)

    second = invoke_cached_cli(["--format", "json", "config", "profile", "complete-setup"])

    assert second.exit_code == 0, second.stdout + second.stderr
    payload = _envelope(second)["result"]
    assert isinstance(payload, dict)
    assert payload["already_complete"] is True
    assert payload["setup_state"] == ProfileSetupState.COMPLETE.value

    state_after_second, revision_after_second = _stored_state(profile_id)
    assert state_after_second is ProfileSetupState.COMPLETE
    assert revision_after_second == revision_after_first, "the no-op must not advance the record revision"
