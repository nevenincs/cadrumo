"""Integration boundary test: AeatError propagation through command_error_boundary.

Verifies the full round-trip without mocks, patches, stubs, or fakes:

  CLI invocation (CliRunner) → real AeatError subclass raised in callback
  → command_error_boundary catches → _emit_error_and_exit → typer.Exit(code=N)
  → CliRunner captures exit_code → assertion against live ERROR_REGISTRY

The existing :mod:`test_error_registry_contract` module verifies that
representative errors render with the correct grep-stable prefix
(REFUSED, AUTH, INTEGRITY …) for all :class:`ErrorCategory` values.

This module verifies the *boundary mechanism itself*: that the decorator
wired at import time in :mod:`aeat.entrypoints.cli.__init__` catches the
error, looks it up in the live registry, and terminates with the
category-registered exit code — not merely that the registry has entries.

Expected exit codes are read from the live :func:`get_error_exit_code`
at test runtime, not hardcoded.  Category assertions are preconditions
that lock the test to the authoritative registry record.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from ...core.errors import (
    ErrorCategory,
    get_error_exit_code,
    get_registered_error_code,
)
from . import app
from ._log_levels import LogLevelResolutionError

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

# Typer's CliRunner merges sys.stderr into result.output by default so that
# write_stderr() calls in _emit_error_and_exit are captured in result.output.
_RUNNER = CliRunner()

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
            # Env-var path: AEAT_LOG_LEVEL set to a value not in the allowed
            # set; resolve_log_level() raises on the env-var parse branch.
            ["config", "repair"],
            "AEAT_LOG_LEVEL",
            "NOT_A_VALID_LEVEL",
            "AEAT_LOG_LEVEL env set to an unrecognised value",
        ),
    ],
    ids=["flag-collision", "invalid-env"],
)
def test_log_level_resolution_error_exits_refused(
    args: list[str],
    env_key: str | None,
    env_val: str | None,
    trigger_description: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LogLevelResolutionError raised in the root callback exits with the REFUSED code.

    The test verifies three things:
    1. The CLI runner receives a non-zero exit code (boundary fired).
    2. The exit code equals ``get_error_exit_code(ErrorCategory.REFUSED)``,
       the value the live registry declares for this error class.
    3. The captured output contains the ``REFUSED`` prefix that operators
       use to grep structured error payloads.

    No mocks.  The error is raised through real business logic in
    :func:`aeat.entrypoints.cli._log_levels.resolve_log_level` which is
    called by the production root-app callback wrapped by
    :func:`aeat.entrypoints.cli._errors.command_error_boundary`.

    ``catch_exceptions=False`` ensures that if the boundary fails to catch
    the error, the runner re-raises it and the test fails with a traceback
    rather than a misleading wrong-exit-code assertion.
    """
    if env_key is not None and env_val is not None:
        monkeypatch.setenv(env_key, env_val)

    result = _RUNNER.invoke(app, args, catch_exceptions=False)

    assert result.exit_code == _REFUSED_EXIT, (
        f"CLI boundary did not produce the REFUSED exit for {trigger_description!r}: "
        f"got exit_code={result.exit_code!r}, want {_REFUSED_EXIT!r}. "
        f"Output:\n{result.output}"
    )
    assert "REFUSED" in result.output, (
        f"Stderr envelope must contain the REFUSED prefix for {trigger_description!r}. Output:\n{result.output}"
    )
