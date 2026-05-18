"""Shared :mod:`click` context helpers safe to import from any layer.

The helpers walk the active :class:`click.Context` chain to surface
root-level CLI flags (e.g. ``--json``) without forcing callers to thread
the context object explicitly. They live in :mod:`aeat.core` so domain
code can call :func:`json_output_requested` without inverting the
dependency direction onto :mod:`aeat.entrypoints.cli`.
"""

from __future__ import annotations

from collections.abc import Iterable

import click

_JSON_PARAM_NAMES = frozenset({"json", "as_json", "json_out", "json_output"})


def current_cli_flag(name: str) -> bool:
    """Return the boolean value of ``name`` from any ancestor context's ``obj`` dict.

    Walks the :class:`click.Context` parent chain looking for the first
    ``ctx.obj`` mapping that carries ``name``; the truthiness of the
    associated value is returned. Returns ``False`` when no context is
    active or no ancestor carries the flag.

    Args:
        name: Key to look up inside each ancestor's ``ctx.obj`` dict.

    Returns:
        ``True`` when the nearest ancestor binding for ``name`` is
        truthy; ``False`` otherwise.
    """

    ctx = click.get_current_context(silent=True)
    while ctx is not None:
        if isinstance(ctx.obj, dict) and name in ctx.obj:
            return bool(ctx.obj[name])
        ctx = ctx.parent
    return False


def current_context_has_any(names: Iterable[str]) -> bool:
    """Return ``True`` when any of ``names`` is truthy on an ancestor context.

    Checks both ``ctx.params`` (the parsed CLI arguments for the
    current command) and ``ctx.obj`` (the ad-hoc state dict callers
    use to share root-level flags) for every candidate name on every
    ancestor.

    Args:
        names: Candidate parameter / state names to probe.

    Returns:
        ``True`` if any name resolves to a truthy value anywhere on the
        context chain; ``False`` otherwise (including when no context is
        active).
    """

    ctx = click.get_current_context(silent=True)
    while ctx is not None:
        for name in names:
            if bool(ctx.params.get(name, False)):
                return True
        if isinstance(ctx.obj, dict):
            for name in names:
                if bool(ctx.obj.get(name, False)):
                    return True
        ctx = ctx.parent
    return False


def json_output_requested() -> bool:
    """Return ``True`` when the active context requests JSON output.

    Checks every recognised JSON flag spelling — ``--json``, ``--as-json``,
    ``--json-out``, ``--json-output`` — across the Click context chain. It
    also recognises the root AEAT ``--format json`` option, including Typer's
    Python-facing ``format_`` parameter name.
    The variant tolerance lets callers register the flag under whichever
    Python parameter name fits their command without breaking the
    output-mode probe.
    """

    ctx = click.get_current_context(silent=True)
    while ctx is not None:
        if _context_layer_requests_json(ctx):
            return True
        ctx = ctx.parent
    return False


def _context_layer_requests_json(ctx: click.Context) -> bool:
    """Return True when this single context layer carries any recognised JSON request."""
    if _params_request_json(ctx.params):
        return True
    return isinstance(ctx.obj, dict) and _params_request_json(ctx.obj)


def _params_request_json(params: dict[str, object]) -> bool:
    """Return True when ``params`` carries any recognised JSON flag or ``format=json`` option."""
    if any(bool(params.get(name, False)) for name in _JSON_PARAM_NAMES):
        return True
    return _context_value_is_json(params.get("format")) or _context_value_is_json(params.get("format_"))


def _context_value_is_json(value: object) -> bool:
    """Return ``True`` when a Click context value requests JSON output."""

    return isinstance(value, str) and value.strip().lower() == "json"


__all__ = ["current_cli_flag", "json_output_requested"]
