"""CLI surface tests for the ``setup_incomplete`` profile lifecycle status.

A profile minted at the start of the interactive setup flow is live and
resumable but not yet workable: its manifest carries
``UserProfileStatus.SETUP_INCOMPLETE``. These tests drive the real
``aeat config profile list`` and ``aeat app overview calendar
--all-profiles`` surfaces against real on-disk bucket manifests (no mocks,
per the roundtrip-discipline rule) and prove:

- ``config profile list`` names the ``setup_incomplete`` status on the
  row (text token and JSON ``status`` field) and raises a non-blocking
  info advisory on the typed Notice channel — never a silent active-looking
  row.
- a listing with only workable ``active`` profiles carries neither the
  ``setup_incomplete`` token nor the advisory (anti-tautology).
- ``overview calendar --all-profiles`` never silently drops a
  setup-incomplete profile: it names it on a machine line, raises the
  honesty advisory, and does not count it as a calendar-bearing profile.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.bucket import (
    BUCKET_MANIFEST_SCHEMA_VERSION,
    BucketManifest,
    ManifestKdfParams,
    provision_bucket_directory,
    write_manifest,
)
from ....core.config import load_settings
from ....domain.user_profile import UserProfileStatus
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ._profile_lifecycle_support import create_profile_via_cli
from .envelope_helpers import unwrap_envelope_notices, unwrap_schema_envelope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SETUP_INCOMPLETE_BUCKET_ID = "33333333-3333-4333-8333-333333333333"
_STAGED_CREATED_AT = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _stage_setup_incomplete_manifest(*, bucket_id: str, label: str) -> None:
    """Materialise a real on-disk bucket manifest at ``SETUP_INCOMPLETE``.

    The listing and overview surfaces resolve lifecycle status from the
    plaintext ``manifest.toml`` alone (they never open the encrypted
    record for a non-active profile), so a manifest-only bucket is the
    exact on-disk shape a mid-setup profile presents to those scanners.
    """
    root = load_settings().cadrumo_local_storage_root
    paths = provision_bucket_directory(root, bucket_id)
    write_manifest(
        paths,
        BucketManifest(
            bucket_id=bucket_id,
            label=label,
            created_at=_STAGED_CREATED_AT,
            last_unlocked_at=None,
            kdf_params=ManifestKdfParams(
                algorithm="argon2id",
                version=0x13,
                memory_cost=19_456,
                time_cost=2,
                parallelism=1,
                salt=b"0123456789abcdef",
                output_length=32,
            ),
            recovery_enrolled=False,
            schema_version=BUCKET_MANIFEST_SCHEMA_VERSION,
            status=UserProfileStatus.SETUP_INCOMPLETE,
        ),
    )


def test_config_list_names_setup_incomplete_status_and_advises() -> None:
    """``config profile list`` distinguishes a mid-setup profile from an active one."""
    create_profile_via_cli("workable")
    _stage_setup_incomplete_manifest(bucket_id=_SETUP_INCOMPLETE_BUCKET_ID, label="onboarding")

    text = _invoke(("config", "profile", "list"))
    assert text.exit_code == 0, text.output
    # The stable machine token names the lifecycle status per row so a
    # mid-setup profile is never rendered indistinguishably from a workable one.
    assert "\tonboarding\tsetup_incomplete" in text.output
    assert "\tworkable\tactive" in text.output

    payload = _invoke(("--format", "json", "config", "profile", "list"))
    assert payload.exit_code == 0, payload.output
    result = unwrap_schema_envelope(payload.output)
    by_name = {row["name"]: row for row in result["profiles"]}
    assert by_name["onboarding"]["status"] == "setup_incomplete"
    assert by_name["workable"]["status"] == "active"

    notices = unwrap_envelope_notices(payload.output)
    codes = {notice["code"] for notice in notices}
    assert "config.profile.setup_incomplete" in codes
    advisory = next(n for n in notices if n["code"] == "config.profile.setup_incomplete")
    assert advisory["severity"] == "info"
    assert advisory["context"]["labels"] == "onboarding"


def test_config_list_all_active_carries_no_setup_incomplete_advisory() -> None:
    """Anti-tautology: a fully-onboarded listing has neither the token nor the notice."""
    create_profile_via_cli("only-active")

    payload = _invoke(("--format", "json", "config", "profile", "list"))
    assert payload.exit_code == 0, payload.output
    result = unwrap_schema_envelope(payload.output)
    assert all(row["status"] == "active" for row in result["profiles"])

    notices = unwrap_envelope_notices(payload.output)
    assert "config.profile.setup_incomplete" not in {notice["code"] for notice in notices}

    text = _invoke(("config", "profile", "list"))
    assert "setup_incomplete" not in text.output


def test_overview_calendar_all_profiles_surfaces_setup_incomplete_honestly() -> None:
    """``overview calendar --all-profiles`` never silently hides a mid-setup profile."""
    create_profile_via_cli("filer")
    _stage_setup_incomplete_manifest(bucket_id=_SETUP_INCOMPLETE_BUCKET_ID, label="onboarding")

    text = _invoke(
        (
            "app",
            "overview",
            "calendar",
            "--from",
            "2026-01-01",
            "--to",
            "2026-03-31",
            "--all-profiles",
            "--allow-incomplete",
        ),
    )
    assert text.exit_code == 0, text.output
    # The mid-setup profile is named on a stable machine line rather than dropped.
    # The bucket id is redacted by the envelope funnel, so match the line's
    # prefix and its (un-redacted) label rather than the raw UUID.
    incomplete_lines = [
        line
        for line in text.output.splitlines()
        if line.startswith("profile_setup_incomplete\t") and line.endswith("\tonboarding")
    ]
    assert len(incomplete_lines) == 1, text.output
    # It is not workable, so it is not counted as a calendar-bearing profile.
    assert "profiles\t1" in text.output

    payload = _invoke(
        (
            "--format",
            "json",
            "app",
            "overview",
            "calendar",
            "--from",
            "2026-01-01",
            "--to",
            "2026-03-31",
            "--all-profiles",
            "--allow-incomplete",
        ),
    )
    assert payload.exit_code == 0, payload.output
    notices = unwrap_envelope_notices(payload.output)
    advisory = next(
        (n for n in notices if n["code"] == "overview.calendar.setup_incomplete"),
        None,
    )
    assert advisory is not None, notices
    assert advisory["severity"] == "info"
    assert advisory["context"]["labels"] == "onboarding"
