"""Deterministic dry-run replay of a recorded :class:`RunTrace`.

Replay loads a persisted trace, recomputes the current
``corpus_sha256``, refuses on drift, and re-enters the same Typer CLI
path with the captured argv. Live replay is explicitly out of scope —
``dry_run=False`` raises :class:`AeatObservabilityError`.

See [[2026-04-14-run-trace-adr]] decision D5.
"""

from __future__ import annotations

import shlex

from ..config import PROJECT_ROOT, Settings
from ._errors import AeatCorpusDriftError, AeatObservabilityError
from ._fingerprint import compute_corpus_sha256
from ._models import ArgumentRecord, ArgumentSource, RunTrace
from ._store import load_trace


def _argv_from_arguments(
    entrypoint: str,
    arguments: tuple[ArgumentRecord, ...],
) -> list[str]:
    """Reconstruct a Typer-compatible argv from the captured arguments.

    Strips the leading program name from ``entrypoint`` (e.g.
    ``"aeat workflow run"`` → ``["workflow", "run"]``). Positional
    arguments (``source`` :attr:`ArgumentSource.POSITIONAL`) are
    emitted first — in the captured order — as bare values with no
    ``--`` prefix, matching how the original ``typer.Argument`` was
    supplied. Flags (``source`` :attr:`ArgumentSource.FLAG`) follow
    as ``--<name> <value>`` pairs. ``ENV`` / ``CONFIG`` / ``DEFAULT``
    sources are not re-emitted — they are recovered from the
    environment on the replayed call site.
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
        flag_name = arg.name if arg.name.startswith("--") else f"--{arg.name.replace('_', '-')}"
        parts.append(flag_name)
        parts.append(arg.value)
    return parts


def replay_run(run_id: str, *, dry_run: bool = True) -> RunTrace:
    """Replay a recorded run after gating on corpus drift.

    Args:
        run_id: Identifier of the recorded run to replay.
        dry_run: Must be ``True``. ``False`` raises explicitly because
            live replay is out of scope (#99).

    Returns:
        The loaded :class:`RunTrace` of the original run.

    Raises:
        AeatObservabilityError: When ``dry_run=False``.
        AeatCorpusDriftError: When the current corpus hash differs
            from the recorded one.
    """
    if not dry_run:
        raise AeatObservabilityError(
            "replay_run is dry-run only; live replay is out of scope (#99)",
        )
    original = load_trace(run_id)
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
    from ..cli import app

    app(argv, standalone_mode=False)
    return original


__all__ = ["replay_run"]
