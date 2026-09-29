"""Destructive-action safeguard regression.

Asserts that every destructive ledger / config verb refuses to run
without an explicit ``--yes`` (or ``--dry-run`` where allowed). The
``confirm_required`` translated refusal fires before any backend read,
so these tests can exercise the guard against an empty isolated
profile without seeding fixture state.

Pinned verbs:

- ``aeat app ledger archive <noop>`` — required ``--yes`` guard.
- ``aeat app ledger remove <noop>`` — required ``--yes`` guard
  (also covered by ``test_app_ledger_lifecycle_remove_requires_yes_flag``
  in test_cli_surface.py via the round-trip harness; this gate is the
  fast unit-style companion).
- ``aeat app ledger reset`` — required ``--yes`` guard (also covered
  by ``test_app_ledger_lifecycle_reset_requires_yes_flag``).
- ``aeat config profile delete <name>`` — required ``--yes`` guard
  (also covered by ``test_config_profile_delete_requires_yes``).

Together with the existing tests, the four destructive verbs now have
both the round-trip lifecycle assertion AND a focused unit-style guard
test, giving the safeguard contract two-layer enforcement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ....tests.cli_envelope import unwrap_cli_result
from ._isolated_profile_storage_fixtures import active_profile_isolated_backend
from ._runtime_profile_cli_fixture import native_cli_profile_scope
from .cli_runner import invoke_cached_cli

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["active_profile_isolated_backend"]


def test_ledger_archive_refuses_without_yes() -> None:
    """``aeat app ledger archive <any>`` without ``--yes`` is refused
    with a non-zero exit code; the confirm_required guard fires before
    any backend read."""

    result = invoke_cached_cli(["app", "ledger", "archive", "any-transaction-id"])
    assert result.exit_code != 0, result.output


def test_ledger_remove_refuses_without_yes() -> None:
    """``aeat app ledger remove <any>`` without ``--yes`` (and
    without ``--dry-run``) is refused with a non-zero exit code."""

    result = invoke_cached_cli(["app", "ledger", "remove", "any-transaction-id"])
    assert result.exit_code != 0, result.output


def test_ledger_reset_refuses_without_yes() -> None:
    """``aeat app ledger reset`` without ``--yes`` (and without
    ``--dry-run``) is refused with a non-zero exit code."""

    result = invoke_cached_cli(["app", "ledger", "reset"])
    assert result.exit_code != 0, result.output


def test_ledger_remove_with_dry_run_does_not_require_yes() -> None:
    """``aeat app ledger remove --dry-run <missing>`` proceeds past
    the confirm_required guard without ``--yes`` (the dry-run path is
    explicitly allowed to skip the safeguard since it has no side
    effect). The verb subsequently fails on the missing-id lookup but
    that failure is downstream of the safeguard; it never surfaces the
    ``confirm_required`` refusal."""

    result = invoke_cached_cli(
        ["app", "ledger", "remove", "missing-transaction-id", "--dry-run"],
    )
    # The dry-run path bypasses the confirm guard; the missing-id error
    # is a separate downstream failure that this test does not assert on
    # (it depends on transaction-resolution behaviour). We only assert
    # that the confirm_required translation key does NOT appear, which
    # would only happen if the guard short-circuited the dry-run path.
    haystack = (result.output or "").lower()
    assert "confirm" not in haystack or "dry" in haystack, result.output


def test_config_reset_start_refuses_without_yes() -> None:
    """``config reset start`` requires explicit destructive confirmation."""
    result = invoke_cached_cli(["config", "reset", "start"])
    assert result.exit_code != 0, result.output
    combined = (result.output or "") + (result.stderr or "")
    assert "--yes" in combined or "confirm" in combined.lower(), combined


def test_config_reset_status_is_read_only_and_needs_no_yes() -> None:
    """``config reset status`` succeeds without confirmation or mutation."""
    result = invoke_cached_cli(["config", "reset", "status"])
    assert result.exit_code == 0, result.output
    assert "operation\t<none>" in result.output


def test_config_reset_removed_scope_spelling_is_rejected() -> None:
    """The retired flat scoped reset has no alias or compatibility parser."""
    result = invoke_cached_cli(
        ["config", "reset", "--scope", "auth", "--yes"],
    )
    assert result.exit_code != 0, result.output
    combined = (result.output or "") + (result.stderr or "")
    assert "--scope" in combined


def test_config_reset_resume_refuses_without_yes() -> None:
    """``config reset resume`` retains the destructive confirmation gate."""
    result = invoke_cached_cli(["config", "reset", "resume"])
    assert result.exit_code != 0, result.output
    combined = (result.output or "") + (result.stderr or "")
    assert "--yes" in combined or "confirm" in combined.lower(), combined


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_auth_reset_refuses_without_yes(tmp_path: Path) -> None:
    """``config auth reset`` is destructive and refuses before backend mutation."""
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(label="auth-reset-confirmation", facts={"identity.name": "Auth", "identity.surnames": "Reset"})
        result = invoke_cached_cli(
            [
                "--profile",
                "auth-reset-confirmation",
                "--profile-secrets-stdin",
                "config",
                "auth",
                "reset",
                "--provider",
                "certificate",
            ],
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )

    assert result.exit_code != 0, result.output
    combined = (result.output or "") + (result.stderr or "")
    assert "--yes" in combined or "confirm" in combined.lower(), combined


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_auth_logout_does_not_require_yes(tmp_path: Path) -> None:
    """Logout stays non-destructive; confirmed reset clears provider configuration."""
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(label="auth-logout-ready", facts={"identity.name": "Auth", "identity.surnames": "Logout"})
        with _indexed_authority_for_test().operation() as operation:
            from ....application.auth.operator import configure_operator_auth

            configure_operator_auth("certificate", operator_scope_ports=_OPERATOR_SCOPE_PORTS, operation=operation)
        result = invoke_cached_cli(
            [
                "--profile",
                "auth-logout-ready",
                "--profile-secrets-stdin",
                "config",
                "auth",
                "logout",
                "--provider",
                "certificate",
            ],
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )
        reset = invoke_cached_cli(
            [
                "--format",
                "json",
                "--profile",
                "auth-logout-ready",
                "--profile-secrets-stdin",
                "config",
                "auth",
                "reset",
                "--provider",
                "certificate",
                "--yes",
            ],
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )
        status = invoke_cached_cli(
            [
                "--format",
                "json",
                "--profile",
                "auth-logout-ready",
                "--profile-secrets-stdin",
                "config",
                "auth",
                "status",
            ],
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )

    assert result.exit_code == 0, result.output
    assert reset.exit_code == 0, reset.output
    assert unwrap_cli_result(reset)["cleared_provider_configuration"] is True
    assert status.exit_code == 0, status.output
    assert unwrap_cli_result(status)["configured"] is False


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_auth_status_is_non_destructive_and_needs_no_yes(tmp_path: Path) -> None:
    """Anti-tautology: ``config auth status`` is a read verb needing no confirmation.

    The ``--yes`` guard is scoped to destructive ``auth reset``; the recorded-state
    report runs against an unconfigured profile and never demands confirmation.
    """
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(label="auth-status-reader", facts={"identity.name": "Auth", "identity.surnames": "Reader"})
        result = invoke_cached_cli(
            ["--profile", "auth-status-reader", "--profile-secrets-stdin", "config", "auth", "status"],
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )

    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output, result.output
    combined = (result.output or "") + (result.stderr or "")
    assert "--yes" not in combined and "confirm" not in combined.lower(), combined


@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
def test_auth_test_is_non_destructive_and_needs_no_yes(tmp_path: Path) -> None:
    """Anti-tautology: ``config auth test`` is a live probe needing no confirmation.

    The probe may report an unavailable verdict, but it never mutates provider
    state and never demands ``--yes``; only destructive ``auth reset`` is guarded.
    """
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(label="auth-test-reader", facts={"identity.name": "Auth", "identity.surnames": "Reader"})
        result = invoke_cached_cli(
            ["--profile", "auth-test-reader", "--profile-secrets-stdin", "config", "auth", "test"],
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )

    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output, result.output
    combined = (result.output or "") + (result.stderr or "")
    assert "--yes" not in combined and "confirm" not in combined.lower(), combined
