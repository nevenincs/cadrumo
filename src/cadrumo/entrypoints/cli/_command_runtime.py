"""Project the production-authored command specification into Typer.

The specification graph owns every executable structural fact.  This module is
only its runtime compiler: it resolves translation, value and behavior targets
at the selected node boundary and never discovers commands by inspecting a
handler module.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import cache
from types import GenericAlias
from typing import Any, cast

import typer
from click import Choice

from ...core.i18n import tr
from ._command_spec import (
    ArgumentSpec,
    BindingState,
    CommandSpec,
    CommandSpecGraph,
    DefaultKind,
    DeferredTarget,
    OptionSpec,
    ParameterDefault,
    SchemaState,
)
from ._command_suggestions import (
    CadrumoTyperGroup,
    LazyFactoryTarget,
    LazySubcommand,
)
from ._command_target import resolve_deferred_target


class CommandSpecTyperGroup(CadrumoTyperGroup):
    """Runtime group whose lazy table is namespaced to CommandSpec authority."""


@cache
def _group_class(graph: CommandSpecGraph, key: str) -> type[CommandSpecTyperGroup]:
    return type(
        f"CommandSpecTyperGroup_{key}",
        (CommandSpecTyperGroup,),
        {"lazy_subcommands": _lazy_children(graph, graph.by_key()[key])},
    )


def _parameter_default(default: ParameterDefault) -> tuple[object, Callable[[], object] | None]:
    if default.kind is DefaultKind.REQUIRED:
        return ..., None
    if default.kind is DefaultKind.LITERAL:
        return default.literal, None
    if default.factory is None:  # guarded by ParameterDefault itself
        raise RuntimeError("factory parameter default has no target")

    factory_target = default.factory

    def deferred_factory() -> object:
        factory = resolve_deferred_target(factory_target)
        if not callable(factory):
            raise TypeError(f"parameter default target is not callable: {factory_target.identity!r}")
        return cast(Callable[[], object], factory)()

    return None, deferred_factory


def _annotation(target: DeferredTarget) -> object:
    annotation = resolve_deferred_target(target)
    if not isinstance(annotation, type) and not callable(annotation):
        raise TypeError(f"parameter annotation target is not a type: {target.identity!r}")
    return annotation


def _parameter(spec: ArgumentSpec | OptionSpec) -> inspect.Parameter:
    default, default_factory = _parameter_default(spec.default)
    annotation = _annotation(spec.value.annotation)
    if isinstance(spec, OptionSpec) and spec.multiple:
        annotation = GenericAlias(list, (annotation,))
    parser = None if spec.value.parser is None else resolve_deferred_target(spec.value.parser)
    click_type = (
        Choice(spec.value.choices, case_sensitive=spec.constraint.case_sensitive)
        if spec.value.choices
        else None
        if spec.value.click_type is None
        else resolve_deferred_target(spec.value.click_type)
    )
    if isinstance(click_type, type):
        click_type = click_type()
    choice_metavar = None if not spec.value.choices else f"<{'|'.join(spec.value.choices)}>"
    argument_choice_metavar = None if choice_metavar is None else f"{spec.name}:{choice_metavar}"
    if isinstance(spec, ArgumentSpec):
        argument_factory = cast(Any, typer.Argument)
        argument_kwargs: dict[str, object] = {
            "default_factory": default_factory,
            "help": None if spec.help_key is None else tr(spec.help_key.value),
            "metavar": spec.metavar or argument_choice_metavar,
            "show_default": spec.show_default,
            "hidden": spec.hidden,
            "min": spec.constraint.minimum,
            "max": spec.constraint.maximum,
            "clamp": spec.constraint.clamp,
            "case_sensitive": spec.constraint.case_sensitive,
            "exists": spec.constraint.exists,
            "file_okay": spec.constraint.file_okay,
            "dir_okay": spec.constraint.dir_okay,
            "writable": spec.constraint.writable,
            "readable": spec.constraint.readable,
            "resolve_path": spec.constraint.resolve_path,
            "allow_dash": spec.constraint.allow_dash,
        }
        if parser is not None:
            argument_kwargs["parser"] = parser
        if click_type is not None:
            argument_kwargs["click_type"] = click_type
        typer_default = argument_factory(default, **argument_kwargs)
        kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
    else:
        callback = None if spec.value.callback is None else resolve_deferred_target(spec.value.callback)
        completion = None if spec.value.completion is None else resolve_deferred_target(spec.value.completion)
        option_factory = cast(Any, typer.Option)
        option_kwargs: dict[str, object] = {
            "default_factory": default_factory,
            "help": None if spec.help_key is None else tr(spec.help_key.value),
            "metavar": spec.metavar or choice_metavar,
            "show_default": spec.show_default,
            "hidden": spec.hidden,
            "count": spec.count,
            "prompt": None if spec.prompt_key is None else tr(spec.prompt_key.value),
            "confirmation_prompt": (
                False if spec.confirmation_prompt_key is None else tr(spec.confirmation_prompt_key.value)
            ),
            "envvar": list(spec.envvar) or None,
            "is_eager": spec.eager,
            "callback": callback,
            "shell_complete": completion,
            "min": spec.constraint.minimum,
            "max": spec.constraint.maximum,
            "clamp": spec.constraint.clamp,
            "case_sensitive": spec.constraint.case_sensitive,
            "exists": spec.constraint.exists,
            "file_okay": spec.constraint.file_okay,
            "dir_okay": spec.constraint.dir_okay,
            "writable": spec.constraint.writable,
            "readable": spec.constraint.readable,
            "resolve_path": spec.constraint.resolve_path,
            "allow_dash": spec.constraint.allow_dash,
        }
        if parser is not None:
            option_kwargs["parser"] = parser
        if click_type is not None:
            option_kwargs["click_type"] = click_type
        # Typer derives flag semantics from the boolean annotation and paired
        # declarations. Its legacy ``is_flag`` / ``flag_value`` parameters are
        # deprecated and ignored, so projecting them would add warnings without
        # preserving any contract fact.
        typer_default = option_factory(default, *spec.declarations, **option_kwargs)
        kind = inspect.Parameter.KEYWORD_ONLY
    return inspect.Parameter(
        spec.name,
        kind,
        annotation=annotation,
        default=typer_default,
    )


def _behavior_wrapper(spec: CommandSpec) -> Callable[..., object]:
    binding = spec.handler
    if binding is None or binding.state is not BindingState.TARGET or binding.target is None:
        raise RuntimeError(f"command {spec.key!r} has no executable target")

    target_ref = binding.target
    signature: inspect.Signature

    def invoke(*args: object, **kwargs: object) -> object:
        bound = signature.bind(*args, **kwargs)
        context_parameter = spec.invocation.context_parameter
        if spec.kind == "group" and context_parameter is not None:
            structural_context = bound.arguments.get(context_parameter)
            if structural_context is None or not hasattr(structural_context, "find_root"):
                raise TypeError("command invocation context has an invalid type")
            if getattr(structural_context, "invoked_subcommand", None) is not None:
                # Ancestor groups are structural only. Their terminal behavior
                # must not be imported or executed while Click descends toward
                # the fully parsed child authority.
                return None
        if context_parameter is not None and (
            spec.kind == "leaf" or (spec.kind == "group" and spec.invocation.terminal_behavior == "executable")
        ):
            from ._config._secure_input import clear_staged_machine_secret_payloads
            from ._profile_authentication_gate import preflight_parsed_leaf

            context = bound.arguments.get(context_parameter)
            if context is None or not hasattr(context, "find_root"):
                raise TypeError("command invocation context has an invalid type")
            try:
                from ._tui_policy import enforce_tui_request

                enforce_tui_request(cast(typer.Context, context), spec=spec)
                preflight_parsed_leaf(cast(typer.Context, context), spec=spec, arguments=bound.arguments)
                target = resolve_deferred_target(target_ref)
                if not callable(target):
                    raise TypeError(f"command target is not callable: {target_ref.identity!r}")
                return cast(Callable[..., object], target)(**bound.arguments)
            finally:
                clear_staged_machine_secret_payloads()
        target = resolve_deferred_target(target_ref)
        if not callable(target):
            raise TypeError(f"command target is not callable: {target_ref.identity!r}")
        return cast(Callable[..., object], target)(**bound.arguments)

    parameters: list[inspect.Parameter] = []
    context_parameter = spec.invocation.context_parameter
    if context_parameter is not None:
        parameters.append(
            inspect.Parameter(
                context_parameter,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=typer.Context,
            )
        )
    # Python constrains signature order twice over: a KEYWORD_ONLY parameter
    # may not precede a POSITIONAL_OR_KEYWORD one, and within the positional
    # group a parameter with no default may not follow one that has a default.
    # A spec violating either builds an illegal signature, so the command
    # cannot be constructed AT ALL -- `app ledger ratios set`,
    # `app ledger evidence batch` and `app modelo reconcile import` all shipped
    # in that state, unreachable through the real CLI. Sorting here makes the
    # violation unrepresentable instead of leaving every spec author to
    # rediscover the rule. The sort is stable, so arguments keep the relative
    # order the spec declares them in -- the part an operator actually observes
    # as positional order.
    built = [_parameter(parameter) for parameter in spec.parameters]
    parameters.extend(
        sorted(
            built,
            key=lambda parameter: (
                parameter.kind is inspect.Parameter.KEYWORD_ONLY,
                parameter.default is not inspect.Parameter.empty,
            ),
        )
    )
    invoke.__name__ = f"invoke_{spec.key}"
    invoke.__qualname__ = invoke.__name__
    signature = inspect.Signature(parameters)
    cast(Any, invoke).__signature__ = signature
    return invoke


class _SpecNodeFactory:
    """Stable callable identity for one lazily materialized spec node."""

    def __init__(self, graph: CommandSpecGraph, key: str) -> None:
        self._graph = graph
        self._key = key
        self.__module__ = __name__
        self.__qualname__ = f"command_spec_targets.{key}"

    def __call__(self) -> typer.Typer:
        return _node_app(self._graph, self._key)


def _lazy_children(graph: CommandSpecGraph, parent: CommandSpec) -> tuple[LazySubcommand, ...]:
    """Compile one node-local immutable child projection from CommandSpec."""
    children = tuple(spec for spec in graph.specs if spec.parent_key == parent.key)
    return tuple(
        LazySubcommand(
            child.token,
            LazyFactoryTarget(
                _SpecNodeFactory(graph, child.key),
                optional_dependencies=frozenset(child.handler.optional_dependencies)
                if child.handler is not None
                else frozenset(),
            ),
            help=tr(child.help_key.value),
            short_help=None if child.short_help_key is None else tr(child.short_help_key.value),
            hidden=child.invocation.hidden,
        )
        for child in children
    )


def _node_app(graph: CommandSpecGraph, key: str) -> typer.Typer:
    spec = graph.by_key()[key]
    if spec.handler is not None and spec.handler.state is BindingState.UNAVAILABLE:
        reason = spec.handler.reason_key
        raise RuntimeError(tr(reason.value) if reason is not None else f"command {key!r} is unavailable")
    if spec.kind == "leaf":
        app = typer.Typer()
        command_factory = cast(Any, app.command)
        command_factory(
            spec.token,
            help=tr(spec.help_key.value),
            short_help=None if spec.short_help_key is None else tr(spec.short_help_key.value),
            hidden=spec.invocation.hidden,
        )(_behavior_wrapper(spec))
        return app

    app = typer.Typer(
        name=spec.token,
        help=tr(spec.help_key.value),
        no_args_is_help=spec.invocation.no_args_is_help,
        invoke_without_command=spec.invocation.invoke_without_command,
        chain=spec.invocation.chain,
        add_help_option=spec.invocation.add_help_option,
        add_completion=spec.invocation.add_completion,
        cls=_group_class(graph, key),
    )
    if spec.invocation.invoke_without_command:
        app.callback(invoke_without_command=True)(_behavior_wrapper(spec))
    else:
        # Typer needs a callback to materialize a group whose children are all
        # deferred.  This adapter carries no command facts; those come from the
        # spec and the callback is never an executable handler target.
        def metadata_group_adapter() -> None:
            return None

        metadata_group_adapter.__name__ = f"group_{spec.key}"
        app.callback(invoke_without_command=False)(metadata_group_adapter)
    return app


@cache
def build_command_app(graph: CommandSpecGraph) -> typer.Typer:
    """Compile the sole production command graph into a demand-loaded app."""
    root = next(spec for spec in graph.specs if spec.kind == "root")
    return _node_app(graph, root.key)


@cache
def build_command_subtree(graph: CommandSpecGraph, key: str) -> typer.Typer:
    """Compile one declared subtree for an atomic family migration."""
    spec = graph.by_key().get(key)
    if spec is None:
        raise LookupError(f"unknown command spec key: {key!r}")
    return _node_app(graph, key)


def command_schema_targets(graph: CommandSpecGraph) -> tuple[tuple[str, DeferredTarget], ...]:
    """Project result identities without importing schema implementations."""
    rows: list[tuple[str, DeferredTarget]] = []
    for node in graph.nodes():
        schema = node.spec.result_schema
        if schema.state is SchemaState.TARGET:
            if schema.target is None:  # guarded by ResultSchemaSpec itself
                raise RuntimeError(f"command {node.spec.key!r} has an empty schema target")
            if schema.identity is None:  # guarded by ResultSchemaSpec itself
                raise RuntimeError(f"command {node.spec.key!r} has an empty schema identity")
            rows.append((schema.identity, schema.target))
    return tuple(rows)


__all__ = [
    "CommandSpecTyperGroup",
    "build_command_app",
    "build_command_subtree",
    "command_schema_targets",
    "resolve_deferred_target",
]
