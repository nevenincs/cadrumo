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

from ..config import Settings
from ..product_identity import PRODUCT_IDENTITY
from .errors import AeatCorpusDriftError, CadrumoObservabilityError
from ._fingerprint import compute_corpus_sha256
from ._models import ArgumentRecord, ArgumentSource, RunTrace
from ._store import load_trace

# Marker environment variable set for the duration of ``replay_run``'s
# re-entered CLI call so run_context can label the child trace.
REPLAY_ACTIVE_ENV_VAR = "CADRUMO_REPLAY_ACTIVE"

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

    Strips the leading program name from ``entrypoint`` (for example,
    ``"program workflow run"`` → ``["workflow", "run"]``).

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
    if parts and parts[0] == PRODUCT_IDENTITY.cli_executable:
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
    assert_envelope: bool = False,
    assert_db_state: bool = False,
) -> RunTrace:
    """Replay a recorded run after gating on corpus drift.

    When ``assert_envelope`` is set and ``invoke`` is provided, the
    re-entered invocation's emitted ``--format json`` envelope is
    captured and asserted byte-identical (after the declared narrow mask)
    against the golden envelope persisted for the original run — closing
    the research F1 gap so replay proves "the same JSON came out", not
    only "the same argv re-runs". The capture/canonicalise/mask/compare
    logic lives in the shared substrate primitive
    (:mod:`cadrumo.core.observability._golden`); the operator golden gate
    reuses the same primitive.

    Args:
        run_id: Identifier of the recorded run to replay.
        invoke: Optional callable that re-enters the CLI with the reconstructed
            argv.  When ``None`` the function loads and validates the trace
            but does not re-execute it, returning the original
            :class:`RunTrace` directly.
        assert_envelope: When ``True`` (and ``invoke`` is provided), load
            the original run's persisted ``envelope.json``, capture the
            re-entered invocation's emitted envelope, and assert they match
            after masking.
        assert_db_state: When ``True`` (and ``invoke`` is provided), the
            OPTIONAL post-state tier: recompute the application
            data-root fingerprint after re-entry and assert it equals
            the recorded ``db_sha256``. This proves state-transition
            determinism (a retried write is a true no-op) and is
            meaningful only for a scenario that runs against a hermetic
            synthetic data root (a test-scoped
            ``cadrumo_local_storage_root`` override); the shared
            operator data root would flap it, which is why it is opt-in
            and never a hard gate for all replays.

    Returns:
        The loaded :class:`RunTrace` of the original run.

    Raises:
        CadrumoObservabilityError: When the trace carries removed write-era
            flags, when ``assert_envelope`` is set but the re-entered
            invocation emitted no envelope to compare, or when
            ``assert_db_state`` is set and the post-state application
            data-root fingerprint drifts from the recorded one.
        AeatCorpusDriftError: When the current corpus hash differs
            from the recorded one.
        GoldenReplayMismatchError: When ``assert_envelope`` is set and the
            replayed envelope diverges from its captured expectation.
    """
    original = load_trace(run_id)
    for arg in original.arguments:
        if _argument_uses_removed_write_flag(arg):
            raise CadrumoObservabilityError(
                f"refusing to replay run {run_id!r}: recorded entrypoint "
                f"{original.entrypoint!r} used removed flag "
                f"{arg.name!r}={arg.value!r}. Replay will not reconstruct "
                "obsolete write-era CLI arguments.",
            )
    settings = Settings()
    observed = compute_corpus_sha256(settings)
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

    # Lazy imports keep the substrate seams out of the module-load graph
    # (and preserve the canonical ``REPLAY_ACTIVE_ENV_VAR`` line above).
    from ._capture import capture_envelopes

    expected_envelope: dict[str, object] | None = None
    if assert_envelope:
        from ._store import load_envelope_document

        expected_envelope = load_envelope_document(run_id)

    # Restore the prior value on exit so the process env is unchanged
    # for any caller that imports ``replay_run`` programmatically.
    #
    # NOTE: The os.environ READ/WRITE here is a documented exception to
    # the "every AEAT-prefixed config flows through Settings" mandate.
    # This is subprocess-IPC, not config: ``invoke(argv)`` re-enters the
    # CLI which on next ``load_settings()`` reads
    # ``Settings.cadrumo_replay_active`` — and the value comes from the
    # os.environ mutation we perform below. Settings is read-only, so
    # the write side has no Settings equivalent.
    previous = os.environ.get(REPLAY_ACTIVE_ENV_VAR)
    # Store the *original* run_id, not just "1", so the re-entered
    # run_context can label the new trace's ``replay_of`` field with
    # the source run. This lets ``aeat run show`` distinguish replay
    # traces from fresh runs and chain them back to their original.
    os.environ[REPLAY_ACTIVE_ENV_VAR] = run_id  # env-write: intentional — scoped context-manager
    captured: list[dict[str, object]] = []
    try:
        with capture_envelopes() as sink:
            invoke(argv)
        captured = sink
    finally:
        if previous is None:
            os.environ.pop(REPLAY_ACTIVE_ENV_VAR, None)
        else:
            os.environ[REPLAY_ACTIVE_ENV_VAR] = previous  # env-write: intentional — restore prior state

    if expected_envelope is not None:
        _assert_replayed_envelope(run_id, expected_envelope, captured)
    if assert_db_state:
        from ._fingerprint import compute_data_root_sha256

        observed_db = compute_data_root_sha256(settings)
        _assert_db_state_unchanged(run_id, original.db_sha256, observed_db)
    return original


def _assert_db_state_unchanged(run_id: str, recorded: str, observed: str) -> None:
    """Assert the post-replay application data-root fingerprint matches the recorded one.

    The optional post-state tier: for a hermetic synthetic data-root
    scenario, a drift means the re-entered invocation was NOT the no-op
    the recorded state asserts (e.g. a retried ledger add that was
    expected to be idempotent mutated state).
    """
    if recorded != observed:
        raise CadrumoObservabilityError(
            f"db-state drift on replay of run {run_id!r}: "
            f"recorded={recorded[:12]}... observed={observed[:12]}...; the "
            "re-entered invocation was expected to be a no-op against a "
            "hermetic synthetic application data root",
        )


def _assert_replayed_envelope(
    run_id: str,
    expected: dict[str, object],
    captured: list[dict[str, object]],
) -> None:
    """Assert the last captured re-entry envelope matches the golden expectation.

    Delegates the canonicalise/mask/compare to the shared golden
    primitive so this replay consumer and the operator golden gate never
    diverge on masking. The lazy import keeps ``_golden`` (and its
    ``json_contract`` dependency) off the module-load graph.
    """
    from ._golden import assert_golden_match

    if not captured:
        raise CadrumoObservabilityError(
            f"refusing to assert envelope for replay of {run_id!r}: the "
            "re-entered invocation emitted no --format json envelope to compare",
        )
    assert_golden_match(expected, captured[-1])


__all__ = ["REPLAY_ACTIVE_ENV_VAR", "replay_run"]
