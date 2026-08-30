"""Integration boundary test: CadrumoError propagation through command_error_boundary.

Verifies the full round-trip without mocks, patches, stubs, or fakes:

  shared CLI runner invocation → real CadrumoError subclass raised in callback
  → command_error_boundary catches → _emit_error_and_exit → typer.Exit(code=N)
  → runner captures exit_code → assertion against live ERROR_REGISTRY

The existing :mod:`test_error_registry_contract` module verifies that
representative errors render with the correct grep-stable prefix
(REFUSED, AUTH, INTEGRITY …) for all :class:`ErrorCategory` values.

This module verifies the *boundary mechanism itself*: that the decorator
wired at import time in :mod:`cadrumo.entrypoints.cli.__init__` catches the
error, looks it up in the live registry, and terminates with the
category-registered exit code — not merely that the registry has entries.

Expected exit codes are read from the live :func:`get_error_exit_code`
at test runtime, not hardcoded.  Category assertions are preconditions
that lock the test to the authoritative registry record.
"""

from __future__ import annotations

import json

import pytest

from ....core.errors.error_codes import ErrorCategory, get_error_exit_code, get_registered_error_code
from ....tests.cli_runner import invoke_cached_cli
from .._log_levels import LogLevelResolutionError

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# ---------------------------------------------------------------------------
# Precondition: confirm the registry record the tests depend on.
# These assertions run at collection time; if the registry is changed the
# parametrized tests below fail with a clear precondition message.
# ---------------------------------------------------------------------------

_LOG_LEVEL_CODE = get_registered_error_code(LogLevelResolutionError("probe"))
assert _LOG_LEVEL_CODE.category == ErrorCategory.REFUSED, (
    "Registry precondition violated: LogLevelResolutionError must be REFUSED. "
    "Update this test file if the category changes."
)
_REFUSED_EXIT: int = get_error_exit_code(ErrorCategory.REFUSED)


# ---------------------------------------------------------------------------
# Integration probes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "env_key", "env_val", "trigger_description"),
    [
        (
            # Flag collision: the root-app callback calls resolve_log_level() which
            # raises when --quiet and --verbose are both set.  A real mounted
            # command path is used so Click parses through the root callback.
            ["--quiet", "--verbose", "config", "repair"],
            None,
            None,
            "--quiet/--verbose mutual-exclusion flag collision",
        ),
        (
            # Env-var path: CADRUMO_LOG_LEVEL set to a value not in the allowed
            # set; resolve_log_level() raises on the env-var parse branch.
            ["config", "repair"],
            "CADRUMO_LOG_LEVEL",
            "NOT_A_VALID_LEVEL",
            "CADRUMO_LOG_LEVEL env set to an unrecognised value",
        ),
    ],
    ids=["flag-collision", "invalid-env"],
)
def test_log_level_resolution_error_exits_refused(
    args: list[str],
    env_key: str | None,
    env_val: str | None,
    trigger_description: str,
) -> None:
    """LogLevelResolutionError raised in the root callback exits with the REFUSED code.

    The test verifies three things:
    1. The CLI runner receives a non-zero exit code (boundary fired).
    2. The exit code equals ``get_error_exit_code(ErrorCategory.REFUSED)``,
       the value the live registry declares for this error class.
    3. The captured output contains the ``REFUSED`` prefix that operators
       use to grep structured error payloads.

    No mocks. No monkeypatch (per CLAUDE.md mandate). The env-var case
    pins state via ``override_settings(cadrumo_log_level=env_val)`` so the
    real production resolver sees the override; the flag-collision case
    needs no override and runs against the default Settings.

    ``catch_exceptions=False`` ensures that if the boundary fails to catch
    the error, the runner re-raises it and the test fails with a traceback
    rather than a misleading wrong-exit-code assertion.
    """
    from ....core.config import override_settings

    # The refusal prefix asserted below is catalogue text, and the product
    # default output language is Spanish, so the language is pinned rather than
    # assumed. Without this the assertion reads "Refused." against "Rechazado."
    # and fails on a correctly-rendered envelope.
    overrides: dict[str, str] = {"cadrumo_output_language": "en"}
    if env_key is not None and env_val is not None:
        # Translate the env-var name to the Settings field name. The
        # parametrise table currently only exercises CADRUMO_LOG_LEVEL.
        overrides[env_key.lower()] = env_val
    with override_settings(**overrides):
        result = invoke_cached_cli(args, catch_exceptions=False)

    assert result.exit_code == _REFUSED_EXIT, (
        f"CLI boundary did not produce the REFUSED exit for {trigger_description!r}: "
        f"got exit_code={result.exit_code!r}, want {_REFUSED_EXIT!r}. "
        f"Output:\n{result.output}"
    )
    assert "Refused." in result.output, (
        f"Stderr envelope must carry the sentence-case `Refused.` prefix for {trigger_description!r}. "
        f"Output:\n{result.output}"
    )


def test_invalid_log_level_environment_value_reaches_the_json_boundary_with_no_action() -> None:
    """The configuration-value refusal keeps its typed no-action contract at the root boundary."""
    from ....core.config import override_settings

    with override_settings(cadrumo_output_language="en", cadrumo_log_level="NOT_A_VALID_LEVEL"):
        result = invoke_cached_cli(["--format", "json", "config", "repair"], catch_exceptions=False)

    assert result.exit_code == _REFUSED_EXIT, result.output
    envelope = json.loads(result.output)
    assert envelope["error"]["action"] == {
        "failed_condition_id": "cli.log_level.environment_value.recognised",
        "evidence": [
            {
                "condition_id": "cli.log_level.environment_value.recognised",
                "evidence_id": "cli.log_level.environment_value.recognised.observation",
                "provenance": "runtime_observation",
                "values": {
                    "environment_variable": "CADRUMO_LOG_LEVEL",
                    "environment_value_recognised": False,
                },
            }
        ],
        "action": None,
        "argument_bindings": [],
        "missing_argument_names": [],
        "conditionality": "not_applicable",
        "no_recovery_outcome": "operator_decision",
    }
