"""Import-light command authority for the hosted agent family."""

from __future__ import annotations

from cadrumo.application.operator_surface.command_ports import (
    CommandNodeKind,
    CommandWriteRoute,
    ProfileAuthenticationPosture,
)

from .command_parameter_contracts import OptionSpec
from .command_shared_contracts import (
    PATH_VALUE,
    DeferredTarget,
    LazyBinding,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
)
from .command_shared_contracts import translation_key as _key
from .command_spec import CommandSpec, ExecutionPolicySpec, InvocationSpec

_METADATA = ExecutionPolicySpec(frozenset({"state-free"}), frozenset({"none"}), "metadata", CommandWriteRoute.NONE)
# It resumes the person's sign-in and asks the runtime to start an agent that works on the
# profile's encrypted facts. The runtime owns every write; this process writes no storage itself.
_SERVE = ExecutionPolicySpec(
    frozenset({"profile-custody", "encrypted-facts"}), frozenset({"local-state"}), "interactive", CommandWriteRoute.NONE
)
_LANG = ValueContract(DeferredTarget("...core.external_constants", "OutputLanguage", __package__))

AGENT_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_agent",
        "app",
        "agent",
        CommandNodeKind.GROUP,
        _key("cli.app.agent.app_help"),
        None,
        InvocationSpec(no_args_is_help=True),
        (),
        _METADATA,
        None,
        ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        "app_agent_serve",
        "app_agent",
        "serve",
        CommandNodeKind.LEAF,
        _key("cli.app.agent.serve.help"),
        None,
        InvocationSpec(context_parameter="ctx"),
        (
            OptionSpec(
                "agent_source",
                ("--agent-source",),
                PATH_VALUE,
                ParameterDefault.value(None),
                _key("cli.app.agent.serve.agent_source_help"),
            ),
            OptionSpec(
                "output_language",
                ("--output-language", "--language"),
                _LANG,
                ParameterDefault.value(None),
                _key("cli.config.auth.output_language_help"),
            ),
        ),
        _SERVE,
        LazyBinding.available(DeferredTarget("._app_agent_serve", "app_agent_serve", __package__)),
        ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
        # It signs in itself, only by resuming the person's stored sign-in on the agent host's frontend.
        profile_authentication=ProfileAuthenticationPosture.SELF_AUTHENTICATING,
    ),
)

__all__ = ["AGENT_COMMAND_SPECS"]
