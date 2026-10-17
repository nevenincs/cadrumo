"""Load deferred declarations and implementations for runtime commands."""

from __future__ import annotations

from importlib import import_module

from cadrumo_client.commands.shared_contracts import DeferredTarget
from cadrumo_client.commands.target import resolve_target_attribute


def resolve_deferred_target(target: DeferredTarget) -> object:
    """Import a declared runtime command target at its composition boundary."""
    return resolve_target_attribute(import_module(target.module), target)
