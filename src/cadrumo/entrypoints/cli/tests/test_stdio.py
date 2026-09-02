"""Regression tests for the CLI stdio UTF-8 guard.

Closes #292 (typer cp1252 UnicodeEncodeError) and #389 (review queue
+ iva rates list crashes on Windows cp1252). The guard runs at the
top of :mod:`cadrumo.entrypoints.cli` before any echo / log / Rich
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
``stdout=`` / ``stderr=`` kwargs (no ``sys.stdout`` patching).

Also covers ``disable_rich_cli_rendering``: Typer/Click's Rich-based
help, error, and traceback rendering is disabled globally so option
tables render as plain text regardless of the invoking terminal's
real width.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import override

import pytest
import typer
import typer.core

from .._stdio import configure_stdio_for_utf8, disable_rich_cli_rendering

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_reconfigurable_streams_receive_utf8_replace(tmp_path: Path) -> None:
    """A stream exposing ``reconfigure`` must end up on UTF-8 with the
    ``replace`` error policy. The replace policy degrades non-
    encodable characters to ``?`` rather than crashing — the right
    trade-off when the underlying terminal cannot represent the
    character anyway."""

    with (
        (tmp_path / "stdout.txt").open("w", encoding="cp1252", errors="strict") as stdout,
        (tmp_path / "stderr.txt").open("w", encoding="cp1252", errors="strict") as stderr,
    ):
        configure_stdio_for_utf8(stdout=stdout, stderr=stderr)

        assert stdout.encoding == "utf-8"
        assert stdout.errors == "replace"
        assert stderr.encoding == "utf-8"
        assert stderr.errors == "replace"


def test_non_reconfigurable_streams_are_skipped_silently() -> None:
    """A stream without ``reconfigure`` (test-capture fixtures,
    custom wrappers) must be left untouched. The helper must not
    raise."""

    stdout = io.StringIO()
    stderr = io.StringIO()
    assert not hasattr(stdout, "reconfigure")

    configure_stdio_for_utf8(stdout=stdout, stderr=stderr)


def test_reconfigure_failure_is_swallowed(tmp_path: Path) -> None:
    """A stream that raises on ``reconfigure`` (e.g. a pipe that
    refuses mid-run encoding changes) must not crash the CLI
    startup."""

    stdout_path = tmp_path / "stdout.txt"
    stderr_path = tmp_path / "stderr.txt"
    stdout_path.write_text("already read", encoding="cp1252")
    stderr_path.write_text("already read", encoding="cp1252")
    with (
        stdout_path.open("r", encoding="cp1252", errors="strict") as stdout,
        stderr_path.open("r", encoding="cp1252", errors="strict") as stderr,
    ):
        assert stdout.read(1) == "a"
        assert stderr.read(1) == "a"
        configure_stdio_for_utf8(stdout=stdout, stderr=stderr)

        assert stdout.encoding == "cp1252"
        assert stdout.errors == "strict"
        assert stderr.encoding == "cp1252"
        assert stderr.errors == "strict"


def test_configure_stdio_for_utf8_handles_none_streams() -> None:
    """Some pythonw-style environments expose ``sys.stdout`` /
    ``sys.stderr`` as ``None``. The helper must accept that without
    raising."""

    result = configure_stdio_for_utf8(stdout=None, stderr=None)
    assert result is None


def test_configure_stdio_for_utf8_is_idempotent(tmp_path: Path) -> None:
    """Calling the helper more than once must not raise. The Typer
    callback re-imports the entrypoint package in some test setups;
    the helper must survive that."""

    with (
        (tmp_path / "stdout.txt").open("w", encoding="cp1252", errors="strict") as stdout,
        (tmp_path / "stderr.txt").open("w", encoding="cp1252", errors="strict") as stderr,
    ):
        configure_stdio_for_utf8(stdout=stdout, stderr=stderr)
        configure_stdio_for_utf8(stdout=stdout, stderr=stderr)

        assert stdout.encoding == "utf-8"
        assert stdout.errors == "replace"


def test_configure_stdio_for_utf8_accepts_explicit_streams(tmp_path: Path) -> None:
    """Tests can pass stdout/stderr directly instead of mutating sys.

    The helper's primary contract — reconfigure each stream to UTF-8
    + replace — is exercised without any module-level state mutation
    when the caller provides explicit streams.
    """

    with (
        (tmp_path / "out.txt").open("w", encoding="cp1252", errors="strict") as out,
        (tmp_path / "err.txt").open("w", encoding="cp1252", errors="strict") as err,
    ):
        configure_stdio_for_utf8(stdout=out, stderr=err)

        assert out.encoding == "utf-8"
        assert err.encoding == "utf-8"


def test_configure_stdio_for_utf8_tolerates_non_reconfigurable_explicit_streams() -> None:
    """Explicit streams without ``reconfigure`` are skipped silently,
    matching the default-streams behavior."""

    out = io.StringIO()
    err = io.StringIO()

    # Must not raise.
    configure_stdio_for_utf8(stdout=out, stderr=err)


# --- Rich-disabled plain-text rendering -------------------------------------


def test_disable_rich_cli_rendering_flips_typer_has_rich() -> None:
    """disable_rich_cli_rendering() flips the module-level flag every Typer/Click
    render call reads live (help, parse errors, tracebacks), for every Typer()
    app in the command tree — not a per-instance setting."""

    original = typer.core.HAS_RICH
    try:
        typer.core.HAS_RICH = True
        disable_rich_cli_rendering()
        assert typer.core.HAS_RICH is False
    finally:
        typer.core.HAS_RICH = original


def test_console_help_invocation_renders_plain_text_with_full_flag_names(tmp_path: Path) -> None:
    """The real console entry point must render ``--help`` as plain text.

    Persona runs invoke ``aeat ... --help`` through the console script. With
    Rich disabled, Click's plain formatter wraps long option names onto their
    own line instead of ellipsising them, and never emits box-drawing
    characters, regardless of how narrow the invoking terminal is.
    """

    aeat_exe = shutil.which("aeat")
    assert aeat_exe is not None, "the aeat console script must be installed for this test"
    env = {key: value for key, value in os.environ.items() if not key.startswith("AEAT_")}
    env.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
            "CADRUMO_SECRET_PASSPHRASE": "help-width-test-passphrase",
            "COLUMNS": "80",
        },
    )

    result = subprocess.run(  # noqa: S603 - test intentionally invokes the resolved aeat console script.
        [aeat_exe, "--language", "en", "config", "profile", "create", "--help"],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "--does-intracomunitario" in result.stdout
    assert "--third-party-transactions-above-347-threshold" in result.stdout
    assert "--iva-intracommunity-operations-exceed-50000-eur" in result.stdout
    assert "--irpf-estimation-regime" in result.stdout
    assert "--uses-objective-estimation-irpf" not in result.stdout
    assert "--does-intracomu…" not in result.stdout
    assert "--third-party-tr…" not in result.stdout
    assert "--iva-intracommu…" not in result.stdout
    for box_drawing_char in "┌┐└┘│─":
        assert box_drawing_char not in result.stdout, (
            f"Rich box-drawing character {box_drawing_char!r} found in plain-text help output"
        )


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
    ``cadrumo.core.logging.get_logger``) because it runs before settings are loaded
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
        stdio_logger = logging.getLogger("cadrumo.entrypoints.cli._stdio")
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
