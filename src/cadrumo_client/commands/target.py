"""Owner-supplied command target loading and neutral attribute traversal."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from cadrumo.core.errors.hierarchy import InternalInvariantError

from .shared_contracts import DeferredTarget

type TargetResolver = Callable[[DeferredTarget], object]


def resolve_target_attribute(module: ModuleType, target: DeferredTarget) -> object:
    """Read the declared public attribute from a module loaded by its owner."""
    value: object = module
    for part in target.qualname.split("."):
        if part.startswith("_"):
            raise InternalInvariantError(f"command target is not public: {target.identity!r}")
        try:
            value = getattr(value, part)
        except AttributeError as error:
            raise InternalInvariantError(f"command target does not exist: {target.identity!r}") from error
    return value


__all__ = ["TargetResolver", "resolve_target_attribute"]
