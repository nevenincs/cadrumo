"""Real-behaviour tests for ``config profile archive export`` and ``inspect``.

Each case reproduces a defect an operator hit backing a profile up through the
shipped CLI, and asserts the invariant that defect broke.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....adapters.persistence.storage.bucket.sealed_archive_writer import CADRUMO_BUCKET_BUNDLE_SUFFIX
from .....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from .....application.user_profile.capsule_archive import inspect_profile_capsule_archive
from .....core.bucket_pointer import resolve_active_bucket_id
from .isolated_storage_fixture import live_cli_profile as live_cli_profile
from .isolated_storage_fixture import profile_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("live_cli_profile")]


def test_export_without_a_name_backs_up_the_active_profile(tmp_path: Path) -> None:
    """The profile argument is optional, as every other inspect verb's is.

    Reproduction: ``config profile archive export --output backup...`` with no
    name failed on a missing argument, although the help and every sibling
    verb default to the active profile.
    """
    target = tmp_path / f"backup{CADRUMO_BUCKET_BUNDLE_SUFFIX}"

    exported = profile_cli("archive", "export", "--output", str(target))

    assert exported.exit_code == 0, exported.output
    assert str(inspect_profile_capsule_archive(target).bucket_id) == str(resolve_active_bucket_id())


def test_a_target_without_the_sealed_suffix_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    """The suffix is the operator's flag to fix, so the refusal must name it.

    Reproduction: ``--output backup.tar.gz`` reached the sealed-archive writer,
    whose refusal arrived untranslated and named an internal write operation
    instead of the suffix ``--output`` needs.
    """
    destination = tmp_path / "exports"
    destination.mkdir()
    target = destination / "backup.tar.gz"

    refused = profile_cli("archive", "export", "--output", str(target))

    assert refused.exit_code == 2, refused.output
    error = json.loads(refused.stderr)["error"]
    assert error["code"] == "REFUSED_CLI_BOUNDARY"
    assert error["context"] == {"suffix": CADRUMO_BUCKET_BUNDLE_SUFFIX}
    assert list(destination.iterdir()) == []


def test_inspect_reads_an_archive_with_no_profile_session(tmp_path: Path) -> None:
    """Inspecting discloses only the plaintext header, so it needs no key.

    Reproduction: ``config profile archive inspect --file ...`` demanded
    profile authentication first, so an operator on a machine without a
    keychain -- exactly who is holding an archive to restore -- could not see
    what the file was without unlocking an unrelated profile.
    """
    target = tmp_path / f"backup{CADRUMO_BUCKET_BUNDLE_SUFFIX}"
    assert profile_cli("archive", "export", "--output", str(target)).exit_code == 0
    close_active_bucket_session()

    inspected = profile_cli("archive", "inspect", "--file", str(target))

    assert inspected.exit_code == 0, inspected.output
    assert json.loads(inspected.stdout)["command"] == "config.profile.archive.inspect"
