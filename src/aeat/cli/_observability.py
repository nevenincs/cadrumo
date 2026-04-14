"""Shared helpers for wiring ``aeat.observability.run_context`` at the CLI layer.

Every outermost public CLI command wraps its body in
:func:`run_context` and emits one ``STEP_START`` / ``STEP_END`` pair
via :func:`record_event`. This module factors the boilerplate so each
CLI file stays minimal — see [[2026-04-14-run-trace-plan]] step 12.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from aeat.observability import (
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


def build_arguments(values: Mapping[str, Any]) -> tuple[ArgumentRecord, ...]:
    """Build a tuple of :class:`ArgumentRecord` from a Typer locals mapping.

    Args:
        values: Mapping of CLI argument name → captured value. ``None``
            values are skipped (they were never passed by the user).

    Returns:
        A tuple of strict :class:`ArgumentRecord` records, every entry
        marked with ``ArgumentSource.FLAG``.
    """
    records: list[ArgumentRecord] = []
    for name in sorted(values):
        rendered = _stringify(values[name])
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
) -> Iterator[RunContextInfo]:
    """Convenience wrapper that builds arguments and enters :func:`run_context`.

    Args:
        entrypoint: Stable string identifying the CLI entrypoint
            (e.g. ``"aeat workflow run"``).
        arguments: Mapping of CLI argument name → captured value
            (typically the function's ``locals()`` filtered to the
            argument names).
    """
    with run_context(entrypoint=entrypoint, arguments=build_arguments(arguments)) as info:
        yield info


__all__ = ["build_arguments", "cli_run_context"]
