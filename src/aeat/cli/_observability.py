"""Shared helpers for wiring ``aeat.observability.run_context`` at the CLI layer.

Every outermost public CLI command wraps its body in
:func:`run_context` and emits one ``STEP_START`` / ``STEP_END`` pair
via :func:`record_event`. This module factors the boilerplate so each
CLI file stays minimal — see [[2026-04-14-run-trace-plan]] step 12.

Callers pass the positional-argument names via the ``positional``
parameter so replay can reconstruct a Typer-compatible argv with
positional arguments emitted first (in the declared order, without
a ``--`` prefix) followed by any captured flags.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from ..observability import (
    ArgumentRecord,
    ArgumentSource,
    RunContextInfo,
    run_context,
)


def _stringify(value: Any) -> str | None:
    """Convert a Typer-captured argument value to a string for replay capture.

    Returns ``None`` for ``None`` so callers can skip unset optionals.
    Bools / ints / floats / Paths / enums / strings round-trip via
    ``str(...)``. Other types are coerced via ``repr`` so the
    capture is never lossy from the perspective of audit (replay
    reconstructs the argv, which only emits flag arguments).
    """
    if value is None:
        return None
    if isinstance(value, bool | int | float | str):
        return str(value)
    return str(value)


def build_arguments(
    values: Mapping[str, Any],
    *,
    positional: Sequence[str] = (),
) -> tuple[ArgumentRecord, ...]:
    """Build a tuple of :class:`ArgumentRecord` from a Typer locals mapping.

    Positional arguments listed in ``positional`` are emitted first in
    the given order (tagged :attr:`ArgumentSource.POSITIONAL`);
    every remaining entry is emitted in ``values`` insertion order
    tagged :attr:`ArgumentSource.FLAG`. Order is preserved verbatim —
    replay must re-emit positionals in the same sequence the command
    declared them.

    Args:
        values: Mapping of CLI argument name → captured value. ``None``
            values are skipped (they were never passed by the user).
        positional: Ordered sequence of argument names that Typer
            declared as :class:`typer.Argument` (positional). Each
            listed name must appear in ``values``. Missing values
            raise :class:`KeyError`.

    Returns:
        A tuple of strict :class:`ArgumentRecord` records ordered
        positionals-first, then flags in declaration order.
    """
    positional_set = set(positional)
    records: list[ArgumentRecord] = []
    for name in positional:
        rendered = _stringify(values[name])
        if rendered is None:
            continue
        records.append(
            ArgumentRecord(name=name, value=rendered, source=ArgumentSource.POSITIONAL),
        )
    for name, value in values.items():
        if name in positional_set:
            continue
        rendered = _stringify(value)
        if rendered is None:
            continue
        records.append(
            ArgumentRecord(name=name, value=rendered, source=ArgumentSource.FLAG),
        )
    return tuple(records)


@contextmanager
def cli_run_context(
    *,
    entrypoint: str,
    arguments: Mapping[str, Any],
    positional: Sequence[str] = (),
) -> Iterator[RunContextInfo]:
    """Convenience wrapper that builds arguments and enters :func:`run_context`.

    Args:
        entrypoint: Stable string identifying the CLI entrypoint
            (e.g. ``"aeat workflow run"``).
        arguments: Mapping of CLI argument name → captured value
            (typically the function's ``locals()`` filtered to the
            argument names).
        positional: Ordered sequence of argument names declared as
            Typer positional :class:`typer.Argument` values.
    """
    built = build_arguments(arguments, positional=positional)
    with run_context(entrypoint=entrypoint, arguments=built) as info:
        yield info


__all__ = ["build_arguments", "cli_run_context"]
