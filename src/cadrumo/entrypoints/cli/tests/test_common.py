"""Tests for localized error surfaces in _common.py helpers.

contract / contract: ``draft_by_id`` raises a localized ``typer.BadParameter`` whose
message is drawn from the locale catalogue — never a hard-coded f-string.

contract / contract: ``_active_profile_or_exit`` emits localized error and next-step
values in both text and JSON channels through the real CLI runner when no
active profile is present.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import typer

from ....core.config import override_settings
from ....core.i18n.render import tr
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_runtime_profile, isolated_sessionless_storage_root
from .._common import draft_by_id

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


# ---------------------------------------------------------------------------
# contract / contract — draft_id_not_found localized error
# ---------------------------------------------------------------------------


@pytest.fixture
def _active_profile_env(tmp_path: Path) -> Iterator[Path]:
    """Active-profile runtime with CLI directories isolated; no drafts present."""
    with override_settings(cadrumo_output_language="en"), isolated_cli_runtime_profile(tmp_path=tmp_path) as runtime:
        yield runtime.storage_root


def test_draft_by_id_raises_bad_parameter_for_unknown_id(
    _active_profile_env: Path,
) -> None:
    """draft_by_id raises typer.BadParameter for a nonexistent draft ID."""
    with pytest.raises(typer.BadParameter):
        draft_by_id("nonexistent-draft-id-xyz")


def test_draft_by_id_error_message_matches_locale_catalogue(
    _active_profile_env: Path,
) -> None:
    """The raised message is sourced from the locale catalogue, not a raw f-string."""
    draft_id = "nonexistent-draft-id-xyz"
    expected = tr("cli.common.errors.draft_id_not_found", draft_id=draft_id)

    with pytest.raises(typer.BadParameter) as exc_info:
        draft_by_id(draft_id)

    assert str(exc_info.value) == expected
    # Guard: the old hard-coded literal must not appear.
    assert f"draft id {draft_id!r} not found" not in str(exc_info.value)


def test_draft_by_id_error_message_contains_draft_id_interpolation(
    _active_profile_env: Path,
) -> None:
    """The error message includes the actual draft_id value."""
    draft_id = "abc-123"
    with pytest.raises(typer.BadParameter) as exc_info:
        draft_by_id(draft_id)

    assert draft_id in str(exc_info.value)


# ---------------------------------------------------------------------------
# contract / contract — no_active_profile_error_value localized in text + JSON channels
# ---------------------------------------------------------------------------


@pytest.fixture
def _sessionless_env(tmp_path: Path) -> Iterator[Path]:
    """Pristine storage root with no profile, English locale."""
    with override_settings(cadrumo_output_language="en"), isolated_sessionless_storage_root(tmp_path=tmp_path) as root:
        yield root


# The localized cli.config.errors.no_active_profile refusal embeds this
# locale-invariant next-step command; every cold-start channel must surface it.
_EXPECTED_NEXT_COMMAND = "aeat config profile create NAME"


def test_active_profile_or_exit_locale_key_resolves_to_real_string() -> None:
    """The catalogue provides a non-placeholder value for the refusal key production requests."""
    message = tr("cli.config.errors.no_active_profile")

    # The key must not fall back to the dotted-key literal (unresolved placeholder).
    assert message != "cli.config.errors.no_active_profile"
    assert message.strip()
    assert _EXPECTED_NEXT_COMMAND in message


def test_active_profile_or_exit_emits_localized_payload_in_text_channel(
    _sessionless_env: Path,
) -> None:
    """A CLI verb reaching the no-active-profile refusal emits actionable next-step text."""
    result = invoke_cached_cli(["app", "ledger", "list"])

    assert result.exit_code != 0
    assert _EXPECTED_NEXT_COMMAND in result.output


def test_active_profile_or_exit_emits_localized_payload_in_json_channel(
    _sessionless_env: Path,
) -> None:
    """A CLI verb reaching the no-active-profile refusal carries the guidance in JSON."""
    result = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])

    assert result.exit_code != 0
    assert _EXPECTED_NEXT_COMMAND in result.output
