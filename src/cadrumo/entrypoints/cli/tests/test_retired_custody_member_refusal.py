"""The CLI surfaces a retired-custody refusal cleanly, rather than leaking it.

A bucket directory carrying the retired plaintext ``manifest.toml`` makes
capsule discovery refuse with ``LEGACY_CUSTODY_DETECTED`` and destructive-reset
guidance.  That refusal is deliberate: the discovery guard reports no parsed
attributes and no candidate identity, so a caller may act only on the refusal
and never on an inferred retired profile.

These tests assert the OPERATOR-FACING half of it.  The refusal itself is
covered at the custody layer; what is covered nowhere else is that a CLI verb
renders it as a clean refusal rather than an unhandled traceback -- the same
discrimination the ambiguous-label surface tests make.

They live here rather than beside the setup-incomplete surface tests because
they are a different subject.  Both once shared a module, on the since-invalid
premise that a staged retired member was how an uncommitted bucket was
produced; a module named for one subject while testing the other is how a
live surface came to be uncovered without anyone noticing.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from click.testing import Result

from ....core.config import load_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage

__all__ = ["isolated_profile_storage"]
from ....tests.bucket_layout import provision_bucket_directory
from ._profile_lifecycle_support import create_profile_via_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LEGACY_BUCKET_ID = "33333333-3333-4333-8333-333333333333"

#: The exception type whose NAME in the output means the refusal escaped to the
#: global boundary instead of being rendered as an operator refusal.
_LEAKED_EXCEPTION_NAME = "ProfileCustodyRefusedError"


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _stage_retired_custody_member(*, bucket_id: str) -> None:
    """Put the retired plaintext manifest into a real bucket directory.

    This is the guard's intended stimulus rather than manufactured corruption:
    capsule discovery refuses on the member's PRESENCE, so the file's content is
    irrelevant and the manifest model it once parsed has itself been retired.
    Writing a stub is therefore more truthful than reconstructing a schema that
    nothing reads any more.
    """
    root = load_settings().cadrumo_local_storage_root
    assert root is not None
    paths = provision_bucket_directory(root, bucket_id)
    (paths.bucket_dir / "manifest.toml").write_text(
        f'bucket_id = "{bucket_id}"\n',
        encoding="utf-8",
    )


def _assert_clean_retired_custody_refusal(result: Result) -> None:
    """Assert a non-zero exit carrying the refusal and its guidance, not a traceback."""
    combined = result.output
    stderr = getattr(result, "stderr", None)
    if stderr:
        combined = f"{combined}\n{stderr}"
    assert result.exit_code != 0, combined
    assert "LEGACY_CUSTODY_DETECTED" in combined, combined
    assert "DESTRUCTIVE_RESET" in combined, combined
    assert "manifest.toml" in combined, combined
    assert _LEAKED_EXCEPTION_NAME not in combined, combined


def test_config_list_refuses_cleanly_on_a_retired_custody_member() -> None:
    """`config profile list` renders the retired-custody refusal, not a traceback."""
    create_profile_via_cli("workable")
    _stage_retired_custody_member(bucket_id=_LEGACY_BUCKET_ID)

    _assert_clean_retired_custody_refusal(_invoke(("config", "profile", "list")))


def test_overview_calendar_refuses_cleanly_on_a_retired_custody_member() -> None:
    """The overview calendar renders the same refusal rather than leaking it."""
    create_profile_via_cli("filer")
    _stage_retired_custody_member(bucket_id=_LEGACY_BUCKET_ID)

    result = _invoke(
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

    _assert_clean_retired_custody_refusal(result)
