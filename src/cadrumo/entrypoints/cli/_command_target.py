"""Neutral deferred command-target resolver shared by runtime and preflight."""

from __future__ import annotations

from importlib import import_module

from ._command_spec import DeferredTarget


def resolve_deferred_target(target: DeferredTarget) -> object:
    """Resolve one explicitly declared public production target."""
    value: object = import_module(target.module)
    for part in target.qualname.split("."):
        if part.startswith("_"):
            raise RuntimeError(f"command target is not public: {target.identity!r}")
        try:
            value = getattr(value, part)
        except AttributeError as error:
            raise RuntimeError(f"command target does not exist: {target.identity!r}") from error
    return value


__all__ = ["resolve_deferred_target"]
