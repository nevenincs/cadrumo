"""Project the production-authored command specification into Typer.

The specification graph owns every executable structural fact.  This module is
only its runtime compiler: it resolves translation, value and behavior targets
at the selected node boundary and never discovers commands by inspecting a
handler module.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager, nullcontext
from enum import Enum
from functools import cache
from types import GenericAlias
from typing import Any, Final, cast, override

import typer
from click import Choice
from pydantic import TypeAdapter, ValidationError
from typer._click.core import Context as TyContext
from typer._click.core import Parameter as TyParameter
from typer._click.types import ParamType as TyParamType

from ...core.errors.hierarchy import InternalInvariantError
from ...core.i18n.render import tr
from ._command_target import resolve_deferred_target
from .command_spec import (
    ArgumentSpec,
    BindingState,
    Capability,
    CommandSpec,
    CommandSpecGraph,
    DefaultKind,
    DeferredTarget,
    ExecutionPolicySpec,
    OptionSpec,
    ParameterDefault,
)
from .command_suggestions import CadrumoTyperGroup, LazyFactoryTarget, LazySubcommand


class CommandSpecTyperGroup(CadrumoTyperGroup):
    """Runtime group whose lazy table is namespaced to CommandSpec authority."""


class _PydanticStringParamType(TyParamType):
    """Convert an opaque string annotation through its declared Pydantic schema.

    Subclasses Typer's vendored Click type: Typer wraps any other object in a
    function adapter, which loses this type's name in help and raises the
    wrong ``BadParameter`` class on a refused value.
    """

    name = "registry value"

    def __init__(self, annotation: type[str]) -> None:
        self._adapter = TypeAdapter(annotation)
        self.name = annotation.__name__

    @override
    def convert(self, value: Any, param: TyParameter | None, ctx: TyContext | None) -> str:
        from ...domain.calculations.registry.authority import bundled_indexed_authority

        # Registry-declared string types validate against governed facts, and
        # Click converts before the command body leases its authority.
        try:
            with bundled_indexed_authority().operation():
                return self._adapter.validate_python(value)
        except (TypeError, ValueError, ValidationError) as exc:
            self.fail(str(exc), param, ctx)


@cache
def _group_class(graph: CommandSpecGraph, key: str) -> type[CommandSpecTyperGroup]:
    return type(
        f"CommandSpecTyperGroup_{key}",
        (CommandSpecTyperGroup,),
        {"lazy_subcommands": _lazy_children(graph, graph.spec(key))},
    )


def _parameter_default(default: ParameterDefault) -> tuple[object, Callable[[], object] | None]:
    if default.kind is DefaultKind.REQUIRED:
        return ..., None
    if default.kind is DefaultKind.LITERAL:
        return default.literal, None
    if default.factory is None:  # guarded by ParameterDefault itself
        raise InternalInvariantError("factory parameter default has no target")

    factory_target = default.factory

    def deferred_factory() -> object:
        from ...domain.calculations.registry.authority import bundled_indexed_authority

        factory = resolve_deferred_target(factory_target)
        if not callable(factory):
            raise TypeError(f"parameter default target is not callable: {factory_target.identity!r}")
        # A default factory runs while Click parses, before the command body
        # takes its own lease, and registry-declared defaults read governed
        # facts. It reads them under the same published authority the command
        # then uses, rather than refusing for want of a scope.
        with bundled_indexed_authority().operation():
            return cast(Callable[[], object], factory)()

    # Typer treats any literal other than Ellipsis as a supplied default and
    # refuses it beside ``default_factory``; Ellipsis is its "no literal" marker.
    return ..., deferred_factory


def _annotation(target: DeferredTarget) -> object:
    annotation = resolve_deferred_target(target)
    if not isinstance(annotation, type) and not callable(annotation):
        raise TypeError(f"parameter annotation target is not a type: {target.identity!r}")
    return annotation


def _shared_parameter_kwargs(
    spec: ArgumentSpec | OptionSpec,
    *,
    default_factory: Callable[[], object] | None,
    metavar: str | None,
    parser: object | None,
    click_type: object | None,
) -> dict[str, object]:
    """Project the Typer kwargs shared by positional and named parameters."""
    kwargs: dict[str, object] = {
        "default_factory": default_factory,
        "help": None if spec.help_key is None else tr(spec.help_key.value),
        "metavar": metavar,
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
        kwargs["parser"] = parser
    if click_type is not None:
        kwargs["click_type"] = click_type
    return kwargs


def _parameter_value_projection(
    spec: ArgumentSpec | OptionSpec,
) -> tuple[object, object | None, object | None, str | None]:
    """Resolve annotation, parser, Click type, and choice metavar from a spec."""
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
    if (
        click_type is None
        and isinstance(annotation, type)
        and annotation is not str
        and issubclass(annotation, str)
        and not issubclass(annotation, Enum)
    ):
        click_type = _PydanticStringParamType(annotation)
    if isinstance(click_type, type):
        click_type = click_type()
    choice_metavar = None if not spec.value.choices else f"<{'|'.join(spec.value.choices)}>"
    return annotation, parser, click_type, choice_metavar


def _argument_parameter(
    spec: ArgumentSpec,
    *,
    default: object,
    default_factory: Callable[[], object] | None,
    annotation: object,
    parser: object | None,
    click_type: object | None,
    choice_metavar: str | None,
) -> inspect.Parameter:
    """Materialize one positional argument from its production spec."""
    argument_factory = cast(Any, typer.Argument)
    argument_choice_metavar = None if choice_metavar is None else f"{spec.name}:{choice_metavar}"
    argument_kwargs = _shared_parameter_kwargs(
        spec,
        default_factory=default_factory,
        metavar=spec.metavar or argument_choice_metavar,
        parser=parser,
        click_type=click_type,
    )
    typer_default = argument_factory(default, **argument_kwargs)
    return inspect.Parameter(
        spec.name,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=annotation,
        default=typer_default,
    )


def _option_parameter(
    spec: OptionSpec,
    *,
    default: object,
    default_factory: Callable[[], object] | None,
    annotation: object,
    parser: object | None,
    click_type: object | None,
    choice_metavar: str | None,
) -> inspect.Parameter:
    """Materialize one named option from its production spec."""
    callback = None if spec.value.callback is None else resolve_deferred_target(spec.value.callback)
    completion = None if spec.value.completion is None else resolve_deferred_target(spec.value.completion)
    option_factory = cast(Any, typer.Option)
    option_kwargs = _shared_parameter_kwargs(
        spec,
        default_factory=default_factory,
        metavar=spec.metavar or choice_metavar,
        parser=parser,
        click_type=click_type,
    )
    option_kwargs.update(
        {
            "count": spec.count,
            "prompt": None if spec.prompt_key is None else tr(spec.prompt_key.value),
            "confirmation_prompt": (
                False if spec.confirmation_prompt_key is None else tr(spec.confirmation_prompt_key.value)
            ),
            "envvar": list(spec.envvar) or None,
            "is_eager": spec.eager,
            "callback": callback,
            "shell_complete": completion,
        }
    )
    # Typer expresses a positive/negative boolean pair as one slash-delimited
    # declaration. The command graph keeps the two operator-facing tokens
    # separately so consumers can enumerate them, therefore join only the
    # canonical ``--x`` / ``--no-x`` shape at this adapter boundary. Passing
    # those tokens separately makes both aliases select ``True``.
    declarations = spec.declarations
    if (
        spec.is_flag
        and len(declarations) == 2
        and declarations[0].startswith("--")
        and declarations[1] == f"--no-{declarations[0][2:]}"
    ):
        declarations = (f"{declarations[0]}/{declarations[1]}",)
    # Typer derives flag semantics from the boolean annotation and declaration.
    # Its legacy ``is_flag`` / ``flag_value`` parameters are deprecated and
    # ignored, so projecting them would add warnings without preserving facts.
    typer_default = option_factory(default, *declarations, **option_kwargs)
    return inspect.Parameter(
        spec.name,
        inspect.Parameter.KEYWORD_ONLY,
        annotation=annotation,
        default=typer_default,
    )


def _parameter(spec: ArgumentSpec | OptionSpec) -> inspect.Parameter:
    """Materialize one spec-owned argument or option parameter."""
    default, default_factory = _parameter_default(spec.default)
    annotation, parser, click_type, choice_metavar = _parameter_value_projection(spec)
    if isinstance(spec, ArgumentSpec):
        return _argument_parameter(
            spec,
            default=default,
            default_factory=default_factory,
            annotation=annotation,
            parser=parser,
            click_type=click_type,
            choice_metavar=choice_metavar,
        )
    return _option_parameter(
        spec,
        default=default,
        default_factory=default_factory,
        annotation=annotation,
        parser=parser,
        click_type=click_type,
        choice_metavar=choice_metavar,
    )


def _invoke_deferred_target(target_ref: DeferredTarget, arguments: Mapping[str, object]) -> object:
    """Resolve and invoke one declared command behavior target."""
    target = resolve_deferred_target(target_ref)
    if not callable(target):
        raise TypeError(f"command target is not callable: {target_ref.identity!r}")
    invoke: Callable[..., object] = target
    return invoke(**arguments)


def _require_behavior_target(spec: CommandSpec) -> DeferredTarget:
    """Return the executable target declared by one command spec."""
    binding = spec.handler
    if binding is None or binding.state is not BindingState.TARGET or binding.target is None:
        raise InternalInvariantError(f"command {spec.key!r} has no executable target")
    return binding.target


def _invocation_context(bound: inspect.BoundArguments, context_parameter: str) -> object:
    """Require the Click context object bound under a command's context parameter."""
    context = bound.arguments.get(context_parameter)
    if context is None or not hasattr(context, "find_root"):
        raise TypeError("command invocation context has an invalid type")
    return context


def _requires_leaf_preflight(spec: CommandSpec) -> bool:
    """Report whether a spec's terminal behavior needs profile preflight."""
    return spec.kind == "leaf" or (spec.kind == "group" and spec.invocation.terminal_behavior == "executable")


GOVERNED_FACT_SCOPE_CAPABILITIES: Final[frozenset[Capability]] = frozenset({"registry", "encrypted-facts"})
"""Capabilities whose behavior reads governed registry facts.

Decoding encrypted profile facts is itself pinned to the authority generation,
so a command holding either capability reads governed facts."""


def runs_in_governed_fact_scope(spec: CommandSpec) -> bool:
    """Report whether dispatch runs this spec's behavior inside its governed-fact scope."""
    return (
        spec.invocation.context_parameter is not None
        and _requires_leaf_preflight(spec)
        and not spec.policy.expanded_capabilities.isdisjoint(GOVERNED_FACT_SCOPE_CAPABILITIES)
    )


def _governed_fact_scope(spec: CommandSpec, context: typer.Context) -> AbstractContextManager[None]:
    """Open the invocation's pinned authority as the scope its behavior reads under.

    A handler that opens its own scope can forget to, and one that relies on an
    earlier lease is only correct in the session posture that took it.
    """
    if not runs_in_governed_fact_scope(spec):
        return nullcontext()
    from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
    from .state_projection_support import authority_operation

    return validating_governed_facts(authority_operation(context))


def refuse_declared_live_write(policy: ExecutionPolicySpec) -> None:
    """Refuse a behavior whose policy declares a live AEAT write.

    Live AEAT submission is permanently forbidden, so a ``live_write``
    declaration is never a permission: dispatch raises the access gate's typed
    refusal before any preflight, provisioning or handler import can run.

    Raises:
        LiveSubmitForbiddenError: When ``policy.live_write`` is set.
    """
    if not policy.live_write:
        return
    from ...core.access_gate.gate import AeatAccessGate
    from ...core.config import load_settings

    AeatAccessGate(settings=load_settings()).require_live_write()


def _invoke_bound_behavior(
    graph: CommandSpecGraph,
    spec: CommandSpec,
    target_ref: DeferredTarget,
    bound: inspect.BoundArguments,
) -> object:
    """Apply group short-circuiting, the live-write refusal and terminal preflight."""
    context_parameter = spec.invocation.context_parameter
    if spec.kind == "group" and context_parameter is not None:
        structural_context = _invocation_context(bound, context_parameter)
        if getattr(structural_context, "invoked_subcommand", None) is not None:
            # Ancestor groups are structural only. Their terminal behavior
            # must not be imported or executed while Click descends toward
            # the fully parsed child authority.
            return None
    try:
        refuse_declared_live_write(spec.policy)
    except Exception as error:
        _capture_refusal_spine(error)
        raise
    if context_parameter is not None and _requires_leaf_preflight(spec):
        from ...application.user_profile.profile_summary import summary_inventory_snapshot
        from ._profile_authentication_gate import preflight_parsed_leaf
        from .config.secure_input import clear_staged_machine_secret_payloads

        context = _invocation_context(bound, context_parameter)
        # A leaf that writes nothing sees one profile listing for its whole run;
        # any leaf that may write profile state keeps observing live.
        listing_scope = (
            summary_inventory_snapshot() if spec.policy.side_effects == frozenset({"none"}) else nullcontext()
        )
        try:
            with _governed_fact_scope(spec, cast(typer.Context, context)), listing_scope:
                preflight_parsed_leaf(
                    cast(typer.Context, context),
                    graph=graph,
                    spec=spec,
                    arguments=bound.arguments,
                )
                return _invoke_deferred_target(target_ref, bound.arguments)
        except Exception as error:
            _capture_refusal_spine(error)
            raise
        finally:
            clear_staged_machine_secret_payloads()
    if _requires_leaf_preflight(spec):
        from ...application.provisioning import provision_cli_storage
        from ._profile_authentication_contract import command_needs_state_tree

        # A runnable command with no context to preflight is provisioned here;
        # a group rendering its own help is not.
        provision_cli_storage(writes_state=command_needs_state_tree(graph.node(spec.key)))
    try:
        return _invoke_deferred_target(target_ref, bound.arguments)
    except Exception as error:
        _capture_refusal_spine(error)
        raise


def _capture_refusal_spine(error: Exception) -> None:
    from .errors import capture_refusal_spine

    capture_refusal_spine(error)


def _wrapper_parameters(spec: CommandSpec) -> list[inspect.Parameter]:
    """Build the legal Python signature projected from one command spec."""
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
    return parameters


def _behavior_wrapper(graph: CommandSpecGraph, spec: CommandSpec) -> Callable[..., object]:
    target_ref = _require_behavior_target(spec)

    signature: inspect.Signature

    def invoke(*args: object, **kwargs: object) -> object:
        bound = signature.bind(*args, **kwargs)
        return _invoke_bound_behavior(graph, spec, target_ref, bound)

    parameters = _wrapper_parameters(spec)
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
    children = graph.children(parent.key)
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
    spec = graph.spec(key)
    if spec.handler is not None and spec.handler.state is BindingState.UNAVAILABLE:
        reason = spec.handler.reason_key
        raise InternalInvariantError(tr(reason.value) if reason is not None else f"command {key!r} is unavailable")
    if spec.kind == "leaf":
        app = typer.Typer()
        command_factory = cast(Any, app.command)
        command_factory(
            spec.token,
            help=tr(spec.help_key.value),
            short_help=None if spec.short_help_key is None else tr(spec.short_help_key.value),
            hidden=spec.invocation.hidden,
        )(_behavior_wrapper(graph, spec))
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
        app.callback(invoke_without_command=True)(_behavior_wrapper(graph, spec))
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
    return _node_app(graph, graph.root().key)


@cache
def build_command_subtree(graph: CommandSpecGraph, key: str) -> typer.Typer:
    """Compile one declared subtree for an atomic family migration."""
    graph.spec(key)
    return _node_app(graph, key)


__all__ = [
    "GOVERNED_FACT_SCOPE_CAPABILITIES",
    "CommandSpecTyperGroup",
    "build_command_app",
    "build_command_subtree",
    "refuse_declared_live_write",
    "resolve_deferred_target",
    "runs_in_governed_fact_scope",
]
