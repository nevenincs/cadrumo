"""Shared :mod:`click` context helpers safe to import from any layer.

The helpers walk the active :class:`click.Context` chain to surface root-level
CLI flags (e.g. ``--json``) without forcing callers to thread the context
object explicitly. They live in :mod:`core` so domain code can call
:func:`json_output_requested`, :func:`current_cli_flag`, or
:func:`context_chain_requests_json` without inverting the dependency direction
onto :mod:`entrypoints.cli`. Terminal error handlers that have no live
context can fall back to :func:`argv_requests_json`.

This module answers output-mode questions only. It is not an active-profile,
bucket-session, or command-dispatch state source; those boundaries remain in the
CLI bootstrap and storage/session helpers that own them.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, cast

import click

from .type_guards import is_str_keyed_dict

_JSON_PARAM_NAMES = frozenset({"json", "as_json", "json_out", "json_output"})


class _ContextLike(Protocol):
    """Structural view of a Click context (upstream or Typer's vendored fork).

    The two concrete context classes are nominally different but expose the
    same ``params`` / ``obj`` / ``parent`` shape needed by the output-mode probe.
    """

    params: dict[str, object]
    obj: object
    parent: _ContextLike | None


def _current_context() -> _ContextLike | None:
    """Return the innermost active context from either Click runtime.

    Typer vendors its own Click fork (``typer._click``), whose context
    stack is a DIFFERENT contextvar from upstream ``click``'s — at Typer
    runtime ``click.get_current_context`` is always ``None`` and any probe
    that only consults it silently reports "no JSON requested" for every
    invocation. Check upstream first (plain-click embedders), then the
    vendored stack (the ``aeat`` CLI's actual runtime).
    """
    ctx: object = click.get_current_context(silent=True)
    if ctx is None:
        try:
            from typer._click.globals import get_current_context as _vendored_get
        except ImportError:  # pragma: no cover - typer without a vendored fork
            return None
        ctx = _vendored_get(silent=True)
    # CAST-RATIONALE-CLICK-CONTEXT: either Click runtime's context object is
    # structurally a ``_ContextLike``; the concrete classes differ across the
    # upstream and vendored forks, so the runtime type is asserted here.
    return cast("_ContextLike | None", ctx)


def _iter_context_chain() -> Iterable[_ContextLike]:
    """Yield the active context and its ancestors, innermost first."""
    ctx = _current_context()
    while ctx is not None:
        yield ctx
        ctx = ctx.parent


def current_cli_flag(name: str) -> bool:
    """Return the boolean value of ``name`` from any ancestor context's ``obj`` dict.

    Walks the :class:`click.Context` parent chain looking for the first
    ``ctx.obj`` mapping that carries ``name``; the truthiness of the
    associated value is returned. Returns ``False`` when no context is
    active or no ancestor carries the flag. This helper intentionally reads
    ``ctx.obj`` only; option values stored in ``ctx.params`` are handled by
    :func:`json_output_requested`.

    Args:
        name: Key to look up inside each ancestor's ``ctx.obj`` dict.

    Returns:
        ``True`` when the nearest ancestor binding for ``name`` is
        truthy; ``False`` otherwise.
    """
    for ctx in _iter_context_chain():
        obj = ctx.obj
        if isinstance(obj, dict):
            # CAST-RATIONALE-CLICK-CONTEXT-OBJ: click types ctx.obj as Any; the
            # isinstance guard above proves the str-keyed dict shape used here.
            obj_map = cast("dict[str, object]", obj)
            if name in obj_map:
                return bool(obj_map[name])
    return False


def json_output_requested() -> bool:
    """Return ``True`` when the active context requests JSON output.

    Checks every recognised JSON flag spelling — ``--json``, ``--as-json``,
    ``--json-out``, ``--json-output`` — across the Click context chain. It
    also recognises the root AEAT ``--format json`` option, including Typer's
    Python-facing ``format_`` parameter name.
    The variant tolerance lets callers register the flag under whichever
    Python parameter name fits their command without breaking the
    output-mode probe. For terminal handlers without a live current context,
    use :func:`context_chain_requests_json` when an exception carries a context
    or :func:`argv_requests_json` as the last-resort argv parser.
    """
    return any(_context_layer_requests_json(ctx) for ctx in _iter_context_chain())


def context_chain_requests_json(ctx: object) -> bool:
    """Return ``True`` when ``ctx`` or any ancestor requests JSON output.

    Companion to :func:`json_output_requested` for call sites where the
    context stack is already unwound (e.g. the root group's terminal
    exception handler, where a :class:`click.UsageError` carries its
    parse-time context on ``exc.ctx`` but no context is "current").
    Accepts either Click runtime's context object structurally.

    Args:
        ctx: Upstream or Typer-vendored Click context, or any object exposing
            compatible ``params``, ``obj``, and ``parent`` attributes.
    """
    current = ctx
    while current is not None:
        params = getattr(current, "params", None)
        if is_str_keyed_dict(params) and _params_request_json(params):
            return True
        obj = getattr(current, "obj", None)
        if is_str_keyed_dict(obj) and _params_request_json(obj):
            return True
        current = getattr(current, "parent", None)
    return False


def argv_requests_json(argv: Iterable[str]) -> bool:
    """Return ``True`` when raw ``argv`` tokens request JSON output.

    Last-resort probe for terminal handlers that have neither an active
    context stack nor an exception-carried context (e.g. a crash before
    or outside command dispatch). Recognises ``--format json``,
    ``--format=json``, and the ``--json`` flag family. It is syntactic only:
    command parsing and value validation still belong to Click/Typer.
    """
    args = list(argv)
    for index, arg in enumerate(args):
        if arg in {"--json", "--as-json", "--json-out", "--json-output"}:
            return True
        if arg == "--format" and index + 1 < len(args) and _context_value_is_json(args[index + 1]):
            return True
        if arg.startswith("--format=") and _context_value_is_json(arg.removeprefix("--format=")):
            return True
    return False


def _context_layer_requests_json(ctx: _ContextLike) -> bool:
    """Return True when this single context layer carries any recognised JSON request."""
    if _params_request_json(ctx.params):
        return True
    obj = ctx.obj
    # CAST-RATIONALE-CLICK-CONTEXT-OBJ: click types ctx.obj as Any; the isinstance
    # guard on the same expression narrows it to the str-keyed dict before lookup.
    return isinstance(obj, dict) and _params_request_json(cast("dict[str, object]", obj))


def _params_request_json(params: dict[str, object]) -> bool:
    """Return True when ``params`` carries any recognised JSON flag or ``format=json`` option."""
    if any(bool(params.get(name, False)) for name in _JSON_PARAM_NAMES):
        return True
    return _context_value_is_json(params.get("format")) or _context_value_is_json(params.get("format_"))


def _context_value_is_json(value: object) -> bool:
    """Return ``True`` when a Click context value requests JSON output."""
    return isinstance(value, str) and value.strip().lower() == "json"


__all__ = [
    "argv_requests_json",
    "context_chain_requests_json",
    "current_cli_flag",
    "json_output_requested",
]
