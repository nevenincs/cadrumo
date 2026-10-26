"""Load deferred command declarations and implementations for the tax CLI."""

from __future__ import annotations

from importlib import import_module

from cadrumo_client.commands.shared_contracts import DeferredTarget
from cadrumo_client.commands.target import resolve_target_attribute


def resolve_deferred_target(target: DeferredTarget) -> object:
    """Import a declared tax CLI target at its composition boundary."""
    return resolve_target_attribute(import_module(target.module), target)
