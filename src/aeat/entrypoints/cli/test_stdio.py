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

from aeat.entrypoints.cli._stdio import configure_stdio_for_utf8

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
