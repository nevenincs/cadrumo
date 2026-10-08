"""Portable archive inspection tests for the unkeyed CLI header reader."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

from .....adapters.persistence.storage.bucket.sealed_archive_writer import CADRUMO_BUCKET_BUNDLE_SUFFIX
from .....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from .....application.user_profile.capsule_archive import (
    export_profile_capsule_archive,
    inspect_profile_capsule_archive,
)
from .....core.bucket_pointer import resolve_active_bucket_id
from .isolated_storage_fixture import live_cli_profile as live_cli_profile
from .isolated_storage_fixture import profile_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("live_cli_profile")]


def test_inspect_reads_archive_header_after_the_profile_session_closes(tmp_path: Path) -> None:
    """The header inspection remains available without an unlocked profile."""
    profile_id = resolve_active_bucket_id()
    assert profile_id is not None
    target = tmp_path / f"backup{CADRUMO_BUCKET_BUNDLE_SUFFIX}"
    export_profile_capsule_archive(profile_id=UUID(str(profile_id)), target=target)
    expected = inspect_profile_capsule_archive(target)
    close_active_bucket_session()

    inspected = profile_cli("archive", "inspect", "--file", str(target))

    assert inspected.exit_code == 0, inspected.output
    document = json.loads(inspected.stdout)
    assert document["command"] == "config.profile.archive.inspect"
    assert document["result"]["archive_schema_version"] == expected.archive_schema_version
    assert document["result"]["manifest_digest"] == expected.manifest_digest
    assert "Editor" not in json.dumps(document["result"])


def test_inspect_refuses_a_missing_archive_without_a_traceback(tmp_path: Path) -> None:
    missing = tmp_path / f"missing{CADRUMO_BUCKET_BUNDLE_SUFFIX}"
    inspected = profile_cli("archive", "inspect", "--file", str(missing))
    assert inspected.exit_code != 0, inspected.output
    assert "Traceback" not in inspected.output
