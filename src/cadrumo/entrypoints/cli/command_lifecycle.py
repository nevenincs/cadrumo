"""AEAT command-dispatch lifecycle layered over the shared graph compiler."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from inspect import BoundArguments
from typing import cast

import typer

from cadrumo_client.commands.compiler import runs_in_governed_fact_scope
from cadrumo_client.commands.graph import CommandSpecGraph
from cadrumo_client.commands.spec import CommandSpec

from .profile_connection import ProfileConnectionActivator, require_bound_profile_connection


def dispatch_cli_behavior(
    graph: CommandSpecGraph,
    spec: CommandSpec,
    bound: BoundArguments,
    behavior: Callable[[], object],
    *,
    activate_connection: ProfileConnectionActivator = require_bound_profile_connection,
) -> object:
    """Apply AEAT profile admission, governed scope, provisioning and cleanup."""
    context_parameter = spec.invocation.context_parameter
    needs_preflight = spec.kind == "leaf" or (
        spec.kind == "group" and spec.invocation.terminal_behavior == "executable"
    )
    if context_parameter is not None and needs_preflight:
        from cadrumo.application.user_profile.profile_summary import summary_inventory_snapshot
        from cadrumo_client.commands.secure_input import clear_staged_machine_secret_payloads

        from ._profile_authentication_gate import preflight_parsed_leaf

        try:
            context = bound.arguments.get(context_parameter)
            find_root = getattr(context, "find_root", None)
            if context is None or not callable(find_root):
                raise TypeError("command invocation context has an invalid type")
            root = find_root()
            ensure_object = getattr(root, "ensure_object", None)
            if not callable(ensure_object) or not isinstance(ensure_object(dict), dict):
                raise TypeError("command root context has an invalid type")
            invocation_context = cast(typer.Context, context)
            listing_scope = (
                summary_inventory_snapshot() if spec.policy.side_effects == frozenset({"none"}) else nullcontext()
            )
            with _governed_fact_scope(spec, invocation_context), listing_scope:
                preflight_parsed_leaf(
                    invocation_context,
                    graph=graph,
                    spec=spec,
                    arguments=bound.arguments,
                    activate_connection=activate_connection,
                )
                return behavior()
        except Exception as error:
            from .errors import capture_refusal_spine

            capture_refusal_spine(error)
            raise
        finally:
            clear_staged_machine_secret_payloads()

    if needs_preflight:
        from cadrumo.application.cli_provisioning import provision_cli_storage

        from ._profile_authentication_contract import command_needs_state_tree

        provision_cli_storage(writes_state=command_needs_state_tree(graph.node(spec.key)))
    try:
        return behavior()
    except Exception as error:
        from .errors import capture_refusal_spine

        capture_refusal_spine(error)
        raise


def _governed_fact_scope(spec: CommandSpec, context: typer.Context) -> AbstractContextManager[None]:
    """Open the pinned authority scope for a governed AEAT command behavior."""
    if not runs_in_governed_fact_scope(spec):
        return nullcontext()
    from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

    from .state_projection_support import authority_operation

    return validating_governed_facts(authority_operation(context))


__all__ = ["dispatch_cli_behavior"]
