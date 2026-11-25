"""Bare invocation under an open session reads governed facts inside the root's pinned authority."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session

from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....application.user_profile.lifecycle import ProfileCapsuleLifecycle
from .cli_fixture_worlds import invoke_joined_cli
from .profile_lifecycle_support import profile_id_for_label, seed

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_bare_invocation_with_an_open_session_renders_the_full_overview(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        seed("default")
        profile_id = profile_id_for_label("default")
        ProfileCapsuleLifecycle().select(profile_id)

        with open_test_profile_session(profile_id):
            bare = invoke_joined_cli(["--format", "json"])

    assert bare.exit_code == 0, bare.output
    envelope = json.loads(bare.output)
    assert envelope["command"] == "root.status"
    assert envelope["result"]["active_profile_name"] == "default"
    assert envelope["result"]["work_units"] == 0
