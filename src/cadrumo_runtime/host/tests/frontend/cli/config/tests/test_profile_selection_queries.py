"""The runtime names the profile a frontend means: the one its text names, and the one selected.

The runtime, its native transport and the profile are real; the profile is
created through the command line's own ``create`` verb. Both questions are
asked on a connection that holds no session, and neither grants one.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import Result

from cadrumo.core.bucket_pointer import pointer_path
from cadrumo_client.contracts.sign_in import SignInPresence

from .installation_profile_support import PROFILE_LABEL, installation_client, served_installation

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_a_login_target_is_resolved_by_label_or_identifier_and_an_unknown_one_names_nothing(
    tmp_path: Path, invoke_cli: Callable[..., Result]
) -> None:
    with (
        served_installation(tmp_path, run_cli=invoke_cli) as installation,
        installation_client(installation.endpoint) as client,
    ):
        by_label = client.login_target(PROFILE_LABEL.upper())
        by_id = client.login_target(f"  {installation.profile_id}  ")
        unknown = client.login_target("No such profile")

    assert (by_label.profile_id, by_label.label) == (installation.profile_id, PROFILE_LABEL)
    assert (by_id.profile_id, by_id.label) == (installation.profile_id, PROFILE_LABEL)
    assert (unknown.profile_id, unknown.label) == (None, None)


def test_the_selection_is_answered_by_the_runtime_and_an_unreadable_one_is_unknown(
    tmp_path: Path, invoke_cli: Callable[..., Result]
) -> None:
    with served_installation(tmp_path, run_cli=invoke_cli) as installation:
        with installation_client(installation.endpoint) as client:
            selected = client.active_profile()
        pointer = pointer_path(installation.root)
        pointer.write_bytes(b"not a pointer")
        with installation_client(installation.endpoint) as client:
            unreadable = client.active_profile()
        pointer.unlink()
        with installation_client(installation.endpoint) as client:
            nothing = client.active_profile()

    # Created through the command line and then left: selected, and not signed in by this test.
    assert selected.selected_profile_id == installation.profile_id
    assert selected.signed_in_profile_id is None
    assert selected.presence is SignInPresence.ABSENT
    assert (unreadable.selected_profile_id, unreadable.signed_in_profile_id) == (None, None)
    assert unreadable.presence is SignInPresence.UNKNOWN
    assert (nothing.selected_profile_id, nothing.signed_in_profile_id) == (None, None)
    assert nothing.presence is SignInPresence.ABSENT
