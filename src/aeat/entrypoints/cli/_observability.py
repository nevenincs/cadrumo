"""Shared helpers for wiring :func:`aeat.core.observability.run_context` at the CLI layer.

Every outermost public CLI command wraps its body in
:func:`aeat.core.observability.run_context` and emits one
``STEP_START`` / ``STEP_END`` pair via
:func:`aeat.core.observability.record_event`. This module factors the
boilerplate so each CLI file stays minimal.

Callers pass the positional-argument names via the ``positional``
parameter so replay can reconstruct a Typer-compatible ``argv`` with
positional arguments emitted first (in the declared order, without a
``--`` prefix) followed by any captured flags.

Argument values whose name matches one of the secret-smelling
substrings in :data:`_REDACT_NAME_SUBSTRINGS` are recorded as
``"***"`` rather than their literal value. This is a defensive shield:
wrapped CLI commands must not accept secrets on argv. If a command
does expose a secret-like argument (e.g. ``--password``, ``--token``),
the audit log must never capture the plaintext. Callers that need a
value recorded verbatim must rename the parameter.

Caveat — name-side redaction only: this shield does NOT inspect
argument **values**. An operator who passes a token or a NIF in the
value position of an otherwise innocent-looking flag (for example
``aeat filing reconcile --by "tok-ABCXYZ"``) will have the literal
value written into ``events.jsonl`` and the persisted
:class:`aeat.core.observability.RunTrace`. When wrapping a new CLI
command whose argument can contain sensitive material, either rename
the argument to something in the denylist or extend the redaction
policy with a per-command allowlist of redacted argument names.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from ...core.observability import (
    ArgumentRecord,
    ArgumentSource,
    RunContextInfo,
    run_context,
)

_REDACT_NAME_SUBSTRINGS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "passphrase",
        "credential",
    }
)
_REDACTED_VALUE = "***"


def _stringify(value: Any) -> str | None:
    """Convert a Typer-captured argument value to a string for replay capture.

    :data:`None` is returned unchanged so callers can skip unset
    optionals. Every other type is coerced via :func:`str`: ``StrEnum``
    values (e.g.
    :class:`aeat.application.filing.reconciliation.ReconciliationStatus`)
    render as their ``.value`` because :class:`enum.StrEnum` subclasses
    :class:`str`, :class:`pathlib.Path` instances render as POSIX
    strings, and primitives round-trip naturally.
    """
    if value is None:
        return None
    return str(value)


def _is_secret_name(name: str) -> bool:
    """Return :data:`True` when ``name`` contains a secret-smelling substring.

    The comparison is case-insensitive and matches on substrings so
    ``aeat_certificate_password``, ``client_secret``, ``api_key``, etc.
    are all redacted.
    """
    lowered = name.lower()
    return any(needle in lowered for needle in _REDACT_NAME_SUBSTRINGS)


def build_arguments(
    values: Mapping[str, Any],
    *,
    positional: Sequence[str] = (),
    flag_map: Mapping[str, str] | None = None,
) -> tuple[ArgumentRecord, ...]:
    """Build a tuple of :class:`ArgumentRecord` from a Typer locals mapping.

    Positional arguments listed in ``positional`` are emitted first in
    the given order (tagged
    :attr:`aeat.core.observability.ArgumentSource.POSITIONAL`); every
    remaining entry is emitted in ``values`` insertion order tagged
    :attr:`aeat.core.observability.ArgumentSource.FLAG`. Order is
    preserved verbatim — replay must re-emit positionals in the same
    sequence the command declared them.

    Args:
        values: Mapping of CLI argument name to captured value.
            :data:`None` values are skipped because they were never
            passed by the user.
        positional: Ordered sequence of argument names that Typer
            declared as :class:`typer.Argument` (positional). Each
            listed name must appear in ``values``.
        flag_map: Optional mapping from Python parameter name to the
            actual Typer option string (e.g. ``{"as_json": "--json"}``).
            This is an escape-hatch for callers whose parameter name
            differs from the CLI flag. Current wrapped commands prefer
            the simpler approach of using the CLI-flag spelling
            directly as the dict key (``arguments = {"json": as_json}``),
            which makes ``flag_map`` unnecessary. Use ``flag_map`` only
            when the caller cannot rename the dict key — for example
            when feeding ``locals()`` verbatim.

    Returns:
        A tuple of strict :class:`aeat.core.observability.ArgumentRecord`
        instances ordered positionals-first, then flags in declaration
        order.

    Raises:
        KeyError: If a name listed in ``positional`` is missing from
            ``values``.
    """
    positional_set = set(positional)
    aliases: Mapping[str, str] = flag_map or {}
    records: list[ArgumentRecord] = []
    for name in positional:
        rendered = _stringify(values[name])
        if rendered is None:
            continue
        if _is_secret_name(name):
            rendered = _REDACTED_VALUE
        records.append(
            ArgumentRecord(name=name, value=rendered, source=ArgumentSource.POSITIONAL),
        )
    for name, value in values.items():
        if name in positional_set:
            continue
        rendered = _stringify(value)
        if rendered is None:
            continue
        if _is_secret_name(name):
            rendered = _REDACTED_VALUE
        records.append(
            ArgumentRecord(
                name=name,
                value=rendered,
                source=ArgumentSource.FLAG,
                cli_flag=aliases.get(name),
            ),
        )
    return tuple(records)


@contextmanager
def cli_run_context(
    *,
    entrypoint: str,
    arguments: Mapping[str, Any],
    positional: Sequence[str] = (),
    flag_map: Mapping[str, str] | None = None,
) -> Iterator[RunContextInfo]:
    """Convenience wrapper combining :func:`build_arguments` and ``run_context``.

    Args:
        entrypoint: Stable string identifying the CLI entrypoint
            (e.g. ``"aeat workflow run"``).
        arguments: Mapping of CLI argument name to captured value,
            typically the function's :func:`locals` filtered to the
            argument names.
        positional: Ordered sequence of argument names declared as
            Typer positional :class:`typer.Argument` values.
        flag_map: Optional mapping from Python parameter name to the
            actual Typer option string for renamed flags
            (e.g. ``{"as_json": "--json"}``). Without this, the replay
            ``argv`` reconstruction would derive ``--as-json`` which
            Typer does not recognise.

    Yields:
        The :class:`aeat.core.observability.RunContextInfo` produced by
        :func:`aeat.core.observability.run_context`.
    """
    built = build_arguments(arguments, positional=positional, flag_map=flag_map)
    with run_context(entrypoint=entrypoint, arguments=built) as info:
        yield info


__all__ = ["build_arguments", "cli_run_context"]
