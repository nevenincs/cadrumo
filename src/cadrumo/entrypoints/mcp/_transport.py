"""Transport dispatch: turn a tool descriptor plus arguments into one outcome.

This is the SDK-independent layer that :mod:`entrypoints.mcp._server` composes to
run a verb. Local ``READ`` and ``MUTATE`` verbs run warm in-process
(:func:`~entrypoints.mcp._inprocess.dispatch_verb_in_process`); the AEAT-sede /
open-world ``LIVE`` family stays on the supervised subprocess
(:func:`~entrypoints.mcp._call_runtime.run_supervised`). Both transports return the
same :class:`SubprocessToolOutcome` and parse through the same
:func:`~entrypoints.mcp._inprocess.parse_cli_envelope`, so the envelope cannot fork
between them. :func:`_run_tool` is the single entry point the server's direct and
``execute`` paths share; it owns the fail-fast wedge handling that degrades a
warm-eligible verb to the subprocess transport (with a visible warning Notice)
rather than wedging the whole warm transport.
"""

from __future__ import annotations

import sys
import sysconfig
import threading
from dataclasses import dataclass
from pathlib import Path

from ...adapters.persistence.storage import close_active_bucket_session
from ...core import PRODUCT_IDENTITY
from ...core.config import load_settings
from ...core.external_constants import UTF_8_ENCODING
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ._call_runtime import CallTier, run_supervised, tier_for, timeout_seconds
from ._inprocess import (
    CompletedCliRun,
    dispatch_verb_in_process,
    parse_cli_envelope,
    tier_runs_in_process,
    warm_capture_holder_age,
)
from ._input_schema import cli_argv_for
from ._meta_tools import ToolRunOutcome
from ._tools import McpToolDescriptor

# The telemetry ``executable`` observation for a call served through the warm
# in-process runtime, where no child executable exists. It stands in the same
# field the subprocess transport fills with the resolved CLI executable path, so
# a payload-free telemetry row records which transport served the call.
_INPROCESS_MARKER = "<in-process>"
# The telemetry ``executable`` observation for a warm-eligible verb that degraded
# to the subprocess transport because the warm capture was busy or wedged, so a
# degradation is visible in telemetry as well as in the envelope's warning Notice.
_WEDGE_FALLBACK_MARKER = "<subprocess-wedge-fallback>"


def _timeout_refusal_envelope(*, command_key: str, tier: CallTier, timeout_s: float) -> dict[str, object]:
    """Build the localized timed-out refusal envelope for a hung CLI call."""
    message = tr(
        "mcp.call.timeout",
        command=command_key,
        tier=tier.value,
        seconds=int(timeout_s),
        default=(
            "'{command}' exceeded the {tier}-tier time limit ({seconds}s) and was cancelled. "
            "Retry, or run the equivalent Cadrumo command directly in a terminal for a long operation."
        ),
    )
    return {"status": "error", "refusal": message, "timed_out": True}


def _installed_cli_executable() -> str:
    """Resolve the sibling CLI installed in the server's Python environment.

    The MCP server and CLI are console scripts from one distribution cohort.
    Resolving the interpreter's scripts directory preserves that relationship
    even when ``PATH`` is empty, points at another environment, or contains a
    checkout shim. Missing installation state fails closed instead of falling
    back to an unrelated executable.
    """
    scripts_dir = Path(sysconfig.get_path("scripts")).resolve()
    executable_name = PRODUCT_IDENTITY.cli_executable
    if sys.platform == "win32":
        executable_name = f"{executable_name}.exe"
    executable = (scripts_dir / executable_name).resolve()
    if not executable.is_file():
        message = f"Installed Cadrumo CLI executable is missing from the MCP server environment: {executable}"
        raise FileNotFoundError(message)
    return str(executable)


def _cli_resolution_refusal_envelope(error: OSError) -> dict[str, object]:
    """Build a structured refusal for an incomplete MCP installation."""
    return {
        "status": "error",
        "refusal": str(error),
        "installation_incomplete": True,
    }


@dataclass(frozen=True)
class SubprocessToolOutcome(ToolRunOutcome):
    """One supervised CLI dispatch and the executable actually passed to it."""

    envelope: dict[str, object]
    is_error: bool
    executable: str


def _run_subprocess_tool(
    descriptor: McpToolDescriptor,
    arguments: dict[str, object],
) -> SubprocessToolOutcome:
    """Run one tool's CLI command and retain the executable observed by the runtime.

    The argv is reconstructed from the descriptor's per-verb input schema and the
    named ``arguments`` the client supplied - positional arguments in CLI order,
    then options - so the retired ``{args: [string]}`` bag has no path back in.

    The call runs through :func:`~entrypoints.mcp._call_runtime.run_supervised`
    with a per-tier wall-clock ceiling derived from the command's annotations:
    a hung call is terminated together with
    its whole process tree (a live pull spawns a browser child) and returns an
    instructive, localized timed-out refusal rather than hanging the MCP call.

    ``stdin`` is isolated to ``DEVNULL`` inside the runtime. Over the stdio
    transport the server's own stdin IS the MCP client pipe; without this
    isolation the spawned CLI child inherits that pipe and any read from it
    blocks forever. Output is decoded as UTF-8 explicitly (the CLI always emits
    UTF-8; the platform default is cp1252 on Windows, which would mojibake every
    accented character for the LLM client), with ``errors="replace"`` matching the
    CLI's own emit-side fallback.
    """
    tier = tier_for(
        read_only=descriptor.annotations.read_only_hint,
        open_world=descriptor.annotations.open_world_hint,
    )
    timeout_s = timeout_seconds(tier)
    try:
        executable = _installed_cli_executable()
        argv = [executable, *cli_argv_for(descriptor.verb_schema, arguments)]
        result = run_supervised(argv, timeout_s=timeout_s, encoding=UTF_8_ENCODING)
    except OSError as error:
        return SubprocessToolOutcome(
            envelope=_cli_resolution_refusal_envelope(error),
            is_error=True,
            executable="",
        )
    if result.timed_out:
        return SubprocessToolOutcome(
            envelope=_timeout_refusal_envelope(
                command_key=descriptor.command_key,
                tier=tier,
                timeout_s=timeout_s,
            ),
            is_error=True,
            executable=result.executable,
        )
    envelope, is_error = parse_cli_envelope(
        CompletedCliRun(stdout=result.stdout, stderr=result.stderr, returncode=result.returncode),
    )
    return SubprocessToolOutcome(
        envelope=envelope,
        is_error=is_error,
        executable=result.executable,
    )


def _inprocess_timeout_notice(*, command_key: str) -> Notice:
    """The idempotent-retry advisory for a soft-timed-out warm call.

    A warm in-process call cannot be force-terminated the way a supervised
    subprocess tree can, so on ceiling breach the worker is abandoned and MAY still
    complete in the background. This warning tells the operator the mutation might
    have landed and to re-run the SAME call with the SAME idempotency key: the
    single-subject idempotency guard makes that retry safe (a match returns the
    existing record as a no-op; it never double-writes).
    """
    message = tr(
        "mcp.call.timeout.may_complete",
        command=command_key,
        default=(
            "'{command}' exceeded its time limit; the operation may still be completing in the "
            "background. Re-run it with the same idempotency key to check - the idempotency guard "
            "makes the retry safe and never double-writes."
        ),
    )
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="mcp.call.timeout.may_complete",
        message=message,
        suggestion=None,
        context={"command": command_key, "idempotent_retry": "safe"},
    )


def _warm_degradation_notice(*, command_key: str, wedged: bool) -> Notice:
    """The warning naming a warm-to-subprocess degradation so it is not silent.

    When the warm transport is wedged (a worker holding the capture past the wedge
    threshold) or merely busy (the capture could not be acquired within the wait
    bound), the call is served by the proven subprocess transport instead. The
    envelope is identical by the parity oracle, so only latency changes; this
    warning Notice names the wedge/contention so telemetry and the operator see the
    degradation.
    """
    reason = "wedged" if wedged else "busy"
    message = tr(
        "mcp.serving.warm_degraded",
        command=command_key,
        reason=reason,
        default=(
            "'{command}' was served through the subprocess transport because the warm in-process "
            "runtime was {reason}; the result is identical, only slower. Warm serving resumes once "
            "the slow call clears."
        ),
    )
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="mcp.serving.warm_transport_degraded",
        message=message,
        suggestion=None,
        context={"command": command_key, "transport": "subprocess", "reason": reason},
    )


def _envelope_with_notice(envelope: dict[str, object], notice: Notice) -> dict[str, object]:
    """Append a typed ``Notice`` to an envelope and raise its status to warning.

    The single diagnostic channel (``cli-notices-are-the-only-diagnostic-channel``):
    a transport-degradation or soft-timeout advisory rides the envelope's ``notices``
    array, and a ``success`` envelope becomes ``warning`` so the status stays in
    lock-step with its notice severity.
    """
    result = dict(envelope)
    existing = result.get("notices")
    notices = list(existing) if isinstance(existing, list) else []
    notices.append(notice.model_dump(mode="json"))
    result["notices"] = notices
    if result.get("status") == "success":
        result["status"] = "warning"
    return result


def _run_inprocess_tool(
    descriptor: McpToolDescriptor,
    arguments: dict[str, object],
    *,
    tier: CallTier,
    timeout_s: float,
    acquire_timeout_s: float,
) -> SubprocessToolOutcome | None:
    """Serve one verb through the warm in-process runtime under a wall-clock ceiling.

    The verb runs in the server process through the real CLI pipeline
    (:func:`~entrypoints.mcp._inprocess.dispatch_verb_in_process`), reusing the
    same command functions and envelope builders as the subprocess transport, so
    the envelope - parsed through the same
    :func:`~entrypoints.mcp._inprocess.parse_cli_envelope` - is byte-identical.
    The per-tier ceiling is retained: an in-process call cannot be
    force-terminated the way a supervised subprocess tree can, so the call runs in
    a dedicated worker thread joined with the timeout. On breach the localized
    timed-out refusal is returned carrying an idempotent-retry Notice (the
    abandoned worker MAY still complete in the background). This whole runner is
    itself dispatched off the event loop by the shared progress wrapper, so the
    join never blocks the loop.

    Returns ``None`` when the stdout capture could not be acquired within
    ``acquire_timeout_s`` (a slow or wedged prior call still holds it); the caller
    then degrades to the supervised subprocess transport rather than queuing.

    Idle-lock custody (D4): the warm runtime never retains decrypted bucket-session
    key material between calls. The CLI opens and closes its own bucket session
    within the call, and the worker runs in its OWN thread context (a raw thread
    does not inherit the server's ``ContextVar`` state), so the session the CLI
    binds cannot leak into the long-lived server context. The ``finally`` relock is
    defence in depth: it evicts and zeroises any residual session before the worker
    context ends, covering both an unexpected in-call fault and a timed-out worker
    that finishes in the background after its ceiling was reported. A crashed server
    process holds no decrypted state on disk and re-warms its caches on restart, so
    restart is clean and single-writer persistence is unchanged (the atexit hook
    zeroises any still-bound session on interpreter exit).
    """
    holder: dict[str, CompletedCliRun | None] = {}

    def _target() -> None:
        try:
            holder["run"] = dispatch_verb_in_process(
                descriptor.verb_schema,
                arguments,
                acquire_timeout_s=acquire_timeout_s,
            )
        finally:
            # Relock: evict and zeroise any bucket session still bound in this
            # worker's context so no decrypted key material survives the call.
            # Idempotent - a no-op when the CLI already closed its session.
            close_active_bucket_session()

    worker = threading.Thread(target=_target, name="cadrumo-mcp-inprocess", daemon=True)
    worker.start()
    worker.join(timeout_s)
    if worker.is_alive():
        envelope = _envelope_with_notice(
            _timeout_refusal_envelope(command_key=descriptor.command_key, tier=tier, timeout_s=timeout_s),
            _inprocess_timeout_notice(command_key=descriptor.command_key),
        )
        return SubprocessToolOutcome(envelope=envelope, is_error=True, executable=_INPROCESS_MARKER)
    run = holder.get("run")
    if run is None:
        # The capture could not be acquired within the bound (a slow or wedged
        # prior call still holds it): signal the caller to degrade to subprocess.
        return None
    envelope, is_error = parse_cli_envelope(run)
    return SubprocessToolOutcome(envelope=envelope, is_error=is_error, executable=_INPROCESS_MARKER)


def _degraded_subprocess_outcome(
    descriptor: McpToolDescriptor,
    arguments: dict[str, object],
    *,
    wedged: bool,
) -> SubprocessToolOutcome:
    """Serve a warm-eligible verb on the subprocess transport with a degradation Notice.

    The declared, tested fallback to the proven production transport: envelope
    identical by the parity oracle, plus a warning Notice naming the wedge or
    contention so the degradation is visible, never silent.
    """
    outcome = _run_subprocess_tool(descriptor, arguments)
    envelope = _envelope_with_notice(
        outcome.envelope,
        _warm_degradation_notice(command_key=descriptor.command_key, wedged=wedged),
    )
    return SubprocessToolOutcome(envelope=envelope, is_error=outcome.is_error, executable=_WEDGE_FALLBACK_MARKER)


def _run_tool(descriptor: McpToolDescriptor, arguments: dict[str, object]) -> SubprocessToolOutcome:
    """Dispatch one tool through the transport its call tier selects.

    Local ``READ`` and ``MUTATE`` verbs run warm in-process (interpreter start,
    the pydantic import floor, and the registry load are paid once per session,
    not per call); the AEAT-sede / open-world ``LIVE`` family stays on the
    supervised subprocess for its process-tree kill and operator progress sink.
    Both transports return the same :class:`SubprocessToolOutcome` shape and parse
    through the same :func:`~entrypoints.mcp._inprocess.parse_cli_envelope`, so the
    envelope cannot fork between them. Both meta-execute and the direct per-verb
    path route through here.

    Fail-fast wedge handling (never a whole-transport wedge): if a prior warm call
    has held the stdout capture past the wedge threshold the warm transport is
    declared wedged and this verb degrades to the subprocess transport immediately;
    otherwise it tries the warm path with a bounded capture wait and, if that wait
    is exhausted (the capture is busy but not yet wedged), degrades too. Either
    degradation carries a warning Notice, and warm serving resumes automatically
    once the slow worker completes and releases the capture.
    """
    tier = tier_for(
        read_only=descriptor.annotations.read_only_hint,
        open_world=descriptor.annotations.open_world_hint,
    )
    if not tier_runs_in_process(tier):
        return _run_subprocess_tool(descriptor, arguments)
    settings = load_settings()
    wedge_threshold_s = settings.cadrumo_mcp_wedge_threshold_seconds
    holder_age = warm_capture_holder_age()
    if holder_age is not None and holder_age >= wedge_threshold_s:
        return _degraded_subprocess_outcome(descriptor, arguments, wedged=True)
    outcome = _run_inprocess_tool(
        descriptor,
        arguments,
        tier=tier,
        timeout_s=timeout_seconds(tier),
        acquire_timeout_s=settings.cadrumo_mcp_warm_capture_wait_seconds,
    )
    if outcome is None:
        # Warm capture busy for the whole bound: degrade. Re-read the holder age so
        # the Notice distinguishes a wedged holder from mere transient contention.
        holder_age = warm_capture_holder_age()
        return _degraded_subprocess_outcome(
            descriptor,
            arguments,
            wedged=holder_age is not None and holder_age >= wedge_threshold_s,
        )
    return outcome
