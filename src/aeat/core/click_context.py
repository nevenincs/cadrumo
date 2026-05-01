"""Shared Click-context helpers that must not import ``aeat.entrypoints.cli``."""

from __future__ import annotations

from collections.abc import Iterable

import click

_JSON_PARAM_NAMES = frozenset({"json", "as_json", "json_out", "json_output"})


def current_cli_flag(name: str) -> bool:
    """Return a boolean root-context CLI flag when present."""

    ctx = click.get_current_context(silent=True)
    while ctx is not None:
        if isinstance(ctx.obj, dict) and name in ctx.obj:
            return bool(ctx.obj[name])
        ctx = ctx.parent
    return False


def current_context_has_any(names: Iterable[str]) -> bool:
    """Return whether any parameter or root-state flag is set truthy."""

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
    """Return ``True`` when the current Click context carries JSON mode."""

    return current_context_has_any(_JSON_PARAM_NAMES)


__all__ = ["current_cli_flag", "json_output_requested"]
