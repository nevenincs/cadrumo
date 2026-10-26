"""Verify that a failure other than NoActiveProfileError is never read as "no profile".

``_ratios_bucket_id``, ``_ratios_bucket_and_profile`` and ``_rule_bucket_id``
catch only ``NoActiveProfileError``. Anything else, such as a corrupt
active-profile pointer, must reach the top-level error boundary as its own
typed envelope rather than as the profile-create guidance an absent profile
gets.

Real-behavior test: uses a genuinely corrupt ``active-profile`` pointer file on
disk to drive the real production call stack. No monkeypatching, no test
doubles. The call chain under test:

  ``aeat app ledger ratios list``
    → ``_ratios_bucket_and_profile()``
      → ``require_active_bucket_id()``
        → ``resolve_active_bucket_id()``
          → ``read_pointer(storage_root)``
            → ``ActiveProfilePointerError``
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.tests.secure_sql import isolated_sessionless_storage_root
from ....core.bucket_pointer import pointer_path
from ....tests.cli_envelope import require_error_document
from .cli_runner import invoke_cached_cli
from .sessionless_root_fixtures import _sessionless_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _object_member(document: dict[str, object], key: str) -> dict[str, object]:
    member = document[key]
    assert isinstance(member, dict)
    return {str(name): value for name, value in member.items()}


__all__ = ["_sessionless_root"]


@pytest.fixture
def _corrupt_pointer_root(tmp_path: Path) -> Iterator[Path]:
    """Storage root whose active-profile pointer file contains a partial TOML payload.

    The file is valid TOML but lacks the pointer's required fields, so the
    reader refuses it as the typed pointer corruption.
    """
    with isolated_sessionless_storage_root(tmp_path=tmp_path) as storage_root:
        pointer_file = pointer_path(storage_root)
        pointer_file.parent.mkdir(parents=True, exist_ok=True)
        # Valid TOML syntax, but missing ``bucket_id`` — triggers ValidationError.
        pointer_file.write_text("schema_version = 1\n", encoding="utf-8")
        yield storage_root


# ---------------------------------------------------------------------------
# Baseline: NoActiveProfileError still maps to the profile-create refusal
# ---------------------------------------------------------------------------


def test_no_pointer_projects_the_canonical_profile_action(_sessionless_root: Path) -> None:
    """With no pointer file the expected NoActiveProfileError surfaces as the
    profile-create guidance — the narrow except still catches it correctly."""
    result = invoke_cached_cli(["--format", "json", "app", "ledger", "ratios", "list"])

    assert result.exit_code != 0
    error = _object_member(require_error_document(result.output), "error")
    action = _object_member(error, "action")
    assert action["failed_condition_id"] == "profile.active.available"
    reference = _object_member(action, "action")
    assert reference["action_id"] == "operator.profile.create"
    assert reference["target_command_key"] == "config.profile.create"
    assert action["conditionality"] == "requires_arguments"
    assert action["missing_argument_names"] == ["profile_name"]
    assert action["no_recovery_outcome"] is None


# ---------------------------------------------------------------------------
# Core assertion: unexpected exception must NOT become the no-profile refusal
# ---------------------------------------------------------------------------


def test_corrupt_pointer_projects_the_typed_pointer_refusal(
    _corrupt_pointer_root: Path,
) -> None:
    """A corrupt pointer surfaces as itself, routed to its repair, and never as "no profile"."""
    result = invoke_cached_cli(["--format", "json", "app", "ledger", "ratios", "list"])

    assert result.exit_code != 0
    error = _object_member(require_error_document(result.output), "error")
    assert error["code"] == "INTEGRITY_ACTIVE_PROFILE_POINTER"
    assert _object_member(error, "context")["path"] == str(pointer_path(_corrupt_pointer_root))
    action = _object_member(error, "action")
    assert action["failed_condition_id"] == "profile.active.pointer.valid"
    assert _object_member(action, "action")["action_id"] == "operator.profile.repair_active_pointer"
