"""Deterministic read-only replay of a recorded :class:`RunTrace`.

Replay loads a persisted trace, recomputes the current
``corpus_sha256``, refuses on drift, and re-enters the same Typer CLI
path reconstructed from captured :class:`ArgumentRecord` values.

Replay also refuses recorded arguments containing the removed
``--no-dry-run`` flag, so old traces cannot reintroduce an obsolete
CLI shape during argv reconstruction.
"""

from __future__ import annotations

import os
import shlex
from collections.abc import Callable

from ..config import PROJECT_ROOT, Settings
from ._errors import AeatCorpusDriftError, AeatObservabilityError
from ._fingerprint import compute_corpus_sha256
from ._models import ArgumentRecord, ArgumentSource, RunTrace
from ._store import load_trace

# Marker environment variable set for the duration of ``replay_run``'s
# re-entered CLI call so run_context can label the child trace.
REPLAY_ACTIVE_ENV_VAR = "AEAT_REPLAY_ACTIVE"

# Flag tokens the replay scrubber strips from a recorded command so the
# replayed invocation cannot promote a dry run into a live write.
_REMOVED_WRITE_FLAG_NAMES: frozenset[str] = frozenset(
    {
        "no-dry-run",
        "no_dry_run",
    },
)


def _argument_uses_removed_write_flag(arg: ArgumentRecord) -> bool:
    """Return True if ``arg`` is a removed write-era flag with a truthy value.

    The boolean flags captured as :class:`ArgumentRecord` values arrive
    as the stringified value ``"True"`` / ``"False"``. A ``False``
    capture means the caller did not opt in. Any non-False value pair is
    rejected before argv reconstruction.
    """
    if arg.source is not ArgumentSource.FLAG:
        return False
    if arg.name not in _REMOVED_WRITE_FLAG_NAMES:
        return False
    return arg.value.strip().lower() != "false"


def _argv_from_arguments(
    entrypoint: str,
    arguments: tuple[ArgumentRecord, ...],
) -> list[str]:
    """Reconstruct a Typer-compatible argv from the captured arguments.

    Strips the leading program name from ``entrypoint`` (e.g.
    ``"aeat workflow run"`` → ``["workflow", "run"]``).

    Positional arguments (``source`` :attr:`ArgumentSource.POSITIONAL`)
    are emitted first — in the captured order — as bare values with
    no ``--`` prefix, matching how the original ``typer.Argument``
    was supplied.

    Flag arguments (``source`` :attr:`ArgumentSource.FLAG`) are then
    emitted using one of two shapes depending on their stringified
    value:

    - ``"True"`` — emit the bare flag name (``--json``). Value-less
      boolean options like ``typer.Option(False, "--json")`` reject
      the ``=True`` form, so we normalise to the Typer convention.
    - ``"False"`` — omit entirely. Most boolean flags default to
      False, so replay simply not re-emitting them matches the
      original user intent. The tradeoff is that toggled-off
      flags like ``--no-sync`` on a ``typer.Option(True, "--sync/--no-sync")``
      alias pair lose fidelity; this is a known limitation.
    - Any other value — emit the ``--<name>=<value>`` form; the
      ``=`` binding prevents values that start with ``-`` from being
      mis-parsed as another flag.

    ``ENV`` / ``CONFIG`` / ``DEFAULT`` sources are not re-emitted —
    they are recovered from the environment on the replayed call
    site.
    """
    parts = shlex.split(entrypoint)
    if parts and parts[0] == "aeat":
        parts = parts[1:]
    for arg in arguments:
        if arg.source is ArgumentSource.POSITIONAL:
            parts.append(arg.value)
    for arg in arguments:
        if arg.source is not ArgumentSource.FLAG:
            continue
        if arg.cli_flag is not None:
            # Explicit override from the caller — use the exact Typer
            # flag string (``--json``) instead of deriving from the
            # Python param name (``as_json`` → ``--as-json``).
            flag_name = arg.cli_flag
        elif arg.name.startswith("--"):
            flag_name = arg.name
        else:
            flag_name = f"--{arg.name.replace('_', '-')}"
        if arg.value == "True":
            # Value-less boolean flag — emit the bare option name.
            parts.append(flag_name)
        elif arg.value == "False":
            # Boolean flag that was not set (or was explicitly
            # negated) — skip. See docstring for the fidelity
            # tradeoff on ``--sync/--no-sync``-style paired flags.
            continue
        else:
            parts.append(f"{flag_name}={arg.value}")
    return parts


def replay_run(
    run_id: str,
    *,
    invoke: Callable[[list[str]], object] | None = None,
) -> RunTrace:
    """Replay a recorded run after gating on corpus drift.

    Args:
        run_id: Identifier of the recorded run to replay.
        invoke: Optional callable that re-enters the CLI with the reconstructed
            argv.  When ``None`` the function loads and validates the trace
            but does not re-execute it, returning the original
            :class:`RunTrace` directly.

    Returns:
        The loaded :class:`RunTrace` of the original run.

    Raises:
        AeatObservabilityError: When the trace carries removed write-era flags.
        AeatCorpusDriftError: When the current corpus hash differs
            from the recorded one.
    """
    original = load_trace(run_id)
    for arg in original.arguments:
        if _argument_uses_removed_write_flag(arg):
            raise AeatObservabilityError(
                f"refusing to replay run {run_id!r}: recorded entrypoint "
                f"{original.entrypoint!r} used removed flag "
                f"{arg.name!r}={arg.value!r}. Replay will not reconstruct "
                "obsolete write-era CLI arguments.",
            )
    settings = Settings()
    observed = compute_corpus_sha256(PROJECT_ROOT / ".vault", settings)
    if observed != original.corpus_sha256:
        raise AeatCorpusDriftError(
            run_id=run_id,
            recorded=original.corpus_sha256,
            observed=observed,
            entrypoint=original.entrypoint,
        )
    argv = _argv_from_arguments(original.entrypoint, original.arguments)
    if invoke is None:
        return original

    # Restore the prior value on exit so the process env is unchanged
    # for any caller that imports ``replay_run`` programmatically.
    #
    # NOTE: The os.environ READ/WRITE here is a documented exception to
    # the "every AEAT-prefixed config flows through Settings" mandate.
    # This is subprocess-IPC, not config: ``invoke(argv)`` re-enters the
    # CLI which on next ``load_settings()`` reads
    # ``Settings.aeat_replay_active`` — and the value comes from the
    # os.environ mutation we perform below. Settings is read-only, so
    # the write side has no Settings equivalent.
    previous = os.environ.get(REPLAY_ACTIVE_ENV_VAR)
    # Store the *original* run_id, not just "1", so the re-entered
    # run_context can label the new trace's ``replay_of`` field with
    # the source run. This lets ``aeat run show`` distinguish replay
    # traces from fresh runs and chain them back to their original.
    os.environ[REPLAY_ACTIVE_ENV_VAR] = run_id  # env-write: intentional — scoped context-manager
    try:
        invoke(argv)
    finally:
        if previous is None:
            os.environ.pop(REPLAY_ACTIVE_ENV_VAR, None)
        else:
            os.environ[REPLAY_ACTIVE_ENV_VAR] = previous  # env-write: intentional — restore prior state
    return original


__all__ = ["REPLAY_ACTIVE_ENV_VAR", "replay_run"]
