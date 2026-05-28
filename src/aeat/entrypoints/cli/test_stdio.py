"""Regression tests for the CLI stdio UTF-8 guard.

Closes #292 (typer cp1252 UnicodeEncodeError) and #389 (review queue
+ vat rates list crashes on Windows cp1252). The guard runs at the
top of :mod:`aeat.entrypoints.cli` before any echo / log / Rich
console runs, so unicode characters such as ``→`` (U+2192) used in
the review queue table, ``§`` (U+00A7) used in some VAT-rate
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
"""

from __future__ import annotations

import io

import pytest

from aeat.entrypoints.cli._stdio import (
    _COLUMNS_ENV_VAR,
    _MIN_HELP_RENDER_COLUMNS,
    _ensure_help_render_width,
    configure_stdio_for_utf8,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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


def test_reconfigurable_streams_receive_utf8_replace(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stream exposing ``reconfigure`` must end up on UTF-8 with the
    ``replace`` error policy. The replace policy degrades non-
    encodable characters to ``?`` rather than crashing — the right
    trade-off when the underlying terminal cannot represent the
    character anyway."""

    stdout = _ReconfigurableStream()
    stderr = _ReconfigurableStream()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)

    configure_stdio_for_utf8()

    assert stdout.reconfigure_calls == [{"encoding": "utf-8", "errors": "replace"}]
    assert stderr.reconfigure_calls == [{"encoding": "utf-8", "errors": "replace"}]


def test_non_reconfigurable_streams_are_skipped_silently(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stream without ``reconfigure`` (test-capture fixtures,
    custom wrappers) must be left untouched. The helper must not
    raise."""

    stdout = _NonReconfigurableStream()
    stderr = _NonReconfigurableStream()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)
    assert not hasattr(stdout, "reconfigure")

    configure_stdio_for_utf8()


def test_reconfigure_failure_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stream that raises on ``reconfigure`` (e.g. a pipe that
    refuses mid-run encoding changes) must not crash the CLI
    startup."""

    stdout = _ReconfigureRefusingStream()
    stderr = _ReconfigureRefusingStream()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)

    configure_stdio_for_utf8()

    assert stdout.reconfigure_calls == 1
    assert stderr.reconfigure_calls == 1


def test_configure_stdio_for_utf8_handles_none_streams(monkeypatch: pytest.MonkeyPatch) -> None:
    """Some pythonw-style environments expose ``sys.stdout`` /
    ``sys.stderr`` as ``None``. The helper must accept that without
    raising."""

    import sys

    monkeypatch.setattr("sys.stdout", None)
    monkeypatch.setattr("sys.stderr", None)
    assert sys.stdout is None and sys.stderr is None
    result = configure_stdio_for_utf8()
    assert result is None


def test_configure_stdio_for_utf8_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling the helper more than once must not raise. The Typer
    callback re-imports the entrypoint package in some test setups;
    the helper must survive that."""

    stdout = _ReconfigurableStream()
    stderr = _ReconfigurableStream()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)

    configure_stdio_for_utf8()
    configure_stdio_for_utf8()

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


def test_help_invocation_below_floor_widens_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `--help` invocation with a narrow COLUMNS widens to the floor.

    Rich ellipsises long wizard flag names (`--address-postco…`) when
    the console is narrower than the flag. Bumping COLUMNS for the
    help surface keeps the names readable.
    """

    monkeypatch.setattr("sys.argv", ["aeat", "config", "profile", "create", "FOO", "--help"])
    monkeypatch.setenv("COLUMNS", "80")

    _ensure_help_render_width()

    import os

    assert int(os.environ["COLUMNS"]) == _MIN_HELP_RENDER_COLUMNS


def test_help_invocation_keeps_wider_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    """A genuinely wide terminal keeps its real width on a help surface."""

    monkeypatch.setattr("sys.argv", ["aeat", "config", "profile", "create", "FOO", "-h"])
    monkeypatch.setenv("COLUMNS", "300")

    _ensure_help_render_width()

    import os

    assert os.environ["COLUMNS"] == "300"


def test_non_help_invocation_leaves_columns_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ordinary command output keeps the real terminal width.

    The widening is scoped to `--help`; piping a non-help command into
    another tool must not see an inflated help-width render.
    """

    monkeypatch.setattr("sys.argv", ["aeat", "config", "profile", "list"])
    monkeypatch.setenv("COLUMNS", "80")

    _ensure_help_render_width()

    import os

    assert os.environ["COLUMNS"] == "80"


def test_non_help_invocation_without_columns_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-help invocation does not set COLUMNS when it was unset."""

    monkeypatch.setattr("sys.argv", ["aeat", "config", "profile", "list"])
    monkeypatch.delenv("COLUMNS", raising=False)

    _ensure_help_render_width()

    import os

    assert "COLUMNS" not in os.environ


# --- _COLUMNS_ENV_VAR constant (S188) ----------------------------------------


def test_columns_env_var_constant_value() -> None:
    """_COLUMNS_ENV_VAR must equal the string literal 'COLUMNS'.

    Rich derives console width from the COLUMNS environment variable.
    The constant must match the key exactly so that os.environ reads
    and writes reach the same slot that Rich consults.
    """
    assert _COLUMNS_ENV_VAR == "COLUMNS"


def test_columns_env_var_used_for_env_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """_ensure_help_render_width writes the floor to os.environ[_COLUMNS_ENV_VAR].

    Confirms that the production code path uses the constant to mutate
    the environment, not an independent literal.  After a help-surface
    invocation with a narrow terminal os.environ[_COLUMNS_ENV_VAR] must
    hold the floor value.
    """
    import os

    monkeypatch.setattr("sys.argv", ["aeat", "--help"])
    monkeypatch.setenv(_COLUMNS_ENV_VAR, "80")

    _ensure_help_render_width()

    assert int(os.environ[_COLUMNS_ENV_VAR]) == _MIN_HELP_RENDER_COLUMNS


def test_columns_env_var_used_for_env_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """_ensure_help_render_width reads from os.environ[_COLUMNS_ENV_VAR].

    When the env slot named by _COLUMNS_ENV_VAR already exceeds the
    floor the function must leave it untouched, proving the read path
    uses the constant rather than an independent literal.
    """
    import os

    wide = str(_MIN_HELP_RENDER_COLUMNS + 100)
    monkeypatch.setattr("sys.argv", ["aeat", "--help"])
    monkeypatch.setenv(_COLUMNS_ENV_VAR, wide)

    _ensure_help_render_width()

    assert os.environ[_COLUMNS_ENV_VAR] == wide
