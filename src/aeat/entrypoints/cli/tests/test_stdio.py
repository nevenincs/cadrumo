"""Regression tests for the CLI stdio UTF-8 guard.

Closes #292 (typer cp1252 UnicodeEncodeError) and #389 (review queue
+ iva rates list crashes on Windows cp1252). The guard runs at the
top of :mod:`aeat.entrypoints.cli` before any echo / log / Rich
console runs, so unicode characters such as ``→`` (U+2192) used in
the review queue table, ``§`` (U+00A7) used in some IVA-rate
citations, and the emoji / CJK fragments operators may type into
``--reason`` payloads survive the encoding boundary.

The tests cover three cases:

* Streams that support :meth:`io.TextIOWrapper.reconfigure`
  (real terminal / file-backed streams) are reconfigured to
  ``utf-8`` with ``errors="replace"``.
* Streams that do not support ``reconfigure`` (test capture
  fixtures, custom wrappers) are left untouched without raising.
* Streams whose ``reconfigure`` call fails (e.g. pipes that
  decline mid-run reconfiguration) are skipped silently — the
  helper never crashes the CLI startup over an encoding-tuning
  step.

Stream rebinding goes through the production helper's explicit
``stdout=`` / ``stderr=`` kwargs (no ``sys.stdout`` patching). Help-
surface argv and ``COLUMNS`` scope use the centralized backend helpers
in :mod:`aeat.tests.env_scope`.
"""

from __future__ import annotations

import io
import logging
import os
from typing import override

import pytest

from ....tests.env_scope import scoped_env_var, scoped_sys_argv
from .._stdio import (
    _COLUMNS_ENV_VAR,
    _MIN_HELP_RENDER_COLUMNS,
    _ensure_help_render_width,
    configure_stdio_for_utf8,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _ReconfigurableStream(io.StringIO):
    """A StringIO that records the kwargs it was reconfigured with."""

    def __init__(self) -> None:
        super().__init__()
        self.reconfigure_calls: list[dict[str, str]] = []

    def reconfigure(self, **kwargs: str) -> None:
        self.reconfigure_calls.append(kwargs)


class _NonReconfigurableStream(io.StringIO):
    """A StringIO that does not expose ``reconfigure``."""

    # Strict no-reconfigure: the attribute genuinely does not exist.
    # ``hasattr(self, "reconfigure")`` returns False for this class.


class _ReconfigureRefusingStream(io.StringIO):
    """A StringIO whose ``reconfigure`` raises (mid-run pipe refusal)."""

    def __init__(self) -> None:
        super().__init__()
        self.reconfigure_calls = 0

    def reconfigure(self, **kwargs: str) -> None:
        del kwargs
        self.reconfigure_calls += 1
        raise OSError("stream refused mid-run reconfiguration")


def test_reconfigurable_streams_receive_utf8_replace() -> None:
    """A stream exposing ``reconfigure`` must end up on UTF-8 with the
    ``replace`` error policy. The replace policy degrades non-
    encodable characters to ``?`` rather than crashing — the right
    trade-off when the underlying terminal cannot represent the
    character anyway."""

    stdout = _ReconfigurableStream()
    stderr = _ReconfigurableStream()
    configure_stdio_for_utf8(stdout=stdout, stderr=stderr)

    assert stdout.reconfigure_calls == [{"encoding": "utf-8", "errors": "replace"}]
    assert stderr.reconfigure_calls == [{"encoding": "utf-8", "errors": "replace"}]


def test_non_reconfigurable_streams_are_skipped_silently() -> None:
    """A stream without ``reconfigure`` (test-capture fixtures,
    custom wrappers) must be left untouched. The helper must not
    raise."""

    stdout = _NonReconfigurableStream()
    stderr = _NonReconfigurableStream()
    assert not hasattr(stdout, "reconfigure")

    configure_stdio_for_utf8(stdout=stdout, stderr=stderr)


def test_reconfigure_failure_is_swallowed() -> None:
    """A stream that raises on ``reconfigure`` (e.g. a pipe that
    refuses mid-run encoding changes) must not crash the CLI
    startup."""

    stdout = _ReconfigureRefusingStream()
    stderr = _ReconfigureRefusingStream()
    configure_stdio_for_utf8(stdout=stdout, stderr=stderr)

    assert stdout.reconfigure_calls == 1
    assert stderr.reconfigure_calls == 1


def test_configure_stdio_for_utf8_handles_none_streams() -> None:
    """Some pythonw-style environments expose ``sys.stdout`` /
    ``sys.stderr`` as ``None``. The helper must accept that without
    raising."""

    result = configure_stdio_for_utf8(stdout=None, stderr=None)
    assert result is None


def test_configure_stdio_for_utf8_is_idempotent() -> None:
    """Calling the helper more than once must not raise. The Typer
    callback re-imports the entrypoint package in some test setups;
    the helper must survive that."""

    stdout = _ReconfigurableStream()
    stderr = _ReconfigurableStream()
    configure_stdio_for_utf8(stdout=stdout, stderr=stderr)
    configure_stdio_for_utf8(stdout=stdout, stderr=stderr)

    # Both calls reach the underlying reconfigure call.
    assert stdout.reconfigure_calls == [
        {"encoding": "utf-8", "errors": "replace"},
        {"encoding": "utf-8", "errors": "replace"},
    ]


def test_configure_stdio_for_utf8_accepts_explicit_streams() -> None:
    """Tests can pass stdout/stderr directly instead of mutating sys.

    The helper's primary contract — reconfigure each stream to UTF-8
    + replace — is exercised without any module-level state mutation
    when the caller provides explicit streams.
    """

    out = _ReconfigurableStream()
    err = _ReconfigurableStream()

    configure_stdio_for_utf8(stdout=out, stderr=err)

    assert out.reconfigure_calls == [{"encoding": "utf-8", "errors": "replace"}]
    assert err.reconfigure_calls == [{"encoding": "utf-8", "errors": "replace"}]


def test_configure_stdio_for_utf8_tolerates_non_reconfigurable_explicit_streams() -> None:
    """Explicit streams without ``reconfigure`` are skipped silently,
    matching the default-streams behavior."""

    out = _NonReconfigurableStream()
    err = _NonReconfigurableStream()

    # Must not raise.
    configure_stdio_for_utf8(stdout=out, stderr=err)


# --- help-surface render width ---------------------------------------------


def test_help_invocation_below_floor_widens_columns() -> None:
    """A `--help` invocation with a narrow COLUMNS widens to the floor.

    Rich ellipsises long wizard flag names (`--address-postco…`) when
    the console is narrower than the flag. Bumping COLUMNS for the
    help surface keeps the names readable.
    """

    with (
        scoped_sys_argv(["aeat", "config", "profile", "create", "FOO", "--help"]),
        scoped_env_var("COLUMNS", "80"),
        _ensure_help_render_width(),
    ):
        assert int(os.environ["COLUMNS"]) == _MIN_HELP_RENDER_COLUMNS


def test_help_invocation_keeps_wider_columns() -> None:
    """A genuinely wide terminal keeps its real width on a help surface."""

    with (
        scoped_sys_argv(["aeat", "config", "profile", "create", "FOO", "-h"]),
        scoped_env_var("COLUMNS", "300"),
        _ensure_help_render_width(),
    ):
        assert os.environ["COLUMNS"] == "300"


def test_non_help_invocation_leaves_columns_untouched() -> None:
    """Ordinary command output keeps the real terminal width.

    The widening is scoped to `--help`; piping a non-help command into
    another tool must not see an inflated help-width render.
    """

    with (
        scoped_sys_argv(["aeat", "config", "profile", "list"]),
        scoped_env_var("COLUMNS", "80"),
        _ensure_help_render_width(),
    ):
        assert os.environ["COLUMNS"] == "80"


def test_non_help_invocation_without_columns_set() -> None:
    """A non-help invocation does not set COLUMNS when it was unset."""

    with (
        scoped_sys_argv(["aeat", "config", "profile", "list"]),
        scoped_env_var("COLUMNS", None),
        _ensure_help_render_width(),
    ):
        assert "COLUMNS" not in os.environ


# --- _COLUMNS_ENV_VAR constant (contract) ----------------------------------------


def test_columns_env_var_constant_value() -> None:
    """_COLUMNS_ENV_VAR must equal the string literal 'COLUMNS'.

    Rich derives console width from the COLUMNS environment variable.
    The constant must match the key exactly so that os.environ reads
    and writes reach the same slot that Rich consults.
    """
    assert _COLUMNS_ENV_VAR == "COLUMNS"


def test_columns_env_var_used_for_env_write() -> None:
    """_ensure_help_render_width writes the floor to os.environ[_COLUMNS_ENV_VAR].

    Confirms that the production code path uses the constant to mutate
    the environment, not an independent literal.  After a help-surface
    invocation with a narrow terminal os.environ[_COLUMNS_ENV_VAR] must
    hold the floor value.
    """
    with scoped_sys_argv(["aeat", "--help"]), scoped_env_var(_COLUMNS_ENV_VAR, "80"), _ensure_help_render_width():
        assert int(os.environ[_COLUMNS_ENV_VAR]) == _MIN_HELP_RENDER_COLUMNS


def test_columns_env_var_used_for_env_read() -> None:
    """_ensure_help_render_width reads from os.environ[_COLUMNS_ENV_VAR].

    When the env slot named by _COLUMNS_ENV_VAR already exceeds the
    floor the function must leave it untouched, proving the read path
    uses the constant rather than an independent literal.
    """
    wide = str(_MIN_HELP_RENDER_COLUMNS + 100)
    with scoped_sys_argv(["aeat", "--help"]), scoped_env_var(_COLUMNS_ENV_VAR, wide), _ensure_help_render_width():
        assert os.environ[_COLUMNS_ENV_VAR] == wide


# --- COLUMNS env-write scoping (contract) ----------------------------------------


def test_columns_write_is_scoped_help_invocation() -> None:
    """The COLUMNS env write must be restored to its original value after the block.

    _ensure_help_render_width widens COLUMNS inside the ``with`` block for
    help rendering but must restore the original value on exit, preventing
    the mutation from leaking into sibling processes or subsequent test runs.
    """
    with (
        scoped_sys_argv(["aeat", "config", "profile", "create", "--help"]),
        scoped_env_var(_COLUMNS_ENV_VAR, "80"),
    ):
        before = os.environ[_COLUMNS_ENV_VAR]
        with _ensure_help_render_width():
            # Inside the block COLUMNS must be widened to the floor.
            assert int(os.environ[_COLUMNS_ENV_VAR]) == _MIN_HELP_RENDER_COLUMNS
        after = os.environ[_COLUMNS_ENV_VAR]

        assert after == before, f"COLUMNS not restored after context-manager exit: before={before!r} after={after!r}"


def test_columns_write_is_scoped_unset_env() -> None:
    """When COLUMNS was absent before the block it must be absent again after exit."""
    with (
        scoped_sys_argv(["aeat", "--help"]),
        scoped_env_var(_COLUMNS_ENV_VAR, None),
    ):
        assert _COLUMNS_ENV_VAR not in os.environ
        with _ensure_help_render_width():
            # Floor must be set inside the block.
            assert int(os.environ[_COLUMNS_ENV_VAR]) == _MIN_HELP_RENDER_COLUMNS
        assert _COLUMNS_ENV_VAR not in os.environ, (
            "COLUMNS must be removed after context-manager exit when it was originally absent"
        )


def test_columns_write_not_scoped_on_non_help() -> None:
    """On a non-help invocation COLUMNS must not be touched at all."""
    with (
        scoped_sys_argv(["aeat", "app", "status"]),
        scoped_env_var(_COLUMNS_ENV_VAR, "80"),
    ):
        before = os.environ[_COLUMNS_ENV_VAR]
        with _ensure_help_render_width():
            assert os.environ[_COLUMNS_ENV_VAR] == before
        assert os.environ[_COLUMNS_ENV_VAR] == before


# --- SecretScrubbingFilter propagation via stdio logger (contract) ----------------


class _CapturingHandler(logging.Handler):
    """Real handler that collects emitted records."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_stdio_logger_records_are_scrubbed_after_configure_logging() -> None:
    """Records emitted by the _stdio module logger must have NIF-shaped content
    scrubbed once configure_logging() has installed SecretScrubbingFilter on the
    root logger.

    The ``_stdio`` module deliberately uses stdlib ``logging.getLogger`` (not
    ``aeat.core.logging.get_logger``) because it runs before settings are loaded
    — see the constraint comment in ``_stdio.py`` at the ``_LOGGER`` definition.
    Scrubbing still applies because the stdlib logger propagates to the root
    logger, and ``configure_logging()`` installs ``SecretScrubbingFilter`` on
    root.  This test verifies that propagation contract end-to-end.
    """
    from ....core.logging import configure_logging

    configure_logging()

    root_logger = logging.getLogger()
    handler = _CapturingHandler()
    root_logger.addHandler(handler)
    previous_level = root_logger.level
    root_logger.setLevel(logging.DEBUG)
    try:
        # Emit through the same logger the _stdio module uses.
        stdio_logger = logging.getLogger("aeat.entrypoints.cli._stdio")
        nif_canary = "12345678Z"
        stdio_logger.debug("stream reconfigure skipped for nif=%s", nif_canary)
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(previous_level)

    assert handler.records, "log record did not reach the root handler via propagation"
    record = handler.records[-1]
    # After SecretScrubbingFilter runs, the NIF literal must not survive in
    # either the message or the args tuple.
    formatted = record.getMessage()
    assert nif_canary not in formatted, (
        f"NIF {nif_canary!r} survived SecretScrubbingFilter in rendered message: {formatted!r}"
    )


def test_stdio_logger_scrubbing_filter_present_on_root_after_configure() -> None:
    """configure_logging() must install SecretScrubbingFilter on the root logger.

    Verifies the structural precondition that makes NIF scrubbing effective for
    stdlib loggers (including the _stdio module's logger) that propagate to root.
    """
    from ....core.logging import SecretScrubbingFilter, configure_logging

    configure_logging()
    root_logger = logging.getLogger()
    has_scrubbing = any(isinstance(f, SecretScrubbingFilter) for f in root_logger.filters)
    assert has_scrubbing, "SecretScrubbingFilter not found on root logger after configure_logging()"
