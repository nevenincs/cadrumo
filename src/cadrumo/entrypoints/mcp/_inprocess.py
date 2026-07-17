"""Warm in-process CLI verb execution for the MCP serving path.

Every MCP tool call historically spawns a fresh ``aeat`` subprocess, so every
per-process cost - interpreter start, the pydantic application-import floor, the
registry fingerprint walk, TOML parse, and validation - is re-paid per call, a
hard floor above one second on Windows regardless of caching (research option
R6). This module serves a verb through ONE warm in-process runtime instead: the
server process already imported the CLI package (the tool descriptors are built
from it) and warmed the registry authority ``lru_cache``, so a repeat call pays
only the calculation engine, storage, and envelope emit.

The load-bearing guarantee is byte-identical envelope parity with the subprocess
transport. :func:`run_cli_in_process` invokes the EXACT command the subprocess
would - ``get_command(app).main(..., standalone_mode=True)`` - so the same
command functions, the same ``_emit_envelope`` / ``emit_json_success`` builders,
and the same per-callback error boundary produce the same stdout success
document and the same stderr error document; the ONLY difference from the
subprocess is that the terminating ``SystemExit`` is caught here rather than
ending a process. Envelope assembly is never re-implemented
(``composition-service-no-parallel-write-path``); this module only chooses where
the CLI runs, never what it emits. :func:`parse_cli_envelope` is the single
transport-neutral parser both paths feed their completed run through, so the two
transports cannot fork the result shape.

The transport split is explicit and tested, never silent. The AEAT-sede /
open-world (``LIVE``) family spawns a Playwright browser child that needs the
supervised subprocess's process-tree kill and the operator progress sink, so it
stays on the subprocess transport by design (:func:`tier_runs_in_process`).
``READ`` and ``MUTATE`` (local compute plus encrypted storage) run warm
in-process.
"""

from __future__ import annotations

import contextlib
import io
import json
import threading
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from ...core import PRODUCT_IDENTITY
from ._call_runtime import CallTier
from ._input_schema import VerbInputSchema, cli_argv_for

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

# The CLI writes its JSON envelope to the PROCESS-GLOBAL ``sys.stdout`` and its
# error document to ``sys.stderr``. Over the MCP stdio transport the server's own
# stdout IS the JSON-RPC client pipe, so an in-process call MUST capture those
# streams (``contextlib.redirect_stdout`` swaps the global) before a byte reaches
# the wire. Because the redirect target is a process global, two concurrent
# in-process calls would clobber each other's capture and corrupt the pipe, so
# the whole capture-and-run section is serialised under this lock. The bounded
# call concurrency (the ``_call_runtime`` capacity limiter) still lets the event
# loop and any subprocess-transport calls proceed; only the in-process
# stream-capture window is mutually exclusive.
_CAPTURE_LOCK = threading.Lock()

# Tiers that CANNOT run in-process. The AEAT-sede / open-world family runs a
# Playwright portal pull that spawns a browser child; only the supervised
# subprocess can process-tree-kill it on timeout and route its Cl@ve progress
# banner to the operator, so it stays on the subprocess transport. Local READ and
# MUTATE verbs are bounded in-process compute and run warm.
_SUBPROCESS_ONLY_TIERS: frozenset[CallTier] = frozenset({CallTier.LIVE})


def tier_runs_in_process(tier: CallTier) -> bool:
    """Return whether a call of ``tier`` may run through the warm in-process runtime.

    ``LIVE`` (AEAT-sede / open-world) stays on the supervised subprocess; every
    other tier runs in-process.
    """
    return tier not in _SUBPROCESS_ONLY_TIERS


class CompletedCliRun(BaseModel):
    """One completed CLI dispatch, transport-agnostic.

    Mirrors the observable surface a supervised subprocess run exposes - the
    captured ``stdout``/``stderr`` text and the process ``returncode`` - so the
    in-process and subprocess transports parse into an envelope through the one
    shared :func:`parse_cli_envelope`.
    """

    model_config = _STRICT_FROZEN

    stdout: str
    stderr: str
    returncode: int


def _exit_code(code: object) -> int:
    """Coerce a caught ``SystemExit.code`` to an integer return code.

    ``standalone_mode=True`` ends every path in ``sys.exit``: ``None`` (clean
    exit) is ``0``, an ``int`` passes through, and a string message (unusual for
    the CLI, which exits with typed codes) reads as a generic failure ``1`` -
    matching the shell convention a subprocess would report.
    """
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


def run_cli_in_process(argv_tail: Sequence[str]) -> CompletedCliRun:
    """Run the real ``aeat`` Typer app in-process, capturing its output streams.

    ``argv_tail`` is the argv the subprocess transport would pass after the
    executable - ``["--format", "json", *cli_path, *positional, *options]`` from
    :func:`~entrypoints.mcp._input_schema.cli_argv_for`. The command is dispatched
    exactly as the console entry point does
    (``get_command(app).main(..., standalone_mode=True)``), so the whole CLI
    pipeline - root callback, bucket-session activation, the verb body, the
    envelope emit, and the error boundary - runs identically; the terminating
    ``SystemExit`` (which would end the subprocess) is caught and its code
    returned instead. stdout and stderr are captured under the module capture lock
    so no CLI output reaches the MCP JSON-RPC pipe and concurrent calls cannot
    interleave their redirects.

    Returns:
        The :class:`CompletedCliRun` carrying the captured streams and code.
    """
    from typer.main import get_command

    from ..cli import app

    command = get_command(app)
    out = io.StringIO()
    err = io.StringIO()
    returncode = 0
    with _CAPTURE_LOCK, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            command.main(
                args=list(argv_tail),
                prog_name=PRODUCT_IDENTITY.cli_executable,
                standalone_mode=True,
            )
        except SystemExit as exit_request:
            returncode = _exit_code(exit_request.code)
    return CompletedCliRun(stdout=out.getvalue(), stderr=err.getvalue(), returncode=returncode)


def dispatch_verb_in_process(schema: VerbInputSchema, arguments: dict[str, object]) -> CompletedCliRun:
    """Build a verb's argv from its schema and run it through the warm runtime.

    The argv is reconstructed from the per-verb input schema and the named
    ``arguments`` through the same
    :func:`~entrypoints.mcp._input_schema.cli_argv_for` the subprocess transport
    uses, so both transports dispatch the identical command line.
    """
    return run_cli_in_process(cli_argv_for(schema, arguments))


def parse_cli_envelope(run: CompletedCliRun) -> tuple[dict[str, object], bool]:
    """Parse a completed CLI run into its JSON envelope and error flag.

    The single transport-neutral parser: the CLI emits its success envelope on
    stdout and its error document on stderr, so the payload is the non-empty
    stdout, falling back to stderr. A body that is not JSON (an unexpected crash
    before the envelope emit) becomes a typed error envelope carrying the raw
    text. ``is_error`` is true when the envelope declares an error status or the
    run exited non-zero. Both transports feed their run through this one function,
    so a subprocess and an in-process call of the same verb cannot fork the
    result shape.

    Returns:
        The envelope mapping and its error flag.
    """
    raw = run.stdout.strip() or run.stderr.strip()
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "error", "raw": raw}, True
    if not isinstance(envelope, dict):
        return {"status": "error", "raw": raw}, True
    is_error = envelope.get("status") == "error" or run.returncode != 0
    return envelope, bool(is_error)
