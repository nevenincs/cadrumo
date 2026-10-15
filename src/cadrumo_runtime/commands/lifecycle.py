"""Runtime profile admission and cleanup around shared command dispatch."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from inspect import BoundArguments
from typing import cast

import typer

from cadrumo_client.commands.compiler import runs_in_governed_fact_scope
from cadrumo_client.commands.graph import CommandSpecGraph
from cadrumo_client.commands.spec import CommandSpec


def dispatch_runtime_behavior(
    graph: CommandSpecGraph,
    spec: CommandSpec,
    bound: BoundArguments,
    behavior: Callable[[], object],
) -> object:
    """Run runtime admission and the selected handler under one owned scope."""
    if spec.kind != "leaf":
        return behavior()
    context_parameter = spec.invocation.context_parameter
    from cadrumo_client.commands.secure_input import clear_staged_machine_secret_payloads

    from .presentation import capture_runtime_error_context
    from .profile_admission import preflight_runtime_command

    runtime_context: typer.Context | None = None
    try:
        if context_parameter is None:
            raise TypeError(f"runtime command {spec.key!r} requires an invocation context")

        context = bound.arguments.get(context_parameter)
        find_root = getattr(context, "find_root", None)
        if context is None or not callable(find_root):
            raise TypeError("runtime command invocation context has an invalid type")
        root = find_root()
        ensure_object = getattr(root, "ensure_object", None)
        if not callable(ensure_object):
            raise TypeError("runtime command root context has an invalid type")
        state = ensure_object(dict)
        if not isinstance(state, dict):
            raise TypeError("runtime command root context did not provide dictionary state")
        runtime_context = cast(typer.Context, context)

        from cadrumo.adapters.persistence.storage.profile_custody import build_profile_custody_port
        from cadrumo.application.user_profile.custody_ports import bind_profile_custody_port
        from cadrumo.application.user_profile.profile_summary import summary_inventory_snapshot

        state["cadrumo.runtime.command_spec"] = spec
        listing_scope = (
            summary_inventory_snapshot() if spec.policy.side_effects == frozenset({"none"}) else nullcontext()
        )
        with (
            bind_profile_custody_port(build_profile_custody_port()),
            _governed_fact_scope(spec, runtime_context),
            listing_scope,
        ):
            preflight_runtime_command(runtime_context, spec, bound.arguments)
            return behavior()
    except Exception as error:
        if runtime_context is not None:
            capture_runtime_error_context(runtime_context, error)
        raise
    finally:
        clear_staged_machine_secret_payloads()


def _governed_fact_scope(spec: CommandSpec, context: typer.Context) -> AbstractContextManager[None]:
    """Pin governed registry facts to the selected runtime invocation."""
    if not runs_in_governed_fact_scope(spec):
        return nullcontext()
    from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

    from .profile_support import authority_operation

    return validating_governed_facts(authority_operation(context))


__all__ = ["dispatch_runtime_behavior"]
