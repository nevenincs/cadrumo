"""Tests for localized error surfaces in _common.py helpers.

S77 / S78: ``_draft_by_id`` raises a localized ``typer.BadParameter`` whose
message is drawn from the locale catalogue — never a hard-coded f-string.

S79 / S80: ``_active_profile_or_exit`` emits localized error and next-step
values in both text and JSON channels through the real CLI runner when no
active profile is present.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import typer

from aeat.core.i18n import tr
from aeat.entrypoints.cli._common import _draft_by_id
from aeat.tests.cli_runner import invoke_cached_cli
from aeat.tests.secure_sql import isolated_cli_runtime_profile, isolated_sessionless_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


# ---------------------------------------------------------------------------
# S77 / S78 — draft_id_not_found localized error
# ---------------------------------------------------------------------------


@pytest.fixture
def _active_profile_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Active-profile runtime with CLI directories isolated; no drafts present."""
    monkeypatch.setenv("AEAT_OUTPUT_LANGUAGE", "en")
    with isolated_cli_runtime_profile(tmp_path=tmp_path) as runtime:
        yield runtime.storage_root


def test_draft_by_id_raises_bad_parameter_for_unknown_id(
    _active_profile_env: Path,
) -> None:
    """_draft_by_id raises typer.BadParameter for a nonexistent draft ID."""
    with pytest.raises(typer.BadParameter):
        _draft_by_id("nonexistent-draft-id-xyz")


def test_draft_by_id_error_message_matches_locale_catalogue(
    _active_profile_env: Path,
) -> None:
    """The raised message is sourced from the locale catalogue, not a raw f-string."""
    draft_id = "nonexistent-draft-id-xyz"
    expected = tr("cli.common.errors.draft_id_not_found", draft_id=draft_id)

    with pytest.raises(typer.BadParameter) as exc_info:
        _draft_by_id(draft_id)

    assert str(exc_info.value) == expected
    # Guard: the old hard-coded literal must not appear.
    assert f"draft id {draft_id!r} not found" not in str(exc_info.value)


def test_draft_by_id_error_message_contains_draft_id_interpolation(
    _active_profile_env: Path,
) -> None:
    """The error message includes the actual draft_id value."""
    draft_id = "abc-123"
    with pytest.raises(typer.BadParameter) as exc_info:
        _draft_by_id(draft_id)

    assert draft_id in str(exc_info.value)


# ---------------------------------------------------------------------------
# S79 / S80 — no_active_profile_error_value localized in text + JSON channels
# ---------------------------------------------------------------------------


@pytest.fixture
def _sessionless_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Pristine storage root with no profile, English locale."""
    monkeypatch.setenv("AEAT_OUTPUT_LANGUAGE", "en")
    with isolated_sessionless_storage_root(tmp_path=tmp_path) as root:
        yield root


def test_active_profile_or_exit_locale_keys_resolve_to_real_strings() -> None:
    """The locale catalogue provides non-placeholder values for both S79 keys."""
    error_value = tr("cli.common.errors.no_active_profile_error_value")
    next_value = tr("cli.common.next.create_profile_command")

    # Keys must not fall back to the dotted-key literal (unresolved placeholder).
    assert error_value != "cli.common.errors.no_active_profile_error_value"
    assert next_value != "cli.common.next.create_profile_command"
    # Values must be non-empty strings.
    assert error_value.strip()
    assert next_value.strip()


def test_active_profile_or_exit_emits_localized_payload_in_text_channel(
    _sessionless_env: Path,
) -> None:
    """A CLI verb reaching _active_profile_or_exit emits locale-sourced next-step text."""
    expected_next = tr("cli.common.next.create_profile_command")

    result = invoke_cached_cli(["app", "ledger", "list"])

    assert result.exit_code != 0
    assert expected_next in result.output


def test_active_profile_or_exit_emits_localized_payload_in_json_channel(
    _sessionless_env: Path,
) -> None:
    """A CLI verb reaching _active_profile_or_exit emits locale-sourced values in JSON."""
    expected_error = tr("cli.common.errors.no_active_profile_error_value")
    expected_next = tr("cli.common.next.create_profile_command")

    result = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])

    assert result.exit_code != 0
    # Either the error or the next value from the locale must appear.
    assert expected_error in result.output or expected_next in result.output
